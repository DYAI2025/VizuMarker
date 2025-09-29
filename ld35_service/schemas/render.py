from pydantic import BaseModel
from typing import List, Dict, Optional
from .annotation import Annotation

class RenderOptions(BaseModel):
    include_legend: Optional[bool] = True
    highlight_class: Optional[str] = "hl"
    include_scores: Optional[bool] = False
    primary_marker_priority: Optional[str] = "score"  # score, length, family_rank
    max_overlapping_markers: Optional[int] = 5
    include_pdf: Optional[bool] = False

class RenderRequest(BaseModel):
    text: str
    annotations: List[Annotation]
    doc_id: Optional[str] = None
    options: Optional[RenderOptions] = None

class RenderResponse(BaseModel):
    html: str