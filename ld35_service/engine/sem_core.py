# ld35_service/engine/sem_core.py
"""
Enhanced semantic engine core for LD3.5 with composed markers, 
sentence-level spans, and activation formulas instead of just regex word triggers.
"""
from __future__ import annotations
import json
import re
import math
import ast
import operator
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Set
from collections import defaultdict


# -------- Utilities --------
def load_json(p: Path) -> dict:
    """Load JSON file safely"""
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def sentence_boundaries(text: str) -> List[Tuple[int, int]]:
    """Simple German sentence splitter with paragraph breaks"""
    N = len(text)
    out = []
    start = 0
    enders = set(".!?…")
    i = 0
    
    while i < N:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < N else ""
        
        if ch in enders:
            j = i + 1
            # Skip closing quotes/brackets
            closing_chars = r'"»\'")\]}' 
            while j < N and text[j] in closing_chars:
                j += 1
            if j >= N or text[j].isspace():
                out.append((start, j))
                start = j
                i = j
                continue
                
        # Hard break on double newlines
        if ch == "\n" and (nxt == "\n" or nxt == "\r"):
            out.append((start, i))
            start = i + 1
            i += 1
            continue
            
        i += 1
    
    if start < N:
        out.append((start, N))
    
    return out


# -------- Canon indexing --------
class Canon:
    """Canonical marker definitions loader and indexer"""
    
    def __init__(self, markers: List[dict]):
        self.by_id: Dict[str, dict] = {m["id"]: m for m in markers}
        self.atomics = [m for m in markers if m.get("kind") == "atomic"]
        self.composed = [m for m in markers if m.get("kind") == "composed"]

    @classmethod
    def from_files(cls, resources_dir: Path):
        """Load canonical markers from resources directory"""
        canon_file = resources_dir / "markers_canonical.ld35.json"
        if canon_file.exists():
            canon = load_json(canon_file)
            markers = canon.get("markers", [])
            return cls(markers)
        return cls([])


# -------- Atomic detection with better pattern matching --------
def compile_atomic_regex(canon: Canon) -> Dict[str, Tuple[List[re.Pattern], List[re.Pattern]]]:
    """Compile regex patterns from atomic markers with demote patterns"""
    rx = {}
    for m in canon.atomics:
        detects = m.get("detects", [])
        demote_if = m.get("demote_if", [])
        
        # Compile positive patterns
        patterns = []
        for d in detects:
            pattern = d.get("regex", "")
            flags_str = d.get("flags", "")
            
            flags = 0
            if "i" in flags_str.lower():
                flags |= re.IGNORECASE
            if "m" in flags_str.lower():
                flags |= re.MULTILINE
            if "s" in flags_str.lower():
                flags |= re.DOTALL
                
            try:
                compiled_pattern = re.compile(pattern, flags)
                patterns.append(compiled_pattern)
            except re.error as e:
                print(f"Warning: Invalid regex pattern in {m['id']}: {pattern} - {e}")
        
        # Compile demote patterns
        demote_patterns = []
        for d in demote_if:
            pattern = d.get("regex", "")
            flags_str = d.get("flags", "")
            
            flags = 0
            if "i" in flags_str.lower():
                flags |= re.IGNORECASE
            if "m" in flags_str.lower():
                flags |= re.MULTILINE
            if "s" in flags_str.lower():
                flags |= re.DOTALL
                
            try:
                compiled_pattern = re.compile(pattern, flags)
                demote_patterns.append(compiled_pattern)
            except re.error as e:
                print(f"Warning: Invalid demote regex pattern in {m['id']}: {pattern} - {e}")
                
        rx[m["id"]] = (patterns, demote_patterns)
    return rx


