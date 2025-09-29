from celery import Celery
from typing import List
from ..core.config import settings
from ..core.ld35_engine import process_ld35_annotations, process_with_llm_fallback
from ..core.storage import document_storage
from ..utils.chunking import normalize_text
from ..schemas.annotation import Annotation
import logging
import re

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery('ld35_service')
celery_app.conf.broker_url = settings.CELERY_BROKER_URL
celery_app.conf.result_backend = settings.CELERY_RESULT_BACKEND

@celery_app.task
def process_annotation_task(doc_id: str, text: str, options: dict = None) -> dict:
    """
    Celery task to process annotation of a single document
    """
    if not options:
        options = {}
    
    try:
        # Store original text
        if not document_storage.save_original_text(doc_id, text):
            raise Exception(f"Failed to save original text for document {doc_id}")
        
        # Normalize the text
        normalized_text = normalize_text(text)
        
        # Determine which processing method to use
        use_ld35 = options.get('use_ld35', True)
        use_llm_fallback = options.get('use_llm_fallback', False)
        
        annotations = []
        
        if use_ld35:
            try:
                annotations = process_ld35_annotations(normalized_text, options)
            except Exception as e:
                logger.error(f"LD-3.5 processing failed: {str(e)}")
                if use_llm_fallback:
                    logger.info("Falling back to LLM processing")
                    annotations = process_with_llm_fallback(normalized_text, options)
                else:
                    raise e
        else:
            if use_llm_fallback:
                annotations = process_with_llm_fallback(normalized_text, options)
            else:
                # No processing method specified, return empty
                annotations = []
        
        # Save annotations
        if not document_storage.save_annotations(doc_id, annotations):
            raise Exception(f"Failed to save annotations for document {doc_id}")
        
        # Return the results
        result = {
            "annotations": [
                ann.dict() if hasattr(ann, "dict") else ann for ann in annotations
            ],
            "text": normalized_text,
            "processing_options": options,
            "doc_id": doc_id,
        }

        return result
        
    except Exception as e:
        logger.error(f"Annotation task failed for document {doc_id}: {str(e)}")
        raise e

@celery_app.task
def process_batch_annotation_task(documents: list, options: dict = None) -> list:
    """
    Celery task to process a batch of documents
    """
    if not options:
        options = {}
    
    results = []
    
    for doc in documents:
        try:
            doc_id = doc.get('id')
            text = doc.get('text', '')
            doc_options = doc.get('options', options)
            
            # Process the document via the single document task
            # This allows us to reuse the same processing logic
            result = process_annotation_task.delay(doc_id, text, doc_options).get()
            
            results.append({
                'id': doc_id,
                'result': result,
                'status': 'completed'
            })
        except Exception as e:
            logger.error(f"Processing document failed: {str(e)}")
            results.append({
                'id': doc.get('id'),
                'error': str(e),
                'status': 'failed'
            })
    
    return results

@celery_app.task
def render_document_task(doc_id: str, options: dict = None) -> dict:
    """
    Celery task to render a document to HTML and PDF
    """
    if not options:
        options = {}
    
    try:
        # Load the original text and annotations
        text = document_storage.load_original_text(doc_id)
        if not text:
            raise Exception(f"Original text not found for document {doc_id}")
        
        annotations = document_storage.load_annotations(doc_id)
        if not annotations:
            raise Exception(f"Annotations not found for document {doc_id}")
        
        # Import rendering modules
        from ..utils.html_renderer import render_annotations_to_html
        from ..utils.pdf_generator import generate_pdf_from_html
        from ..schemas.render import RenderOptions
        
        # Convert options to RenderOptions
        render_options = RenderOptions(**options) if options else RenderOptions()
        
        # Generate HTML
        html_content = render_annotations_to_html(text, annotations, render_options)
        
        # Save rendered HTML
        if not document_storage.save_rendered_html(doc_id, html_content):
            raise Exception(f"Failed to save rendered HTML for document {doc_id}")
        
        # Generate and save PDF if requested
        if render_options.include_pdf:
            pdf_content = generate_pdf_from_html(html_content)
            
            # Save exports
            export_results = document_storage.save_exports(doc_id, pdf=pdf_content)
            if not export_results.get('pdf', False):
                raise Exception(f"Failed to save PDF export for document {doc_id}")
        
        # Convert annotations back to appropriate format for response
        result_annotations = [ann for ann in annotations]
        
        return {
            "doc_id": doc_id,
            "html_saved": True,
            "pdf_saved": render_options.include_pdf,
            "annotations_count": len(result_annotations)
        }
        
    except Exception as e:
        logger.error(f"Render task failed for document {doc_id}: {str(e)}")
        raise e

