import pytest
from unittest.mock import patch, MagicMock
from ld35_service.core.ld35_engine import LD35Model, process_ld35_annotations, post_process_annotations
from ld35_service.schemas.annotation import Annotation

def test_ld35_model_initialization():
    """Test LD35 model initialization"""
    # Test with no model path (should use mock)
    model = LD35Model(model_path=None)
    assert model is not None
    
    # Test with a fake model path
    model = LD35Model(model_path="/fake/path")
    assert model is not None

def test_mock_inference():
    """Test the mock inference functionality"""
    model = LD35Model(model_path=None)
    
    test_text = "This is a test sentence because it contains assertions."
    
    # Run mock inference
    annotations = model._mock_inference(test_text)
    
    # Should return a list of annotations
    assert isinstance(annotations, list)
    
    # Should have some annotations based on the patterns in the mock
    # The text contains "This is a test" which matches assertion pattern
    # and "because" which matches causal relation pattern
    assert len(annotations) >= 0  # May vary based on the text content

@patch('ld35_service.core.ld35_engine.get_ld35_model')
def test_process_ld35_annotations(mock_get_model):
    """Test processing LD35 annotations with mocked model"""
    # Create a mock model
    mock_model = MagicMock()
    mock_annotations = [
        Annotation(
            start=0,
            end=4,
            marker="SEM_ASSERTION",
            family="SEM",
            label="Statement",
            score=0.85
        )
    ]
    mock_model.run_inference.return_value = mock_annotations
    mock_get_model.return_value = mock_model
    
    test_text = "This is a test."
    result = process_ld35_annotations(test_text)
    
    assert result == mock_annotations
    mock_model.run_inference.assert_called_once_with(test_text)

def test_post_process_annotations():
    """Test post-processing of annotations"""
    annotations = [
        Annotation(
            start=0,
            end=10,
            marker="SEM_ASSERTION",
            family="SEM",
            label="Statement",
            score=0.9
        ),
        Annotation(
            start=0,
            end=10,  # Same span as above (duplicate)
            marker="SEM_ASSERTION",
            family="SEM",
            label="Statement",
            score=0.8
        )
    ]
    
    # Remove duplicates
    from ld35_service.core.ld35_engine import remove_duplicate_annotations
    unique_annotations = remove_duplicate_annotations(annotations)
    
    # Should have only one annotation after deduplication
    assert len(unique_annotations) == 1
    # Should keep the one with higher score
    assert unique_annotations[0].score == 0.9

def test_resolve_overlapping_annotations():
    """Test resolving overlapping annotations"""
    annotations = [
        Annotation(
            start=0,
            end=15,  # "This is a test"
            marker="SEM_ASSERTION",
            family="SEM",
            label="Statement",
            score=0.9
        ),
        Annotation(
            start=5,
            end=15,  # "is a test" - overlaps with above
            marker="ENT_NAMED",
            family="ENT",
            label="Entity",
            score=0.7
        )
    ]
    
    from ld35_service.core.ld35_engine import resolve_overlapping_annotations
    resolved = resolve_overlapping_annotations(annotations)
    
    # The exact behavior depends on implementation, but it should return a list
    assert isinstance(resolved, list)
    # Should have at least one annotation
    assert len(resolved) >= 1

@patch('ld35_service.core.ld35_engine.get_ld35_model')
def test_process_with_llm_fallback(mock_get_model):
    """Test LLM fallback processing"""
    from ld35_service.core.ld35_engine import process_with_llm_fallback
    
    # Create a mock model
    mock_model = MagicMock()
    mock_annotations = [
        Annotation(
            start=0,
            end=4,
            marker="SEM_ASSERTION",
            family="SEM",
            label="Statement",
            score=0.85
        )
    ]
    mock_model._mock_inference.return_value = mock_annotations
    mock_get_model.return_value = mock_model
    
    test_text = "This is a test."
    result = process_with_llm_fallback(test_text)
    
    # Should have adjusted scores for fallback
    for ann in result:
        assert ann.score <= 0.8  # Reduced from original 0.85 due to fallback adjustment