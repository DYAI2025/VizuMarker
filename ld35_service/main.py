from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .api.v1.api import router as v1_router
from .core.config import settings

app = FastAPI(
    title="LD35 Service",
    description="VizuMarker - Automatic marker detection for large texts",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=settings.ALLOWED_ORIGIN_REGEX,
)

# Include API routes (authentication will be handled at the endpoint level)
app.include_router(v1_router, prefix="/api/v1")

# Serve the static frontend if available
frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "public"
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

@app.get("/")
def read_root():
    return {"message": "VizuMarker LD35 Service", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
