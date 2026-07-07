"""Multilingual adapters (Groups F-J: 77 sites).

Group F (Asia-Pacific):     people, globaltimes, scmp, taiwannews, yomiuri, thehindu,
                            mainichi, asahi, yahoo_jp, timesofindia, hindustantimes,
                            economictimes, indianexpress, philstar, manilatimes, inquirer,
                            jakartapost, antaranews, tempo_id, focustaiwan, taipeitimes,
                            vnexpress, vietnamnews
Group G (Europe/ME):        thesun, bild, lemonde, themoscowtimes, arabnews, aljazeera,
                            israelhayom, euronews, spiegel, sueddeutsche, welt, faz,
                            corriere, repubblica, ansa, elpais, elmundo, abc_es,
                            lavanguardia, lefigaro, liberation, france24, ouestfrance,
                            wyborcza, pap, idnes, intellinews, balkaninsight,
                            centraleuropeantimes, aftonbladet, tv2_no, yle, icelandmonitor,
                            middleeasteye, almonitor, haaretz, jpost, jordantimes
Group H (Africa):           allafrica, africanews, theafricareport, panapress
Group I (Latin America):    clarin, lanacion_ar, folha, oglobo, elmercurio, biobiochile,
                            eltiempo, elcomercio_pe
Group J (Russia/C.Asia):    gogo_mn, ria, rg, rbc

Languages: zh, ja, de, fr, en, es, it, pt, pl, cs, sv, no, ru, mn, hi, ar, he
"""

# --- Group F: Asia-Pacific (original 6) ---
from src.crawling.adapters.multilingual.people import PeopleAdapter
from src.crawling.adapters.multilingual.globaltimes import GlobalTimesAdapter
from src.crawling.adapters.multilingual.scmp import SCMPAdapter
from src.crawling.adapters.multilingual.taiwannews import TaiwanNewsAdapter
from src.crawling.adapters.multilingual.yomiuri import YomiuriAdapter
from src.crawling.adapters.multilingual.thehindu import TheHinduAdapter

# --- Group F: Asia-Pacific (new) ---
from src.crawling.adapters.multilingual.mainichi import MainichiAdapter
from src.crawling.adapters.multilingual.asahi import AsahiAdapter
from src.crawling.adapters.multilingual.yahoo_jp import YahooJPAdapter
from src.crawling.adapters.multilingual.timesofindia import TimesOfIndiaAdapter
from src.crawling.adapters.multilingual.hindustantimes import HindustanTimesAdapter
from src.crawling.adapters.multilingual.economictimes import EconomicTimesAdapter
from src.crawling.adapters.multilingual.indianexpress import IndianExpressAdapter
from src.crawling.adapters.multilingual.philstar import PhilStarAdapter
from src.crawling.adapters.multilingual.manilatimes import ManilaTimesAdapter
from src.crawling.adapters.multilingual.inquirer import InquirerAdapter
from src.crawling.adapters.multilingual.jakartapost import JakartaPostAdapter
from src.crawling.adapters.multilingual.antaranews import AntaraNewsAdapter
from src.crawling.adapters.multilingual.tempo_id import TempoIDAdapter
from src.crawling.adapters.multilingual.focustaiwan import FocusTaiwanAdapter
from src.crawling.adapters.multilingual.taipeitimes import TaipeiTimesAdapter
from src.crawling.adapters.multilingual.vnexpress import VnExpressAdapter
from src.crawling.adapters.multilingual.vietnamnews import VietnamNewsAdapter

# --- Group G: Europe/ME (original 7) ---
from src.crawling.adapters.multilingual.thesun import TheSunAdapter
from src.crawling.adapters.multilingual.bild import BildAdapter
from src.crawling.adapters.multilingual.lemonde import LeMondeAdapter
from src.crawling.adapters.multilingual.themoscowtimes import MoscowTimesAdapter
from src.crawling.adapters.multilingual.arabnews import ArabNewsAdapter
from src.crawling.adapters.multilingual.aljazeera import AlJazeeraAdapter
from src.crawling.adapters.multilingual.israelhayom import IsraelHayomAdapter

