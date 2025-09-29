from fastapi import APIRouter, HTTPException, Response, Depends
from typing import Dict, Any
import os
from pathlib import Path
import json
import zipfile
from io import BytesIO
from ...core.config import settings
from ...core.storage import document_storage
from ...core.security import verify_token, security

router = APIRouter()

@router.get("/{doc_id}.ann.json")
def get_axf_json(doc_id: str, credentials: str = Depends(security)):
    """
    Get AXF JSON annotations for a document
    """
    # Verify the token
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Use the document storage to load annotations
    annotations = document_storage.load_annotations(doc_id)
    if not annotations:
        raise HTTPException(status_code=404, detail="AXF annotations not found")
    
    # Get original text
    text = document_storage.load_original_text(doc_id)
    if not text:
        text = ""
    
    # Format as AXF
    axf_content = {
        "text": text,
        "annotations": [ann.dict() for ann in annotations]
    }
    
    content = json.dumps(axf_content, indent=2)
    
    return Response(
        content=content,
        media_type='application/json',
        headers={'Content-Disposition': f'attachment; filename="{doc_id}.ann.json"'}
    )


@router.get("/{doc_id}.bio.tsv")
def get_bio_tsv(doc_id: str, credentials: str = Depends(security)):
    """
    Get BIO TSV format for a document
    """
    # Verify the token
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    bio_path = Path(settings.STORAGE_PATH) / "exports" / f"{doc_id}.bio.tsv"
    if not bio_path.exists():
        raise HTTPException(status_code=404, detail="BIO TSV not found")
    
    with open(bio_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return Response(
        content=content,
        media_type='text/tab-separated-values',
        headers={'Content-Disposition': f'attachment; filename="{doc_id}.bio.tsv"'}
    )


@router.get("/{doc_id}.md")
def get_markdown(doc_id: str, credentials: str = Depends(security)):
    """
    Get Markdown with inline HTML for a document
    """
    # Verify the token
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    md_path = Path(settings.STORAGE_PATH) / "exports" / f"{doc_id}.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="Markdown not found")
    
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return Response(
        content=content,
        media_type='text/markdown',
        headers={'Content-Disposition': f'attachment; filename="{doc_id}.md"'}
    )


@router.get("/{doc_id}.pdf")
def get_pdf(doc_id: str, credentials: str = Depends(security)):
    """
    Get PDF export for a document
    """
    # Verify the token
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    pdf_path = Path(settings.STORAGE_PATH) / "exports" / f"{doc_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    
    with open(pdf_path, 'rb') as f:
        content = f.read()
    
    return Response(
        content=content,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{doc_id}.pdf"'}
    )


@router.get("/batch/{batch_id}.zip")
def get_batch_export(batch_id: str, credentials: str = Depends(security)):
    """
    Get a batch export as ZIP file containing all formats
    """
    # Verify the token
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    from ...workers.annotation_tasks import celery_app
    from celery.result import AsyncResult
    
    # In a real implementation, you'd get the batch job results
    # For now, we'll create a basic ZIP with available documents
    
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Get all documents for this batch (simplified approach)
        # In reality, you'd fetch the batch job results
        doc_ids = document_storage.get_all_documents()
        
        for doc_id in doc_ids:
            # Add each document's files to the ZIP
            # AXF JSON
            axf_path = Path(settings.STORAGE_PATH) / "annotations" / f"{doc_id}.ann.json"
            if axf_path.exists():
                zip_file.write(axf_path, f"{doc_id}.ann.json")
            
            # HTML
            html_path = Path(settings.STORAGE_PATH) / "rendered" / f"{doc_id}.html"
            if html_path.exists():
                zip_file.write(html_path, f"{doc_id}.html")
                
            # BIO TSV
            bio_path = Path(settings.STORAGE_PATH) / "exports" / f"{doc_id}.bio.tsv"
            if bio_path.exists():
                zip_file.write(bio_path, f"{doc_id}.bio.tsv")
                
            # Markdown
            md_path = Path(settings.STORAGE_PATH) / "exports" / f"{doc_id}.md"
            if md_path.exists():
                zip_file.write(md_path, f"{doc_id}.md")
                
            # PDF
            pdf_path = Path(settings.STORAGE_PATH) / "exports" / f"{doc_id}.pdf"
            if pdf_path.exists():
                zip_file.write(pdf_path, f"{doc_id}.pdf")
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename="batch_{batch_id}.zip"'}
    )


@router.get("/dataset/{dataset_id}.jsonl")
def get_jsonl_dataset(dataset_id: str, credentials: str = Depends(security)):
    """
    Get a JSONL dataset export
    """
    # Verify the token
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    jsonl_path = Path(settings.STORAGE_PATH) / "datasets" / f"{dataset_id}.jsonl"
    if not jsonl_path.exists():
        raise HTTPException(status_code=404, detail="JSONL dataset not found")
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return Response(
        content=content,
        media_type='application/jsonl',
        headers={'Content-Disposition': f'attachment; filename="{dataset_id}.jsonl"'}
    )