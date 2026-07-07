"""Site-specific crawling adapters for all 116 news sites.

Adapter hierarchy:
    base_adapter     - Abstract base adapter interface
    kr_major/        - Korean major dailies + economy + niche (Groups A+B+C: 11 adapters)
    kr_tech/         - Korean IT/science + tech (Groups C+D: 11 adapters)
    english/         - English-language (Group E: 22 adapters)
    multilingual/    - Asia-Pacific + Europe/ME + Africa + LatAm + Russia (Groups F-J: 77 adapters)

Usage:
    from src.crawling.adapters import get_adapter
    adapter = get_adapter("chosun")
    result = adapter.extract_article(html, url)
"""

from src.crawling.adapters.base_adapter import BaseSiteAdapter

# Import sub-package registries
from src.crawling.adapters.kr_major import ADAPTER_REGISTRY as _KR_MAJOR
from src.crawling.adapters.kr_tech import ADAPTER_REGISTRY as _KR_TECH
from src.crawling.adapters.english import ENGLISH_ADAPTERS as _ENGLISH
from src.crawling.adapters.multilingual import MULTILINGUAL_ADAPTERS as _MULTILINGUAL

# Master registry: site_id -> adapter class
ADAPTER_REGISTRY: dict[str, type[BaseSiteAdapter]] = {}
ADAPTER_REGISTRY.update(_KR_MAJOR)
ADAPTER_REGISTRY.update(_KR_TECH)
ADAPTER_REGISTRY.update(_ENGLISH)
ADAPTER_REGISTRY.update(_MULTILINGUAL)


def get_adapter(site_id: str) -> BaseSiteAdapter:
    """Get an adapter instance by site_id.

    Args:
        site_id: Site identifier matching sources.yaml key (e.g., "chosun").

    Returns:
        Instantiated adapter for the site.

    Raises:
        KeyError: If no adapter is registered for the given site_id.
    """
    cls = ADAPTER_REGISTRY.get(site_id)
    if cls is None:
        raise KeyError(
            f"No adapter registered for site_id={site_id!r}. "
            f"Available: {sorted(ADAPTER_REGISTRY.keys())}"
        )
    return cls()


def list_adapters() -> list[str]:
    """Return sorted list of all registered site_ids."""
    return sorted(ADAPTER_REGISTRY.keys())


__all__ = [
    "BaseSiteAdapter",
    "ADAPTER_REGISTRY",
    "get_adapter",
    "list_adapters",
]
