import secrets

from fastapi import HTTPException

from app.config import get_settings


def require_admin_api_key(supplied_key: str | None) -> None:
    configured_key = get_settings().admin_api_key

    if not configured_key:
        raise HTTPException(
            status_code=503,
            detail="Shared settings writes are disabled; configure ADMIN_API_KEY",
        )

    if not supplied_key or not secrets.compare_digest(
        supplied_key,
        configured_key,
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid admin API key",
        )
