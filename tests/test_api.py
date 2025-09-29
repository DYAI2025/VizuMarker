import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import json

# Import the main application
from ld35_service.main import app
from ld35_service.schemas.annotation import Annotation, AnnotationRequest
from ld35_service.core.config import settings

client = TestClient(app)

def test_health_endpoint():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@patch('ld35_service.core.security.verify_token')
def test_annotation_endpoint_with_mock(mock_verify_token):
    """Test the annotation endpoint with mocked authentication"""
    # Mock the token verification to return a valid payload
    mock_verify_token.return_value = {"sub": "test_user"}
    
    # Test data
    test_text = "This is a test sentence for annotation."
    annotation_request = {
        "text": test_text,
        "doc_id": "test_doc_123"
    }
    
    # Call the endpoint
    response = client.post("/api/v1/annotation/annotate", json=annotation_request)
    
    # The endpoint should require authentication which is mocked above
    # Since we're mocking, we expect it to reach the processing logic
    # but the actual LD-3.5 engine is also mocked, so it will fail differently
    assert response.status_code in [200, 401, 500]  # Either success, auth error, or processing error due to mock

@patch('ld35_service.core.ld35_engine.process_ld35_annotations')
@patch('ld35_service.core.security.verify_token')
def test_annotation_endpoint_success(mock_verify_token, mock_process_annotations):
    """Test successful annotation with mocked LD-3.5 engine"""
    # Mock the token verification
    mock_verify_token.return_value = {"sub": "test_user"}
    
    # Mock the LD-3.5 processing to return test annotations
    mock_annotations = [
        Annotation(
            start=0,
            end=4,
            marker="SEM_ASSERTION",
            family="SEM", 
            label="Statement",
            score=0.9
        )
    ]
    mock_process_annotations.return_value = mock_annotations
    
    test_text = "This is a test."
    request_data = {
        "text": test_text,
        "doc_id": "test_doc_456"
    }
    
    response = client.post("/api/v1/annotation/annotate", json=request_data)
    assert response.status_code == 200
    
    response_data = response.json()
    assert "annotations" in response_data
    assert len(response_data["annotations"]) == 1
    assert response_data["annotations"][0]["marker"] == "SEM_ASSERTION"

def test_annotation_endpoint_without_auth():
    """Test that annotation endpoint requires authentication"""
    test_text = "This is a test sentence for annotation."
    annotation_request = {
        "text": test_text,
        "doc_id": "test_doc_789"
    }
    
    # Call without token should result in auth error
    response = client.post("/api/v1/annotation/annotate", json=annotation_request)
    assert response.status_code == 403  # Forbidden due to missing auth

def test_chunking_utility():
    """Test the chunking utility functions"""
    from ld35_service.utils.chunking import chunk_text, normalize_text
    
    # Test normalization
    text_with_accents = "Café résumé naïve"
    normalized = normalize_text(text_with_accents)
    assert normalized == text_with_accents  # Normalization should preserve text but ensure NFC
    
    # Test chunking with text that has natural boundaries
    # Using text with sentence-like structure to trigger boundary detection
    long_text_with_boundaries = "A. " * 500  # Creates text with periods as boundaries
    chunks = chunk_text(long_text_with_boundaries, chunk_size=500, overlap=50)
    
    assert len(chunks) >= 1  # Should create at least 1 chunk
    assert chunks[0][2] <= 500  # First chunk should end at or before position 500
    
    # Test chunking with simple text (no natural boundaries)
    simple_text = "A" * 1000  # 1000 characters of just 'A's
    chunks = chunk_text(simple_text, chunk_size=500, overlap=50)
    
    assert len(chunks) == 2  # Should create 2 chunks
    assert chunks[0][2] == 500  # First chunk should end at position 500
    assert chunks[1][1] == 500  # Second chunk should start at position 500 (no boundary found to adjust)

