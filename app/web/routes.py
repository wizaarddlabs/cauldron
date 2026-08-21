from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.ranking.store import (
    load_preferences,
    save_preferences,
)
from app.ranking.preferences import RankingPreferences

from app.config import get_settings
from app.config_store import save_config


router = APIRouter(tags=["web"])

templates = Jinja2Templates(
    directory="app/web/templates"
)


# =========================================================
# SORTING HELPERS
# =========================================================

def _parse_sort_criteria(value):
    """
    Normalize sort criteria from the web form.

    The frontend stores the ordering as a comma-separated
    string, e.g.:

        cached,resolution,quality,seeders

    This also safely handles older/malformed configs such as:

        ["cached,resolution,quality,seeders"]
    """

    if isinstance(value, str):
        return [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

    if isinstance(value, list):
        criteria = []

        for item in value:
            if isinstance(item, str):
                criteria.extend(
                    part.strip()
                    for part in item.split(",")
                    if part.strip()
                )

        return criteria

    return []


def _get_sort_criteria(form):
    """
    Get normalized sorting criteria from a submitted form.
    """

    criteria = _parse_sort_criteria(
        form.get("sort_criteria", "")
    )

    if not criteria:
        criteria = [
            "cached",
            "seeders",
            "resolution",
            "quality",
        ]

    return criteria


# =========================================================
# MANIFEST
# =========================================================

@router.get("/manifest.json")
async def manifest():
    from app.config import get_settings

    settings = get_settings()

    return {
        "id": settings.addon_id,
        "version": settings.addon_version,
        "name": settings.addon_name,
        "description": "Open-source torrent search + debrid resolution service.",
        "types": ["movie", "series"],
        "catalogs": [],
        "resources": ["stream"],
        "idPrefixes": ["tt", "k2"],
        "background": f"{settings.addon_url}/static/cauldron.png",
        "logo": f"{settings.addon_url}/static/cauldron.png",
    }


@router.get("/{config_id}/manifest.json")
async def config_manifest(config_id: str):
    from app.config import get_settings

    settings = get_settings()

    return {
        "id": settings.addon_id,
        "version": settings.addon_version,
        "name": settings.addon_name,
        "description": "Open-source torrent search + debrid resolution service.",
        "types": ["movie", "series"],
        "catalogs": [],
        "resources": ["stream"],
        "idPrefixes": ["tt", "k2"],
        "background": f"{settings.addon_url}/static/cauldron.png",
        "logo": f"{settings.addon_url}/static/cauldron.png",
    }


# =========================================================
# HOME / SETTINGS PAGE
# =========================================================

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):

    prefs = load_preferences()
    settings = get_settings()

    manifest = request.query_params.get(
        "manifest"
    )

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "prefs": prefs,
            "settings": settings,
            "manifest": manifest,
        },
    )


# =========================================================
# SAVE SETTINGS
# =========================================================

@router.post("/settings")
async def update_settings(request: Request):

    form = await request.form()

    sort_criteria = _get_sort_criteria(
        form
    )

    prefs = {

        "resolution": form.getlist(
            "resolution"
        ),

        "language": form.getlist(
            "language"
        ),

        "audio": form.get(
            "audio",
            "any",
        ),

        "quality_profile": form.get(
            "quality_profile",
            "balanced",
        ),

        "codec": form.getlist(
            "codec"
        ),

        "sort_mode": form.get(
            "sort_mode",
            "balanced",
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

        "prefer_atmos":
            "prefer_atmos" in form,

        "allow_cam":
            "allow_cam" in form,

        "allow_season_packs":
            "allow_season_packs" in form,

        "min_seeders":
            int(
                form.get(
                    "min_seeders",
                    0,
                )
            ),

        "seeder_weight":
            float(
                form.get(
                    "seeder_weight",
                    1,
                )
            ),

        # IMPORTANT:
        # Always store this as a normalized list.
        "sort_criteria":
            sort_criteria,

        "sort_order":
            form.get(
                "sort_order",
                "desc",
            ),
    }

    save_preferences(
        RankingPreferences(
            **prefs
        )
    )

    return RedirectResponse(
        "/",
        status_code=303,
    )


# =========================================================
# CONFIGURE PAGE
# =========================================================

@router.get(
    "/configure",
    response_class=HTMLResponse,
)
async def configure(request: Request):

    settings = get_settings()

    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "settings": settings,
        },
    )


