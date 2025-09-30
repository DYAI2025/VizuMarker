#!/usr/bin/env python3
"""
Simple development server for testing VizuMarker frontend without celery dependencies
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import sys
import os

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from ld35_service.engine.sem_core import analyze_text

app = FastAPI(title="VizuMarker Dev Server", version="0.1.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="frontend/public"), name="static")

class AnnotateRequest(BaseModel):
    text: str

class AnnotationResponse(BaseModel):
    text: str
    annotations: list
    doc_id: str = None

@app.post("/api/v1/annotation/annotate", response_model=AnnotationResponse)
async def annotate_text(request: AnnotateRequest):
    """Annotate text with LD-3.5 semantic markers"""
    try:
        resources_dir = Path("resources")
        result = analyze_text(request.text, resources_dir)
        
        return AnnotationResponse(
            text=request.text,
            annotations=result.get("annotations", []),
            doc_id=f"doc_{hash(request.text) & 0x7FFFFFFF}"  # Simple hash-based ID
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Redirect to the frontend"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)