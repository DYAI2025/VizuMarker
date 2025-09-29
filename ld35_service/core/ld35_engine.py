import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict
from ..schemas.annotation import Annotation
from ..utils.chunking import normalize_text
from .config import settings
import yaml
import logging

logger = logging.getLogger(__name__)

class LD35Model:
    """
    LD-3.5 model implementation using real Canon/Weights/Promotion components
    from the LeanDeep_Engine folder.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        # Set up paths to the real LD-3.5 components
        project_root = Path(__file__).resolve().parents[2]
        self.engine_path = project_root / "LeanDeep_Engine"
        self.resources_path = project_root / "resources"
        default_marker_engine_base = project_root / "ME_ENGINE_CORE_V0.9" / "CORE_MarkerEngine_V0.9"
        self.marker_engine_base = (
            Path(settings.MARKER_ENGINE_PATH)
            if settings.MARKER_ENGINE_PATH
            else default_marker_engine_base
        )
        self.bundle_path = self.engine_path / "Marker_LD3.5_SSoTh" / "Marker_LD3.5_SSoTh"
        self.carl_path = self.engine_path / "carl"

        # Load the real LD-3.5 components
        self.markers_canonical = self._load_markers_canonical()
        self.markers_index = self._build_marker_index(self.markers_canonical)
        self.weights = self._load_weights()
        self.promotion_mapping = self._load_promotion_mapping()
        self.marker_definitions = self._load_marker_definitions()
        self.promotion_rules = self._load_promotion_rules()

        # Optional upstream marker engine core for gating
        self._marker_engine = self._initialize_marker_engine()

        # Import the CARL runtime from the actual engine
        engine_py_path = self.engine_path / "engine_py.py"
        if engine_py_path.exists():
            sys.path.insert(0, str(self.engine_path))
            try:
                from engine_py import run as carl_run
                self.carl_run = carl_run
            except ImportError:
                logger.warning("Could not import run from engine_py.py")
                self.carl_run = None
        else:
            logger.warning("engine_py.py not found")
            self.carl_run = None
    
    def _load_markers_canonical(self) -> Dict[str, Any]:
        """Load the canonical markers JSON file as primary reference."""
        markers: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        for path in [
            self.resources_path / "markers_canonical.ld35.json",
            self.resources_path / "markers_canonical.json",
            self.carl_path / "markers_canonical.ld35.json",
            self.carl_path / "markers_canonical.json",
            self.bundle_path / "Markers_canonical.json",
        ]:
            data = self._load_json_candidates([path])
            if isinstance(data, list):
                iterable = data
            elif isinstance(data, dict) and data.get("markers"):
                iterable = data.get("markers", [])
            else:
                iterable = []
            for entry in iterable:
                marker_id = entry.get("id") if isinstance(entry, dict) else None
                if marker_id and marker_id not in seen:
                    markers.append(entry)
                    seen.add(marker_id)
            if markers and path.parent == self.resources_path:
                # ensure resource overrides are prioritized; continue merging but keep order
                continue
        if markers:
            return {"markers": markers, "original_array": markers}
        logger.warning("No canonical marker JSON found; continuing with empty marker set")
        return {"markers": [], "original_array": []}

    def _build_marker_index(self, canonical: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Build a lookup dictionary keyed by marker id from canonical data."""
        markers = canonical.get("markers") or canonical.get("original_array") or []
        if isinstance(markers, dict):
            iterable = markers.values()
        else:
            iterable = markers

        index: Dict[str, Dict[str, Any]] = {}
        for entry in iterable:
            if not isinstance(entry, dict):
                continue
            marker_id = entry.get("id")
            if not marker_id:
                continue
            index[marker_id] = entry
        return index
    
    def _load_weights(self) -> Dict:
        """Load the weights JSON file"""
        data = self._load_json_candidates([
            self.resources_path / "weights.ld35.json",
            self.resources_path / "weights.json",
            self.carl_path / "weights.ld35.json",
            self.carl_path / "weights.json",
        ])
        return data if isinstance(data, dict) else {}

    def _load_json_candidates(self, candidates: List[Path]) -> Any:
        for path in candidates:
            if path and path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        logger.info("Loaded configuration from %s", path)
                        return data
                except Exception as exc:
                    logger.warning("Failed to load %s: %s", path, exc)
        return None
    
    def _load_promotion_mapping(self) -> Dict:
        """Load the promotion mapping JSON file"""
        data = self._load_json_candidates([
            self.resources_path / "promotion_mapping.ld35.json",
            self.resources_path / "promotion_mapping.json",
            self.carl_path / "promotion_mapping.ld35.json",
            self.carl_path / "promotion_mapping.json",
        ])
        return data if isinstance(data, dict) else {}
    
    def run_inference(self, text: str) -> List[Annotation]:
        """
        Run LD-3.5 inference on the provided text using the real CARL runtime
        """
        triggered_markers = self._run_marker_engine(text)
        if self.carl_run is not None:
            try:
                # Call the actual CARL runtime function with proper paths
                # We need to handle the format mismatch between the canonical file and engine expectations
                results = self._run_carl_engine(text)
                annotations = self._convert_carl_results_to_annotations(results, text)
                if annotations:
                    return annotations
                logger.debug("CARL runtime produced no annotations; falling back to pattern heuristics")
                atomic_annotations, marker_matches = self._pattern_based_detection(text)
                composed_annotations = self._detect_composed_markers(text, marker_matches)
                return atomic_annotations + composed_annotations
            except Exception as e:
                logger.error(f"CARL runtime error: {e}")
                # Fall back to pattern-based detection if CARL fails
                atomic_annotations, marker_matches = self._pattern_based_detection(text)
                composed_annotations = self._detect_composed_markers(text, marker_matches)
                return atomic_annotations + composed_annotations
        else:
            # Fall back to pattern-based detection if CARL is not available
            atomic_annotations, marker_matches = self._pattern_based_detection(text)
            composed_annotations = self._detect_composed_markers(text, marker_matches)
            return atomic_annotations + composed_annotations
    
    def _run_carl_engine(self, text: str):
        """
        Run the CARL engine with proper handling for file format issues
        """
        import json
        import os
        from pathlib import Path

        # Get the paths for CARL components
        canon_path = self.engine_path / "carl" / "markers_canonical.json"
        promotion_path = self.engine_path / "carl" / "promotion_mapping.json"
        weights_path = self.engine_path / "carl" / "weights.json"

        # Instead of calling the run function directly, we'll use the internal functions
        # which allows us to adapt the data structure as needed
        from engine_py import segment_dialog, detect_events, promote_sem, _build_counts, _features_from_counts, _compute_indices, _density, _package_output
        import time
        
        # Record start time
        t0 = time.time()
        
        # Segment the text
        segments = segment_dialog(text)
        
        # Load and adapt the canonical markers
        with open(canon_path, 'r', encoding='utf-8') as f:
            raw_canon_data = json.load(f)
            # The engine expects canon to be a dict with 'markers' key, but the file is a list
            # So we adapt it to the expected format
            canon = {"markers": raw_canon_data if isinstance(raw_canon_data, list) else raw_canon_data}
        
        # Load promotion and weights
        with open(promotion_path, 'r', encoding='utf-8') as f:
            promo = json.load(f)
        with open(weights_path, 'r', encoding='utf-8') as f:
            weights = json.load(f)

        # Run detection
        events = detect_events(text, segments, canon)
        
        # Run promotion
        events, promo_list = promote_sem(events, promo)

        # Calculate hash for metadata
        import hashlib
        def _sha256_str(s):
            return hashlib.sha256(s.encode("utf-8")).hexdigest()
        
        canon_hash = _sha256_str(json.dumps(raw_canon_data, ensure_ascii=False))
        engine_version = "CARL-PY-0.9"
        engine_hash = _sha256_str(engine_version)

        # Calculate counts, features, and indices
        counts = _build_counts(events)
        features = _features_from_counts(counts, len(text))
        indices = _compute_indices(features, weights)
        elapsed_ms = (time.time() - t0) * 1000
        
        # Package the output
        out = _package_output(
            text,
            segments,
            events,
            indices,
            canon_hash,
            engine_hash,
            elapsed_ms=elapsed_ms,
        )
        out["promotion"] = promo_list
        return out
    
    def _convert_carl_results_to_annotations(self, carl_results: Any, text: str) -> List[Annotation]:
        """
        Convert CARL runtime results to Annotation objects
        """
        annotations = []
        
        # Process the CARL results based on their structure
        if isinstance(carl_results, dict):
            # Handle different possible structures of CARL results
            if 'markers' in carl_results:
                markers = carl_results['markers']
            elif 'results' in carl_results:
                markers = carl_results['results']
            else:
                markers = carl_results  # Assume the whole dict contains markers
            
            # Process markers list or dict
            if isinstance(markers, list):
                for marker in markers:
                    annotation = self._create_annotation_from_marker(marker, text)
                    if annotation:
                        annotations.append(annotation)
            elif isinstance(markers, dict):
                for marker_id, marker_data in markers.items():
                    if isinstance(marker_data, dict):
                        # If the marker_data contains position information
                        if 'start' in marker_data and 'end' in marker_data:
                            annotation = self._create_annotation_from_marker(marker_data, text)
                            if annotation:
                                annotations.append(annotation)
                        else:
                            # If it's just metadata, try to detect positions in text
                            annotation = self._detect_annotation_in_text(marker_data, text)
                            if annotation:
                                annotations.append(annotation)
        
        elif isinstance(carl_results, list):
            for item in carl_results:
                if isinstance(item, dict):
                    annotation = self._create_annotation_from_marker(item, text)
                    if annotation:
                        annotations.append(annotation)
        
        return annotations
    
    def _create_annotation_from_marker(self, marker_data: Dict, text: str) -> Optional[Annotation]:
        """
        Create an Annotation from marker data
        """
        try:
            # Extract marker information
            marker_id = marker_data.get('id', 'UNKNOWN')
            marker_type = 'SEM'  # Default type, will be detected from ID
            
            # Determine marker type from the ID prefix
            if marker_id.startswith('ATO_'):
                marker_type = 'ATO'
            elif marker_id.startswith('SEM_'):
                marker_type = 'SEM'
            elif marker_id.startswith('CLU_'):
                marker_type = 'CLU'
            elif marker_id.startswith('MEMA_'):
                marker_type = 'MEMA'
            
            # Extract position info, if available
            start = marker_data.get('start', 0)
            end = marker_data.get('end', 0)
            
            # If no position info, try to find the text in the original text
            if start == 0 and end == 0 and 'pattern' in marker_data:
                pattern = marker_data['pattern']
                import re
                matches = list(re.finditer(str(pattern), text, re.IGNORECASE))
                if matches:
                    match = matches[0]  # Use first match
                    start = match.start()
                    end = match.end()
            
            # Extract score, default to 0.8 if not provided
            score = marker_data.get('score', marker_data.get('confidence', 0.8))
            
            # Extract label, default to marker_id if not provided
            label = marker_data.get('label', marker_data.get('concept', marker_id))
            
            # Create annotation
            annotation = Annotation(
                start=start,
                end=end,
                marker=marker_id,
                family=marker_type,
                label=label,
                score=score
            )
            
            return annotation
        except Exception as e:
            logger.warning(f"Could not create annotation from marker data: {e}")
            return None
    
    def _detect_annotation_in_text(self, marker_data: Dict, text: str) -> Optional[Annotation]:
        """
        Try to detect annotation positions in text based on marker patterns
        """
        try:
            # Try to find the marker pattern in the text
            marker_id = marker_data.get('id', 'UNKNOWN')
            
            # Look for patterns in the marker data
            patterns = []
            if 'pattern' in marker_data:
                patterns.append(marker_data['pattern'])
            if 'examples' in marker_data and isinstance(marker_data['examples'], list):
                for example in marker_data['examples'][:3]:  # Check first 3 examples
                    if isinstance(example, str):
                        patterns.append(example)
            
            # Search for patterns in the text
            import re
            for pattern in patterns:
                matches = list(re.finditer(re.escape(str(pattern)), text, re.IGNORECASE))
                if matches:
                    match = matches[0]
                    # Determine marker family from ID
                    marker_type = 'SEM'  # Default
                    if marker_id.startswith('ATO_'):
                        marker_type = 'ATO'
                    elif marker_id.startswith('SEM_'):
                        marker_type = 'SEM'
                    elif marker_id.startswith('CLU_'):
                        marker_type = 'CLU'
                    elif marker_id.startswith('MEMA_'):
                        marker_type = 'MEMA'
                    
                    # Create annotation
                    annotation = Annotation(
                        start=match.start(),
                        end=match.end(),
                        marker=marker_id,
                        family=marker_type,
                        label=marker_data.get('concept', marker_id),
                        score=0.7  # Default score for pattern-matched annotations
                    )
                    return annotation
            
            # If no pattern found, return a zero-span annotation at start
            # This is just to provide some annotation when positions aren't clear
            marker_type = 'SEM'
            if marker_id.startswith('ATO_'):
                marker_type = 'ATO'
            elif marker_id.startswith('CLU_'):
                marker_type = 'CLU'
            elif marker_id.startswith('MEMA_'):
                marker_type = 'MEMA'
                
            return Annotation(
                start=0,
                end=0,
                marker=marker_id,
                family=marker_type,
                label=marker_data.get('concept', marker_id),
                score=0.5  # Lower score for unclear positions
            )
        except Exception as e:
            logger.warning(f"Could not detect annotation in text: {e}")
            return None
    
    def _pattern_based_detection(
        self, text: str, allowed_markers: Optional[Set[str]] = None
    ) -> Tuple[List[Annotation], Dict[str, List[Tuple[int, int]]]]:
        """Detect atomic markers and collect anchor spans for downstream promotion."""
        if not self.markers_index:
            return [], {}

        import re

        annotations: List[Annotation] = []
        marker_matches: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        seen_keys = set()

        family_order = {"ATO": 0, "SEM": 1, "CLU": 2, "MEMA": 3}
        marker_items = sorted(
            self.markers_index.items(),
            key=lambda kv: family_order.get(self._get_marker_type_from_id(kv[0]), 4),
        )

        for marker_id, marker_data in marker_items:
            if allowed_markers is not None and marker_id not in allowed_markers:
                continue

            try:
                regex_specs, literal_terms = self._collect_marker_signals(marker_id, marker_data)
                if not regex_specs and not literal_terms:
                    continue

                marker_type = self._get_marker_type_from_id(marker_id)
                label = self._get_marker_label(marker_data, marker_id)
                score = self._get_marker_score(marker_data)

                for pattern, flags in regex_specs:
                    try:
                        compiled = re.compile(pattern, flags)
                    except re.error as exc:
                        logger.debug("Invalid regex for %s: %s", marker_id, exc)
                        continue

                    for match in compiled.finditer(text):
                        start, end = match.span()
                        if start == end:
                            continue
                        key = (start, end, marker_id)
                        if key in seen_keys:
                            continue
                        annotations.append(
                            Annotation(
                                start=start,
                                end=end,
                                marker=marker_id,
                                family=marker_type,
                                label=label,
                                score=score,
                            )
                        )
                        seen_keys.add(key)
                        marker_matches[marker_id].append((start, end))

                for term in literal_terms:
                    escaped = re.escape(term)
                    if term.replace(" ", "").isalpha() or term.isalnum():
                        escaped = rf"\b{escaped}\b"
                    try:
                        literal_regex = re.compile(escaped, re.IGNORECASE)
                    except re.error:
                        continue
                    for match in literal_regex.finditer(text):
                        start, end = match.span()
                        if start == end:
                            continue
                        key = (start, end, marker_id)
                        if key in seen_keys:
                            continue
                        annotations.append(
                            Annotation(
                                start=start,
                                end=end,
                                marker=marker_id,
                                family=marker_type,
                                label=label,
                                score=max(0.4, score - 0.1),
                            )
                        )
                        seen_keys.add(key)
                        marker_matches[marker_id].append((start, end))

            except Exception as exc:
                logger.debug(f"Pattern fallback failed for marker {marker_id}: {exc}")

        return annotations, marker_matches

    def _collect_marker_signals(self, marker_id: str, canonical_entry: Dict[str, Any]) -> Tuple[List[Tuple[str, int]], Set[str]]:
        import re

        regex_specs: List[Tuple[str, int]] = []
        literal_terms: Set[str] = set()

        def add_regex(pattern: str, flags: Optional[int] = None) -> None:
            pattern = (pattern or "").strip()
            if not pattern:
                return
            treat_as_regex = False
            regex_indicators = set("\\[](){}|*+?^$")
            if pattern.startswith("(?") or "\\b" in pattern or any(ch in regex_indicators for ch in pattern):
                treat_as_regex = True
            if not treat_as_regex and "." in pattern:
                # Treat ellipsis / plain dots as literal
                pattern = rf"\b{re.escape(pattern)}\b"
            elif not treat_as_regex:
                pattern = rf"\b{re.escape(pattern)}\b"
            regex_specs.append((pattern, flags if flags is not None else re.IGNORECASE))

        def add_literal(term: str) -> None:
            term = (term or "").strip()
            if len(term) > 2:
                literal_terms.add(term)

        def process_pattern_spec(spec: Any) -> None:
            if not spec:
                return
            if isinstance(spec, str):
                add_regex(spec)
            elif isinstance(spec, list):
                for item in spec:
                    if isinstance(item, str):
                        add_regex(item)
                    elif isinstance(item, dict):
                        regex_value = item.get("regex") or item.get("pattern")
                        if not isinstance(regex_value, str):
                            continue
                        flags = 0
                        for flag_name in item.get("flags", []) or []:
                            attr = getattr(re, str(flag_name).upper(), None)
                            if isinstance(attr, int):
                                flags |= attr
                        add_regex(regex_value, flags or re.IGNORECASE)
            elif isinstance(spec, dict):
                regex_value = spec.get("regex") or spec.get("pattern")
                if isinstance(regex_value, str):
                    flags = 0
                    for flag_name in spec.get("flags", []) or []:
                        attr = getattr(re, str(flag_name).upper(), None)
                        if isinstance(attr, int):
                            flags |= attr
                    add_regex(regex_value, flags or re.IGNORECASE)

        pattern_spec = canonical_entry.get("pattern")
        process_pattern_spec(pattern_spec)

        definition = self.marker_definitions.get(marker_id)
        if definition:
            process_pattern_spec(definition.get("pattern"))
            process_pattern_spec(definition.get("patterns"))

        def parse_detects(source: Any) -> None:
            detects = source.get("detects") if isinstance(source, dict) else None
            if not isinstance(detects, list):
                return
            for det in detects:
                if not isinstance(det, dict):
                    continue
                regex_value = det.get("regex")
                if not isinstance(regex_value, str):
                    continue
                flags_value = det.get("flags")
                flags = 0
                if isinstance(flags_value, str):
                    for flag_char in flags_value:
                        attr = getattr(re, flag_char.upper(), None)
                        if isinstance(attr, int):
                            flags |= attr
                elif isinstance(flags_value, list):
                    for flag_name in flags_value:
                        attr = getattr(re, str(flag_name).upper(), None)
                        if isinstance(attr, int):
                            flags |= attr
                add_regex(regex_value, flags or re.IGNORECASE)

        parse_detects(canonical_entry)
        if definition:
            parse_detects(definition)

        for source in (canonical_entry, definition or {}):
            frame = source.get("frame") if isinstance(source, dict) else None
            if isinstance(frame, dict):
                signals = frame.get("signal")
                if isinstance(signals, list):
                    for sig in signals:
                        if isinstance(sig, str):
                            add_literal(sig)
                elif isinstance(signals, str):
                    add_literal(signals)

            examples = source.get("examples") if isinstance(source, dict) else None
            if isinstance(examples, dict):
                for key in ("positive", "negative", "negatives", "neutral"):
                    values = examples.get(key)
                    if isinstance(values, list):
                        for example in values:
                            if isinstance(example, str):
                                add_literal(example)
            elif isinstance(examples, list):
                for example in examples:
                    if isinstance(example, str):
                        add_literal(example)

        return regex_specs, literal_terms

    def _detect_composed_markers(
        self,
        text: str,
        marker_matches: Dict[str, List[Tuple[int, int]]],
        allowed_markers: Optional[Set[str]] = None,
    ) -> List[Annotation]:
        composed_annotations: List[Annotation] = []
        sentences = self._get_sentences(text)
        tokens = self._get_tokens(text)

        composed_cfg = self.weights.get("composed", {}) if isinstance(self.weights, dict) else {}
        min_children_default = int(composed_cfg.get("min_children", 1) or 1)
        min_score_default = float(composed_cfg.get("min_score", 0.6) or 0.6)

        for marker_id, marker_data in self.markers_index.items():
            if marker_data.get("kind") not in {"composed", "COMPOSED"}:
                continue
            if allowed_markers is not None and marker_id not in allowed_markers:
                continue

            definition = self.marker_definitions.get(marker_id, {})
            composed_of = marker_data.get("composed_of") or definition.get("composed_of")
            if not composed_of:
                continue

            child_info: List[Tuple[str, float, List[Tuple[int, int]]]] = []
            for child in composed_of:
                if isinstance(child, dict):
                    child_id = child.get("marker_id")
                    weight = float(child.get("weight", 1.0) or 1.0)
                else:
                    child_id = str(child)
                    weight = 1.0
                if not child_id:
                    continue
                matches = marker_matches.get(child_id, [])
                child_info.append((child_id, weight, matches))

            if not child_info:
                continue

            child_counts = {child_id: len(matches) for child_id, _, matches in child_info}
            total_children = sum(child_counts.values())
            if total_children < min_children_default:
                continue

            weight_sum = sum(weight for _, weight, _ in child_info) or 1.0
            score = sum(len(matches) * weight for _, weight, matches in child_info) / weight_sum

            min_score = float(
                marker_data.get("min_score")
                or definition.get("min_score")
                or min_score_default
            )
            if score < min_score:
                continue

            activation_expr = marker_data.get("activation") or definition.get("activation")
            context = {**child_counts, "score": score, "total_children": total_children}
            if not self._evaluate_expression(activation_expr, context):
                continue

            child_spans = [span for _, _, matches in child_info for span in matches]
            span_policy = marker_data.get("span_policy") or definition.get("span_policy") or {}
            span = self._apply_span_policy(text, sentences, tokens, child_spans, span_policy)
            if not span:
                continue

            promo_rule = self.promotion_rules.get(marker_id)
            final_family = marker_data.get("family") or definition.get("family") or self._get_marker_type_from_id(marker_id)
            if promo_rule:
                promo_context = {"score": score, "total_children": total_children}
                if not self._evaluate_expression(promo_rule.get("activate_when"), promo_context):
                    continue
                min_score_rule = promo_rule.get("min_score")
                if min_score_rule is not None and score < float(min_score_rule):
                    continue
                final_family = promo_rule.get("promote_to", final_family)

            label = self._get_marker_label(marker_data or definition, marker_id)
            composed_annotations.append(
                Annotation(
                    start=span[0],
                    end=span[1],
                    marker=marker_id,
                    family=final_family,
                    label=label,
                    score=score,
                )
            )
            marker_matches.setdefault(marker_id, []).append(span)

        return composed_annotations

    def _load_marker_definitions(self) -> Dict[str, Dict[str, Any]]:
        definitions: Dict[str, Dict[str, Any]] = {}
        bundle_dir = self.marker_engine_base / "_Marker_5.0"
        if not bundle_dir.exists():
            return definitions

        for yaml_path in bundle_dir.glob("*.yaml"):
            try:
                text = yaml_path.read_text("utf-8")
                if not text.strip():
                    continue
                data = yaml.safe_load(text)
                if isinstance(data, dict) and data.get("id"):
                    definitions[data["id"]] = data
            except Exception as exc:
                logger.debug("Failed to load marker definition %s: %s", yaml_path.name, exc)
        return definitions

    def _load_promotion_rules(self) -> Dict[str, Dict[str, Any]]:
        mapping = self._load_json_candidates([
            self.resources_path / "promotion_mapping.ld35.json",
            self.resources_path / "promotion_mapping.json",
            self.carl_path / "promotion_mapping.ld35.json",
            self.carl_path / "promotion_mapping.json",
        ]) or {}
        rules = {}
        for entry in mapping.get("promotions", []):
            marker_id = entry.get("marker_id")
            if marker_id:
                rules[marker_id] = entry
        return rules

    def _evaluate_expression(self, expression: Optional[str], context: Dict[str, Any]) -> bool:
        if not expression:
            return True
        expr = expression.replace("&&", " and ").replace("||", " or ")
        safe_globals = {"__builtins__": {}}
        try:
            return bool(eval(expr, safe_globals, context))
        except Exception as exc:
            logger.debug("Failed to evaluate expression '%s': %s", expression, exc)
            return False

    def _apply_span_policy(
        self,
        text: str,
        sentences: List[Dict[str, int]],
        tokens: List[Dict[str, int]],
        child_spans: List[Tuple[int, int]],
        span_policy: Dict[str, Any],
    ) -> Optional[Tuple[int, int]]:
        if not child_spans:
            return None

        mode = (span_policy or {}).get("mode", "anchor_window")
        if mode == "sentence_union":
            if not sentences:
                return self._anchor_window(text, tokens, child_spans, span_policy)
            sentence_ids = sorted(
                {self._find_sentence_index(sentences, (start + end) // 2) for start, end in child_spans}
            )
            sentence_ids = [idx for idx in sentence_ids if idx is not None]
            if not sentence_ids:
                return self._anchor_window(text, tokens, child_spans, span_policy)
            max_span = span_policy.get("max_sentence_span", 1)
            if sentence_ids[-1] - sentence_ids[0] + 1 > max_span:
                if span_policy.get("fallback") == "anchor_window":
                    return self._anchor_window(text, tokens, child_spans, span_policy)
                return None
            start = sentences[sentence_ids[0]]["start"]
            end = sentences[sentence_ids[-1]]["end"]
            return (start, end)

        return self._anchor_window(text, tokens, child_spans, span_policy)

    def _anchor_window(
        self,
        text: str,
        tokens: List[Dict[str, int]],
        spans: List[Tuple[int, int]],
        span_policy: Dict[str, Any],
    ) -> Optional[Tuple[int, int]]:
        if not spans:
            return None
        window_tokens = span_policy.get("window_tokens") or [-8, 8]
        anchor_span = max(spans, key=lambda s: s[1] - s[0])
        anchor_index = self._find_token_index(tokens, anchor_span[0])
        if anchor_index is None:
            start = max(0, anchor_span[0] - 50)
            end = min(len(text), anchor_span[1] + 50)
            return (start, end)
        left = max(0, anchor_index + int(window_tokens[0]))
        right = min(len(tokens) - 1, anchor_index + int(window_tokens[1]))
        return (tokens[left]["start"], tokens[right]["end"])

    def _get_sentences(self, text: str) -> List[Dict[str, int]]:
        import re

        sentences: List[Dict[str, int]] = []
        for match in re.finditer(r'[^.!?\n]+(?:[.!?]+|\n+)', text):
            sentences.append({"start": match.start(), "end": match.end()})
        if not sentences:
            sentences.append({"start": 0, "end": len(text)})
        elif sentences[-1]["end"] < len(text):
            sentences.append({"start": sentences[-1]["end"], "end": len(text)})
        return sentences

    def _get_tokens(self, text: str) -> List[Dict[str, int]]:
        import re

        return [
            {"start": m.start(), "end": m.end()}
            for m in re.finditer(r"\b\w+\b", text)
        ]

    def _find_sentence_index(self, sentences: List[Dict[str, int]], position: int) -> Optional[int]:
        for idx, sentence in enumerate(sentences):
            if sentence["start"] <= position < sentence["end"]:
                return idx
        if sentences:
            return len(sentences) - 1
        return None

    def _find_token_index(self, tokens: List[Dict[str, int]], position: int) -> Optional[int]:
        for idx, token in enumerate(tokens):
            if token["start"] <= position < token["end"]:
                return idx
        if tokens and position >= tokens[-1]["end"]:
            return len(tokens) - 1
        return None

    def _initialize_marker_engine(self):
        """Initialise optional upstream marker engine core if available."""
        try:
            engine_base = self.marker_engine_base
            if not engine_base.exists():
                return None

            if str(engine_base) not in sys.path:
                sys.path.append(str(engine_base))

            from marker_engine_core import MarkerEngine  # type: ignore

            marker_root = engine_base / "_Marker_5.0"
            detect_registry = engine_base / "DETECT_" / "DETECT_registry.json"
            schema_root = engine_base / "SCH_"
            plugin_root = engine_base / "plugins"

            engine = MarkerEngine(
                marker_root=str(marker_root),
                schema_root=str(schema_root),
                detect_registry=str(detect_registry),
                plugin_root=str(plugin_root),
            )
            logger.info("Marker engine core initialised from %s", engine_base)
            return engine
        except Exception as exc:
            logger.warning("Could not initialise marker engine core: %s", exc)
            return None

    def _run_marker_engine(self, text: str) -> Set[str]:
        if not getattr(self, "_marker_engine", None):
            return set()
        try:
            result = self._marker_engine.analyze(text)  # type: ignore[attr-defined]
            markers = {hit.get("marker") for hit in result.get("hits", []) if hit.get("marker")}
            return {marker for marker in markers if isinstance(marker, str)}
        except Exception as exc:
            logger.debug("Marker engine analyse failed: %s", exc)
            return set()

    def _get_marker_type_from_id(self, marker_id: str) -> str:
        """
        Determine marker type (family) from the marker ID prefix
        """
        if marker_id.startswith('ATO_'):
            return 'ATO'
        elif marker_id.startswith('SEM_'):
            return 'SEM'
        elif marker_id.startswith('CLU_'):
            return 'CLU'
        elif marker_id.startswith('MEMA_'):
            return 'MEMA'
        else:
            return 'SEM'  # Default type

    def _get_marker_label(self, marker_data: Dict[str, Any], default: str) -> str:
        frame = marker_data.get('frame')
        if isinstance(frame, dict):
            concept = frame.get('concept')
            if isinstance(concept, str) and concept.strip():
                return concept
        description = marker_data.get('description')
        if isinstance(description, str) and description.strip():
            return description.strip()
        return default

    def _get_marker_score(self, marker_data: Dict[str, Any]) -> float:
        scoring = marker_data.get('scoring')
        score_candidates: List[float] = []
        if isinstance(scoring, dict):
            for key in ('weight', 'base', 'score'):
                value = scoring.get(key)
                if isinstance(value, (int, float)):
                    score_candidates.append(float(value))
        explicit = marker_data.get('score')
        if isinstance(explicit, (int, float)):
            score_candidates.append(float(explicit))
        if not score_candidates:
            return 0.7
        # Normalise into [0,1] range for downstream comparability
        score = max(score_candidates)
        if score > 1.0:
            score = min(1.0, score / 2.0)
        return max(0.3, float(score))


# Global model instance
_ld35_model = None


def get_ld35_model() -> LD35Model:
    """
    Get or initialize the LD-3.5 model instance.
    """
    global _ld35_model
    if _ld35_model is None:
        _ld35_model = LD35Model()
    return _ld35_model


def process_ld35_annotations(text: str, options: Optional[Dict[str, Any]] = None) -> List[Annotation]:
    """
    Process annotations using the LD-3.5 engine with chunking support
    """
    if not options:
        options = {}
    
    # Get the LD-3.5 model instance
    model = get_ld35_model()
    
    # Normalize text to ensure stable offsets
    normalized_text = normalize_text(text)
    
    # Get chunk size from options
    chunk_size = options.get('chunk_size', 12000)
    overlap = options.get('overlap', 200)
    
    # Import chunking utilities
    from ..utils.chunking import chunk_text, merge_chunk_annotations
    
    # Split text into chunks
    chunks = chunk_text(normalized_text, chunk_size, overlap)
    
    # Process each chunk and gather results
    all_chunk_annotations = []
    for chunk_text, start_offset, _ in chunks:
        # Process chunk with LD35 model
        chunk_annotations = model.run_inference(chunk_text)
        
        # Adjust offsets to global positions
        all_chunk_annotations.append((chunk_annotations, start_offset))
    
    # Merge annotations from all chunks
    merged_annotations = merge_chunk_annotations(all_chunk_annotations)
    
    # Apply any post-processing if needed
    final_annotations = post_process_annotations(merged_annotations)
    
    return final_annotations


def process_with_llm_fallback(text: str, options: Optional[Dict[str, Any]] = None) -> List[Annotation]:
    """
    Process annotations using an LLM fallback if LD-3.5 is not available
    """
    if not options:
        options = {}
    
    logger.warning("Using LLM fallback processing")
    
    # Use the same LD-3.5 model but with a different processing approach
    model = LD35Model()
    annotations, _ = model._pattern_based_detection(text)
    
    # Adjust scores to indicate these come from fallback
    for ann in annotations:
        ann.score = max(0.3, ann.score - 0.2)  # Reduce score to indicate fallback
    
    return annotations


def post_process_annotations(annotations: List[Annotation]) -> List[Annotation]:
    """
    Apply post-processing to annotations such as resolving overlaps,
    normalizing formats, etc.
    """
    # Remove duplicates
    unique_annotations = remove_duplicate_annotations(annotations)
    
    # Resolve overlaps based on priority (score, length, family_rank)
    resolved_annotations = resolve_overlapping_annotations(unique_annotations)
    
    return resolved_annotations


def remove_duplicate_annotations(annotations: List[Annotation]) -> List[Annotation]:
    """
    Remove duplicate annotations (same start, end, marker)
    """
    seen = set()
    unique = []
    
    for ann in annotations:
        key = (ann.start, ann.end, ann.marker)
        if key not in seen:
            seen.add(key)
            unique.append(ann)
    
    return unique


def resolve_overlapping_annotations(annotations: List[Annotation]) -> List[Annotation]:
    """
    Resolve overlapping annotations based on priority rules
    """
    # Sort by priority: score (descending), then length (descending), then family rank
    sorted_anns = sorted(
        annotations,
        key=lambda x: (x.score, x.end - x.start),  # Simplified priority
        reverse=True
    )
    
    # For overlapping annotations, keep the highest priority one
    # This is a simplified approach; more complex resolution could be implemented
    non_overlapping = []
    for ann in sorted_anns:
        # Check if this annotation overlaps with any already selected
        is_overlapping = False
        for existing in non_overlapping:
            # Check for overlap
            if max(ann.start, existing.start) < min(ann.end, existing.end):
                is_overlapping = True
                break
        
        if not is_overlapping:
            non_overlapping.append(ann)
    
    # Return in original order
    return sorted(non_overlapping, key=lambda x: x.start)
