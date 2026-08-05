import logging
import socket
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.api.stremio import router as stremio_router
from app.web.routes import router as web_router

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
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
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
# ROUTES
# ==================================================

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

        "redis": "offline",

        "jackett": "offline",

        "debrid": "ready"

    }



    try:

        socket.gethostbyname(
            "redis"
        )

        services["redis"] = "online"


    except Exception:

        pass



    try:

        socket.gethostbyname(
            "jackett"
        )

        services["jackett"] = "online"


    except Exception:

        pass



    return services