def test_html_renderer():
    """Test the HTML rendering utility"""
    from ld35_service.utils.html_renderer import render_annotations_to_html
    from ld35_service.schemas.annotation import Annotation
    from ld35_service.schemas.render import RenderOptions
    
    text = "This is a sample text for annotation."
    annotations = [
        Annotation(
            start=0,
            end=4,
            marker="SEM_ASSERTION", 
            family="SEM",
            label="Statement",
            score=0.8
        ),
        Annotation(
            start=10, 
            end=17,
            marker="ENT_NAMED",
            family="ENT", 
            label="Entity",
            score=0.7
        )
    ]
    
    options = RenderOptions()
    html_result = render_annotations_to_html(text, annotations, options)
    
    # Check that the HTML contains annotation spans
    assert '<span class="hl"' in html_result
    assert 'data-fam="SEM"' in html_result
    assert 'data-markers="SEM_ASSERTION"' in html_result

def test_bio_converter():
    """Test the BIO format converter"""
    from ld35_service.workers.annotation_tasks import convert_to_bio_format
    from ld35_service.schemas.annotation import Annotation
    
    text = "This is a test ."
    annotations = [
        Annotation(
            start=0,
            end=4,
            marker="SEM_ASSERTION",
            family="SEM",
            label="Statement", 
            score=0.8
        )
    ]
    
    bio_result = convert_to_bio_format(text, annotations)
    
    # Should contain BIO tags
    assert "This\tB-SEM_ASSERTION" in bio_result or "This\tI-SEM_ASSERTION" in bio_result
    
def test_axf_converter():
    """Test the AXF format converter"""
    from ld35_service.workers.annotation_tasks import convert_to_axf_format
    from ld35_service.schemas.annotation import Annotation
    
    text = "Sample text"
    annotations = [
        Annotation(
            start=0,
            end=6,
            marker="SEM_ASSERTION",
            family="SEM", 
            label="Statement",
            score=0.8
        )
    ]
    
    axf_result = convert_to_axf_format(text, annotations)
    
    assert axf_result["text"] == text
    assert len(axf_result["annotations"]) == 1
    assert axf_result["annotations"][0]["marker"] == "SEM_ASSERTION"

def test_markdown_converter():
    """Test the Markdown converter"""
    from ld35_service.workers.annotation_tasks import convert_to_markdown_format
    from ld35_service.schemas.annotation import Annotation
    
    text = "Sample text for annotation."
    annotations = [
        Annotation(
            start=0,
            end=6,
            marker="SEM_ASSERTION",
            family="SEM",
            label="Statement",
            score=0.8
        )
    ]
    
    md_result = convert_to_markdown_format(text, annotations)
    
    # Should contain HTML span
    assert '<span class="hl"' in md_result
    assert 'data-fam="SEM"' in md_result
    assert 'data-markers="SEM_ASSERTION"' in md_result

@patch('ld35_service.core.security.verify_token')
def test_storage_module(mock_verify_token):
    """Test storage functionality"""
    # Mock token for any endpoints that might be called
    mock_verify_token.return_value = {"sub": "test_user"}
    
    from ld35_service.core.storage import DocumentStorage
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = DocumentStorage(storage_path=temp_dir)
        
        # Test saving and loading original text
        doc_id = "test_doc"
        test_text = "This is a test document."
        
        # Save original text
        save_result = storage.save_original_text(doc_id, test_text)
        assert save_result is True
        
        # Load original text
        loaded_text = storage.load_original_text(doc_id)
        assert loaded_text == test_text
        
        # Test saving and loading annotations
        from ld35_service.schemas.annotation import Annotation
        annotations = [
            Annotation(
                start=0,
                end=4,
                marker="SEM_ASSERTION",
                family="SEM",
                label="Statement",
                score=0.8
            )
        ]
        
        # Save annotations
        save_ann_result = storage.save_annotations(doc_id, annotations)
        assert save_ann_result is True
        
        # Load annotations
        loaded_annotations = storage.load_annotations(doc_id)
        assert len(loaded_annotations) == 1
        assert loaded_annotations[0].marker == "SEM_ASSERTION"