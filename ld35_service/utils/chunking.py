import re
from typing import List, Tuple
from ..schemas.annotation import Annotation

def chunk_text(text: str, chunk_size: int = 12000, overlap: int = 200) -> List[Tuple[str, int, int]]:
    """
    Split text into chunks of specified size, with overlap to preserve context.
    Returns list of (chunk_text, start_offset, end_offset)
    """
    chunks = []
    text_len = len(text)
    
    if text_len <= chunk_size:
        return [(text, 0, text_len)]
    
    start = 0
    while start < text_len:
        end = start + chunk_size
        
        # If we're at the end, include the remaining text
        if end >= text_len:
            end = text_len
        else:
            # Try to break at sentence or paragraph boundary
            search_start = end - overlap
            if search_start > start:
                # Look for natural break points
                chunk_end = end
                for boundary in ['\\n\\n', '. ', '! ', '? ', '; ', ': ']:
                    last_boundary = text.rfind(boundary, search_start, end)
                    if last_boundary != -1:
                        chunk_end = last_boundary + len(boundary)
                        break
                
                end = chunk_end
        
        chunk_text = text[start:end]
        chunks.append((chunk_text, start, end))
        
        # Move start forward by chunk_size (not end, to maintain overlap)
        start += chunk_size
        
        # If we're near the end, ensure we capture the last part
        if start >= text_len:
            break
    
    return chunks

def normalize_text(text: str) -> str:
    """
    Normalize text using NFC normalization to ensure stable offsets
    and handle graphemes correctly (not splitting combining characters)
    """
    import unicodedata
    return unicodedata.normalize('NFC', text)

def adjust_annotation_offsets(annotations: List[Annotation], offset: int) -> List[Annotation]:
    """
    Adjust annotation offsets by adding the chunk's global offset
    """
    adjusted = []
    for ann in annotations:
        new_ann = ann.copy()
        new_ann.start += offset
        new_ann.end += offset
        adjusted.append(new_ann)
    
    return adjusted

def merge_chunk_annotations(all_chunk_annotations: List[Tuple[List[Annotation], int]]) -> List[Annotation]:
    """
    Merge annotations from all chunks, adjusting offsets appropriately
    """
    merged_annotations = []
    for chunk_annotations, offset in all_chunk_annotations:
        adjusted_annotations = adjust_annotation_offsets(chunk_annotations, offset)
        merged_annotations.extend(adjusted_annotations)
    
    # Remove duplicates or overlapping annotations that might have been split across chunks
    merged_annotations = remove_cross_chunk_duplicates(merged_annotations)
    
    return merged_annotations

def remove_cross_chunk_duplicates(annotations: List[Annotation]) -> List[Annotation]:
    """
    Remove annotations that might be duplicated across chunk boundaries
    """
    # Sort by start position
    sorted_anns = sorted(annotations, key=lambda x: (x.start, x.end))
    
    unique_annotations = []
    seen_spans = set()
    
    for ann in sorted_anns:
        span_key = (ann.start, ann.end, ann.marker)
        if span_key not in seen_spans:
            seen_spans.add(span_key)
            unique_annotations.append(ann)
    
    return unique_annotations