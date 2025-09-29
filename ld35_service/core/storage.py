from pathlib import Path
from typing import Dict, List, Optional, Any
from ..schemas.annotation import Annotation
from ..schemas.render import RenderOptions
from ..core.config import settings
import json
import os


class DocumentStorage:
    """
    Handles storage and retrieval of documents and their annotations
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or settings.STORAGE_PATH)
        
        # Create storage directories if they don't exist
        (self.storage_path / "originals").mkdir(parents=True, exist_ok=True)
        (self.storage_path / "annotations").mkdir(parents=True, exist_ok=True)
        (self.storage_path / "rendered").mkdir(parents=True, exist_ok=True)
        (self.storage_path / "exports").mkdir(parents=True, exist_ok=True)
        (self.storage_path / "datasets").mkdir(parents=True, exist_ok=True)
    
    def save_original_text(self, doc_id: str, text: str) -> bool:
        """Save the original text of a document"""
        try:
            path = self.storage_path / "originals" / f"{doc_id}.txt"
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            return True
        except Exception as e:
            print(f"Error saving original text: {e}")
            return False
    
    def load_original_text(self, doc_id: str) -> Optional[str]:
        """Load the original text of a document"""
        try:
            path = self.storage_path / "originals" / f"{doc_id}.txt"
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            return None
        except Exception as e:
            print(f"Error loading original text: {e}")
            return None
    
    def save_annotations(self, doc_id: str, annotations: List[Annotation]) -> bool:
        """Save annotations in AXF format"""
        try:
            path = self.storage_path / "annotations" / f"{doc_id}.ann.json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    "annotations": [ann.dict() for ann in annotations]
                }, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving annotations: {e}")
            return False
    
    def load_annotations(self, doc_id: str) -> Optional[List[Annotation]]:
        """Load annotations from AXF format"""
        try:
            path = self.storage_path / "annotations" / f"{doc_id}.ann.json"
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return [Annotation(**ann) for ann in data["annotations"]]
            return None
        except Exception as e:
            print(f"Error loading annotations: {e}")
            return None
    
    def save_rendered_html(self, doc_id: str, html_content: str) -> bool:
        """Save rendered HTML"""
        try:
            path = self.storage_path / "rendered" / f"{doc_id}.html"
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            return True
        except Exception as e:
            print(f"Error saving rendered HTML: {e}")
            return False
    
    def load_rendered_html(self, doc_id: str) -> Optional[str]:
        """Load rendered HTML"""
        try:
            path = self.storage_path / "rendered" / f"{doc_id}.html"
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
            return None
        except Exception as e:
            print(f"Error loading rendered HTML: {e}")
            return None
    
    def save_exports(self, doc_id: str, **formats) -> Dict[str, bool]:
        """Save multiple export formats"""
        results = {}
        
        # Save BIO-TSV if provided
        if 'bio' in formats:
            try:
                path = self.storage_path / "exports" / f"{doc_id}.bio.tsv"
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(formats['bio'])
                results['bio'] = True
            except Exception as e:
                print(f"Error saving BIO-TSV: {e}")
                results['bio'] = False
        
        # Save Markdown if provided
        if 'md' in formats:
            try:
                path = self.storage_path / "exports" / f"{doc_id}.md"
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(formats['md'])
                results['md'] = True
            except Exception as e:
                print(f"Error saving Markdown: {e}")
                results['md'] = False
        
        # Save PDF if provided
        if 'pdf' in formats:
            try:
                path = self.storage_path / "exports" / f"{doc_id}.pdf"
                with open(path, 'wb') as f:
                    f.write(formats['pdf'])
                results['pdf'] = True
            except Exception as e:
                print(f"Error saving PDF: {e}")
                results['pdf'] = False
        
        return results
    
    def document_exists(self, doc_id: str) -> bool:
        """Check if a document exists in storage"""
        original_path = self.storage_path / "originals" / f"{doc_id}.txt"
        return original_path.exists()
    
    def get_all_documents(self) -> List[str]:
        """Get list of all stored document IDs"""
        originals_dir = self.storage_path / "originals"
        if not originals_dir.exists():
            return []
        
        # Get all .txt files and extract document IDs
        doc_ids = []
        for file_path in originals_dir.glob("*.txt"):
            doc_ids.append(file_path.stem)
        
        return doc_ids
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document and all its associated files"""
        try:
            # Delete all related files
            (self.storage_path / "originals" / f"{doc_id}.txt").unlink(missing_ok=True)
            (self.storage_path / "annotations" / f"{doc_id}.ann.json").unlink(missing_ok=True)
            (self.storage_path / "rendered" / f"{doc_id}.html").unlink(missing_ok=True)
            (self.storage_path / "exports" / f"{doc_id}.bio.tsv").unlink(missing_ok=True)
            (self.storage_path / "exports" / f"{doc_id}.md").unlink(missing_ok=True)
            (self.storage_path / "exports" / f"{doc_id}.pdf").unlink(missing_ok=True)
            
            return True
        except Exception as e:
            print(f"Error deleting document: {e}")
            return False


# Global storage instance
document_storage = DocumentStorage()
