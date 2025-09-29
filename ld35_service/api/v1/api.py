from fastapi import APIRouter
from .annotation import router as annotation_router
from .render import router as render_router
from .export import router as export_router

router = APIRouter()

# Include all API routes
router.include_router(annotation_router, prefix="/annotation", tags=["annotation"])
router.include_router(render_router, prefix="/render", tags=["render"])
router.include_router(export_router, prefix="/export", tags=["export"])