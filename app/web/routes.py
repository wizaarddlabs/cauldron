from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.ranking.preferences import (
    get_preferences,
    save_preferences
)

from app.config import get_settings
from app.config_store import save_config


router = APIRouter(tags=["web"])


templates = Jinja2Templates(
    directory="app/web/templates"
)


LAST_MANIFEST = None



@router.get("/", response_class=HTMLResponse)
async def home(request: Request):

    prefs = get_preferences()
    settings = get_settings()

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "prefs": prefs,
            "settings": settings,
            "manifest": LAST_MANIFEST
        }
    )



@router.post("/settings")
async def update_settings(request: Request):

    form = await request.form()

    prefs = {

        "resolution": form.getlist(
            "resolution"
        ),

        "language": form.getlist(
            "language"
        ),

        "audio": form.get(
            "audio",
            "any"
        ),

        "quality_profile": form.get(
            "quality_profile",
            "balanced"
        ),

        "codec": form.get(
            "codec",
            "any"
        ),

        "sort_mode": form.get(
            "sort_mode",
            "balanced"
        ),

        "prefer_4k":
            "prefer_4k" in form,

        "prefer_hdr":
            "prefer_hdr" in form,

        "prefer_dolby_vision":
            "prefer_dolby_vision" in form,

        "prefer_remux":
            "prefer_remux" in form,

        "prefer_hevc":
            "prefer_hevc" in form,

        "allow_cam":
            "allow_cam" in form,

        "min_seeders":
            int(form.get(
                "min_seeders",
                0
            )),

        "seeder_weight":
            float(form.get(
                "seeder_weight",
                1
            ))
    }


    save_preferences(
        prefs
    )


    return RedirectResponse(
        "/",
        status_code=303
    )



@router.post("/generate")
async def generate_manifest(request: Request):

    global LAST_MANIFEST


    form = await request.form()


    config = {

        "provider":
            (
                "torbox"
                if form.get("torbox_key")
                else
                "realdebrid"
                if form.get("realdebrid_key")
                else
                "premiumize"
            ),


        "api_key":
            (
                form.get("torbox_key")
                or
                form.get("realdebrid_key")
                or
                form.get("premiumize_key")
            ),


        "addon_name":
            form.get(
                "addon_name",
                "Cauldron"
            ),


        "jackett_url":
            form.get(
                "jackett_url",
                "http://jackett:9117"
            ),


        "jackett_api_key":
            form.get(
                "jackett_api_key",
                ""
            ),


        "resolution":
            form.getlist(
                "resolution"
            ),


        "language":
            form.getlist(
                "language"
            ),


        "filters":
            form.getlist(
                "filters"
            ),


        "cached_only":
            "cached_only" in form

    }


    config_id = save_config(
        config
    )


    # Build public HTTPS URL behind Nginx Proxy Manager
    scheme = request.headers.get(
        "x-forwarded-proto",
        "https"
    )

    host = request.headers.get(
        "host"
    )


    LAST_MANIFEST = (
        f"{scheme}://{host}/{config_id}/manifest.json"
    )


    return RedirectResponse(
        "/",
        status_code=303
    )
