"""이미지 선택기 v4.1 — 설교 원고 컨텍스트 + 한국어 스타일명 + Single-Slot Focus

v4.1 보완 (2026-05-01):
  · 사이드바 슬롯 → 진짜 클릭 가능한 Streamlit 버튼으로 통합
  · 진행 도크 → 가로 8칸 점프 버튼 (한 글자 라벨)
  · 추천 ★ → 제거 (임의 기준 의미 없음)
  · "전체 갤러리" 모드 추가 → 모든 슬라이드를 슬롯에 임의 배치 가능
  · 60대 친화 18pt+ 글씨, 큰 카드, 명확한 색상 대비

사용: streamlit run scripts/image_selector_v4.py --server.port 8503 -- --dir <설교폴더>
"""

import streamlit as st
import streamlit.components.v1 as components
import sys
import json
import shutil
import base64
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────
# 설교 폴더 탐지
# ──────────────────────────────────────────────
def get_sermon_dir():
    for i, arg in enumerate(sys.argv):
        if arg == "--dir" and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1]).resolve()
    project = Path(__file__).parent.parent.resolve()
    sermons_dir = project / "sermons"
    if sermons_dir.exists():
        dirs = sorted(
            [d for d in sermons_dir.iterdir() if d.is_dir() and d.name[:8].isdigit()],
            reverse=True,
        )
        if dirs:
            return dirs[0]
    return project


SERMON_DIR = get_sermon_dir()
IMAGES_DIR = SERMON_DIR / "images"
SELECTION_FILE = IMAGES_DIR / "_selection.json"
TRIGGER_FILE = IMAGES_DIR / "_trigger.json"
SLOTS_FILE = SERMON_DIR / "slots.json"
STYLE_NAMES_FILE = SERMON_DIR / "style_names.json"


# ──────────────────────────────────────────────
# 슬롯 + 스타일명 로딩
# ──────────────────────────────────────────────
def load_slots():
    if not SLOTS_FILE.exists():
        return []
    return json.loads(SLOTS_FILE.read_text(encoding="utf-8"))


def load_style_names():
    if STYLE_NAMES_FILE.exists():
        return json.loads(STYLE_NAMES_FILE.read_text(encoding="utf-8"))
    return {
        "A": {"name": "스타일 A", "emoji": "🅰️", "color": "#3b82f6", "desc": ""},
        "B": {"name": "스타일 B", "emoji": "🅱️", "color": "#a855f7", "desc": ""},
        "C": {"name": "스타일 C", "emoji": "🅒", "color": "#ec4899", "desc": ""},
        "D": {"name": "스타일 D", "emoji": "🅓", "color": "#f59e0b", "desc": ""},
        "E": {"name": "스타일 E", "emoji": "🅔", "color": "#10b981", "desc": ""},
        "F": {"name": "스타일 F", "emoji": "🅕", "color": "#fb923c", "desc": ""},
    }


SLOTS = load_slots()
STYLE_NAMES = load_style_names()
IMAGE_SLOT_NUMS = [s["num"] for s in SLOTS if s.get("has_image", True)]
ALL_SLOT_NUMS = [s["num"] for s in SLOTS]  # 이미지 + 텍스트 슬롯 모두


def detect_prefixes():
    """images/ 폴더에서 {PREFIX}_{NN}.png 패턴의 프리픽스를 자동 감지."""
    import re
    prefixes = set()
    if IMAGES_DIR.exists():
        for f in IMAGES_DIR.glob("*_*.png"):
            m = re.match(r"^([A-Z])_\d+\.png$", f.name)
            if m:
                prefixes.add(m.group(1))
    return sorted(prefixes) if prefixes else ["A", "B", "C", "D", "E", "F"]


DETECTED_PREFIXES = detect_prefixes()


# ──────────────────────────────────────────────
# 상태 관리
# ──────────────────────────────────────────────
def load_sel():
    if SELECTION_FILE.exists():
        return json.loads(SELECTION_FILE.read_text(encoding="utf-8"))
    return {"selected": {}, "regenerate": [], "status": "selecting", "notes": {}, "prompts": {}}


def save_sel(data):
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    SELECTION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def apply_image(slot, src):
    dst = IMAGES_DIR / f"ppt_{slot}.png"
    shutil.copy2(src, dst)
    data = load_sel()
    data["selected"][slot] = src.name
    if slot in data.get("regenerate", []):
        data["regenerate"].remove(slot)
    data["status"] = "selecting"
    save_sel(data)


def deselect_image(slot):
    data = load_sel()
    if slot in data.get("selected", {}):
        del data["selected"][slot]
    ppt_img = IMAGES_DIR / f"ppt_{slot}.png"
    if ppt_img.exists():
        ppt_img.unlink()
    data["status"] = "selecting"
    save_sel(data)


def request_regenerate(slot):
    data = load_sel()
    regen = data.setdefault("regenerate", [])
    if slot not in regen:
        regen.append(slot)
    data.get("selected", {}).pop(slot, None)
    data["status"] = "selecting"
    ppt_img = IMAGES_DIR / f"ppt_{slot}.png"
    if ppt_img.exists():
        ppt_img.unlink()
    save_sel(data)


def cancel_regenerate(slot):
    data = load_sel()
    regen = data.get("regenerate", [])
    if slot in regen:
        regen.remove(slot)
    save_sel(data)


def write_trigger(slots):
    data = load_sel()
    prompts = data.get("prompts", {})
    slot_prompts = {s: prompts[s].strip() for s in slots if s in prompts and prompts[s].strip()}
    trigger = {
        "action": "regenerate",
        "slots": slots,
        "prompts": slot_prompts,
        "status": "requested",
        "timestamp": datetime.now().isoformat(),
    }
    TRIGGER_FILE.write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")


def get_candidates_for_slot(slot, active_styles=None):
    """슬롯의 후보 6 세트. mapping[X]=None이면 빈 카드 표시.

    반환: [{prefix, page, img, style, empty}, ...]
    """
    if active_styles is None:
        active_styles = DETECTED_PREFIXES
    candidates = []
    mapping = slot.get("candidates") or {}
    for prefix in active_styles:
        style = STYLE_NAMES.get(prefix, {"name": prefix, "color": "#94a3b8", "emoji": "•", "desc": ""})
        # mapping에 명시적 None이면 빈 카드 (NLM이 적합한 이미지 미생성)
        if prefix in mapping and mapping[prefix] is None:
            candidates.append({
                "prefix": prefix, "page": None, "img": None,
                "style": style, "empty": True,
            })
            continue
        # 매핑 있으면 그대로, 없으면 slot 번호 폴백
        page = mapping.get(prefix) if prefix in mapping else slot["num"]
        img = IMAGES_DIR / f"{prefix}_{page}.png"
        if img.exists():
            candidates.append({
                "prefix": prefix, "page": page, "img": img,
                "style": style, "empty": False,
            })
    return candidates


def get_all_set_images():
    """모든 세트의 모든 이미지 — 갤러리 모드용."""
    result = {}
    for prefix in DETECTED_PREFIXES:
        imgs = sorted(IMAGES_DIR.glob(f"{prefix}_*.png"))
        # ppt_*.png 제외
        imgs = [i for i in imgs if not i.name.startswith("ppt_")]
        if imgs:
            result[prefix] = imgs
    return result


# ──────────────────────────────────────────────
# base64 캐시
# ──────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _b64_cached(path_str: str, _mtime: float, max_width: int = 600) -> str:
    # _mtime은 캐시 키 전용 — 파일이 바뀌면 mtime이 달라져 캐시가 자동 무효화됨
    try:
        from PIL import Image
        import io as _io
        img = Image.open(path_str)
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (15, 23, 42))
            bg.paste(img, mask=img.split()[3])
            img = bg
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=82)
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        with open(path_str, "rb") as f:
            return base64.b64encode(f.read()).decode()


def _b64(path_str: str, max_width: int = 600) -> str:
    # 파일 수정시각을 캐시 키에 포함 → 파일 갱신 시 streamlit 재시작 없이도 자동 반영
    try:
        _mt = Path(path_str).stat().st_mtime
    except OSError:
        _mt = 0.0
    return _b64_cached(path_str, _mt, max_width)


@st.cache_data(show_spinner=False)
def _b64_full_cached(path_str: str, _mtime: float) -> str:
    """라이트박스용 — 1600px 고해상도 base64."""
    try:
        from PIL import Image
        import io as _io
        img = Image.open(path_str)
        if img.width > 1600:
            ratio = 1600 / img.width
            img = img.resize((1600, int(img.height * ratio)), Image.LANCZOS)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (15, 23, 42))
            bg.paste(img, mask=img.split()[3])
            img = bg
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=88)
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        with open(path_str, "rb") as f:
            return base64.b64encode(f.read()).decode()


def _b64_full(path_str: str) -> str:
    try:
        _mt = Path(path_str).stat().st_mtime
    except OSError:
        _mt = 0.0
    return _b64_full_cached(path_str, _mt)


# ──────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="설교 이미지 선택기 v4",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────
# 글로벌 스타일 (세련된 다크 + 큰 타이포)
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&family=Noto+Serif+KR:wght@400;500;700&display=swap');

.stApp {
    background: linear-gradient(180deg, #0a0e1a 0%, #0f172a 100%);
    font-family: 'Noto Sans KR', sans-serif;
    font-size: 16px;
}
header[data-testid="stHeader"] { display: none; }
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 100% !important;
}

