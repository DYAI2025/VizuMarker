import os
import sys
from pathlib import Path

# Add the ld35_service directory to the path so tests can import from it
sys.path.insert(0, str(Path(__file__).parent / "ld35_service"))

# You can add fixtures here if needed for your tests
# For example:

import pytest
from fastapi.testclient import TestClient

# Import your main app
from ld35_service.main import app

@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    with TestClient(app) as client:
        yield client

@pytest.fixture
def sample_text():
    """Provide sample text for testing"""
    return "This is a sample text for annotation testing purposes. It contains multiple sentences to test various annotation patterns."

@pytest.fixture
def sample_annotations():
    """Provide sample annotations for testing"""
    from ld35_service.schemas.annotation import Annotation
    return [
        Annotation(
            start=0,
            end=4,
            marker="SEM_ASSERTION",
            family="SEM",
            label="Statement",
            score=0.85
        ),
        Annotation(
            start=10,
            end=15,
            marker="ENT_NAMED",
            family="ENT", 
            label="Entity",
            score=0.78
        )
    ]