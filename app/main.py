import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.api.stremio import router as stremio_router
from app.config import get_settings

settings = get_settings()

logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title=settings.addon_name,
    version=settings.addon_version,
    description="Open-source torrent search + debrid resolution service.",
)

# Stremio's client fetches addon URLs directly from the browser/app, so CORS
# needs to be open for the manifest/stream endpoints to work.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(stremio_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.addon_version}