# --- Group G: Europe/ME (new) ---
from src.crawling.adapters.multilingual.euronews import EuronewsAdapter
from src.crawling.adapters.multilingual.spiegel import SpiegelAdapter
from src.crawling.adapters.multilingual.sueddeutsche import SueddeutscheAdapter
from src.crawling.adapters.multilingual.welt import WeltAdapter
from src.crawling.adapters.multilingual.faz import FAZAdapter
from src.crawling.adapters.multilingual.corriere import CorriereAdapter
from src.crawling.adapters.multilingual.repubblica import RepubblicaAdapter
from src.crawling.adapters.multilingual.ansa import ANSAAdapter
from src.crawling.adapters.multilingual.elpais import ElPaisAdapter
from src.crawling.adapters.multilingual.elmundo import ElMundoAdapter
from src.crawling.adapters.multilingual.abc_es import ABCSpainAdapter
from src.crawling.adapters.multilingual.lavanguardia import LaVanguardiaAdapter
from src.crawling.adapters.multilingual.lefigaro import LeFigaroAdapter
from src.crawling.adapters.multilingual.liberation import LiberationAdapter
from src.crawling.adapters.multilingual.france24 import France24Adapter
from src.crawling.adapters.multilingual.ouestfrance import OuestFranceAdapter
from src.crawling.adapters.multilingual.wyborcza import WyborczaAdapter
from src.crawling.adapters.multilingual.pap import PAPAdapter
from src.crawling.adapters.multilingual.idnes import IDNESAdapter
from src.crawling.adapters.multilingual.intellinews import IntellinewsAdapter
from src.crawling.adapters.multilingual.balkaninsight import BalkanInsightAdapter
from src.crawling.adapters.multilingual.centraleuropeantimes import CentralEuropeanTimesAdapter
from src.crawling.adapters.multilingual.aftonbladet import AftonbladetAdapter
from src.crawling.adapters.multilingual.tv2_no import TV2NorwayAdapter
from src.crawling.adapters.multilingual.yle import YLEAdapter
from src.crawling.adapters.multilingual.icelandmonitor import IcelandMonitorAdapter
from src.crawling.adapters.multilingual.middleeasteye import MiddleEastEyeAdapter
from src.crawling.adapters.multilingual.almonitor import AlMonitorAdapter
from src.crawling.adapters.multilingual.haaretz import HaaretzAdapter
from src.crawling.adapters.multilingual.jpost import JPostAdapter
from src.crawling.adapters.multilingual.jordantimes import JordanTimesAdapter

# --- Group H: Africa ---
from src.crawling.adapters.multilingual.allafrica import AllAfricaAdapter
from src.crawling.adapters.multilingual.africanews import AfricanewsAdapter
from src.crawling.adapters.multilingual.theafricareport import TheAfricaReportAdapter
from src.crawling.adapters.multilingual.panapress import PanapressAdapter

# --- Group I: Latin America ---
from src.crawling.adapters.multilingual.clarin import ClarinAdapter
from src.crawling.adapters.multilingual.lanacion_ar import LaNacionAdapter
from src.crawling.adapters.multilingual.folha import FolhaAdapter
from src.crawling.adapters.multilingual.oglobo import OGloboAdapter
from src.crawling.adapters.multilingual.elmercurio import ElMercurioAdapter
from src.crawling.adapters.multilingual.biobiochile import BioBioChileAdapter
from src.crawling.adapters.multilingual.eltiempo import ElTiempoAdapter
from src.crawling.adapters.multilingual.elcomercio_pe import ElComercioAdapter

# --- Group J: Russia/Central Asia ---
from src.crawling.adapters.multilingual.gogo_mn import GoGoMNAdapter
from src.crawling.adapters.multilingual.ria import RIAAdapter
from src.crawling.adapters.multilingual.rg import RGAdapter
from src.crawling.adapters.multilingual.rbc import RBCAdapter

