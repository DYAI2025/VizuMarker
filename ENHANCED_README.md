# VizuMarker LD3.5 - Enhanced Semantic Analysis

## 🚀 What's New in This Update

VizuMarker has been significantly enhanced with the **LD3.5 semantic engine** that moves beyond simple regex word triggers to provide true semantic understanding through:

### Key Improvements

1. **🧠 Composed Markers with Activation Formulas**

   - SEM/CLU/MEMA markers now use logical activation rules
   - Example: `SEM_EVIDENCE_PHRASE >= 1 && total_children >= 2`
   - More heuristic pattern detection instead of just regex hits

2. **📖 Sentence-Level Spans**

   - Markers now span entire sentences or clauses, not just individual words
   - Policy-driven span expansion: `sentence_union`, `clause_union`, `anchor_window`
   - Better contextual understanding

3. **🎯 Smart Overlap Resolution**

   - Family-based priority: SEM > CLU > ATO > MEMA
   - Score-based conflict resolution
   - Composed markers preferred over atomic ones

4. **⚡ Enhanced Processing Pipeline**
   - Atomic detection → Composition → Overlap resolution
   - Configurable thresholds and weights
   - Batch processing capabilities

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    VizuMarker LD3.5                       │
├─────────────────────────────────────────────────────────────┤
│  Frontend                                                   │
│  ├── semantic-demo.html (Interactive Demo)                 │
│  └── ld35-semantic-viewer.js (Enhanced Viewer)             │
├─────────────────────────────────────────────────────────────┤
│  API Layer                                                  │
│  ├── /annotate (Enhanced with semantic engine)             │
│  ├── /annotate-semantic (Direct semantic endpoint)         │
│  └── /annotate-batch-files (Bulk processing)               │
├─────────────────────────────────────────────────────────────┤
│  Semantic Engine Core                                       │
│  ├── sem_core.py (New semantic processing engine)          │
│  ├── Sentence boundary detection                           │
│  ├── Atomic marker detection                               │
│  ├── Composition with activation formulas                  │
│  └── Overlap resolution with priorities                    │
├─────────────────────────────────────────────────────────────┤
│  Configuration                                              │
│  ├── markers_canonical.ld35.json (Marker definitions)      │
│  ├── promotion_mapping.ld35.json (Promotion rules)         │
│  └── weights.ld35.json (Scoring configuration)             │
├─────────────────────────────────────────────────────────────┤
│  CLI Tools                                                  │
│  └── cli_batch.py (Batch processing CLI)                   │
└─────────────────────────────────────────────────────────────┘
```

## 🛠️ Installation & Usage

### 1. Start the Service

```bash
cd /home/dyai/Dokumente/DYAI_home/DEV/TOOLS/VizuMarker
python -m uvicorn ld35_service.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Try the Interactive Demo

Open in browser: `http://localhost:8000/app/semantic-demo.html`

### 3. API Usage

#### Direct Semantic Analysis

```bash
curl -X POST "http://localhost:8000/api/v1/annotation/annotate-semantic" \
  -H "Content-Type: application/json" \
  -d '{"text": "Du bildest dir das nur ein. Das war nicht so gemeint."}'
```

#### Batch File Processing

```bash
curl -X POST "http://localhost:8000/api/v1/annotation/annotate-batch-files" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "files=@document1.txt" \
  -F "files=@document2.txt"
```

### 4. CLI Batch Processing

```bash
# Process all .txt and .md files in a directory
python -m ld35_service.cli_batch input_texts/ output_annotations/

# With custom resources
python -m ld35_service.cli_batch input_texts/ output_annotations/ --resources custom_resources/
```

## 📋 Configuration

### Marker Definitions (`markers_canonical.ld35.json`)

Enhanced marker definitions with composed markers:

```json
{
  "id": "SEM_GASLIGHTING_PATTERN",
  "family": "SEM",
  "kind": "composed",
  "composed_of": [
    { "marker_id": "ATO_GASLIGHTING_TERM", "weight": 1.0 },
    { "marker_id": "SEM_EVIDENCE_PHRASE", "weight": 0.7 }
  ],
  "activation": "ATO_GASLIGHTING_TERM >= 1 && total_children >= 1",
  "span_policy": { "mode": "sentence_union", "max_sentence_span": 2 },
  "severity": 0.8
}
```

### Weights Configuration (`weights.ld35.json`)

