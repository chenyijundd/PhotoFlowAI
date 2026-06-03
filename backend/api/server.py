"""
PhotoFlow AI - Backend API Server

FastAPI server that provides REST API for the Electron frontend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .photo_service import router as photo_router
from .detail_service import router as detail_router
from .ai_service import router as ai_router
from .burst_service import router as burst_router
from backend.importer.import_service import router as import_router
from .export_service import router as export_router
from database.connection import init_database, close_all_pools
from backend.logging_config import setup_all_logging

# Initialize rotating log handlers
setup_all_logging()

# Ensure database and schema exist at startup
init_database()

app = FastAPI(title="PhotoFlow AI Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(photo_router)
app.include_router(detail_router)
app.include_router(ai_router)
app.include_router(burst_router)
app.include_router(import_router)
app.include_router(export_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/status")
async def get_status():
    return {
        "status": "running",
        "modules": {
            "image_loader": "ready",
            "thumbnail_cache": "ready",
            "blur_detection": "ready",
            "eye_detection": "ready",
            "duplicate_detection": "ready",
            "scoring": "ready",
            "export": "ready",
        },
    }


@app.on_event("shutdown")
async def shutdown_db_pools():
    """Close all pooled database connections on server shutdown."""
    close_all_pools()


def start_server(host: str = "127.0.0.1", port: int = 8765):
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