# Registry mapping SITE_ID -> adapter class
MULTILINGUAL_ADAPTERS: dict[str, type] = {
    # Group F: Asia-Pacific
    "people": PeopleAdapter,
    "globaltimes": GlobalTimesAdapter,
    "scmp": SCMPAdapter,
    "taiwannews": TaiwanNewsAdapter,
    "yomiuri": YomiuriAdapter,
    "thehindu": TheHinduAdapter,
    "mainichi": MainichiAdapter,
    "asahi": AsahiAdapter,
    "yahoo_jp": YahooJPAdapter,
    "timesofindia": TimesOfIndiaAdapter,
    "hindustantimes": HindustanTimesAdapter,
    "economictimes": EconomicTimesAdapter,
    "indianexpress": IndianExpressAdapter,
    "philstar": PhilStarAdapter,
    "manilatimes": ManilaTimesAdapter,
    "inquirer": InquirerAdapter,
    "jakartapost": JakartaPostAdapter,
    "antaranews": AntaraNewsAdapter,
    "tempo_id": TempoIDAdapter,
    "focustaiwan": FocusTaiwanAdapter,
    "taipeitimes": TaipeiTimesAdapter,
    "vnexpress": VnExpressAdapter,
    "vietnamnews": VietnamNewsAdapter,
    # Group G: Europe/ME
    "thesun": TheSunAdapter,
    "bild": BildAdapter,
    "lemonde": LeMondeAdapter,
    "themoscowtimes": MoscowTimesAdapter,
    "arabnews": ArabNewsAdapter,
    "aljazeera": AlJazeeraAdapter,
    "israelhayom": IsraelHayomAdapter,
    "euronews": EuronewsAdapter,
    "spiegel": SpiegelAdapter,
    "sueddeutsche": SueddeutscheAdapter,
    "welt": WeltAdapter,
    "faz": FAZAdapter,
    "corriere": CorriereAdapter,
    "repubblica": RepubblicaAdapter,
    "ansa": ANSAAdapter,
    "elpais": ElPaisAdapter,
    "elmundo": ElMundoAdapter,
    "abc_es": ABCSpainAdapter,
    "lavanguardia": LaVanguardiaAdapter,
    "lefigaro": LeFigaroAdapter,
    "liberation": LiberationAdapter,
    "france24": France24Adapter,
    "ouestfrance": OuestFranceAdapter,
    "wyborcza": WyborczaAdapter,
    "pap": PAPAdapter,
    "idnes": IDNESAdapter,
    "intellinews": IntellinewsAdapter,
    "balkaninsight": BalkanInsightAdapter,
    "centraleuropeantimes": CentralEuropeanTimesAdapter,
    "aftonbladet": AftonbladetAdapter,
    "tv2_no": TV2NorwayAdapter,
    "yle": YLEAdapter,
    "icelandmonitor": IcelandMonitorAdapter,
    "middleeasteye": MiddleEastEyeAdapter,
    "almonitor": AlMonitorAdapter,
    "haaretz": HaaretzAdapter,
    "jpost": JPostAdapter,
    "jordantimes": JordanTimesAdapter,
    # Group H: Africa
    "allafrica": AllAfricaAdapter,
    "africanews": AfricanewsAdapter,
    "theafricareport": TheAfricaReportAdapter,
    "panapress": PanapressAdapter,
    # Group I: Latin America
    "clarin": ClarinAdapter,
    "lanacion_ar": LaNacionAdapter,
    "folha": FolhaAdapter,
    "oglobo": OGloboAdapter,
    "elmercurio": ElMercurioAdapter,
    "biobiochile": BioBioChileAdapter,
    "eltiempo": ElTiempoAdapter,
    "elcomercio_pe": ElComercioAdapter,
    # Group J: Russia/Central Asia
    "gogo_mn": GoGoMNAdapter,
    "ria": RIAAdapter,
    "rg": RGAdapter,
    "rbc": RBCAdapter,
}

__all__ = list(MULTILINGUAL_ADAPTERS.values().__class__.__name__ for _ in [0]) or [
    cls.__name__ for cls in MULTILINGUAL_ADAPTERS.values()
] + ["MULTILINGUAL_ADAPTERS"]
