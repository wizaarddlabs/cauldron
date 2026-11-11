import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.api.stremio import router as stremio_router
from app.cache.store import get_cache_backend_status, get_cache_stats
from app.config import get_settings
from app.http_client import close_http_client
from app.logging_utils import install_redaction_filter
from app.web.routes import router as web_router

settings = get_settings()

logging.basicConfig(level=settings.log_level)
install_redaction_filter()

logger = logging.getLogger(__name__)

DESCRIPTION = "Open-source torrent search + debrid resolution service."


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_http_client()


app = FastAPI(
    title=settings.addon_name,
    version=settings.addon_version,
    description=DESCRIPTION,
    lifespan=lifespan,
)


# ==================================================
# MANIFEST (Stremio addon) - must be first
# ==================================================

@app.get("/manifest.json")
async def manifest():
    response = {
        "id": settings.addon_id,
        "version": settings.addon_version,
        "name": settings.addon_name,
        "description": DESCRIPTION,
        "types": ["movie", "series"],
        "catalogs": [],
        "resources": ["stream"],
        "background": f"{settings.addon_url}/static/cauldron.png",
        "logo": f"{settings.addon_url}/static/cauldron.png",
    }
    logger.debug("Manifest response: %s", response)
    return response


# ==================================================
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ==================================================
# ROUTES
# ==================================================

app.include_router(web_router)
app.include_router(api_router)
app.include_router(stremio_router)


# ==================================================
# STATIC FILES
# ==================================================

STATIC_DIR = Path(__file__).parent / "web" / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ==================================================
# HEALTH
# ==================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": settings.addon_version,
    }


@app.get("/ready")
async def ready():
    cache_backend = await get_cache_backend_status()

    if cache_backend == "unavailable":
        raise HTTPException(
            status_code=503,
            detail="Configured Redis cache is unavailable",
        )

    return {
        "status": "ready",
        "version": settings.addon_version,
        "cache_backend": cache_backend,
    }


# ==================================================
# STATUS
# ==================================================

@app.get("/api/status")
async def status():
    cache_backend = await get_cache_backend_status()

    return {
        "api": "online",
        "redis": "online" if cache_backend == "redis" else "offline",
        "cache_backend": cache_backend,
        "debrid": "ready",
        "cache": get_cache_stats(),
    }
