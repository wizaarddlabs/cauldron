import hashlib
from functools import cache
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.api.debrid_accounts import PROVIDER_LABELS, STREAM_MODE_BEST, STREAM_MODES
from app.config import get_settings
from app.config_store import save_config
from app.ranking.preferences import RankingPreferences
from app.ranking.store import (
    load_preferences,
    save_preferences,
)
from app.security import require_admin_api_key

router = APIRouter(tags=["web"])

templates = Jinja2Templates(
    directory=Path(__file__).parent / "templates"
)

STATIC_DIR = Path(__file__).parent / "static"


@cache
def _asset_hash(name: str) -> str:
    """Short content hash of a static file, computed once per process."""
    try:
        return hashlib.sha256((STATIC_DIR / name).read_bytes()).hexdigest()[:10]
    except OSError:
        return "missing"


def asset_url(name: str) -> str:
    """
    URL of a static asset that changes whenever the file's content does.

    A hand-maintained ?v= number was forgotten in v0.7.0, so browsers kept
    running the cached v0.6.0 settings.js and the new "Add another provider"
    button did nothing.
    """
    return f"/static/{name}?v={_asset_hash(name)}"


templates.env.globals["asset_url"] = asset_url


# =========================================================
# DEBRID PROVIDER SELECTION
# =========================================================

# Shown in this order in the provider dropdowns.
DEBRID_PROVIDERS: list[tuple[str, str]] = list(PROVIDER_LABELS.items())

# Stored as the provider for configs that stream torrents directly.
P2P_PROVIDER = "p2p"

# Older form / API clients send one field per provider; the first non-empty
# one wins, matching the previous behaviour.
_LEGACY_KEY_FIELDS = [f"{value}_key" for value, _ in DEBRID_PROVIDERS]


def _resolve_debrid_choice(
    form,
) -> tuple[list[tuple[str, str]], list[str], str | None]:
    """
    Return (accounts, chosen_providers, error) from the submitted form.

    ``accounts`` is the (provider, api_key) list in priority order; empty
    means direct P2P streams. ``chosen_providers`` (no keys) is used to
    re-show the form after an error. A provider without a key is an error
    rather than a silent fallback to P2P.
    """

    if "provider" not in form:
        for field in _LEGACY_KEY_FIELDS:
            key = (form.get(field) or "").strip()
            if key:
                provider = field.removesuffix("_key")
                return [(provider, key)], [provider], None

        return [], [], None

    providers = form.getlist("provider")
    keys = form.getlist("api_key")

    accounts: list[tuple[str, str]] = []
    chosen: list[str] = []
    error: str | None = None

    for index, raw_provider in enumerate(providers):
        provider = (raw_provider or "").strip().lower()
        api_key = (keys[index] if index < len(keys) else "").strip()

        if provider in ("", P2P_PROVIDER):
            continue

        if provider not in PROVIDER_LABELS:
            error = error or "Unknown debrid provider."
            continue

        if provider in chosen:
            error = error or f"{PROVIDER_LABELS[provider]} is listed more than once."
            continue

        chosen.append(provider)

        if not api_key:
            error = error or (
                f"Enter your {PROVIDER_LABELS[provider]} API key, "
                "or remove that provider."
            )
            continue

        accounts.append((provider, api_key))

    return accounts, chosen, error


def _render_settings(
    request: Request,
    prefs,
    *,
    manifest: str | None = None,
    error: str | None = None,
    chosen_providers: list[str] | None = None,
    stream_mode: str = STREAM_MODE_BEST,
    status_code: int = 200,
) -> Response:
    response = templates.TemplateResponse(
        request,
        "settings.html",
        {
            "prefs": prefs,
            "settings": get_settings(),
            "manifest": manifest,
            "stremio_install_url": (
                "stremio://" + manifest.split("://", 1)[-1] if manifest else None
            ),
            "error": error,
            "providers": DEBRID_PROVIDERS,
            "provider_labels": PROVIDER_LABELS,
            # At least one row; an empty first row means P2P.
            "provider_rows": chosen_providers or [""],
            "stream_mode": stream_mode,
        },
        status_code=status_code,
    )

    # The page may contain a manifest URL, which grants use of the owner's
    # debrid account: keep it out of shared caches and the back/forward cache.
    response.headers["Cache-Control"] = "no-store"

    return response


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

    return _render_settings(
        request,
        load_preferences(),
    )


# =========================================================
# SAVE SETTINGS
# =========================================================

@router.post("/settings")
async def update_settings(request: Request):
    form = await request.form()
    require_admin_api_key(
        request.headers.get("x-admin-api-key")
        or form.get("admin_api_key")
    )

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

@router.get("/configure")
async def configure():
    # Stremio's "Configure" button opens <addon>/configure.
    return RedirectResponse("/", status_code=307)


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

    accounts, chosen_providers, error = _resolve_debrid_choice(form)

    stream_mode = form.get("stream_mode", STREAM_MODE_BEST)
    if stream_mode not in STREAM_MODES:
        stream_mode = STREAM_MODE_BEST

    config = {

        # -------------------------------------------------
        # DEBRID PROVIDER
        # -------------------------------------------------

        # All debrid accounts, in priority order (empty: direct P2P).
        "providers": [
            {"provider": provider, "api_key": key}
            for provider, key in accounts
        ],

        "stream_mode":
            stream_mode,

        # The first account again, in the single-provider fields older
        # Cauldron versions read, so a rollback keeps working.
        "provider":
            accounts[0][0] if accounts else P2P_PROVIDER,

        "api_key":
            accounts[0][1] if accounts else None,

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

    if error:
        # Re-show the form with the user's selections, minus any key.
        return _render_settings(
            request,
            {**config, "api_key": None, "providers": []},
            error=error,
            chosen_providers=chosen_providers,
            stream_mode=stream_mode,
            status_code=400,
        )

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

    # Rendered directly (not redirected to /?manifest=...) so the manifest
    # URL, which works like a password, stays out of browser history.
    return _render_settings(
        request,
        config,
        manifest=manifest_url,
        chosen_providers=[provider for provider, _ in accounts],
        stream_mode=stream_mode,
    )