def should_demote_match(text: str, start: int, end: int, demote_patterns: List[re.Pattern], 
                       context_window: int = 10) -> bool:
    """Check if a match should be demoted based on demote_if patterns"""
    if not demote_patterns:
        return False
    
    # Primary check: does the match itself fit a demote pattern?
    match_text = text[start:end]
    for pattern in demote_patterns:
        if pattern.fullmatch(match_text):
            return True
    
    # Secondary check: look for demote patterns that overlap with the match
    for pattern in demote_patterns:
        for match in pattern.finditer(text):
            demote_start, demote_end = match.span()
            # Check if the demote pattern overlaps with our match
            if not (demote_end <= start or demote_start >= end):
                return True
    
    return False


def detect_atomics(text: str, rx_index: Dict[str, Tuple[List[re.Pattern], List[re.Pattern]]]) -> List[dict]:
    """Detect atomic markers in text with demote_if filtering"""
    anns = []
    
    for marker_id, (patterns, demote_patterns) in rx_index.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                start, end = match.span(0)
                if end <= start:
                    continue
                
                # Check if this match should be demoted (filtered out)
                if should_demote_match(text, start, end, demote_patterns):
                    continue
                    
                # Extract family from marker ID
                family = marker_id.split("_", 1)[0].upper()
                
                anns.append({
                    "marker_id": marker_id,
                    "family": family,
                    "start": start,
                    "end": end,
                    "score": 1.0
                })
    
    # Sort by position for stable order
    anns.sort(key=lambda a: (a["start"], -a["end"]))
    return anns


