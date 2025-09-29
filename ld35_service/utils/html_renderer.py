from typing import List, Dict
from ..schemas.annotation import Annotation
from ..schemas.render import RenderOptions
from collections import defaultdict
import html

def render_annotations_to_html(text: str, annotations: List[Annotation], options: RenderOptions = None) -> str:
    """
    Render text with annotations to HTML with colored spans
    """
    if not options:
        options = RenderOptions()
    
    # Sort annotations by start position (descending) to avoid offset issues during replacement
    sorted_annotations = sorted(annotations, key=lambda x: x.start, reverse=True)
    
    # Group overlapping annotations by position
    position_groups = group_annotations_by_position(annotations)
    
    # Create segments based on annotation boundaries
    segments = create_segments(text, position_groups)
    
    # Build HTML with proper nesting and overlapping handling
    html_parts = []
    for segment_start, segment_end, segment_annotations in segments:
        segment_text = text[segment_start:segment_end]
        
        if not segment_annotations:
            # No annotations in this segment
            html_parts.append(html.escape(segment_text))
        else:
            # Process overlapping annotations
            html_parts.append(render_segment_with_annotations(segment_text, segment_annotations, options))
    
    # Combine all parts
    html_content = "".join(html_parts)
    
    # Add legend if requested
    if options.include_legend:
        legend_html = generate_legend(annotations)
        html_content += legend_html
    
    return html_content


def group_annotations_by_position(annotations: List[Annotation]) -> Dict[int, List[Annotation]]:
    """
    Group annotations by their start and end positions to identify overlaps
    """
    position_groups: Dict[int, List[Annotation]] = defaultdict(list)
    
    for ann in annotations:
        position_groups[ann.start].append(ann)
        position_groups[ann.end].append(ann)  # We'll use this to track when spans end
    
    return position_groups


def create_segments(text: str, position_groups: Dict[int, List[Annotation]]) -> List[tuple]:
    """
    Create text segments based on annotation boundaries
    """
    # Get all unique boundary points (0, text length, and all annotation starts/ends)
    boundaries = set([0, len(text)])
    for start, anns in position_groups.items():
        for ann in anns:
            boundaries.add(ann.start)
            boundaries.add(ann.end)
    
    boundaries = sorted(list(boundaries))
    
    segments = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        
        # Find annotations that are active in this segment
        active_anns = []
        for ann in position_groups[start]:  # Check annotations starting at this boundary
            if ann.start <= start and ann.end >= end:  # Annotation spans this segment
                active_anns.append(ann)
        
        segments.append((start, end, active_anns))
    
    return segments


def render_segment_with_annotations(segment_text: str, annotations: List[Annotation], options: RenderOptions) -> str:
    """
    Render a text segment with potentially overlapping annotations
    """
    if not annotations:
        return html.escape(segment_text)
    
    # Determine primary marker based on priority settings
    primary_annotation = select_primary_annotation(annotations, options)
    
    # Prepare data attributes for all annotations in this segment
    families = "|".join(set([ann.family for ann in annotations]))
    markers = "|".join([ann.marker for ann in annotations])
    
    # Build the span with data attributes
    attrs = f'class="{options.highlight_class}" data-fam="{families}" data-markers="{markers}"'
    
    # If we want to show scores
    if options.include_scores:
        scores = "|".join([str(ann.score) for ann in annotations])
        attrs += f' data-scores="{scores}"'
    
    # Handle overlapping annotations by showing them in tooltip/chip
    extra_markers_html = ""
    if len(annotations) > 1:
        extra_markers_html = generate_overlapping_tooltip(annotations, primary_annotation)
    
    html_span = f'<span {attrs}>{html.escape(segment_text)}</span>'
    
    # Attach extra marker information if there are overlaps
    if extra_markers_html:
        html_span += extra_markers_html
    
    return html_span


def select_primary_annotation(annotations: List[Annotation], options: RenderOptions) -> Annotation:
    """
    Select the primary annotation based on options (score, length, family_rank)
    """
    if options.primary_marker_priority == "score":
        # Highest score first
        return max(annotations, key=lambda x: x.score)
    elif options.primary_marker_priority == "length":
        # Longest span first
        return max(annotations, key=lambda x: x.end - x.start)
    elif options.primary_marker_priority == "family_rank":
        # Could implement family ranking logic here
        # For now, just return highest score
        return max(annotations, key=lambda x: x.score)
    else:
        return annotations[0]  # Default to first


def generate_overlapping_tooltip(annotations: List[Annotation], primary: Annotation) -> str:
    """
    Generate HTML for showing overlapping markers (in tooltip or chip)
    """
    # Filter out the primary annotation
    secondary_annotations = [ann for ann in annotations if ann != primary]
    
    if not secondary_annotations:
        return ""
    
    # Show the number of additional markers
    additional_count = len(secondary_annotations)
    
    # Create a tooltip with details of secondary annotations
    tooltip_content = []
    for ann in secondary_annotations[:5]:  # Show max 5 additional markers
        tooltip_content.append(f"{ann.marker} (score: {ann.score:.2f})")
    
    if len(secondary_annotations) > 5:
        tooltip_content.append(f"+{len(secondary_annotations) - 5} more")
    
    tooltip_html = f'<span class="marker-chip" title="{"; ".join(tooltip_content)}">+{additional_count}</span>'
    
    return tooltip_html


def generate_legend(annotations: List[Annotation]) -> str:
    """
    Generate an HTML legend based on annotation families
    """
    # Collect unique families and their markers
    families = defaultdict(set)
    for ann in annotations:
        families[ann.family].add(ann.marker)
    
    legend_parts = ['<div class="legend"><h3>Legend</h3><ul>']
    
    for family, markers in families.items():
        legend_parts.append(f'<li><strong>{family}:</strong> {", ".join(sorted(markers))}</li>')
    
    legend_parts.append('</ul></div>')
    
    return "".join(legend_parts)