@celery_app.task
def export_document_task(doc_id: str, formats: list) -> dict:
    """
    Celery task to export a document in various formats
    """
    try:
        # Load the original text and annotations
        text = document_storage.load_original_text(doc_id)
        if not text:
            raise Exception(f"Original text not found for document {doc_id}")
        
        annotations = document_storage.load_annotations(doc_id)
        if not annotations:
            raise Exception(f"Annotations not found for document {doc_id}")
        
        export_results = {}
        
        # Export in requested formats
        if 'bio' in formats:
            bio_content = convert_to_bio_format(text, annotations)
            export_results['bio'] = document_storage.save_exports(doc_id, bio=bio_content).get('bio', False)
        
        if 'md' in formats:
            md_content = convert_to_markdown_format(text, annotations)
            export_results['md'] = document_storage.save_exports(doc_id, md=md_content).get('md', False)
        
        if 'axf' in formats:
            axf_content = convert_to_axf_format(text, annotations)
            # Save AXF (already saved as annotations, but we can save a combined version too)
            import json
            axf_json = json.dumps(axf_content, indent=2)
            # Just noting that AXF is already handled in the annotation process
            export_results['axf'] = True
        
        return {
            "doc_id": doc_id,
            "formats": export_results
        }
        
    except Exception as e:
        logger.error(f"Export task failed for document {doc_id}: {str(e)}")
        raise e

def convert_to_bio_format(text: str, annotations: List[Annotation], tokenizer_name: str = "whitespace") -> str:
    """
    Convert annotations to BIO-TSV format
    """
    # This is a simplified implementation - a real implementation would use proper tokenization
    # based on the specified tokenizer
    
    # For now, we'll split by whitespace as a simple tokenizer
    tokens = text.split()
    
    # Create a mapping from character positions to token positions
    char_to_token = {}
    token_start = 0
    
    for i, token in enumerate(tokens):
        for j in range(len(token)):
            char_to_token[token_start + j] = i
        token_start += len(token) + 1  # +1 for the space
    
    # Create BIO labels for each token
    bio_labels = ["O"] * len(tokens)
    
    for ann in annotations:
        start_token_idx = char_to_token.get(ann.start, -1)
        end_token_idx = char_to_token.get(ann.end - 1, -1)  # -1 to get the token containing the last char
        
        if start_token_idx != -1 and end_token_idx != -1 and start_token_idx <= end_token_idx:
            # Apply BIO tagging
            bio_labels[start_token_idx] = f"B-{ann.marker}"
            for i in range(start_token_idx + 1, min(end_token_idx + 1, len(bio_labels))):
                bio_labels[i] = f"I-{ann.marker}"
    
    # Format as TSV
    tsv_lines = []
    for token, label in zip(tokens, bio_labels):
        tsv_lines.append(f"{token}\t{label}")
    
    return "\n".join(tsv_lines)


def convert_to_axf_format(text: str, annotations: List[Annotation]) -> dict:
    """
    Convert to AXF format (returns the standard format)
    """
    return {
        "text": text,
        "annotations": [ann.dict() for ann in annotations]
    }


def convert_to_markdown_format(text: str, annotations: List[Annotation]) -> str:
    """
    Convert to markdown with inline HTML annotations
    """
    # Sort annotations by start position in reverse order to avoid offset issues
    sorted_annotations = sorted(annotations, key=lambda x: x.start, reverse=True)
    
    result_text = text
    
    # Apply annotations from the end of the text to avoid offset changes
    for ann in sorted_annotations:
        # Extract the annotated text
        annotated_text = result_text[ann.start:ann.end]
        
        # Create HTML span
        span_html = f'<span class="hl" data-fam="{ann.family}" data-markers="{ann.marker}">{annotated_text}</span>'
        
        # Replace in the text
        result_text = result_text[:ann.start] + span_html + result_text[ann.end:]
    
    return result_text
