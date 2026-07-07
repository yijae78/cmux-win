"""English-language adapters (Group E: 22 sites).

Original 12: marketwatch, voakorea, huffpost, nytimes, ft, wsj,
             latimes, buzzfeed, nationalpost, cnn, bloomberg, afmedios

Added 10: wired, investing, qz, bbc, theguardian, thetimes,
           telegraph, politico_eu, euractiv, natureasia

Paywall classification:
    Hard paywall (title-only): nytimes, ft, wsj, bloomberg, thetimes, telegraph
    Soft-metered paywall:      marketwatch, latimes, nationalpost, wired
    No paywall:                voakorea, huffpost, buzzfeed, cnn, afmedios,
                               investing, qz, bbc, theguardian, politico_eu,
                               euractiv, natureasia
"""

from src.crawling.adapters.english.marketwatch import MarketWatchAdapter
from src.crawling.adapters.english.voakorea import VOAKoreaAdapter
from src.crawling.adapters.english.huffpost import HuffPostAdapter
from src.crawling.adapters.english.nytimes import NYTimesAdapter
from src.crawling.adapters.english.ft import FTAdapter
from src.crawling.adapters.english.wsj import WSJAdapter
from src.crawling.adapters.english.latimes import LATimesAdapter
from src.crawling.adapters.english.buzzfeed import BuzzFeedAdapter
from src.crawling.adapters.english.nationalpost import NationalPostAdapter
from src.crawling.adapters.english.cnn import CNNAdapter
from src.crawling.adapters.english.bloomberg import BloombergAdapter
from src.crawling.adapters.english.afmedios import AFMediosAdapter
from src.crawling.adapters.english.wired import WiredAdapter
from src.crawling.adapters.english.investing import InvestingAdapter
from src.crawling.adapters.english.qz import QuartzAdapter
from src.crawling.adapters.english.bbc import BBCAdapter
from src.crawling.adapters.english.theguardian import TheGuardianAdapter
from src.crawling.adapters.english.thetimes import TheTimesAdapter
from src.crawling.adapters.english.telegraph import TelegraphAdapter
from src.crawling.adapters.english.politico_eu import PoliticoEUAdapter
from src.crawling.adapters.english.euractiv import EuractivAdapter
from src.crawling.adapters.english.natureasia import NatureAsiaAdapter

__all__ = [
    "MarketWatchAdapter",
    "VOAKoreaAdapter",
    "HuffPostAdapter",
    "NYTimesAdapter",
    "FTAdapter",
    "WSJAdapter",
    "LATimesAdapter",
    "BuzzFeedAdapter",
    "NationalPostAdapter",
    "CNNAdapter",
    "BloombergAdapter",
    "AFMediosAdapter",
    "WiredAdapter",
    "InvestingAdapter",
    "QuartzAdapter",
    "BBCAdapter",
    "TheGuardianAdapter",
    "TheTimesAdapter",
    "TelegraphAdapter",
    "PoliticoEUAdapter",
    "EuractivAdapter",
    "NatureAsiaAdapter",
]

# Adapter registry mapping source_id -> adapter class
ENGLISH_ADAPTERS: dict[str, type] = {
    "marketwatch": MarketWatchAdapter,
    "voakorea": VOAKoreaAdapter,
    "huffpost": HuffPostAdapter,
    "nytimes": NYTimesAdapter,
    "ft": FTAdapter,
    "wsj": WSJAdapter,
    "latimes": LATimesAdapter,
    "buzzfeed": BuzzFeedAdapter,
    "nationalpost": NationalPostAdapter,
    "cnn": CNNAdapter,
    "bloomberg": BloombergAdapter,
    "afmedios": AFMediosAdapter,
    "wired": WiredAdapter,
    "investing": InvestingAdapter,
    "qz": QuartzAdapter,
    "bbc": BBCAdapter,
    "theguardian": TheGuardianAdapter,
    "thetimes": TheTimesAdapter,
    "telegraph": TelegraphAdapter,
    "politico_eu": PoliticoEUAdapter,
    "euractiv": EuractivAdapter,
    "natureasia": NatureAsiaAdapter,
}
