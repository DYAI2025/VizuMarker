from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query, UploadFile, File, Body
from fastapi.security import HTTPAuthorizationCredentials
from typing import Dict, Any, Optional, List
import uuid
import json
import hashlib
from pathlib import Path
from ...schemas.annotation import (
    AnnotationRequest,
    AnnotationResponse,
    BatchAnnotationRequest,
    JobStatusResponse,
)
from ...workers.annotation_tasks import process_annotation_task as celery_annotate_task
from ...core.ld35_engine import process_ld35_annotations, process_with_llm_fallback
from ...core.storage import document_storage
from ...core.security import verify_token, security
from ...engine.sem_core import analyze_text

router = APIRouter()

# In-memory storage for job statuses (in production, use database/Redis)
job_storage: Dict[str, Dict[str, Any]] = {}

@router.post("/annotate", response_model=AnnotationResponse)
def annotate_text(
    request: AnnotationRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AnnotationResponse:
    """
    Annotate a single document with LD-3.5 markers using enhanced semantic engine
    For large documents, consider using the batch endpoint instead
    """
    # Verify the token
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    try:
        # Generate a document ID if not provided
        doc_id = request.doc_id or str(uuid.uuid4())
        
        # Get options
        options = request.options.dict() if request.options else {}
        use_semantic_engine = options.get('use_semantic_engine', True)
        use_ld35_fallback = options.get('use_ld35_fallback', True)
        
        annotations = []
        
        if use_semantic_engine:
            try:
                # Use new semantic engine for better heuristic understanding
                resources_dir = Path(__file__).resolve().parents[3] / "resources"
                result = analyze_text(request.text, resources_dir)
                
                # Convert to Annotation objects
                from ...schemas.annotation import Annotation
                annotations = []
                for ann_data in result.get("annotations", []):
                    annotation = Annotation(
                        start=ann_data["start"],
                        end=ann_data["end"],
                        marker=ann_data["marker_id"],
                        family=ann_data["family"],
                        label=ann_data.get("label", ann_data["marker_id"]),
                        score=ann_data.get("score", 0.7)
                    )
                    annotations.append(annotation)
                    
            except Exception as e:
                if use_ld35_fallback:
                    # Fall back to original LD35 engine
                    annotations = process_ld35_annotations(request.text, options)
                else:
                    raise HTTPException(status_code=500, detail=f"Semantic engine failed: {str(e)}")
        elif use_ld35_fallback:
            annotations = process_ld35_annotations(request.text, options)
        
        # Save document and annotations
        if not document_storage.save_original_text(doc_id, request.text):
            raise Exception("Failed to save document")
        if not document_storage.save_annotations(doc_id, annotations):
            raise Exception("Failed to save annotations")
        
        return AnnotationResponse(doc_id=doc_id, annotations=annotations, text=request.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Annotation failed: {str(e)}")


@router.post("/annotate-semantic")
def annotate_semantic(text: str = Body(..., embed=True)):
    """
    Direct semantic annotation endpoint (no authentication required for testing)
    Returns enhanced semantic analysis with sentence-level spans
    """
    try:
        resources_dir = Path(__file__).resolve().parents[3] / "resources"
        result = analyze_text(text, resources_dir)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Semantic analysis failed: {str(e)}")


@router.post("/annotate-batch-files")
async def annotate_batch_files(
    files: List[UploadFile] = File(...),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """
    Batch annotate multiple uploaded files using semantic engine
    """
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    try:
        resources_dir = Path(__file__).resolve().parents[3] / "resources"
        results = []
        
        for file in files:
            # Read file content
            content = await file.read()
            text = content.decode("utf-8", errors="ignore")
            
            # Analyze with semantic engine
            result = analyze_text(text, resources_dir)
            
            # Add file metadata
            result["source"] = file.filename
            result["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            
            results.append(result)
        
        return {"items": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")


def _convert_to_ann_format(analysis_result: dict) -> dict:
    """Convert semantic analysis result to .ann.json format"""
    return {
        "source": analysis_result.get("source", "unknown"),
        "text_sha256": analysis_result.get("text_sha256", ""),
        "annotations": [
            {
                "marker_id": ann["marker_id"],
                "family": ann["family"], 
                "start": ann["start"],
                "end": ann["end"],
                "score": ann.get("score", 0.7)
            }
            for ann in analysis_result.get("annotations", [])
        ],
        "metadata": analysis_result.get("metadata", {})
    }


@router.post("/annotate-batch")
def annotate_batch(
    request: BatchAnnotationRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """
    Submit a batch of documents for annotation using Celery
    """
    # Verify the token
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    from ...workers.annotation_tasks import process_batch_annotation_task
    
    job_id = str(uuid.uuid4())
    
    # Prepare documents for processing
    documents_for_task = []
    for doc in request.documents:
        doc_dict = {
            'id': doc.id,
            'text': doc.text,
            'options': doc.options.dict() if hasattr(doc, 'options') and doc.options else request.options.dict() if request.options else {}
        }
        documents_for_task.append(doc_dict)
    
    # Start Celery task
    result = process_batch_annotation_task.delay(documents_for_task)
    
    # Store job info (in a real system, you'd integrate with Celery's result backend)
    job_storage[job_id] = {
        "status": "processing",
        "task_id": result.id,
        "documents": len(request.documents),
        "processed": 0,
        "results": []
    }
    
    return {"job_id": job_id}


def _resolve_job_status(job_id: str, credentials: Optional[HTTPAuthorizationCredentials]) -> JobStatusResponse:
    """Shared job status lookup used by both path and query-based endpoints."""
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if job_id not in job_storage:
        raise HTTPException(status_code=404, detail="Job not found")

    job_info = job_storage[job_id]

    # In a real implementation, you'd check the Celery task status
    from ...workers.annotation_tasks import celery_app

    task_result = celery_app.AsyncResult(job_info["task_id"])

    status_mapping = {
        "PENDING": "processing",
        "STARTED": "processing",
        "SUCCESS": "completed",
        "FAILURE": "failed",
    }

    job_status = status_mapping.get(task_result.status, "processing")

    if job_status == "completed" and task_result.result:
        job_info["status"] = job_status
        results = []
        for result in task_result.result:
            results.append(
                {
                    "doc_id": result.get("id"),
                    "status": result.get("status"),
                    "error": result.get("error"),
                    "result": result.get("result"),
                }
            )
        job_info["results"] = results
        job_info["processed"] = sum(1 for item in results if item.get("status") == "completed")
    elif job_status == "failed" and task_result.result:
        job_info["status"] = job_status
        job_info["error"] = str(task_result.result)
    else:
        job_info["status"] = job_status

    return JobStatusResponse(
        job_id=job_id,
        status=job_info["status"],
        total_documents=job_info["documents"],
        processed_documents=job_info["processed"],
        results=job_info["results"] if job_info["status"] == "completed" else None,
        error=job_info.get("error"),
    )


@router.get("/job/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> JobStatusResponse:
    """Get status of a batch annotation job via path parameter."""
    return _resolve_job_status(job_id, credentials)


@router.get("/job", response_model=JobStatusResponse)
def get_job_status_by_query(
    job_id: str = Query(..., description="Job ID returned by /annotate-batch"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> JobStatusResponse:
    """Get status of a batch annotation job via query parameter."""
    return _resolve_job_status(job_id, credentials)
