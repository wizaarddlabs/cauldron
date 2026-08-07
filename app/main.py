import logging
import socket
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import router as api_router
from app.api.stremio import router as stremio_router
from app.web.routes import router as web_router
from app.cache.store import get_cache_stats

from app.config import get_settings


settings = get_settings()


logging.basicConfig(
    level=settings.log_level
)


app = FastAPI(
    title=settings.addon_name,
    version=settings.addon_version,
    description="Open-source torrent search + debrid resolution service.",
)


# ==================================================
# MANIFEST (Stremio addon) - must be first
# ==================================================

@app.get("/manifest.json")
async def manifest():
    print("Manifest endpoint called", flush=True)
    response = {
        "id": settings.addon_id,
        "version": settings.addon_version,
        "name": settings.addon_name,
        "description": "Open-source torrent search + debrid resolution service.",
        "types": ["movie", "series"],
        "catalogs": [],
        "resources": ["stream"],
        "background": f"{settings.addon_url}/static/cauldron.png",
        "logo": f"{settings.addon_url}/static/cauldron.png"
    }
    print("Manifest response:", response, flush=True)
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

# Include routers - web router with manifest first
app.include_router(
    web_router
)

app.include_router(
    api_router
)

app.include_router(
    stremio_router
)



# ==================================================
# STATIC FILES
# ==================================================

WEB_DIR = Path(__file__).parent / "web"


STATIC_DIR = WEB_DIR / "static"


if STATIC_DIR.exists():

    app.mount(
        "/static",
        StaticFiles(
            directory=STATIC_DIR
        ),
        name="static"
    )



# ==================================================
# HEALTH
# ==================================================

@app.get("/health")
async def health():

    return {
        "status": "ok",
        "version": settings.addon_version
    }


# ==================================================
# STATUS
# ==================================================
@app.get("/api/status")
async def status():

    services = {

        "api": "online",

        "redis": "online" if settings.redis_url else "offline",

        "debrid": "ready"

    }

    # Add cache statistics
    services["cache"] = get_cache_stats()

    return services
