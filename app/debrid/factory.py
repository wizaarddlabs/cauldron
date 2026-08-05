"""
Factory for instantiating the right debrid client from a provider name.
"""
from app.debrid.alldebrid import AllDebridClient
from app.debrid.base import DebridClient
from app.debrid.premiumize import PremiumizeClient
from app.debrid.realdebrid import RealDebridClient
from app.debrid.torbox import TorBoxClient
from app.models import DebridProvider

_REGISTRY: dict[DebridProvider, type[DebridClient]] = {
    DebridProvider.REAL_DEBRID: RealDebridClient,
    DebridProvider.ALLDEBRID: AllDebridClient,
    DebridProvider.PREMIUMIZE: PremiumizeClient,
    DebridProvider.TORBOX: TorBoxClient,
}


def get_debrid_client(provider: DebridProvider, api_key: str) -> DebridClient:
    cls = _REGISTRY.get(provider)
    if cls is None:
        raise ValueError(f"Unsupported debrid provider: {provider}")
    return cls(api_key)