# -------- Safe eval for activation formulas --------
OPS = {
    ast.And: operator.and_,
    ast.Or: operator.or_,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


def _eval(node, env):
    """Safely evaluate AST node with environment variables"""
    if isinstance(node, ast.BoolOp):
        vals = [_eval(v, env) for v in node.values]
        if isinstance(node.op, ast.Or):
            return any(vals)
        else:  # ast.And
            return all(vals)
            
    if isinstance(node, ast.Compare):
        left = _eval(node.left, env)
        for op, right in zip(node.ops, node.comparators):
            right = _eval(right, env)
            if not OPS[type(op)](left, right):
                return False
            left = right
        return True
        
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval(node.operand, env)
        
    if isinstance(node, ast.Name):
        return env.get(node.id, 0)
        
    if isinstance(node, ast.Constant):
        return node.value
        
    if isinstance(node, ast.Num):  # For older Python versions
        return node.n
        
    raise ValueError(f"Unsupported expression node: {type(node)}")


def eval_activation(expr: str, env: Dict[str, int | float | bool]) -> bool:
    """Safely evaluate activation expression"""
    if not expr:
        return True
        
    # Normalize C-style operators to Python
    safe_expr = expr.replace("&&", " and ").replace("||", " or ")
    
    try:
        tree = ast.parse(safe_expr, mode="eval")
        result = _eval(tree.body, env)
        return bool(result)
    except Exception as e:
        print(f"Warning: Failed to evaluate activation expression '{expr}': {e}")
        return False


# -------- Span policies for sentence-level spans --------
def sentence_union(sentences: List[Tuple[int, int]], iL: int, iR: int, max_sent: int = 1) -> Tuple[int, int]:
    """Expand span to include up to max_sent sentences"""
    need = max(1, max_sent) - (iR - iL + 1)
    step = 0
    N = len(sentences)
    
    while need > 0 and (iL > 0 or iR < N - 1):
        if step % 2 == 0 and iR < N - 1:
            iR += 1
        elif iL > 0:
            iL -= 1
        step += 1
        need -= 1
        
    return sentences[iL][0], sentences[iR][1]


def clause_union(text: str, start: int, end: int) -> Tuple[int, int]:
    """Expand to nearest comma/semicolon bounds"""
    text_len = len(text)
    
    # Find left boundary
    left_comma = text.rfind(",", 0, start)
    left_semi = text.rfind(";", 0, start)
    left_bound = max(left_comma, left_semi)
    if left_bound >= 0:
        start = left_bound + 1
        
    # Find right boundary
    right_comma = text.find(",", end)
    right_semi = text.find(";", end)
    
    right_bounds = [x for x in (right_comma, right_semi) if x != -1]
    if right_bounds:
        end = min(right_bounds)
        
    return max(0, start), min(text_len, end)


def apply_span_policy(policy: dict, text: str, sentences: List[Tuple[int, int]], 
                     start: int, end: int) -> Tuple[int, int]:
    """Apply span policy to determine final span boundaries"""
    if not policy:
        policy = {}
        
    mode = policy.get("mode", "anchor_window")
    
    if mode == "sentence_union":
        # Find sentences containing the span
        mid = (start + end) // 2
        sent_idx = None
        for i, (s_start, s_end) in enumerate(sentences):
            if s_start <= mid < s_end:
                sent_idx = i
                break
                
        if sent_idx is None:
            return start, end
            
        # Find sentence range for the entire span
        iL = sent_idx
        iR = sent_idx
        
        for i, (s_start, s_end) in enumerate(sentences):
            if s_start <= start < s_end:
                iL = i
            if s_start < end <= s_end:
                iR = i
                
        max_sentences = policy.get("max_sentence_span", 1)
        return sentence_union(sentences, iL, iR, max_sentences)
        
    elif mode == "clause_union":
        return clause_union(text, start, end)
        
    else:  # anchor_window
        window = policy.get("window_tokens", [-8, 8])
        # Rough character-based window (4 chars per token approximation)
        chars_per_token = 4
        left_expand = window[0] * chars_per_token
        right_expand = window[1] * chars_per_token
        
        new_start = max(0, start + left_expand)
        new_end = min(len(text), end + right_expand)
        return new_start, new_end


# -------- Composition engine for semantic patterns --------
def compose(text: str, canon: Canon, atomics: List[dict], promotion: dict, weights: dict) -> List[dict]:
    """Detect composed markers using activation formulas and span policies"""
    sentences = sentence_boundaries(text)
    
    # Index atomic hits per sentence
    per_sent: List[List[dict]] = [[] for _ in sentences]
    
    def get_sentence_idx(pos: int) -> Optional[int]:
        """Find which sentence contains this position"""
        for i, (sent_start, sent_end) in enumerate(sentences):
            if sent_start <= pos < sent_end:
                return i
        return None
    
    # Distribute atomic annotations to sentences
    for atomic in atomics:
        mid = (atomic["start"] + atomic["end"]) // 2
        sent_idx = get_sentence_idx(mid)
        if sent_idx is not None:
            per_sent[sent_idx].append(atomic)
    
    composed_annotations = []
    
    # Process each composed marker
    for marker in canon.composed:
        marker_id = marker["id"]
        activation_expr = marker.get("activation", "total_children >= 1")
        span_policy = marker.get("span_policy", {"mode": "sentence_union", "max_sentence_span": 1})
        composed_of = marker.get("composed_of", [])
        
        if not composed_of:
            continue
            
        # Build weights map
        weights_map = {}
        needed_ids = []
        for comp in composed_of:
            child_id = comp["marker_id"]
            weight = comp.get("weight", 1.0)
            weights_map[child_id] = weight
            needed_ids.append(child_id)
        
        max_span_sentences = span_policy.get("max_sentence_span", 1)
        
        # Check each sentence window
        for i0 in range(len(sentences)):
            # Try different window sizes
            for window_size in range(1, max_span_sentences + 1):
                iR = min(len(sentences) - 1, i0 + window_size - 1)
                
                # Count markers in this window
                window_atomics = []
                for k in range(i0, iR + 1):
                    window_atomics.extend(per_sent[k])
                
                # Build environment for activation formula
                counts = {marker_id: 0 for marker_id in needed_ids}
                for atomic in window_atomics:
                    if atomic["marker_id"] in counts:
                        counts[atomic["marker_id"]] += 1
                
                counts["total_children"] = sum(counts.values())
                
                # Skip if no relevant children
                if counts["total_children"] == 0:
                    continue
                
                # Evaluate activation formula
                if eval_activation(activation_expr, counts):
                    # Calculate score based on present weights
                    present_weight = sum(weights_map[k] for k, v in counts.items() 
                                       if k in weights_map and v > 0)
                    total_weight = sum(weights_map.values()) or 1.0
                    score = present_weight / total_weight
                    
                    # Determine span based on policy
                    window_start = sentences[i0][0]
                    window_end = sentences[iR][1]
                    final_start, final_end = apply_span_policy(
                        span_policy, text, sentences, window_start, window_end
                    )
                    
                    # Extract family from marker ID
                    family = marker_id.split("_", 1)[0].upper()
                    
                    composed_annotations.append({
                        "marker_id": marker_id,
                        "family": family,
                        "start": final_start,
                        "end": final_end,
                        "score": round(score, 3)
                    })
                    
                    # Only create one annotation per starting sentence per marker
                    break
    
    return composed_annotations


# -------- Overlap resolution with family priority --------
FAMILY_ORDER = {"SEM": 0, "CLU": 1, "ATO": 2, "MEMA": 3, "DEESC": 4}


def resolve_overlaps(anns: List[dict], weights: dict) -> List[dict]:
    """Resolve overlapping annotations with family and score priority"""
    # Sort by position first
    anns = sorted(anns, key=lambda a: (a["start"], -(a["end"] - a["start"])))
    
    kept = []
    for current in anns:
        should_drop = False
        
        for j, existing in enumerate(kept):
            # Check for overlap
            if not (current["end"] <= existing["start"] or current["start"] >= existing["end"]):
                # Determine priority
                cur_family_rank = FAMILY_ORDER.get(current["family"], 9)
                existing_family_rank = FAMILY_ORDER.get(existing["family"], 9)
                
                # Priority rules:
                # 1. Family rank (SEM > CLU > ATO > MEMA)
                # 2. Score (higher wins)
                # 3. Length (longer wins)
                if (cur_family_rank < existing_family_rank or
                    (cur_family_rank == existing_family_rank and 
                     current.get("score", 0) > existing.get("score", 0)) or
                    (cur_family_rank == existing_family_rank and 
                     current.get("score", 0) == existing.get("score", 0) and
                     (current["end"] - current["start"]) > (existing["end"] - existing["start"]))):
                    # Current wins, replace existing
                    kept[j] = current
                    should_drop = True
                    break
                else:
                    # Existing wins, drop current
                    should_drop = True
                    break
        
        if not should_drop:
            kept.append(current)
    
    return kept


# -------- Public API --------
def analyze_text(text: str, resources_dir: Path) -> dict:
    """Main entry point for semantic text analysis"""
    # Load canonical definitions
    canon = Canon.from_files(resources_dir)
    
    # Load supporting files
    try:
        promotion = load_json(resources_dir / "promotion_mapping.ld35.json")
    except:
        promotion = {}
        
    try:
        weights = load_json(resources_dir / "weights.ld35.json")
    except:
        weights = {}
    
    # Compile regex patterns
    rx_index = compile_atomic_regex(canon)
    
    # Detect atomic markers
    atomic_annotations = detect_atomics(text, rx_index)
    
    # Detect composed markers
    composed_annotations = compose(text, canon, atomic_annotations, promotion, weights)
    
    # Resolve overlaps
    all_annotations = atomic_annotations + composed_annotations
    final_annotations = resolve_overlaps(all_annotations, weights)
    
    return {
        "text": text,
        "annotations": final_annotations,
        "metadata": {
            "atomic_count": len(atomic_annotations),
            "composed_count": len(composed_annotations),
            "final_count": len(final_annotations)
        }
    }


def sha256(text: str) -> str:
    """Calculate SHA256 hash of text"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()