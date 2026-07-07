"""Korean news site adapters (Groups A + B + partial C: 11 sites).

Group A — Korean Major Dailies (5):
    chosun.com, joongang.co.kr, donga.com, hani.co.kr, yna.co.kr.

Group B — Korean Economy (4):
    mk.co.kr, hankyung.com, fnnews.com, mt.co.kr.

Group C — Korean Niche (2 of 3 in this package):
    nocutnews.co.kr, kmib.co.kr.
    Note: ohmynews.com (also Group C) is in the kr_tech package
    due to its IT/niche editorial focus.

All adapters use RSS as primary discovery method with KR proxy required.
Selectors verified against Step 6 crawling strategies.
"""

from src.crawling.adapters.kr_major.chosun import ChosunAdapter
from src.crawling.adapters.kr_major.joongang import JoongAngAdapter
from src.crawling.adapters.kr_major.donga import DongaAdapter
from src.crawling.adapters.kr_major.hani import HaniAdapter
from src.crawling.adapters.kr_major.yna import YnaAdapter
from src.crawling.adapters.kr_major.mk import MkAdapter
from src.crawling.adapters.kr_major.hankyung import HankyungAdapter
from src.crawling.adapters.kr_major.fnnews import FnnewsAdapter
from src.crawling.adapters.kr_major.mt import MtAdapter
from src.crawling.adapters.kr_major.nocutnews import NocutNewsAdapter
from src.crawling.adapters.kr_major.kmib import KmibAdapter

__all__ = [
    # Group A — Korean Major Dailies
    "ChosunAdapter",
    "JoongAngAdapter",
    "DongaAdapter",
    "HaniAdapter",
    "YnaAdapter",
    # Group B — Korean Economy
    "MkAdapter",
    "HankyungAdapter",
    "FnnewsAdapter",
    "MtAdapter",
    # Group C — Korean Niche
    "NocutNewsAdapter",
    "KmibAdapter",
]

# Registry mapping source_id -> adapter class for dynamic loading
ADAPTER_REGISTRY: dict[str, type] = {
    "chosun": ChosunAdapter,
    "joongang": JoongAngAdapter,
    "donga": DongaAdapter,
    "hani": HaniAdapter,
    "yna": YnaAdapter,
    "mk": MkAdapter,
    "hankyung": HankyungAdapter,
    "fnnews": FnnewsAdapter,
    "mt": MtAdapter,
    "nocutnews": NocutNewsAdapter,
    "kmib": KmibAdapter,
}


def get_adapter(source_id: str) -> type | None:
    """Look up an adapter class by source_id.

    Args:
        source_id: Site identifier matching sources.yaml key.

    Returns:
        Adapter class, or None if source_id is not in this group.
    """
    return ADAPTER_REGISTRY.get(source_id)