# =========================================================
# GENERATE STREMIO CONFIG
# =========================================================

@router.post("/generate")
async def generate_manifest(
    request: Request,
):

    form = await request.form()

    sort_criteria = _get_sort_criteria(
        form
    )

    config = {

        # -------------------------------------------------
        # DEBRID PROVIDER
        # -------------------------------------------------

        "provider":
            (
                "torrin"
                if form.get("torrin_key")
                else
                "torbox"
                if form.get("torbox_key")
                else
                "realdebrid"
                if form.get("realdebrid_key")
                else
                "alldebrid"
                if form.get("alldebrid_key")
                else
                "premiumize"
                if form.get("premiumize_key")
                else
                "offcloud"
                if form.get("offcloud_key")
                else
                "premiumize"
            ),

        "api_key":
            (
                form.get("torrin_key")
                or
                form.get("torbox_key")
                or
                form.get("realdebrid_key")
                or
                form.get("alldebrid_key")
                or
                form.get("premiumize_key")
                or
                form.get("offcloud_key")
            ),

        # -------------------------------------------------
        # BASIC
        # -------------------------------------------------

        "addon_name":
            form.get(
                "addon_name",
                "Cauldron",
            ),

        # -------------------------------------------------
        # FILTERING
        # -------------------------------------------------

        "resolution":
            form.getlist(
                "resolution"
            ),

        "language":
            form.getlist(
                "language"
            ),

        "required_languages":
            form.getlist(
                "required_languages"
            ),

        "preferred_languages":
            form.getlist(
                "preferred_languages"
            ),

        "excluded_languages":
            form.getlist(
                "excluded_languages"
            ),

        "filters":
            form.getlist(
                "filters"
            ),

        "min_seeders":
            int(
                form.get(
                    "min_seeders",
                    0,
                )
                or 0
            ),

        "codec":
            form.getlist(
                "codec"
            ),

        "custom_patterns":
            form.get(
                "custom_patterns",
                "",
            ),

        # -------------------------------------------------
        # QUALITY PREFERENCES
        # -------------------------------------------------

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

        "prefer_atmos":
            "prefer_atmos" in form,

        "allow_cam":
            "allow_cam" in form,

        "allow_season_packs":
            "allow_season_packs" in form,

        "seeder_weight":
            float(
                form.get(
                    "seeder_weight",
                    1,
                )
                or 1
            ),

        # -------------------------------------------------
        # CACHE / STREAM OPTIONS
        # -------------------------------------------------

        "cached_only":
            "cached_only" in form,

        "dedupe_streams":
            "dedupe_streams" in form,

        "max_per_resolution":
            int(
                form.get(
                    "max_per_resolution",
                    0,
                )
                or 0
            ),

        "max_size_gb":
            float(
                form.get(
                    "max_size_gb",
                    0,
                )
                or 0
            ),

        # -------------------------------------------------
        # USER-CONFIGURABLE SORTING
        # -------------------------------------------------

        # IMPORTANT:
        # Store normalized criteria as a list.
        #
        # Example:
        #
        # [
        #     "cached",
        #     "resolution",
        #     "quality",
        #     "seeders",
        # ]
        #
        "sort_criteria":
            sort_criteria,

        "sort_order":
            form.get(
                "sort_order",
                "desc",
            ),
    }

    config_id = save_config(
        config
    )

    # -----------------------------------------------------
    # EXTERNAL MANIFEST URL
    # -----------------------------------------------------

    scheme = request.headers.get(
        "x-forwarded-proto",
        "https",
    )

    host = request.headers.get(
        "host"
    )

    manifest_url = (
        f"{scheme}://{host}/{config_id}/manifest.json"
    )

    return RedirectResponse(
        f"/?manifest={manifest_url}",
        status_code=303,
    )