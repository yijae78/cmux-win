"""Korean IT/niche adapters (Groups C+D: 11 sites).

Sites:
    ohmynews     -- OhmyNews (citizen journalism, Group C)
    38north      -- 38 North (North Korea analysis, English, Group D)
    bloter       -- Bloter (IT/tech news, Group D)
    etnews       -- Electronic Times (electronics/IT industry, Group D)
    sciencetimes -- Science Times (science journalism, Group D)
    zdnet_kr     -- ZDNet Korea (enterprise IT, Group D)
    irobotnews   -- iRobot News (robotics industry, Group D)
    techneedle   -- TechNeedle (startup/tech blog, Group D)
    insight_kr   -- Insight Korea (viral content, Group D)
    stratechery  -- Stratechery (tech strategy analysis, Group D)
    techmeme     -- Techmeme (tech news aggregator, Group D)

Mix of RSS, Sitemap, and Playwright methods.
"""

from src.crawling.adapters.kr_tech.ohmynews import OhmynewsAdapter
from src.crawling.adapters.kr_tech.north38 import North38Adapter
from src.crawling.adapters.kr_tech.bloter import BloterAdapter
from src.crawling.adapters.kr_tech.etnews import EtnewsAdapter
from src.crawling.adapters.kr_tech.sciencetimes import SciencetimesAdapter
from src.crawling.adapters.kr_tech.zdnet_kr import ZdnetKrAdapter
from src.crawling.adapters.kr_tech.irobotnews import IrobotnewsAdapter
from src.crawling.adapters.kr_tech.techneedle import TechneedleAdapter
from src.crawling.adapters.kr_tech.insight_kr import InsightKrAdapter
from src.crawling.adapters.kr_tech.stratechery import StratecheryAdapter
from src.crawling.adapters.kr_tech.techmeme import TechmemeAdapter

__all__ = [
    "OhmynewsAdapter",
    "North38Adapter",
    "BloterAdapter",
    "EtnewsAdapter",
    "SciencetimesAdapter",
    "ZdnetKrAdapter",
    "IrobotnewsAdapter",
    "TechneedleAdapter",
    "InsightKrAdapter",
    "StratecheryAdapter",
    "TechmemeAdapter",
]

# Registry mapping source_id -> adapter class for dynamic loading
ADAPTER_REGISTRY: dict[str, type] = {
    "ohmynews": OhmynewsAdapter,
    "38north": North38Adapter,
    "bloter": BloterAdapter,
    "etnews": EtnewsAdapter,
    "sciencetimes": SciencetimesAdapter,
    "zdnet_kr": ZdnetKrAdapter,
    "irobotnews": IrobotnewsAdapter,
    "techneedle": TechneedleAdapter,
    "insight_kr": InsightKrAdapter,
    "stratechery": StratecheryAdapter,
    "techmeme": TechmemeAdapter,
}
