from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from enum import Enum

class Annotation(BaseModel):
    start: int
    end: int
    marker: str
    family: str
    label: str
    score: float
    meta: Optional[Dict[str, Any]] = None

class AnnotationOptions(BaseModel):
    chunk_size: Optional[int] = 12000
    normalize_text: Optional[bool] = True
    use_ld35: Optional[bool] = True
    use_llm_fallback: Optional[bool] = False
    max_overlap: Optional[int] = 3

class AnnotationRequest(BaseModel):
    text: str
    doc_id: Optional[str] = None
    options: Optional[AnnotationOptions] = None

class AnnotationResponse(BaseModel):
    doc_id: str
    annotations: List[Annotation]
    text: Optional[str] = None

class DocumentForBatch(BaseModel):
    id: str
    text: str
    options: Optional[AnnotationOptions] = None

class BatchAnnotationRequest(BaseModel):
    documents: List[DocumentForBatch]

class JobStatusEnum(str, Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"

class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatusEnum
    total_documents: int
    processed_documents: int
    results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