```json
{
  "composed": {
    "min_score": 0.65,
    "activation_threshold": 0.6
  },
  "overlap_resolver": {
    "prefer_family": ["SEM", "CLU", "ATO", "MEMA"],
    "prefer_composed_over_atomic": true
  },
  "families": {
    "SEM": { "priority": 1, "min_score": 0.65 },
    "CLU": { "priority": 2, "min_score": 0.6 }
  }
}
```

## 🎨 Frontend Integration

### Basic Usage

```html
<div id="viewer"></div>
<script src="ld35-semantic-viewer.js"></script>
<script>
  const viewer = new LD35SemanticViewer("viewer");
  viewer.renderFromApi("Your text to analyze");
</script>
```

### Advanced Configuration

```javascript
const viewer = new LD35SemanticViewer("viewer", {
  showMetadata: true,
  highlightSentences: true,
  showFamilyColors: true,
  showScores: true,
});

// Listen for annotation clicks
document.getElementById("viewer").addEventListener("annotationClick", (e) => {
  console.log("Clicked:", e.detail);
});
```

## 🔍 Example Analysis

**Input Text:**

> "Du bildest dir das nur ein. Das habe ich nie gesagt. Du musst das beweisen können."

**Analysis Result:**

```json
{
  "annotations": [
    {
      "marker_id": "ATO_GASLIGHTING_TERM",
      "family": "ATO",
      "start": 0,
      "end": 27,
      "score": 0.7
    },
    {
      "marker_id": "SEM_GASLIGHTING_PATTERN",
      "family": "SEM",
      "start": 0,
      "end": 89,
      "score": 0.8
    }
  ],
  "metadata": {
    "atomic_count": 2,
    "composed_count": 1,
    "final_count": 2
  }
}
```

## 🚦 Output Format

### .ann.json Format

```json
{
  "source": "document.txt",
  "text_sha256": "abc123...",
  "annotations": [
    {
      "marker_id": "SEM_BEWEISLAST_VERSCHIEBUNG",
      "family": "SEM",
      "start": 45,
      "end": 128,
      "score": 0.74
    }
  ],
  "metadata": {
    "atomic_count": 3,
    "composed_count": 1,
    "final_count": 2
  }
}
```

## ⚙️ Technical Details

### Activation Formula Syntax

- Logical operators: `&&` (AND), `||` (OR)
- Comparisons: `>=`, `<=`, `>`, `<`, `==`, `!=`
- Variables: marker IDs, `total_children`, `score`
- Example: `SEM_EVIDENCE_PHRASE >= 1 && (ATO_ACCUSATION >= 1 || total_children >= 2)`

### Span Policies

- **sentence_union**: Expand to cover complete sentences
- **clause_union**: Expand to comma/semicolon boundaries
- **anchor_window**: Token-based window around matches

### Priority Resolution

1. Family priority (SEM > CLU > ATO > MEMA)
2. Composed over atomic markers
3. Higher scores win
4. Longer spans win (if all else equal)

## 🔧 Development & Customization

### Adding New Markers

1. Add atomic markers to `markers_canonical.ld35.json`
2. Create composed markers with activation formulas
3. Configure weights and thresholds in `weights.ld35.json`
4. Test with the demo interface

### Custom Span Policies

Extend `apply_span_policy()` in `sem_core.py` for custom span logic.

### Custom Activation Logic

The activation evaluator supports safe Python expressions. Complex logic can be added while maintaining security.

## 📊 Performance Notes

- **Sentence-level spans**: More contextual but larger spans
- **Composed markers**: Higher accuracy but more computation
- **Overlap resolution**: Cleaner output but potential information loss
- **Batch processing**: Optimized for large document collections

## 🎯 Benefits Over Previous Version

| Aspect                    | Previous            | Enhanced LD3.5                       |
| ------------------------- | ------------------- | ------------------------------------ |
| **Pattern Detection**     | Regex word triggers | Semantic composition with activation |
| **Span Coverage**         | Word-level          | Sentence/clause-level                |
| **Context Understanding** | Limited             | Rich contextual analysis             |
| **Conflict Resolution**   | Basic overlap       | Smart family-priority resolution     |
| **Configurability**       | Fixed rules         | Policy-driven, configurable          |
| **Batch Processing**      | Manual              | Automated CLI + API                  |

## 🚀 Next Steps

This implementation provides a solid foundation for semantic text analysis. The enhanced engine can be further extended with:

- Machine learning integration for pattern refinement
- Multi-language support
- Real-time streaming analysis
- Custom domain adaptations
- Performance optimizations for large-scale deployment

---

The enhanced VizuMarker LD3.5 transforms regex-based pattern matching into true semantic understanding, making it more suitable for serious text analysis applications while maintaining the flexibility and configurability that made the original successful.