/* 헤더 */
.app-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.7rem 1.4rem; margin-bottom: 1rem;
    border-radius: 14px;
    background: linear-gradient(135deg, #111827, #0f172a);
    border: 1px solid #1f2937;
    box-shadow: 0 4px 18px rgba(0,0,0,0.3);
}
.app-title {
    font-size: 1.3rem; font-weight: 900;
    background: linear-gradient(135deg, #fbbf24, #fde047);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.app-sub { font-size: 0.85rem; color: #64748b; margin-left: 0.7rem; }
.app-counter {
    display: flex; align-items: baseline; gap: 0.4rem;
}
.app-counter .num {
    font-size: 1.5rem; font-weight: 900; color: #fbbf24;
}
.app-counter .total { color: #475569; font-size: 1rem; }
.app-counter .pct { color: #94a3b8; font-size: 0.9rem; margin-left: 0.4rem; }

/* 좌측 사이드바 슬롯 버튼 */
.side-title {
    font-size: 0.85rem; font-weight: 800; letter-spacing: 1.2px;
    color: #94a3b8; text-transform: uppercase;
    margin: 0.2rem 0 0.6rem 0.2rem;
}
.side-stats {
    background: linear-gradient(135deg, #111827, #0f172a);
    border: 1px solid #1f2937;
    border-radius: 14px;
    padding: 1rem 1.1rem;
    margin-bottom: 1rem;
}
.side-stats-row {
    display: flex; align-items: baseline; gap: 0.4rem;
    font-size: 1.05rem; font-weight: 700; color: #f1f5f9;
}
.side-stats-row .big { font-size: 1.7rem; color: #fbbf24; font-weight: 900; }
.side-stats-row .total { color: #64748b; font-size: 0.95rem; font-weight: 600; }
.side-progress {
    background: #1f2937; border-radius: 999px; height: 7px;
    overflow: hidden; margin-top: 0.6rem;
}
.side-progress-fill {
    background: linear-gradient(90deg, #fbbf24, #f59e0b);
    height: 100%; transition: width 0.45s ease;
    box-shadow: 0 0 10px rgba(251,191,36,0.4);
}

/* 사이드바 슬롯 버튼 (Streamlit 버튼 스타일링 — 한 줄당 한 슬롯) */
div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] button[data-testid="baseButton-secondary"][kind="secondary"]:has(+ * span:contains("slot-")),
.slot-btn-wrap button {
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 0.7rem 0.9rem !important;
    height: auto !important;
    min-height: 2.8rem !important;
}

/* 컨텍스트 밴드 */
.context-band {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-left: 5px solid #fbbf24;
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 6px 24px rgba(0,0,0,0.35);
    margin-bottom: 1rem;
}
.context-slot {
    display: flex; align-items: center; gap: 0.9rem; margin-bottom: 0.6rem;
}
.context-slot .num {
    background: linear-gradient(135deg, #fbbf24, #f59e0b);
    color: #0a0e1a;
    font-weight: 900; font-size: 0.95rem;
    padding: 0.3rem 0.8rem; border-radius: 8px;
    letter-spacing: 0.6px;
    box-shadow: 0 2px 8px rgba(251,191,36,0.35);
}
.context-slot .title {
    font-size: 1.25rem; font-weight: 800; color: #f1f5f9;
    flex: 1;
    line-height: 1.35;
}
.context-slot .badge {
    font-size: 1rem; font-weight: 800;
    padding: 0.45rem 1rem; border-radius: 10px;
    white-space: nowrap;
}
.context-slot .badge.done {
    background: rgba(34,197,94,0.18); color: #4ade80;
    border: 1px solid rgba(34,197,94,0.4);
}
.context-slot .badge.wait {
    background: rgba(100,116,139,0.18); color: #94a3b8;
    border: 1px solid #475569;
}
.context-slot .badge.regen {
    background: rgba(239,68,68,0.18); color: #fca5a5;
    border: 1px solid rgba(239,68,68,0.4);
}
.context-text {
    font-family: 'Noto Serif KR', serif;
    font-size: 1.02rem; line-height: 1.85;
    color: #e2e8f0;
    border-left: 3px solid #475569;
    padding-left: 1.1rem;
    margin-top: 0.9rem;
    white-space: pre-wrap;
}

/* 후보 카드 */
.cand-card {
    background: #1e293b;
    border: 2px solid #334155;
    border-radius: 14px;
    padding: 0.8rem;
    transition: all 0.18s ease;
    position: relative;
    margin-bottom: 0.5rem;
}
.cand-card:hover {
    border-color: #60a5fa;
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(96,165,250,0.18);
}
.cand-card.picked {
    border-color: #fbbf24;
    background: linear-gradient(135deg, rgba(251,191,36,0.10), rgba(15,23,42,1));
    box-shadow: 0 0 24px rgba(251,191,36,0.35);
}
.cand-style {
    display: flex; align-items: center; gap: 0.55rem;
    margin-bottom: 0.7rem;
    font-size: 0.95rem; font-weight: 700;
}
.cand-style-emoji { font-size: 1.25rem; }
.cand-style-name { font-size: 0.95rem; font-weight: 800; line-height: 1.1; }
.cand-style-desc { font-size: 0.72rem; color: #94a3b8; margin-top: 0.15rem; line-height: 1.3; }
.cand-img-wrap {
    background: #0a0e1a; border-radius: 10px;
    overflow: hidden; cursor: zoom-in;
    aspect-ratio: 16/9;
    margin-bottom: 0.7rem;
    position: relative;
}
.cand-img-wrap img {
    width: 100%; height: 100%; object-fit: cover;
    display: block;
}
.cand-img-num {
    position: absolute; top: 8px; left: 8px;
    background: rgba(0,0,0,0.75); color: #f1f5f9;
    width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.8rem; font-weight: 800;
    border: 1.5px solid #1f2937;
}
.cand-card.picked .cand-img-num {
    background: linear-gradient(135deg, #fbbf24, #f59e0b);
    color: #0a0e1a;
    border-color: #fde047;
    box-shadow: 0 2px 10px rgba(251,191,36,0.55);
}
.cand-page-tag {
    position: absolute; top: 8px; right: 8px;
    background: rgba(0,0,0,0.75); color: #cbd5e1;
    font-size: 0.65rem; font-weight: 700;
    padding: 3px 7px; border-radius: 5px;
    border: 1px solid #1f2937;
}

/* 버튼 */
button[kind="primary"] {
    background: linear-gradient(135deg, #fbbf24, #f59e0b) !important;
    border: none !important;
    color: #0a0e1a !important;
    font-weight: 800 !important;
    font-size: 1rem !important;
    box-shadow: 0 4px 14px rgba(251,191,36,0.35) !important;
    height: 2.7rem !important;
    border-radius: 10px !important;
}
button[kind="primary"]:hover {
    background: linear-gradient(135deg, #fde047, #f59e0b) !important;
    box-shadow: 0 6px 22px rgba(251,191,36,0.55) !important;
}
button[kind="secondary"] {
    background: #1f2937 !important;
    border: 1px solid #334155 !important;
    color: #cbd5e1 !important;
    font-weight: 600 !important;
    height: 2.5rem !important;
    border-radius: 10px !important;
}
button[kind="secondary"]:hover {
    background: #334155 !important;
    border-color: #475569 !important;
    color: #f1f5f9 !important;
}
/* 사이드 슬롯 버튼은 왼쪽 정렬 */
.slot-btn-wrap button {
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 0.6rem 0.85rem !important;
    height: auto !important;
    min-height: 2.7rem !important;
    font-size: 0.9rem !important;
    line-height: 1.3 !important;
}

/* 이미지 슬롯 — 황금 배경 (따뜻한 톤) */
div[data-slot-type="image"] button[kind="secondary"] {
    background: linear-gradient(135deg, rgba(251,191,36,0.20), rgba(180,83,9,0.10)) !important;
    border: 1px solid rgba(251,191,36,0.40) !important;
    border-left: 4px solid #fbbf24 !important;
    color: #fde68a !important;
    font-weight: 600 !important;
}
div[data-slot-type="image"] button[kind="secondary"]:hover {
    background: linear-gradient(135deg, rgba(251,191,36,0.32), rgba(180,83,9,0.18)) !important;
    border-color: #fbbf24 !important;
    color: #fef3c7 !important;
}
div[data-slot-type="image"] button[kind="primary"] {
    background: linear-gradient(135deg, #fbbf24, #f59e0b) !important;
    color: #0a0e1a !important;
    border: none !important;
    border-left: 4px solid #f59e0b !important;
    box-shadow: 0 0 18px rgba(251,191,36,0.55) !important;
    font-weight: 800 !important;
}

/* 본문 슬롯 — 시안 배경 (차가운 톤) */
div[data-slot-type="text"] button[kind="secondary"] {
    background: linear-gradient(135deg, rgba(6,182,212,0.20), rgba(8,51,68,0.10)) !important;
    border: 1px solid rgba(6,182,212,0.40) !important;
    border-left: 4px solid #06b6d4 !important;
    color: #a5f3fc !important;
    font-weight: 600 !important;
}
div[data-slot-type="text"] button[kind="secondary"]:hover {
    background: linear-gradient(135deg, rgba(6,182,212,0.34), rgba(8,51,68,0.18)) !important;
    border-color: #06b6d4 !important;
    color: #cffafe !important;
}
div[data-slot-type="text"] button[kind="primary"] {
    background: linear-gradient(135deg, #06b6d4, #0e7490) !important;
    color: #0a0e1a !important;
    border: none !important;
    border-left: 4px solid #0891b2 !important;
    box-shadow: 0 0 18px rgba(6,182,212,0.55) !important;
    font-weight: 800 !important;
}

/* 사이드바 슬롯 버튼 — 완전히 붙여서 표시 (어떤 부모/자식 컨테이너에도 gap 0 강제) */
div[data-slot-type] {
    margin: 0 !important;
    padding: 0 !important;
}
div[data-slot-type] *,
div[data-slot-type] *:before,
div[data-slot-type] *:after {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
div[data-slot-type] div.stButton,
div[data-slot-type] [data-testid="stVerticalBlock"],
div[data-slot-type] [data-testid="element-container"] {
    margin: 0 !important;
    padding: 0 !important;
    gap: 0 !important;
}
div[data-slot-type] button {
    margin: 0 !important;
    border-radius: 0 !important;
    min-height: 2.5rem !important;
    border-bottom-width: 0 !important;  /* 인접 버튼 사이 이중 보더 방지 */
}
/* 첫·마지막 슬롯만 둥글기 */
div[data-slot-type]:first-of-type button {
    border-top-left-radius: 8px !important;
    border-top-right-radius: 8px !important;
}
div[data-slot-type]:last-of-type button {
    border-bottom-left-radius: 8px !important;
    border-bottom-right-radius: 8px !important;
    border-bottom-width: 1px !important;
}
/* 부모 vertical block의 gap 강제 0 */
.slot-btn-wrap [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}
.slot-btn-wrap > div {
    gap: 0 !important;
}

/* 갤러리 ✓ 강화 — 사용 중 카드 매우 명확히 */
.gal-card.picked-anywhere {
    border: 5px solid #22c55e !important;
    box-shadow: 0 0 28px rgba(34,197,94,0.75) !important;
    background: linear-gradient(135deg, rgba(34,197,94,0.22), rgba(15,23,42,1)) !important;
    position: relative;
}
.gal-card.picked-anywhere::after {
    content: '✓';
    position: absolute;
    top: 8px; right: 8px;
    width: 42px; height: 42px;
    border-radius: 50%;
    background: linear-gradient(135deg, #22c55e, #16a34a);
    color: #fff;
    font-size: 1.5rem; font-weight: 900;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 3px 14px rgba(34,197,94,0.7);
    border: 2px solid #fff;
    z-index: 5;
}
.gal-card.picked-anywhere::before {
    content: attr(data-slot-tag);
    position: absolute;
    top: 8px; left: 8px;
    background: linear-gradient(135deg, #22c55e, #16a34a);
    color: #fff;
    font-size: 0.95rem; font-weight: 900;
    padding: 5px 12px; border-radius: 8px;
    letter-spacing: 0.6px;
    box-shadow: 0 3px 12px rgba(34,197,94,0.65);
    z-index: 5;
}

/* 네비게이션 바 */
.nav-bar {
    background: linear-gradient(135deg, #111827, #0f172a);
    border: 1px solid #1f2937;
    border-radius: 14px;
    padding: 0.9rem 1.2rem;
    margin-top: 1.2rem;
    box-shadow: 0 4px 18px rgba(0,0,0,0.3);
}

/* 컨펌 배너 */
.confirm-banner {
    background: linear-gradient(135deg, #064e3b, #0a0e1a, #14532d);
    border: 2px solid #22c55e; border-radius: 18px;
    padding: 2.5rem 2rem; text-align: center;
    box-shadow: 0 8px 32px rgba(34,197,94,0.25);
}
.confirm-banner .icon { font-size: 3.5rem; margin-bottom: 0.5rem; }
.confirm-banner .title {
    font-size: 1.6rem; font-weight: 900; color: #4ade80;
    margin-bottom: 0.5rem;
}
.confirm-banner .sub { color: #86efac; font-size: 1.05rem; }

/* 갤러리 다운로드 버튼 — 헤더 박스(height:64px + margin:2rem 0 1rem 0)와 픽셀 단위 정확 매칭 */
[data-testid="stDownloadButton"] {
    margin-top: 2rem !important;
    margin-bottom: 1rem !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
    padding: 0 !important;
}
[data-testid="stDownloadButton"] button {
    height: 64px !important;
    min-height: 64px !important;
    max-height: 64px !important;
    border-radius: 12px !important;
    font-size: 1rem !important;
    font-weight: 800 !important;
    box-shadow: 0 4px 14px rgba(251,191,36,0.35) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 1rem !important;
    margin: 0 !important;
}

/* 빈 카드 (NLM이 매칭 이미지 미생성) */
.cand-card.empty-card {
    background: rgba(15,23,42,0.6) !important;
    border: 2px dashed #475569 !important;
    box-shadow: none !important;
}
.cand-card.empty-card:hover {
    transform: none !important;
    border-color: #64748b !important;
}
.cand-img-wrap.empty-img-wrap {
    background: rgba(15,23,42,0.4) !important;
    cursor: not-allowed !important;
}
.empty-overlay {
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    gap: 0.4rem;
}
.empty-icon {
    font-size: 2.4rem; color: #475569; font-weight: 300;
}
.empty-text {
    color: #64748b; font-size: 0.78rem;
    text-align: center; line-height: 1.4;
}

/* 갤러리 카드 (전체 보기 모드) */
.gal-card {
    background: #1e293b; border: 1.5px solid #334155;
    border-radius: 10px; padding: 5px;
    transition: all 0.15s; cursor: zoom-in;
    position: relative;
    margin-bottom: 8px;  /* 카드 간 세로 간격 */
    overflow: visible;
}
.gal-card:hover { border-color: #fbbf24; transform: translateY(-2px); }
.gal-card.picked-anywhere {
    border-color: #22c55e;
    box-shadow: 0 0 12px rgba(34,197,94,0.25);
}
.gal-card img { width: 100%; border-radius: 7px; aspect-ratio: 16/9; object-fit: cover; }
.gal-card-label { font-size: 0.7rem; color: #94a3b8; text-align: center; margin-top: 4px; padding-bottom: 2px; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 라이트박스 v2 — 95vw 풀스크린 + 줌 ±/휠 + ←→ + ESC + 드래그
# ──────────────────────────────────────────────
components.html("""
<script>
(function() {
    var P = window.parent.document;
    if (P.getElementById('lb2-overlay')) return;  // 한 번만 주입

    // 오버레이 + 툴바 + 큰 이미지
    var ov = P.createElement('div');
    ov.id = 'lb2-overlay';
    ov.style.cssText = [
        'display:none', 'position:fixed', 'inset:0',
        'background:rgba(8,12,22,0.97)', 'z-index:99999',
        'flex-direction:column', 'align-items:center', 'justify-content:center',
        'overflow:hidden'
    ].join(';');

    ov.innerHTML = `
        <div id="lb2-toolbar" style="position:absolute;top:18px;left:50%;transform:translateX(-50%);
             background:rgba(15,23,42,0.85);backdrop-filter:blur(10px);
             border:1px solid rgba(251,191,36,0.35);border-radius:12px;
             padding:8px 14px;display:flex;gap:8px;align-items:center;
             font-family:'Noto Sans KR',sans-serif;color:#f1f5f9;font-size:0.95rem;font-weight:700;">
            <button id="lb2-zoom-out" style="background:#1e293b;color:#cbd5e1;border:1px solid #334155;
                border-radius:8px;padding:6px 12px;cursor:pointer;font-weight:700;">🔍−</button>
            <span id="lb2-zoom-level" style="min-width:60px;text-align:center;color:#fbbf24;">100%</span>
            <button id="lb2-zoom-in" style="background:#1e293b;color:#cbd5e1;border:1px solid #334155;
                border-radius:8px;padding:6px 12px;cursor:pointer;font-weight:700;">🔍+</button>
            <button id="lb2-reset" style="background:#1e293b;color:#cbd5e1;border:1px solid #334155;
                border-radius:8px;padding:6px 12px;cursor:pointer;font-weight:700;">100%</button>
            <span id="lb2-pos" style="margin-left:0.6rem;color:#94a3b8;font-size:0.85rem;font-weight:500;"></span>
            <span style="color:#64748b;font-size:0.78rem;font-weight:500;">키보드 ←→ 이동 · ESC 닫기</span>
            <button id="lb2-close" style="background:#dc2626;color:#fff;border:none;
                border-radius:8px;padding:6px 12px;cursor:pointer;font-weight:700;margin-left:8px;">✕ 닫기 (ESC)</button>
        </div>
        <div id="lb2-img-wrap" style="width:100vw;height:100vh;display:flex;
             align-items:center;justify-content:center;overflow:hidden;cursor:zoom-out;">
            <img id="lb2-img" style="width:auto;height:auto;
                 max-width:96vw;max-height:90vh;min-width:60vw;
                 object-fit:contain;border-radius:8px;box-shadow:0 0 50px rgba(251,191,36,0.2);
                 transform-origin:center center;transition:transform 0.15s ease;
                 user-select:none;-webkit-user-drag:none;" />
        </div>
        <div id="lb2-label" style="position:absolute;bottom:18px;left:50%;transform:translateX(-50%);
             color:#fbbf24;font-size:1rem;font-weight:700;
             background:rgba(15,23,42,0.85);padding:6px 18px;border-radius:10px;
             border:1px solid rgba(251,191,36,0.27);font-family:'Noto Sans KR',sans-serif;"></div>
    `;
    P.body.appendChild(ov);

    // 상태
    var state = { items: [], idx: 0, zoom: 1, panX: 0, panY: 0, dragging: false, sx: 0, sy: 0 };
    var imgEl = ov.querySelector('#lb2-img');
    var wrapEl = ov.querySelector('#lb2-img-wrap');
    var lvlEl = ov.querySelector('#lb2-zoom-level');
    var posEl = ov.querySelector('#lb2-pos');
    var labelEl = ov.querySelector('#lb2-label');

    function applyZoom() {
        imgEl.style.transform = 'translate(' + state.panX + 'px,' + state.panY + 'px) scale(' + state.zoom + ')';
        lvlEl.textContent = Math.round(state.zoom * 100) + '%';
    }
    function setItem(i) {
        if (state.items.length === 0) return;
        state.idx = (i + state.items.length) % state.items.length;
        state.zoom = 1; state.panX = 0; state.panY = 0;
        var item = state.items[state.idx];
        imgEl.src = item.src;
        labelEl.textContent = item.label || '';
        posEl.textContent = (state.idx + 1) + ' / ' + state.items.length;
        applyZoom();
    }
    function open(items, startIdx) {
        state.items = items; state.idx = startIdx || 0;
        setItem(state.idx);
        ov.style.display = 'flex';
    }
    function close() { ov.style.display = 'none'; }

    ov.querySelector('#lb2-close').onclick = close;
    ov.querySelector('#lb2-zoom-in').onclick = function() {
        state.zoom = Math.min(5, state.zoom + 0.25); applyZoom();
    };
    ov.querySelector('#lb2-zoom-out').onclick = function() {
        state.zoom = Math.max(0.3, state.zoom - 0.25);
        if (state.zoom <= 1) { state.panX = 0; state.panY = 0; }
        applyZoom();
    };
    ov.querySelector('#lb2-reset').onclick = function() {
        state.zoom = 1; state.panX = 0; state.panY = 0; applyZoom();
    };

    // 휠 줌
    wrapEl.addEventListener('wheel', function(e) {
        if (ov.style.display !== 'flex') return;
        e.preventDefault();
        var d = e.deltaY < 0 ? 0.15 : -0.15;
        state.zoom = Math.max(0.3, Math.min(5, state.zoom + d));
        if (state.zoom <= 1) { state.panX = 0; state.panY = 0; }
        applyZoom();
    }, { passive: false });

    // 이미지 클릭 시 라이트박스 닫기 (토글)
    imgEl.addEventListener('click', function(e) {
        if (state.zoom <= 1.05) {
            close();
            e.stopPropagation();
        }
    });

    // 드래그 패닝
    wrapEl.addEventListener('mousedown', function(e) {
        if (ov.style.display !== 'flex' || state.zoom <= 1) return;
        state.dragging = true; state.sx = e.clientX - state.panX; state.sy = e.clientY - state.panY;
        wrapEl.style.cursor = 'grabbing';
        e.preventDefault();
    });
    P.addEventListener('mousemove', function(e) {
        if (!state.dragging) return;
        state.panX = e.clientX - state.sx; state.panY = e.clientY - state.sy;
        applyZoom();
    });
    P.addEventListener('mouseup', function() {
        state.dragging = false; wrapEl.style.cursor = 'grab';
    });

    // 키보드
    P.addEventListener('keydown', function(e) {
        if (ov.style.display !== 'flex') return;
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        if (e.key === 'Escape') { close(); e.preventDefault(); }
        else if (e.key === 'ArrowLeft') { setItem(state.idx - 1); e.preventDefault(); }
        else if (e.key === 'ArrowRight') { setItem(state.idx + 1); e.preventDefault(); }
        else if (e.key === '+' || e.key === '=') { state.zoom = Math.min(5, state.zoom + 0.25); applyZoom(); e.preventDefault(); }
        else if (e.key === '-') { state.zoom = Math.max(0.3, state.zoom - 0.25); applyZoom(); e.preventDefault(); }
        else if (e.key === '0') { state.zoom = 1; state.panX = 0; state.panY = 0; applyZoom(); e.preventDefault(); }
    });

    // 이미지 클릭 → 라이트박스 열기
    function getNearbyImages(clicked) {
        // 같은 슬롯 안의 후보들을 모두 모음. data-full 우선 사용.
        function srcOf(img) { return img.dataset.full || img.dataset.fullSrc || img.src; }
        var card = clicked.closest('.cand-card');
        if (card) {
            // Streamlit 컬럼 구조에서 부모 탐색이 안 되므로 문서 전체에서 모든 .cand-card img를 수집
            var allImgs = [];
            P.querySelectorAll('.cand-card:not(.empty-card) .cand-img-wrap img').forEach(function(img) {
                var c = img.closest('.cand-card');
                var nameEl = c ? c.querySelector('.cand-style-name') : null;
                allImgs.push({ src: srcOf(img), label: nameEl ? nameEl.textContent : '' });
            });
            return allImgs;
        }
        var galCard = clicked.closest('.gal-card');
        if (galCard) {
            var galImgs = [];
            P.querySelectorAll('.gal-card img').forEach(function(img) {
                var c = img.closest('.gal-card');
                var lbl = c ? c.querySelector('.gal-card-label') : null;
                galImgs.push({ src: srcOf(img), label: lbl ? lbl.textContent : '' });
            });
            return galImgs;
        }
        return [{ src: srcOf(clicked), label: '' }];
    }

    function attach() {
        var imgs = P.querySelectorAll('.cand-img-wrap img, .gal-card img, [data-lightbox] img');
        imgs.forEach(function(img) {
            if (img._lb2Ready) return;
            img._lb2Ready = true;
            img.style.cursor = 'zoom-in';
            img.addEventListener('click', function(e) {
                e.stopPropagation();
                var items = getNearbyImages(this);
                var startIdx = items.findIndex(function(it) { return it.src === this.src; }.bind(this));
                if (startIdx < 0) startIdx = 0;
                open(items, startIdx);
            });
        });
    }
    attach();

    // 사이드바 슬롯 버튼 → JS 전역 쿼리 + 인라인 스타일 직접 강제 (CSS 의존 제거)
    function styleSlotButtons() {
        var btns = P.querySelectorAll('button');
        var modifiedBlocks = new Set();
        btns.forEach(function(btn) {
            var txt = btn.textContent || '';
            var hasImg = txt.indexOf('🎨') !== -1;
            var hasTxt = txt.indexOf('📜') !== -1;
            if (!hasImg && !hasTxt) return;

            // 1. 부모 element-container 마진/패딩 0 강제
            var ec = btn.closest('div[data-testid="element-container"]');
            if (ec) {
                ec.style.cssText = 'margin:0!important;padding:0!important;';
            }

            // 2. 부모 stVerticalBlock의 gap 4px (약 1mm — 사용자 요청: 0.5mm보다 더)
            var vb = btn.closest('div[data-testid="stVerticalBlock"]');
            if (vb && !modifiedBlocks.has(vb)) {
                vb.style.gap = '4px';
                modifiedBlocks.add(vb);
            }

            // 3. stButton 자체도 마진 0
            var sb = btn.closest('div[data-testid="stButton"]');
            if (sb) sb.style.margin = '0';

            // 4. primary/secondary 검출
            var ti = btn.getAttribute('data-testid') || '';
            var isPrimary = ti.indexOf('primary') !== -1;

            // 5. 버튼 자체 인라인 스타일 강제
            var common = 'text-align:left!important;justify-content:flex-start!important;padding:0.65rem 0.95rem!important;border-radius:0!important;min-height:2.5rem!important;font-size:0.92rem!important;margin:0!important;line-height:1.3!important;display:flex!important;align-items:center!important;width:100%!important;';
            if (hasImg) {
                if (isPrimary) {
                    btn.style.cssText = common + 'background:linear-gradient(135deg,#fbbf24,#f59e0b)!important;color:#0a0e1a!important;border:none!important;border-left:5px solid #d97706!important;font-weight:900!important;box-shadow:inset 0 0 0 100vmax rgba(251,191,36,0.05),0 0 18px rgba(251,191,36,0.55)!important;';
                } else {
                    btn.style.cssText = common + 'background:linear-gradient(135deg,rgba(251,191,36,0.28),rgba(180,83,9,0.12))!important;color:#fde68a!important;border:1px solid rgba(251,191,36,0.45)!important;border-left:5px solid #fbbf24!important;font-weight:700!important;';
                }
            } else if (hasTxt) {
                if (isPrimary) {
                    btn.style.cssText = common + 'background:linear-gradient(135deg,#06b6d4,#0e7490)!important;color:#0a0e1a!important;border:none!important;border-left:5px solid #0891b2!important;font-weight:900!important;box-shadow:0 0 18px rgba(6,182,212,0.55)!important;';
                } else {
                    btn.style.cssText = common + 'background:linear-gradient(135deg,rgba(6,182,212,0.28),rgba(8,51,68,0.12))!important;color:#a5f3fc!important;border:1px solid rgba(6,182,212,0.45)!important;border-left:5px solid #06b6d4!important;font-weight:700!important;';
                }
            }

            // 6. 버튼 내부 텍스트 정렬 보정
            var inner = btn.querySelector('div, p, span');
            if (inner) inner.style.cssText += 'text-align:left!important;width:100%!important;';
        });
    }
    styleSlotButtons();
    // setInterval 제거 — MutationObserver만으로 충분 (성능 향상)

    new MutationObserver(function() {
        setTimeout(attach, 250);
        setTimeout(styleSlotButtons, 250);
    }).observe(P.body, {childList: true, subtree: true});
})();
</script>
""", height=0)


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────
def main():
    if "current_idx" not in st.session_state:
        st.session_state.current_idx = 0
    if "show_gallery" not in st.session_state:
        st.session_state.show_gallery = False
    if "show_batch_summary" not in st.session_state:
        st.session_state.show_batch_summary = False

    # 트리거 처리 중 → 대기 화면
    if TRIGGER_FILE.exists():
        try:
            trigger = json.loads(TRIGGER_FILE.read_text(encoding="utf-8"))
            if trigger.get("status") in ("requested", "processing", "reviewing"):
                render_processing(trigger)
                return
        except Exception:
            pass

    data = load_sel()
    selected = data.get("selected", {})
    regen_list = data.get("regenerate", [])
    status = data.get("status", "selecting")

    render_header(selected, regen_list)

    if status == "confirmed":
        render_confirmed(selected, regen_list)
        return

    # 갤러리 모드 (전체 보기)
    if st.session_state.show_gallery:
        render_gallery_mode(selected)
        return

    if not ALL_SLOT_NUMS:
        st.warning("슬롯이 없습니다. slots.json을 확인하세요.")
        return

    # 일괄 재생성 배너/요약 — 페이지 최상단 (column split 밖)
    render_batch_regen_banner(regen_list)

    # ── 메인 분할 ──
    col_side, col_main = st.columns([1, 4], gap="large")

    with col_side:
        render_side_rail(selected, regen_list)

    with col_main:
        cur_idx = st.session_state.current_idx
        cur_idx = max(0, min(cur_idx, len(ALL_SLOT_NUMS) - 1))
        st.session_state.current_idx = cur_idx

        cur_slot_num = ALL_SLOT_NUMS[cur_idx]
        cur_slot = next((s for s in SLOTS if s["num"] == cur_slot_num), None)
        if cur_slot is None:
            st.warning("슬롯 데이터를 찾을 수 없습니다.")
            return

        render_context_band(cur_slot, selected, regen_list)
        if cur_slot.get("has_image", True):
            render_candidate_grid(cur_slot, selected, regen_list)
            render_regen_input(cur_slot, regen_list)
        else:
            render_text_slide(cur_slot)
        render_navigation(cur_idx, selected, regen_list)


# ──────────────────────────────────────────────
# 헤더
# ──────────────────────────────────────────────
def parse_sermon_meta():
    """설교 폴더명에서 날짜·시리즈·제목을 파싱.
    예: '20260506-룻기강해01-위에서아래로' → ('2026-05-06 (수)', '룻기강해01', '위에서 아래로')
    """
    name = SERMON_DIR.name
    parts = name.split("-", 2)
    date_str = ""
    series = ""
    title = ""
    if len(parts) >= 1 and len(parts[0]) >= 8 and parts[0][:8].isdigit():
        d = parts[0]
        try:
            import datetime
            dt = datetime.date(int(d[:4]), int(d[4:6]), int(d[6:8]))
            weekday = ["월", "화", "수", "목", "금", "토", "일"][dt.weekday()]
            date_str = f"{dt.year}-{dt.month:02d}-{dt.day:02d} ({weekday})"
        except Exception:
            date_str = parts[0]
    if len(parts) >= 2:
        series = parts[1]
    if len(parts) >= 3:
        title = parts[2].replace("-", " ").replace("위에서아래로", "위에서 아래로")
    return date_str, series, title


def render_header(selected, regen_list):
    done = sum(1 for s in IMAGE_SLOT_NUMS if s in selected)
    total = len(IMAGE_SLOT_NUMS)
    pct = int(100 * done / total) if total else 0
    regen_count = sum(1 for s in regen_list if s in IMAGE_SLOT_NUMS)

    date_str, series, title = parse_sermon_meta()

    progress_color = "#fbbf24" if pct < 100 else "#22c55e"

    regen_html = (
        f"<div style='font-size:1rem; color:#fca5a5; font-weight:800; margin-top:0.4rem;'>↻ 재생성 대기 {regen_count}개</div>"
        if regen_count else ""
    )
    header_html = (
        '<div style="background:linear-gradient(135deg, #0c1424 0%, #1a2540 50%, #0f172a 100%);'
        'border:1px solid #1f2937; border-radius:18px;'
        'padding:1.8rem 2.2rem; margin-bottom:1rem;'
        'box-shadow:0 8px 32px rgba(0,0,0,0.4);'
        'position:relative; overflow:hidden;">'
        '<div style="position:absolute; left:0; top:0; bottom:0; width:6px;'
        'background:linear-gradient(180deg, #fbbf24, #f59e0b);"></div>'
        '<div style="display:flex; align-items:center; gap:2rem;">'
        '<div style="flex:2; min-width:0;">'
        '<div style="display:flex; align-items:center; gap:0.8rem; margin-bottom:0.7rem; flex-wrap:wrap;">'
        '<span style="font-size:1.1rem; font-weight:800; letter-spacing:1.2px; color:#fbbf24;'
        'background:rgba(251,191,36,0.18); padding:6px 16px; border-radius:8px;">🎨 설교 이미지 선택기</span>'
        f'<span style="font-size:1.15rem; color:#e2e8f0; font-weight:700;">{date_str if date_str else SERMON_DIR.name}{" · " + series if series else ""}</span>'
        '</div>'
        '<div style="font-size:2.4rem; font-weight:900; color:#f1f5f9; line-height:1.2;'
        'background:linear-gradient(135deg, #fde68a, #fbbf24);'
        '-webkit-background-clip:text; -webkit-text-fill-color:transparent;">'
        f'{title if title else SERMON_DIR.name}'
        '</div>'
        '</div>'
        '<div style="text-align:right; min-width:220px;">'
        '<div style="font-size:0.95rem; color:#cbd5e1; font-weight:800; letter-spacing:1.2px;'
        'text-transform:uppercase; margin-bottom:0.4rem;">진행 상황</div>'
        '<div style="display:flex; align-items:baseline; gap:0.4rem; justify-content:flex-end;">'
        f'<span style="font-size:3.6rem; font-weight:900; color:{progress_color}; line-height:1;'
        f'text-shadow:0 0 18px rgba(251,191,36,0.55);">{done}</span>'
        f'<span style="font-size:1.6rem; color:#64748b; font-weight:700;">/ {total}</span>'
        f'<span style="font-size:1.4rem; color:#cbd5e1; font-weight:800; margin-left:0.4rem;">{pct}%</span>'
        '</div>'
        f'{regen_html}'
        '</div>'
        '</div>'
        f'<div style="margin-top:1.1rem; background:rgba(15,23,42,0.6); border-radius:999px; height:14px; overflow:hidden; border:1px solid rgba(251,191,36,0.2);">'
        f'<div style="background:linear-gradient(90deg, {progress_color}, #fde68a); height:100%; width:{pct}%; box-shadow:0 0 14px rgba(251,191,36,0.6); transition:width 0.5s ease;"></div>'
        '</div>'
        '</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # 액션 바 — 갤러리 토글만 (PPT 다운로드 셀렉트 박스 제거)
    col_pad, col_mode = st.columns([6, 1.2])
    with col_mode:
        if st.session_state.show_gallery:
            if st.button("← 슬롯 모드", use_container_width=True, key="btn_back_slot"):
                st.session_state.show_gallery = False
                st.rerun()
        else:
            if st.button("🖼 전체 갤러리", use_container_width=True, key="btn_gallery"):
                st.session_state.show_gallery = True
                st.rerun()


# ──────────────────────────────────────────────
# 좌측 사이드바
# ──────────────────────────────────────────────
def render_side_rail(selected, regen_list):
    done = sum(1 for s in IMAGE_SLOT_NUMS if s in selected)
    total = len(IMAGE_SLOT_NUMS)
    pct = int(100 * done / total) if total else 0
    cur_idx = st.session_state.current_idx

    st.markdown(f"""
    <div class="side-stats">
        <div class="side-stats-row">
            <span class="big">{done}</span>
            <span>완료</span>
            <span class="total">· 전체 {total}</span>
        </div>
        <div class="side-progress">
            <div class="side-progress-fill" style="width:{pct}%"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 슬롯 목록 제목 — JS gap:2px 영향 없도록 자체 padding/border로 명확 분리
    st.markdown("""
    <div style="font-size:0.95rem; font-weight:800; letter-spacing:1.2px;
                color:#94a3b8; text-transform:uppercase;
                padding:1.1rem 0 0.9rem 0.4rem;
                border-top:1px solid #1f2937; margin:1.2rem 0 0.4rem 0;
                background:linear-gradient(180deg, rgba(15,23,42,0.4), transparent);">
        🗂 전체 슬롯 (이미지 + 본문)
    </div>
    """, unsafe_allow_html=True)

    # 마크다운 래퍼 제거 — 빈 element-container 생성을 방지
    for idx, slot_num in enumerate(ALL_SLOT_NUMS):
        slot = next((s for s in SLOTS if s["num"] == slot_num), None)
        if slot is None:
            continue
        is_image = slot.get("has_image", True)
        is_done = slot_num in selected
        is_regen = slot_num in regen_list
        is_cur = idx == cur_idx

        # 아이콘 — 이미지 vs 본문 명확 구분 (이모지로 JS가 검출)
        if is_image:
            if is_cur:
                icon = "🎨▶"
            elif is_regen:
                icon = "🎨↻"
            elif is_done:
                icon = "🎨✓"
            else:
                icon = "🎨○"
            tag = ""
        else:
            icon = "📜▶" if is_cur else "📜"
            tag = "[본문] "

        desc_short = slot.get("desc", "").split("—")[0].strip()
        if len(desc_short) > 12:
            desc_short = desc_short[:12] + "…"
        label = f"{icon}  PPT{slot_num}  {tag}{desc_short}"

        btn_type = "primary" if is_cur else "secondary"

        if st.button(label, key=f"side_{slot_num}", use_container_width=True, type=btn_type):
            st.session_state.current_idx = idx
            st.rerun()


# ──────────────────────────────────────────────
# 상단 본문 컨텍스트
# ──────────────────────────────────────────────
def render_context_band(slot, selected, regen_list):
    is_image = slot.get("has_image", True)
    is_done = slot["num"] in selected
    is_regen = slot["num"] in regen_list

    if is_image:
        if is_done:
            badge_cls, badge_text = "done", "✓ 선택 완료"
        elif is_regen:
            badge_cls, badge_text = "regen", "↻ 재생성 대기"
        else:
            badge_cls, badge_text = "wait", "○ 미선택"
    else:
        # 본문 슬롯 — 자동 생성, 선택 개념 없음
        badge_cls, badge_text = "done", "📜 본문 슬라이드 (자동 생성)"

    desc = slot.get("desc", "")
    context = slot.get("context", "")

    if is_image:
        ctx_html = context if context else "(이 슬롯은 본문 컨텍스트가 등록되지 않았습니다.)"
    else:
        ctx_html = "📜 PPT에 그대로 사용되는 본문 슬라이드입니다. 아래에서 미리보기 확인하세요."

    st.markdown(f"""
    <div class="context-band">
        <div class="context-slot">
            <div class="num">PPT {slot['num']}</div>
            <div class="title">{desc}</div>
            <div class="badge {badge_cls}">{badge_text}</div>
        </div>
        <div class="context-text">{ctx_html}</div>
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 후보 그리드 (2x3)
# ──────────────────────────────────────────────
def render_candidate_grid(slot, selected, regen_list):
    active = st.session_state.get("active_styles", DETECTED_PREFIXES)
    candidates = get_candidates_for_slot(slot, active_styles=active)
    if not candidates:
        st.info(f"PPT {slot['num']}에 후보 이미지가 없습니다. images/ 폴더와 slots.json을 확인하세요.")
        return

    cols_per_row = 3
    rows = [candidates[i:i + cols_per_row] for i in range(0, len(candidates), cols_per_row)]
    for row_idx, row in enumerate(rows):
        if not row:
            continue
        cols = st.columns(cols_per_row, gap="medium")
        for col_idx, cand in enumerate(row):
            with cols[col_idx]:
                _render_candidate_card(slot, cand, selected, candidate_index=row_idx * cols_per_row + col_idx)


def _render_candidate_card(slot, cand, selected, candidate_index):
    prefix = cand["prefix"]
    style = cand["style"]
    is_empty = cand.get("empty", False)

    # 빈 카드 (NLM이 적합한 이미지를 만들지 못한 경우)
    if is_empty:
        st.markdown(f"""
        <div class="cand-card empty-card">
            <div class="cand-style">
                <span class="cand-style-emoji" style="opacity:0.5;">{style.get('emoji', '•')}</span>
                <div>
                    <div class="cand-style-name" style="color:{style.get('color', '#94a3b8')}; opacity:0.65;">{style.get('name', prefix)}</div>
                    <div class="cand-style-desc">슬라이드 번호 없음</div>
                </div>
            </div>
            <div class="cand-img-wrap empty-img-wrap">
                <div class="empty-overlay">
                    <div class="empty-icon">∅</div>
                    <div class="empty-text">이 세트엔 적합한<br>이미지 없음</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        # 재생성 요청 버튼
        if st.button(f"↻ 재생성 요청", key=f"sel_{slot['num']}_{prefix}",
                     type="secondary", use_container_width=True):
            request_regenerate(slot["num"])
            st.rerun()
        return

    img = cand["img"]
    page = cand["page"]
    is_picked = selected.get(slot["num"]) == img.name
    cls = "picked" if is_picked else ""
    thumb = _b64(str(img))

    # 라이트박스 풀해상도는 lazy — data-full-path만 저장, JS에서 클릭 시 fetch
    st.markdown(f"""
    <div class="cand-card {cls}">
        <div class="cand-style">
            <span class="cand-style-emoji">{style.get('emoji', '•')}</span>
            <div>
                <div class="cand-style-name" style="color:{style.get('color', '#f1f5f9')};">{style.get('name', prefix)}</div>
                <div class="cand-slide-number" style="color:{style.get('color', '#94a3b8')}; font-size:0.85rem; font-weight:800; margin-top:0.15rem;">슬라이드 #{page}</div>
            </div>
        </div>
        <div class="cand-img-wrap">
            <div class="cand-img-num">{candidate_index + 1}</div>
            <img src="data:image/jpeg;base64,{thumb}" data-full-src="data:image/jpeg;base64,{thumb}">
        </div>
    </div>
    """, unsafe_allow_html=True)

    if is_picked:
        if st.button(f"✓ 선택됨 · 해제", key=f"sel_{slot['num']}_{prefix}",
                     type="secondary", use_container_width=True):
            deselect_image(slot["num"])
            st.rerun()
    else:
        if st.button(f"✓ 이걸로 선택", key=f"sel_{slot['num']}_{prefix}",
                     type="primary", use_container_width=True):
            apply_image(slot["num"], img)
            st.rerun()


# ──────────────────────────────────────────────
# 재생성 입력
# ──────────────────────────────────────────────
def render_regen_input(slot, regen_list):
    slot_num = slot["num"]
    is_regen = slot_num in regen_list
    confirm_key = f"confirm_regen_{slot_num}"

    st.markdown("<div style='margin-top:1.4rem;'></div>", unsafe_allow_html=True)

    if is_regen:
        data = load_sel()
        saved_prompt = data.get("prompts", {}).get(slot_num, "")
        prompt_status = f"💾 저장됨: \"{saved_prompt}\"" if saved_prompt else "💬 프롬프트가 비어있음 (NLM이 다른 톤으로 자동 재생성)"

        st.markdown(f"""
        <div style="background:rgba(239,68,68,0.08); border:1px solid rgba(239,68,68,0.4);
                    border-radius:12px; padding:0.9rem 1.2rem;">
            <div style="color:#fca5a5; font-weight:800; font-size:1rem;">
                ↻ PPT {slot_num} 재생성 대기 중
            </div>
            <div style="color:#94a3b8; font-size:0.85rem; margin-top:0.3rem;">
                원하는 이미지 설명을 입력하고 "✓ 저장"을 누르세요. 마지막에 "일괄 재생성" 버튼으로 모아서 보냅니다.
            </div>
            <div style="color:#fbbf24; font-size:0.8rem; margin-top:0.4rem; font-weight:600;">
                {prompt_status}
            </div>
        </div>
        """, unsafe_allow_html=True)
        col_p, col_save, col_c = st.columns([4, 1, 1], gap="small")
        with col_p:
            user_prompt = st.text_input(
                "재생성 프롬프트",
                value=saved_prompt,
                placeholder="예: 더 따뜻한 황금 톤, 미소짓는 인물, 베들레헴 등불…",
                key=f"prompt_{slot_num}",
                label_visibility="collapsed",
            )
        with col_save:
            if st.button("✓ 저장", key=f"save_prompt_{slot_num}", use_container_width=True, type="primary"):
                d = load_sel()
                d.setdefault("prompts", {})[slot_num] = user_prompt or ""
                save_sel(d)
                st.rerun()
        with col_c:
            if st.button("✗ 취소", key=f"cancel_regen_{slot_num}", use_container_width=True):
                cancel_regenerate(slot_num)
                st.session_state.pop(confirm_key, None)
                st.rerun()
    elif st.session_state.get(confirm_key):
        # 확인 모달
        st.markdown(f"""
        <div style="background:linear-gradient(135deg, rgba(239,68,68,0.15), rgba(15,23,42,1));
                    border:2px solid #ef4444; border-radius:12px; padding:1.1rem 1.4rem;">
            <div style="color:#fca5a5; font-weight:800; font-size:1.05rem; display:flex; align-items:center; gap:0.5rem;">
                ⚠ 정말 재생성하시겠습니까?
            </div>
            <div style="color:#94a3b8; font-size:0.85rem; margin-top:0.3rem;">
                PPT {slot_num} 슬롯을 재생성 대기 목록에 추가합니다. 마지막에 "일괄 재생성" 버튼을 누르면 NLM 한도가 사용됩니다.
            </div>
        </div>
        """, unsafe_allow_html=True)
        col_y, col_n, col_pad = st.columns([1, 1, 3])
        with col_y:
            if st.button("✓ 네, 재생성", key=f"yes_regen_{slot_num}",
                         use_container_width=True, type="primary"):
                request_regenerate(slot_num)
                st.session_state.pop(confirm_key, None)
                st.rerun()
        with col_n:
            if st.button("✗ 취소", key=f"no_regen_{slot_num}", use_container_width=True):
                st.session_state.pop(confirm_key, None)
                st.rerun()
    else:
        col_pad, col_btn = st.columns([5, 1])
        with col_btn:
            if st.button("↻ 다시 생성", key=f"regen_{slot_num}",
                         use_container_width=True):
                st.session_state[confirm_key] = True
                st.rerun()


def render_batch_regen_banner(regen_list):
    """재생성 대기 슬롯이 있을 때 상단에 일괄 시작 배너 + 요약 모달."""
    if not regen_list:
        return
    pending = sorted(set(regen_list))
    n = len(pending)
    pp_str = ", ".join(f"PPT{p}" for p in pending)

    show_summary = st.session_state.get("show_batch_summary", False)

    st.markdown(f"""
    <div style="background:linear-gradient(135deg, rgba(245,158,11,0.18), rgba(15,23,42,1));
                border:2px solid #f59e0b; border-radius:14px;
                padding:1rem 1.4rem; margin-bottom:1rem;
                display:flex; align-items:center; gap:1rem;
                box-shadow:0 4px 18px rgba(245,158,11,0.25);">
        <div style="font-size:1.5rem;">↻</div>
        <div style="flex:1;">
            <div style="color:#fde68a; font-weight:800; font-size:1rem;">
                재생성 대기: {n}개 슬롯
            </div>
            <div style="color:#fcd34d; font-size:0.82rem;">
                {pp_str} · 모두 마치셨으면 "일괄 재생성 시작" 클릭 (NLM 한도 {n}회 사용)
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not show_summary:
        col_pad, col_review, col_clear = st.columns([3, 1.5, 1])
        with col_review:
            if st.button(f"🚀 일괄 재생성 시작 ({n}개)", key="batch_regen_review",
                         use_container_width=True, type="primary"):
                st.session_state.show_batch_summary = True
                st.rerun()
        with col_clear:
            if st.button("전체 취소", key="batch_regen_clear", use_container_width=True):
                for s in pending:
                    cancel_regenerate(s)
                st.rerun()
    else:
        # 요약 화면 — 마지막 확인
        data = load_sel()
        prompts = data.get("prompts", {})
        st.markdown(f"""
        <div style="background:linear-gradient(135deg, #1e293b, #0f172a);
                    border:2px solid #fbbf24; border-radius:16px;
                    padding:1.5rem 1.8rem; margin-bottom:1rem;
                    box-shadow:0 8px 30px rgba(251,191,36,0.25);">
            <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:1rem;">
                <span style="font-size:1.4rem;">⚠</span>
                <span style="font-size:1.2rem; font-weight:900; color:#fbbf24;">
                    마지막 확인 — {n}개 슬롯 NLM 재생성
                </span>
            </div>
            <div style="color:#94a3b8; font-size:0.88rem; margin-bottom:1rem;">
                아래 슬롯들과 입력하신 프롬프트를 확인하시고 "확정 — NLM 보내기" 클릭하면 재생성이 시작됩니다.
                <br>NLM 한도 <b style="color:#fde68a;">{n}회</b>가 사용됩니다.
            </div>
        """, unsafe_allow_html=True)
        for s in pending:
            slot_obj = next((x for x in SLOTS if x["num"] == s), {})
            desc = slot_obj.get("desc", "").split("—")[0].strip()
            user_prompt = prompts.get(s, "").strip() or "(추가 프롬프트 없음 — 다른 톤으로 재생성)"
            st.markdown(f"""
            <div style="background:rgba(15,23,42,0.6); border-left:4px solid #fbbf24;
                        border-radius:8px; padding:0.7rem 1rem; margin-bottom:0.5rem;">
                <div style="color:#fde68a; font-weight:700; font-size:0.95rem;">PPT {s} · {desc}</div>
                <div style="color:#cbd5e1; font-size:0.8rem; margin-top:0.2rem;">
                    💬 {user_prompt}
                </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        col_pad, col_send, col_back = st.columns([3, 1.5, 1])
        with col_send:
            if st.button("✓ 확정 — NLM 보내기", key="batch_regen_send",
                         use_container_width=True, type="primary"):
                write_trigger(pending)
                st.session_state.show_batch_summary = False
                st.success(f"NLM에 {n}개 슬롯 재생성 요청을 보냈습니다.")
                st.rerun()
        with col_back:
            if st.button("← 돌아가기", key="batch_regen_back", use_container_width=True):
                st.session_state.show_batch_summary = False
                st.rerun()


# ──────────────────────────────────────────────
# 네비게이션
# ──────────────────────────────────────────────
def render_text_slide(slot):
    """텍스트 슬롯에 대해 자동 생성된 PPT 이미지 표시."""
    text_img = IMAGES_DIR / f"text_PP{slot['num']}.png"
    if not text_img.exists():
        st.info(f"텍스트 슬라이드(text_PP{slot['num']}.png)가 없습니다. `python scripts/generate_text_slides.py <설교폴더>` 실행하세요.")
        return
    thumb = _b64(str(text_img), max_width=1200)
    st.markdown(f"""
    <div style="background:#1e293b; border:2px solid #fbbf24; border-radius:14px;
                padding:1rem; margin-top:0.5rem;">
        <div style="font-size:0.85rem; color:#fbbf24; font-weight:700; margin-bottom:0.6rem;
                    display:flex; align-items:center; gap:0.5rem;">
            <span>📜</span>
            <span>본문 슬라이드 (자동 생성됨 — PPT에 그대로 사용)</span>
        </div>
        <img src="data:image/png;base64,{thumb}" style="width:100%; border-radius:10px; cursor:zoom-in;" class="cand-img-wrap">
    </div>
    """, unsafe_allow_html=True)


def render_navigation(cur_idx, selected, regen_list):
    total = len(ALL_SLOT_NUMS)
    cur_num = ALL_SLOT_NUMS[cur_idx]

    st.markdown('<div class="nav-bar">', unsafe_allow_html=True)
    col_p, col_info, col_n = st.columns([1, 3, 1], gap="small")
    with col_p:
        if cur_idx > 0:
            if st.button("← 이전 슬롯", key="nav_prev", use_container_width=True):
                st.session_state.current_idx = cur_idx - 1
                st.rerun()
        else:
            st.button("←", key="nav_prev_disabled", use_container_width=True, disabled=True)
    with col_info:
        st.markdown(f"""
        <div style="text-align:center; padding-top:0.5rem; color:#94a3b8; font-size:0.95rem;">
            <span style="color:#fbbf24; font-weight:800;">PPT {cur_num}</span>
            <span style="margin:0 0.5rem;">·</span>
            <span>{cur_idx + 1} / {total}</span>
        </div>
        """, unsafe_allow_html=True)
    with col_n:
        if cur_idx < total - 1:
            if st.button("다음 슬롯 →", key="nav_next", use_container_width=True, type="primary"):
                st.session_state.current_idx = cur_idx + 1
                st.rerun()
        else:
            done_all = all(s in selected for s in IMAGE_SLOT_NUMS) and not regen_list  # 컨펌은 이미지 슬롯만 검증
            if done_all:
                if st.button("🎉 최종 컨펌", key="confirm_final", use_container_width=True, type="primary"):
                    d = load_sel()
                    d["status"] = "confirmed"
                    save_sel(d)
                    # 컨펌 즉시 후속 처리 3단계 자동 실행
                    import subprocess as _sp
                    import os as _os
                    _logs = []
                    _ok = True

                    # [1] post_confirm.py — 원고에 이미지 삽입 + sync + preview 갱신
                    _post_script = Path(__file__).parent / "post_confirm.py"
                    if _post_script.exists():
                        try:
                            _r = _sp.run(
                                [sys.executable, str(_post_script), str(SERMON_DIR)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=120,
                            )
                            _logs.append("=== [1] post_confirm.py ===\n" + (_r.stdout or "") + (_r.stderr or ""))
                            _ok = _ok and (_r.returncode == 0)
                        except Exception as _e:
                            _logs.append(f"=== [1] post_confirm 실패: {_e} ===")
                            _ok = False

                    # [2] 미리보기 브라우저 자동 오픈
                    _preview = SERMON_DIR / "preview.html"
                    if _preview.exists():
                        try:
                            _os.startfile(str(_preview))  # type: ignore[attr-defined]
                            _logs.append(f"=== [2] preview.html 브라우저 오픈 ===\n{_preview}")
                        except Exception as _e:
                            _logs.append(f"=== [2] 브라우저 오픈 실패: {_e} ===")

                    # [3] PPT 생성은 자동으로 하지 않음 — 컨펌 화면에서 신교수님이 별도 버튼으로 트리거

                    st.session_state["_post_confirm_log"] = "\n\n".join(_logs)
                    st.session_state["_post_confirm_ok"] = _ok
                    st.rerun()
            else:
                rem = [s for s in IMAGE_SLOT_NUMS if s not in selected]
                st.button(f"미선택 {len(rem)}개", disabled=True, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 갤러리 모드 (전체 보기)
# ──────────────────────────────────────────────
def render_gallery_mode(selected):
    st.markdown("""
    <div style="background:linear-gradient(135deg, #1e293b, #0f172a); border:1px solid #334155;
                border-radius:14px; padding:1.2rem 1.6rem; margin-bottom:1rem;">
        <div style="font-size:1.2rem; font-weight:800; color:#f1f5f9;">
            🖼 전체 갤러리 — 6 세트 모든 슬라이드
        </div>
        <div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem;">
            이미지 클릭 → 큰 화면 슬라이드쇼 (←→ 키로 이동) · 카드 아래 드롭다운으로 슬롯에 직접 매핑
        </div>
    </div>
    """, unsafe_allow_html=True)

    all_sets = get_all_set_images()
    selected_paths = {v: k for k, v in selected.items()}  # img_name → slot_num

    # 슬롯 옵션 ("미선택" + 이미지 슬롯 번호들)
    slot_options = ["(미적용)"] + [f"PPT{n}" for n in IMAGE_SLOT_NUMS]

    for prefix, images in all_sets.items():
        style = STYLE_NAMES.get(prefix, {"name": prefix, "color": "#94a3b8", "emoji": "•", "desc": ""})

        # 세트 헤더 + 다운로드 버튼 — 같은 박스 안에 통합 (병렬 정렬)
        header_box_html = (
            f'<div style="background:linear-gradient(135deg, rgba(30,41,59,0.95), rgba(15,23,42,0.95));'
            f'border:1px solid #334155;'
            f'border-left:5px solid {style["color"]};'
            f'border-radius:12px;'
            f'padding:0 1.4rem;'
            f'margin:2rem 0 1rem 0;'
            f'box-shadow:0 4px 14px rgba(0,0,0,0.3);'
            f'height:64px;'
            f'display:flex; align-items:center;">'
            f'<div style="display:flex; align-items:baseline; gap:0.8rem; flex-wrap:wrap; flex:1;">'
            f'<span style="font-size:1.4rem; font-weight:900; color:{style["color"]};">'
            f'{style["emoji"]} {style["name"]}'
            f'</span>'
            f'<span style="color:#cbd5e1; font-size:0.95rem; font-weight:600;">'
            f'{len(images)}장'
            f'</span>'
            f'<span style="color:#94a3b8; font-size:0.85rem;">· {style.get("desc", "")}</span>'
            f'</div>'
            f'</div>'
        )
        col_h, col_dl = st.columns([5, 1], gap="small")
        with col_h:
            st.markdown(header_box_html, unsafe_allow_html=True)
        with col_dl:
            pptx_path = SERMON_DIR / "raw" / f"{prefix}.pptx"
            if pptx_path.exists():
                st.download_button(
                    label="📥 PPT 1벌",
                    data=pptx_path.read_bytes(),
                    file_name=f"{SERMON_DIR.name}_{prefix}.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    key=f"dl_{prefix}",
                    use_container_width=True,
                )

        # 각 행(6개)마다 새 columns 생성 — 세로 누적·겹침 방지
        for row_start in range(0, len(images), 6):
            row_imgs = images[row_start:row_start + 6]
            row_cols = st.columns(6, gap="medium")
            for col_idx, img in enumerate(row_imgs):
                with row_cols[col_idx]:
                    bound_slot = selected_paths.get(img.name)
                    is_used = bound_slot is not None
                    cls = "picked-anywhere" if is_used else ""
                    thumb = _b64(str(img))
                    used_label = f"PPT{bound_slot}" if is_used else ""
                    slot_tag_attr = f'data-slot-tag="PPT{bound_slot}"' if is_used else ""
                    # lazy load: 라이트박스에서도 썸네일 사용 (성능 우선)
                    st.markdown(f"""
                    <div class="gal-card {cls}" {slot_tag_attr}>
                        <img src="data:image/jpeg;base64,{thumb}" data-full-src="data:image/jpeg;base64,{thumb}">
                        <div class="gal-card-label">{img.stem}{' · 사용 중 ' + used_label if used_label else ''}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    # 슬롯 매핑 드롭다운
                    cur_default = 0
                    if bound_slot:
                        try:
                            cur_default = slot_options.index(f"PPT{bound_slot}")
                        except ValueError:
                            cur_default = 0
                    pick = st.selectbox(
                        "슬롯",
                        slot_options,
                        index=cur_default,
                        key=f"map_{prefix}_{img.stem}",
                        label_visibility="collapsed",
                    )
                    if pick != "(미적용)":
                        target_num = pick.replace("PPT", "")
                        if selected.get(target_num) != img.name:
                            apply_image(target_num, img)
                            st.rerun()
                    else:
                        if bound_slot:
                            deselect_image(bound_slot)
                            st.rerun()


# ──────────────────────────────────────────────
# 컨펌 화면
# ──────────────────────────────────────────────
def render_confirmed(selected, regen_list):
    total = len(IMAGE_SLOT_NUMS)
    _ok = st.session_state.get("_post_confirm_ok", None)
    _log = st.session_state.get("_post_confirm_log", "")
    _pptx = st.session_state.get("_post_confirm_pptx", "")
    if _ok is True:
        sub_msg = f"{total}개 슬롯 확정 · 원고에 이미지 삽입 + 미리보기 자동 오픈 완료 ✓"
    elif _ok is False:
        sub_msg = f"{total}개 슬롯 확정 · ⚠ 일부 단계 실패 (아래 로그 확인)"
    else:
        sub_msg = f"{total}개 슬롯 모두 확정"
    st.markdown(f"""
    <div class="confirm-banner">
        <div class="icon">✅</div>
        <div class="title">이미지 선택 완료!</div>
        <div class="sub">{sub_msg}</div>
    </div>
    """, unsafe_allow_html=True)

    # PPT 생성은 신교수님 컨펌 후 진행 (자동 X)
    if _pptx:
        st.success(f"📊 PPT 생성 완료 → {_pptx}")
    else:
        st.markdown("---")
        st.markdown("#### 📋 다음 단계")
        st.markdown("미리보기에서 원고+이미지를 검수하신 후 — 아래 버튼으로 PPT를 만드세요.")
        if st.button("📊 PPT 만들기", key="confirm_pptx", use_container_width=True, type="primary"):
            import subprocess as _sp
            # 전 부서 공용 PPT 엔진 (네이티브 텍스트 본문 + 진네이비 밴드 표준)
            _pptx_script = Path(__file__).parent / "sermon_pptx.py"
            if _pptx_script.exists():
                with st.spinner("PPT 생성 중... (1~2분)"):
                    try:
                        _r = _sp.run(
                            [sys.executable, str(_pptx_script), str(SERMON_DIR)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=300,
                        )
                        for _line in (_r.stdout or "").splitlines():
                            if "파일:" in _line and ".pptx" in _line:
                                st.session_state["_post_confirm_pptx"] = _line.split("파일:", 1)[1].strip()
                                break
                        st.session_state["_pptx_log"] = (_r.stdout or "")[-2000:]
                        st.session_state["_pptx_ok"] = (_r.returncode == 0)
                    except Exception as _e:
                        st.session_state["_pptx_log"] = f"PPT 생성 실패: {_e}"
                        st.session_state["_pptx_ok"] = False
            st.rerun()

    if _log:
        with st.expander("🔧 후속 처리 로그", expanded=(_ok is False)):
            st.code(_log)
    _pptx_log = st.session_state.get("_pptx_log", "")
    if _pptx_log:
        with st.expander("📊 PPT 생성 로그", expanded=(st.session_state.get("_pptx_ok") is False)):
            st.code(_pptx_log)

    if st.button("↩ 다시 선택하기", use_container_width=True):
        d = load_sel()
        d["status"] = "selecting"
        save_sel(d)
        st.rerun()

    st.markdown("#### 🖼 최종 선택 이미지")
    rows = [(IMAGE_SLOT_NUMS[i:i + 4]) for i in range(0, len(IMAGE_SLOT_NUMS), 4)]
    for row in rows:
        cols = st.columns(len(row))
        for i, slot_num in enumerate(row):
            with cols[i]:
                ppt_img = IMAGES_DIR / f"ppt_{slot_num}.png"
                slot = next((s for s in SLOTS if s["num"] == slot_num), {})
                desc = (slot.get("desc") or "").split("—")[0].strip()
                if ppt_img.exists():
                    st.image(str(ppt_img), use_container_width=True)
                    st.caption(f"PPT {slot_num} · {desc}")
                else:
                    st.markdown(
                        f"<div style='aspect-ratio:16/9; background:#1f2937; border-radius:10px;"
                        f" display:flex; align-items:center; justify-content:center; color:#64748b;'>"
                        f"PPT {slot_num} 미선택</div>",
                        unsafe_allow_html=True,
                    )


# ──────────────────────────────────────────────
# 재생성 대기
# ──────────────────────────────────────────────
def render_processing(trigger):
    slots = trigger.get("slots", [])
    status = trigger.get("status", "requested")
    icon = "🔄" if status == "requested" else "↻"
    text = "Claude가 새 이미지를 만들고 있습니다…" if status == "requested" \
        else "NLM에서 새 이미지를 만드는 중…"
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                border: 2px solid #3b82f6; border-radius: 16px;
                padding: 3rem 2rem; text-align: center;">
        <div style="font-size:3rem;">{icon}</div>
        <div style="font-size:1.4rem; font-weight:800; color:#f1f5f9; margin-top:0.5rem;">
            이미지 재생성 진행 중
        </div>
        <div style="color:#94a3b8; margin-top:0.5rem;">
            PPT {', '.join(slots)} · {text}
        </div>
    </div>
    """, unsafe_allow_html=True)
    components.html(
        "<script>setTimeout(() => window.parent.location.reload(), 6000)</script>",
        height=0,
    )


if __name__ == "__main__":
    main()
