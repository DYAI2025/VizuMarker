# VizuMarker

VizuMarker is an automatic marker detection system (LD-3.5) designed for processing large texts (multiple MB). It provides visual representation of detected spans with color coding, family/marker legends, and supports multiple export formats for training and sharing.

## Features

- **Automatic Marker Detection**: Utilizes LD-3.5 engine for detecting markers in large texts
- **Visual Representation**: Color-coded spans with family/marker legends 
- **Multiple Export Formats**: AXF-JSON, HTML, BIO-TSV, Markdown, PDF
- **Scalability & Robustness**: Chunking, streaming, background jobs, clean offsets
- **Performance**: Server-side rendering for large texts, client-side for smaller ones

## Architecture

### Backend Services

1. **Detection Service** (Python FastAPI)
   - `POST /annotate` - Process single document
   - `POST /annotate-batch` - Process batch of documents
   - `GET /job/{id}` - Check job status and results

2. **Render Service** (Python FastAPI)
   - `POST /render` - Text + annotations → HTML with spans
   - `GET /render/{docId}.html/.pdf` - Retrieve artifacts

### Storage & Orchestration

- Document storage with original text, annotations, export formats
- Queue system for background processing (Celery/Redis)
- Blob storage for large files

### Frontend Viewer

- Client for visualizing marked documents
- Pagination for large texts
- Legend and filtering by family
- Export functionality

## Data Formats

### AXF-LD35 (Ground Truth)
```json
{
  "text": "...",
  "annotations": [
    {
      "start": 62,
      "end": 113,
      "marker": "SEM_ASSERTION",
      "family": "SEM",
      "label": "Behauptung",
      "score": 0.82,
      "meta": {"note":"..."}
    }
  ]
}
```

### HTML Format
```html
<span class="hl" data-fam="SEM" data-markers="SEM_ASSERTION|...">...</span>
```

### BIO-TSV Format
```
Token<TAB>B-SEM_ASSERTION
Token<TAB>I-...
Token<TAB>O
```

## Performance Design

- Client preview: up to ~200k characters (browser rendering)
- Server rendering: above ~200k characters with pagination
- Chunk size: 8k-16k characters with sentence/paragraph boundaries
- Streaming processing to avoid full text copies

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   poetry install
   ```
3. Set up environment variables (see `.env.example`)
4. Run the development server:
   ```bash
   poetry run dev
   ```
5. For a quick local start with the browser UI opened automatically you can instead run
   ```bash
   ./start_vizumarker.py
   ```
   which sets `DISABLE_AUTH=1` so requests work without tokens, opens the viewer at `http://127.0.0.1:8000/app/`, and prints the Swagger link.

6. The LD‑3.5 core combines canonical pattern spans with the upstream marker engine located under `ME_ENGINE_CORE_V0.9/CORE_MarkerEngine_V0.9`. If you keep the engine elsewhere, point `MARKER_ENGINE_PATH` to the folder that contains `_Marker_5.0`, `DETECT_`, and `plugins` before starting the service.
7. Marker rules override files live in `resources/`. Drop `markers_canonical.ld35.json`, `promotion_mapping.ld35.json`, and `weights.ld35.json` there (see the sample bundle we ship) to get composed SEM/CLU spans and promotion logic.

## Development

### Backend
The backend services are built with FastAPI and include:
- Annotation service with LD-3.5 engine integration
- Rendering service for HTML/PDF generation
- Queue workers for batch processing

### Frontend
The viewer is built to handle both client-side rendering for smaller texts and server-side rendered content for larger documents.

## Deployment

The service supports CORS and authentication with bearer tokens. For production deployment, use appropriate containerization and orchestration tools.

## Tests

Run tests with:
```bash
poetry run pytest
```

## License

MIT
