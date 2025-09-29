from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
from fastapi.responses import Response, HTMLResponse
from ...schemas.render import RenderRequest, RenderResponse
from ...utils.html_renderer import render_annotations_to_html
from ...utils.pdf_generator import generate_pdf_from_html
from ...core.config import settings
from ...core.security import verify_token, security

router = APIRouter()

@router.post("/render", response_model=RenderResponse)
def render_annotations(request: RenderRequest, credentials: str = Depends(security)) -> RenderResponse:
    """
    Render text with annotations to HTML
    """
    # Verify the token
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    try:
        html_content = render_annotations_to_html(request.text, request.annotations, request.options)
        return RenderResponse(html=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering failed: {str(e)}")


@router.post("/render-and-save")
def render_and_save(request: RenderRequest, credentials: str = Depends(security)):
    """
    Render annotations and save to storage with document ID
    """
    # Verify the token
    token_payload = verify_token(credentials)
    if not token_payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    try:
        # Generate HTML
        html_content = render_annotations_to_html(request.text, request.annotations, request.options)
        
        # Save HTML to storage
        html_path = Path(settings.STORAGE_PATH) / "rendered" / f"{request.doc_id}.html"
        html_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Generate and save PDF if requested
        if request.options and request.options.include_pdf:
            pdf_content = generate_pdf_from_html(html_content)
            pdf_path = Path(settings.STORAGE_PATH) / "exports" / f"{request.doc_id}.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(pdf_path, 'wb') as f:
                f.write(pdf_content)
        
        return {"message": "Render completed and saved", "doc_id": request.doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering and saving failed: {str(e)}")


@router.get("/{doc_id}.html")
def get_rendered_html(doc_id: str) -> HTMLResponse:
    """
    Get pre-rendered HTML for a document
    """
    html_path = Path(settings.STORAGE_PATH) / "rendered" / f"{doc_id}.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Rendered document not found")
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return HTMLResponse(content=content)


@router.get("/{doc_id}.pdf")
def get_rendered_pdf(doc_id: str) -> Response:
    """
    Get rendered PDF for a document
    """
    pdf_path = Path(settings.STORAGE_PATH) / "exports" / f"{doc_id}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF document not found")
    
    with open(pdf_path, 'rb') as f:
        pdf_content = f.read()
    
    return Response(
        content=pdf_content,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{doc_id}.pdf"'}
    )
