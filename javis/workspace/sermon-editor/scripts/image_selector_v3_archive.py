"""이미지 선택기 v3 — 7벌 체제 + 반복 재생성 루프

워크플로우:
  [1] Claude가 NLM에서 7벌 생성 → 품질 검수 → PPT 슬롯 매핑
  [2] 목사님이 브라우저에서 확인 → 선택 / 다시 생성 표시
  [3] Claude가 재생성 요청 감지 → 해당 슬롯만 재생성
  [4] 반복 → 전체 최종 컨펌 → 다음 단계 진행

사용: streamlit run scripts/image_selector.py --server.port 8503 -- --dir <설교폴더>
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
    dirs = sorted([d for d in project.iterdir() if d.is_dir() and d.name[:8].isdigit()], reverse=True)
    return dirs[0] if dirs else project

SERMON_DIR = get_sermon_dir()
IMAGES_DIR = SERMON_DIR / "images"
SELECTION_FILE = IMAGES_DIR / "_selection.json"
TRIGGER_FILE = IMAGES_DIR / "_trigger.json"

# ──────────────────────────────────────────────
# PPT 슬롯 정의
# 1) 작업 폴더에 slots.json 이 있으면 그것을 로드 (커스텀 슬롯)
#    - num: 슬롯 번호 (두 자리 문자열)
#    - desc: 슬롯 주제 (한국어)
#    - has_image: true=이미지 슬롯, false=텍스트 본문 전용
#    - candidates: {"A": "01", "B": "04", ...} 세트별 매핑된 NLM 페이지 번호 (선택)
# 2) 없으면 images/ 폴더의 PNG 페이지 번호로 자동 슬롯 생성
# ──────────────────────────────────────────────
SLOT_CANDIDATES = {}  # slot_num → {prefix: page_num}

def _build_all_ppt():
    global SLOT_CANDIDATES
    SLOT_CANDIDATES = {}

    slots_file = SERMON_DIR / "slots.json"
    if slots_file.exists():
        try:
            data = json.loads(slots_file.read_text(encoding="utf-8"))
            result = []
            for s in data:
                num = s["num"]
                result.append((num, s["desc"], s.get("has_image", True)))
                cand = s.get("candidates")
                if isinstance(cand, dict):
                    SLOT_CANDIDATES[num] = {
                        prefix: page for prefix, page in cand.items() if page
                    }
            return result
        except Exception as e:
            print(f"[WARN] slots.json 로드 실패: {e}")

    # 자동 감지: 모든 PNG에서 최대 페이지 번호
    max_page = 0
    if IMAGES_DIR.exists():
        for f in IMAGES_DIR.glob("*.png"):
            if f.name.startswith("ppt_") or f.name.startswith("_"):
                continue
            parts = f.stem.rsplit("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                max_page = max(max_page, int(parts[1]))

    if max_page == 0:
        return []
    return [(f"{i:02d}", f"페이지 {i}", True) for i in range(1, max_page + 1)]

ALL_PPT = _build_all_ppt()
IMAGE_SLOTS = [num for num, _, has in ALL_PPT if has]

# ──────────────────────────────────────────────
# 스타일(세트) 자동 감지 — 7벌 체제
# ──────────────────────────────────────────────
PALETTE = [
    "#ef4444", "#a855f7", "#3b82f6", "#f59e0b",
    "#22c55e", "#06b6d4", "#e11d48", "#94a3b8",
    "#f97316", "#8b5cf6", "#14b8a6", "#ec4899",
]
EMOJI_LIST = ["🎬", "🧸", "💎", "🎨", "✨", "🌅", "🔥", "📑", "🌊", "💫", "🍀", "🎯"]

def detect_styles():
    """images/ 폴더에서 {prefix}_{NN}.png 패턴을 자동 감지하여 스타일 목록 생성"""
    prefixes = {}
    if not IMAGES_DIR.exists():
        return []
    for f in sorted(IMAGES_DIR.glob("*.png")):
        if f.name.startswith("ppt_") or f.name.startswith("_"):
            continue
        parts = f.stem.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            prefix = parts[0]
            if prefix not in prefixes:
                prefixes[prefix] = 0
            prefixes[prefix] += 1
    styles = []
    for i, (prefix, count) in enumerate(prefixes.items()):
        color = PALETTE[i % len(PALETTE)]
        emoji = EMOJI_LIST[i % len(EMOJI_LIST)]
        styles.append((prefix, f"{emoji} {prefix}", color))
    return styles


def detect_new_prefixes():
    """최근 2시간 이내 생성된 세트 프리픽스를 반환 (NEW 표시용)"""
    import time as _time
    threshold = _time.time() - 7200  # 2시간
    new = set()
    if not IMAGES_DIR.exists():
        return new
    for f in IMAGES_DIR.glob("*.png"):
        if f.name.startswith("ppt_") or f.name.startswith("_"):
            continue
        parts = f.stem.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            if f.stat().st_mtime > threshold:
                new.add(parts[0])
    return new

# ──────────────────────────────────────────────
# 상태 관리
# ──────────────────────────────────────────────
def load_sel():
    if SELECTION_FILE.exists():
        return json.loads(SELECTION_FILE.read_text(encoding="utf-8"))
    return {"selected": {}, "regenerate": [], "status": "selecting"}

def save_sel(data):
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
    """재생성 트리거 — 사용자 프롬프트 포함"""
    data = load_sel()
    prompts = data.get("prompts", {})
    # 슬롯별 사용자 프롬프트 수집
    slot_prompts = {}
    for s in slots:
        if s in prompts and prompts[s].strip():
            slot_prompts[s] = prompts[s].strip()
    trigger = {
        "action": "regenerate",
        "slots": slots,
        "prompts": slot_prompts,
        "status": "requested",
        "timestamp": datetime.now().isoformat(),
    }
    TRIGGER_FILE.write_text(json.dumps(trigger, ensure_ascii=False, indent=2), encoding="utf-8")

def get_candidates(slot_num, styles):
    """슬롯의 후보 이미지 목록.

    SLOT_CANDIDATES (slots.json의 candidates 필드)에 매핑이 있으면
    그 페이지 번호를 사용하고, 없으면 슬롯 번호 = 페이지 번호 단순 매칭.
    """
    candidates = []
    mapping = SLOT_CANDIDATES.get(slot_num, {})
    for prefix, label, color in styles:
        if prefix in mapping:
            page = mapping[prefix]
            img = IMAGES_DIR / f"{prefix}_{page}.png"
        else:
            # 매핑 없을 때 슬롯 번호 = 페이지 번호로 폴백
            img = IMAGES_DIR / f"{prefix}_{slot_num}.png"
        if img.exists():
            candidates.append((prefix, label, color, img))
    return candidates


def deselect_image(slot):
    """슬롯 선택 해제 — 신교수님이 '✅ 선택됨' 다시 누르면 호출"""
    data = load_sel()
    if slot in data.get("selected", {}):
        del data["selected"][slot]
    ppt_img = IMAGES_DIR / f"ppt_{slot}.png"
    if ppt_img.exists():
        ppt_img.unlink()
    data["status"] = "selecting"
    save_sel(data)

def get_all_images_by_style(styles):
    result = {}
    for prefix, label, color in styles:
        imgs = sorted(IMAGES_DIR.glob(f"{prefix}_*.png"))
        if imgs:
            result[prefix] = {"label": label, "color": color, "images": imgs}
    return result

# ──────────────────────────────────────────────
# base64 캐시 — 썸네일 (그리드용, 빠름)
# ──────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _b64(path_str: str, max_width: int = 400) -> str:
    """그리드용 썸네일 base64 (400px JPEG ~30KB)"""
    try:
        from PIL import Image
        import io as _io
        img = Image.open(path_str)
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (30, 41, 59))
            bg.paste(img, mask=img.split()[3])
            img = bg
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        with open(path_str, "rb") as f:
            return base64.b64encode(f.read()).decode()


@st.cache_data(show_spinner=False)
def _b64_full(path_str: str) -> str:
    """원본 base64 (라이트박스용)"""
    with open(path_str, "rb") as f:
        return base64.b64encode(f.read()).decode()

# ──────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────
st.set_page_config(page_title="이미지 선택기", page_icon="🎨", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');
    .stApp { background: #0f172a; font-family: 'Noto Sans KR', sans-serif; }
    header[data-testid="stHeader"] { display: none; }
    .block-container { padding-top: 0.3rem; padding-bottom: 1rem; }

    .sec-img {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
        border: 1px solid #2d4a6f; border-radius: 10px;
        padding: 0.6rem 1.2rem; margin-top: 1rem; margin-bottom: 0.4rem;
        display: flex; align-items: center; gap: 0.6rem;
    }
    .sec-text {
        background: #1e293b; border: 1px solid #334155; border-radius: 8px;
        padding: 0.4rem 1.2rem; margin-top: 0.5rem; margin-bottom: 0.2rem;
        display: flex; align-items: center; gap: 0.6rem; opacity: 0.6;
    }
    .sec-num {
        font-size: 1.2rem; font-weight: 900;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        min-width: 55px;
    }
    .sec-text .sec-num {
        background: linear-gradient(135deg, #64748b, #475569);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .sec-desc { font-size: 0.82rem; color: #94a3b8; flex-grow: 1; }
    .badge { font-size: 0.65rem; font-weight: 600; padding: 2px 10px; border-radius: 8px; white-space: nowrap; }
    .badge-done { background: rgba(34,197,94,0.15); color: #4ade80; }
    .badge-regen { background: rgba(239,68,68,0.15); color: #f87171; }
    .badge-wait { background: rgba(100,116,139,0.15); color: #64748b; }
    .badge-noimg { background: rgba(100,116,139,0.1); color: #475569; }

    .img-wrap {
        background: #1e293b; border: 2px solid #334155; border-radius: 10px;
        padding: 4px; position: relative; transition: all 0.15s;
    }
    .img-wrap:hover { border-color: #60a5fa; }
    .img-wrap.picked { border-color: #22c55e; box-shadow: 0 0 14px rgba(34,197,94,0.35); }
    .img-wrap.is-new { border-color: #f59e0b; box-shadow: 0 0 10px rgba(245,158,11,0.3); }
    .img-wrap.is-new.picked { border-color: #22c55e; box-shadow: 0 0 14px rgba(34,197,94,0.35); }
    .new-tag {
        position: absolute; bottom: 6px; left: 6px;
        background: linear-gradient(135deg, #f59e0b, #ef4444);
        color: #fff; font-size: 0.55rem; font-weight: 800;
        padding: 1px 6px; border-radius: 4px;
        letter-spacing: 0.5px; animation: new-pulse 1.5s ease-in-out infinite;
    }
    @keyframes new-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    .img-wrap img { width: 100%; border-radius: 7px; display: block; }
    .img-num {
        position: absolute; top: 6px; left: 6px;
        background: rgba(0,0,0,0.75); color: #f1f5f9;
        font-size: 0.7rem; font-weight: 700;
        width: 22px; height: 22px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
    }
    .img-tag {
        position: absolute; top: 6px; right: 6px;
        font-size: 0.5rem; font-weight: 600;
        padding: 1px 5px; border-radius: 4px;
    }
    .img-label { text-align: center; font-size: 0.6rem; color: #64748b; margin-top: 2px; }

    .gal-card {
        background: #1e293b; border: 2px solid #334155; border-radius: 12px;
        padding: 6px; text-align: center; transition: all 0.2s; cursor: pointer;
    }
    .gal-card:hover { border-color: #3b82f6; transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.4); }
    .gal-card img { width: 100%; border-radius: 8px; }
    .gal-label { font-size: 0.8rem; font-weight: 600; margin-top: 4px; }
    .gal-sub { font-size: 0.65rem; color: #64748b; }

    .processing {
        background: linear-gradient(135deg, #1e3a5f, #0f172a);
        border: 2px solid #3b82f6; border-radius: 16px;
        padding: 3rem 2rem; text-align: center; margin: 2rem 0;
        animation: pulse-border 2s ease-in-out infinite;
    }
    @keyframes pulse-border {
        0%, 100% { border-color: #3b82f6; box-shadow: 0 0 10px rgba(59,130,246,0.2); }
        50% { border-color: #8b5cf6; box-shadow: 0 0 25px rgba(139,92,246,0.3); }
    }
    .processing .icon { font-size: 3rem; margin-bottom: 0.5rem; }
    .processing .title { font-size: 1.3rem; font-weight: 700; color: #f1f5f9; }
    .processing .sub { font-size: 0.85rem; color: #94a3b8; margin-top: 0.3rem; }

    /* 라이트박스 (이미지 크게 보기) */
    .lightbox-overlay {
        display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0,0,0,0.85); z-index: 99999;
        justify-content: center; align-items: center; cursor: pointer;
    }
    .lightbox-overlay.active { display: flex; }
    .lightbox-overlay img {
        max-width: 90vw; max-height: 90vh; border-radius: 12px;
        box-shadow: 0 0 40px rgba(0,0,0,0.8);
    }
    .lightbox-label {
        position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%);
        color: #94a3b8; font-size: 0.9rem; font-weight: 500; z-index: 100000;
    }
    .img-wrap img { cursor: pointer; }

    /* Claude 알림 버튼 — 진한 빨강 (primary만) */
    button[kind="primary"] {
        background: linear-gradient(135deg, #dc2626, #991b1b) !important;
        border: none !important;
        color: #fff !important;
        font-weight: 800 !important;
        box-shadow: 0 2px 12px rgba(220,38,38,0.4) !important;
    }
    button[kind="primary"]:hover {
        background: linear-gradient(135deg, #ef4444, #b91c1c) !important;
        box-shadow: 0 4px 20px rgba(239,68,68,0.6) !important;
    }
    /* 선택됨 — 하늘색 (disabled secondary만) */
    button[kind="secondary"][disabled] {
        background: linear-gradient(135deg, #38bdf8, #0ea5e9) !important;
        border: none !important;
        color: #fff !important;
        font-weight: 700 !important;
        opacity: 1 !important;
    }
    /* 새 이미지 선택 — 주황 반짝임 */
    .new-btn-wrap button {
        background: linear-gradient(135deg, #f59e0b, #ef4444, #f59e0b) !important;
        background-size: 200% 100% !important;
        animation: btn-shimmer 2s ease-in-out infinite !important;
        border: none !important;
        color: #fff !important;
        font-weight: 800 !important;
    }
    @keyframes btn-shimmer {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* 최종 컨펌 배너 */
    .confirmed-banner {
        background: linear-gradient(135deg, #065f46, #0f172a, #14532d);
        border: 2px solid #22c55e; border-radius: 16px;
        padding: 2rem; text-align: center; margin: 1rem 0;
        animation: banner-glow 2s ease-in-out infinite;
    }
    @keyframes banner-glow {
        0%, 100% { box-shadow: 0 0 10px rgba(34,197,94,0.2); }
        50% { box-shadow: 0 0 30px rgba(34,197,94,0.4); }
    }
</style>
""", unsafe_allow_html=True)

# 라이트박스 오버레이 + JS (이미지 클릭 → 크게 보기)
components.html("""
<div id="lb-overlay" class="lightbox-overlay" onclick="this.classList.remove('active')">
    <img id="lb-img" src="">
    <div id="lb-label" class="lightbox-label"></div>
</div>
<style>
    .lightbox-overlay {
        display:none; position:fixed; top:0; left:0; width:100vw; height:100vh;
        background:rgba(0,0,0,0.88); z-index:99999;
        justify-content:center; align-items:center; cursor:pointer;
    }
    .lightbox-overlay.active { display:flex; }
    .lightbox-overlay img {
        max-width:92vw; max-height:88vh; border-radius:12px;
        box-shadow:0 0 60px rgba(0,0,0,0.9); object-fit:contain;
    }
    .lightbox-label {
        position:fixed; bottom:24px; left:50%; transform:translateX(-50%);
        color:#94a3b8; font-size:1rem; font-weight:500; z-index:100000;
        background:rgba(0,0,0,0.6); padding:4px 16px; border-radius:8px;
    }
</style>
<script>
(function() {
    var P = window.parent.document;
    // 부모 문서에 오버레이 삽입 (한 번만)
    if (!P.getElementById('lb-overlay-parent')) {
        var overlay = document.createElement('div');
        overlay.id = 'lb-overlay-parent';
        overlay.style.cssText = 'display:none;position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.88);z-index:99999;justify-content:center;align-items:center;cursor:pointer;';
        overlay.innerHTML = '<img id="lb-img-p" style="max-width:92vw;max-height:88vh;border-radius:12px;box-shadow:0 0 60px rgba(0,0,0,0.9);object-fit:contain;" /><div id="lb-label-p" style="position:fixed;bottom:24px;left:50%;transform:translateX(-50%);color:#94a3b8;font-size:1rem;font-weight:500;background:rgba(0,0,0,0.6);padding:4px 16px;border-radius:8px;"></div>';
        overlay.onclick = function() { this.style.display = 'none'; };
        P.body.appendChild(overlay);
    }
    // img-wrap 안의 이미지 클릭 이벤트
    function attach() {
        var wraps = P.querySelectorAll('.img-wrap img, .cascade-img img');
        wraps.forEach(function(img) {
            if (img._lbReady) return;
            img._lbReady = true;
            img.style.cursor = 'pointer';
            img.addEventListener('click', function(e) {
                e.stopPropagation();
                var ov = P.getElementById('lb-overlay-parent');
                var lbImg = P.getElementById('lb-img-p');
                var lbLabel = P.getElementById('lb-label-p');
                lbImg.src = this.src;
                var labelEl = this.closest('.img-wrap') ? this.closest('.img-wrap').nextElementSibling : null;
                lbLabel.textContent = labelEl ? labelEl.textContent : '';
                ov.style.display = 'flex';
            });
        });
    }
    attach();
    // Streamlit 리렌더링 후 재연결
    new MutationObserver(function() { setTimeout(attach, 300); })
        .observe(P.body, {childList: true, subtree: true});
})();
</script>
""", height=0)


# ──────────────────────────────────────────────
# 메인 라우터
# ──────────────────────────────────────────────
def main():
    if "gallery_set" not in st.session_state:
        st.session_state.gallery_set = None

    # 트리거 처리 중이면 대기 화면
    if TRIGGER_FILE.exists():
        trigger = json.loads(TRIGGER_FILE.read_text(encoding="utf-8"))
        if trigger.get("status") in ("requested", "processing"):
            render_processing(trigger)
            return
        if trigger.get("status") == "reviewing":
            render_reviewing(trigger)
            return

    # 갤러리 상세 뷰
    if st.session_state.gallery_set:
        render_gallery_detail(st.session_state.gallery_set)
        return

    # 메인 선택기
    render_selector()


# ──────────────────────────────────────────────
# 재생성 대기 화면
# ──────────────────────────────────────────────
def render_processing(trigger):
    slots = trigger.get("slots", [])
    status = trigger.get("status", "requested")
    ts = trigger.get("timestamp", "")

    if status == "requested":
        status_text = "auto_regen.py가 곧 감지합니다..."
        icon = "⏳"
    else:
        status_text = "NLM에서 새 이미지를 생성하고 있습니다"
        icon = "🔄"

    # 기존 세트 수 표시
    existing = len(detect_styles())

    st.markdown(f"""
    <div class="processing">
        <div class="icon">{icon}</div>
        <div class="title">이미지 재생성 중...</div>
        <div class="sub">PPT {', '.join(slots)} · {status_text}</div>
        <div class="sub" style="margin-top:0.8rem; font-size:0.72rem; color:#64748b;">
            현재 {existing}세트 보유 · 완료되면 자동으로 새 이미지가 표시됩니다
        </div>
        <div class="sub" style="margin-top:0.3rem; font-size:0.65rem; color:#475569;">
            {ts[:19] if ts else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)
    components.html(
        "<script>setTimeout(() => window.parent.location.reload(), 5000)</script>",
        height=0,
    )


def render_reviewing(trigger):
    """Claude가 이미지를 검수하고 슬롯에 매핑하는 중"""
    slots = trigger.get("slots", [])
    st.markdown(f"""
    <div class="processing" style="border-color:#f59e0b;">
        <div class="icon">🔍</div>
        <div class="title">Claude가 이미지를 검수하고 있습니다...</div>
        <div class="sub">PPT {', '.join(slots)} · 원고 내용과 비교하여 올바른 슬롯에 배치 중</div>
        <div class="sub" style="margin-top:0.8rem; font-size:0.72rem; color:#64748b;">
            이미지 추출 완료 · 슬롯 매핑 진행 중 · 완료되면 자동 새로고침
        </div>
    </div>
    """, unsafe_allow_html=True)
    components.html(
        "<script>setTimeout(() => window.parent.location.reload(), 5000)</script>",
        height=0,
    )


# ──────────────────────────────────────────────
# 메인 선택기
# ──────────────────────────────────────────────
def render_selector():
    styles = detect_styles()
    data = load_sel()
    selected = data.get("selected", {})
    regen_list = data.get("regenerate", [])
    status = data.get("status", "selecting")

    done_count = sum(1 for s in IMAGE_SLOTS if s in selected)
    regen_count = len(regen_list)
    total = len(IMAGE_SLOTS)
    num_styles = max(len(styles), 7)
    new_prefixes = detect_new_prefixes()

    # ── 최종 컨펌 완료 상태 ──
    if status == "confirmed":
        st.markdown(f"""
        <div class="confirmed-banner">
            <div style="font-size:2.5rem;">✅</div>
            <div style="font-size:1.3rem; font-weight:900; color:#4ade80; margin-top:0.3rem;">
                이미지 선택 완료!
            </div>
            <div style="font-size:0.85rem; color:#86efac; margin-top:0.3rem;">
                {total}개 슬롯 모두 확정 · Claude가 원고에 반영 중입니다
            </div>
        </div>
        """, unsafe_allow_html=True)

        def _reset_confirm():
            d = load_sel()
            d["status"] = "selecting"
            save_sel(d)
        st.button("↩️ 다시 선택하기", on_click=_reset_confirm)

        # 최종 선택 이미지 표시
        _render_final_images(selected, regen_list)
        return

    # ── 최상단: 헤더 바 (상태 + Claude 알림) ──
    def _notify_claude():
        d = load_sel()
        d["status"] = "notify_claude"
        d["message"] = datetime.now().isoformat()
        save_sel(d)
    top1, top2 = st.columns([4, 1])
    with top1:
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:0.6rem; padding:0.2rem 0;">
            <span style="font-size:0.78rem; color:#4ade80;">✅ {done_count}/{total}</span>
            {"<span style='font-size:0.78rem; color:#f87171;'>🔄 " + str(regen_count) + "</span>" if regen_count else ""}
        </div>
        """, unsafe_allow_html=True)
    with top2:
        st.button("📨 Claude에게 알림", on_click=_notify_claude,
                  type="primary", use_container_width=True)

    # ── 헤더 + 줌 버튼 ──
    zoom_level = st.session_state.get("zoom", 100)

    hdr, z1, z2, z3 = st.columns([5, 0.6, 0.5, 0.6])
    with hdr:
        st.markdown(f"""
        <div style="background:#1e293b; border:1px solid #334155; border-radius:10px;
                    padding:0.5rem 1.2rem; display:flex; align-items:center; gap:0.8rem;">
            <span style="font-size:1.1rem; font-weight:900; color:#f1f5f9;">🎨 이미지 선택기</span>
            <span style="font-size:0.7rem; color:#64748b;">{SERMON_DIR.name} · {len(styles)}벌</span>
        </div>
        """, unsafe_allow_html=True)
    with z1:
        if st.button("➖", key="zoom_out"):
            st.session_state.zoom = max(40, zoom_level - 10)
            st.rerun()
    with z2:
        st.markdown(f"""
        <div style="background:#334155; border-radius:8px; padding:0.3rem 0;
                    text-align:center; font-size:0.8rem; font-weight:700; color:#f1f5f9;">
            {zoom_level}%
        </div>""", unsafe_allow_html=True)
    with z3:
        if st.button("➕", key="zoom_in"):
            st.session_state.zoom = min(200, zoom_level + 10)
            st.rerun()

    # 줌 적용 (CSS 주입)
    if zoom_level != 100:
        st.markdown(f"""
        <style>
            .block-container {{
                transform: scale({zoom_level / 100});
                transform-origin: top left;
                width: {10000 // zoom_level}%;
            }}
        </style>
        """, unsafe_allow_html=True)

    if total > 0:
        st.progress(done_count / total)

    # ── PPT 01~14 슬롯별 이미지 ──
    for slot_num, slot_desc, has_image in ALL_PPT:

        if not has_image:
            st.markdown(f"""
            <div class="sec-text">
                <span class="sec-num">PPT {slot_num}</span>
                <span class="sec-desc">{slot_desc}</span>
                <span class="badge badge-noimg">📝 텍스트 전용</span>
            </div>
            """, unsafe_allow_html=True)
            continue

        is_selected = slot_num in selected
        is_regen = slot_num in regen_list
        candidates = get_candidates(slot_num, styles)

        if is_regen:
            badge = '<span class="badge badge-regen">🔄 다시 생성</span>'
        elif is_selected:
            badge = '<span class="badge badge-done">✅ 선택 완료</span>'
        else:
            badge = '<span class="badge badge-wait">⬜ 미선택</span>'

        st.markdown(f"""
        <div class="sec-img">
            <span class="sec-num">PPT {slot_num}</span>
            <span class="sec-desc">{slot_desc}</span>
            {badge}
        </div>
        """, unsafe_allow_html=True)

        if not candidates:
            st.caption("후보 이미지 없음")
            continue

        # NEW 이미지를 앞으로 정렬 (새 이미지 먼저 → 기존 이미지)
        new_candidates = [(p, l, c, ip) for p, l, c, ip in candidates if p in new_prefixes]
        old_candidates = [(p, l, c, ip) for p, l, c, ip in candidates if p not in new_prefixes]
        sorted_candidates = new_candidates + old_candidates

        # 그리드 열 수: 후보 수에 맞춤 (최소 7, 최대 전체)
        num_cols = min(max(len(sorted_candidates), 7), 14)
        cols = st.columns(num_cols)
        for idx, (prefix, label, color, img_path) in enumerate(sorted_candidates):
            if idx >= num_cols:
                break
            with cols[idx]:
                is_this = selected.get(slot_num) == img_path.name
                is_new = prefix in new_prefixes

                cls = "picked" if is_this else ""
                extra_style = ""
                if is_new and not is_this:
                    extra_style = "border:3px solid #f59e0b; box-shadow:0 0 16px rgba(245,158,11,0.5);"

                new_tag_html = ""
                if is_new:
                    new_tag_html = (
                        '<div style="position:absolute; bottom:6px; left:6px; z-index:10; '
                        'background:linear-gradient(135deg,#f59e0b,#ef4444); '
                        'color:#fff; font-size:0.6rem; font-weight:900; '
                        'padding:2px 8px; border-radius:4px; letter-spacing:1px; '
                        'box-shadow:0 2px 8px rgba(245,158,11,0.5);">NEW</div>'
                    )

                thumb_b64 = _b64(str(img_path))
                st.markdown(f"""
                <div class="img-wrap {cls}" style="{extra_style}">
                    <div class="img-num">{idx + 1}</div>
                    <div class="img-tag" style="background:{color}22; color:{color};">{label}</div>
                    <img src="data:image/jpeg;base64,{thumb_b64}">
                    {new_tag_html}
                </div>
                <div class="img-label">{prefix}{' 🆕' if is_new else ''}</div>
                """, unsafe_allow_html=True)

                if is_this:
                    if st.button("✅ 선택됨 (해제)",
                                 key=f"s_{slot_num}_{prefix}",
                                 type="secondary",
                                 use_container_width=True):
                        deselect_image(slot_num)
                        st.rerun()
                elif is_new:
                    st.markdown(f'<div class="new-btn-wrap">', unsafe_allow_html=True)
                    if st.button(f"⚡ 새 이미지 선택", key=f"s_{slot_num}_{prefix}",
                                 use_container_width=True):
                        apply_image(slot_num, img_path)
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    if st.button(f"선택", key=f"s_{slot_num}_{prefix}",
                                 use_container_width=True):
                        apply_image(slot_num, img_path)
                        st.rerun()

        # 다시 생성 / 취소 + 프롬프트 입력
        if is_regen:
            # 재생성 요청 상태: 주황 박스 + 프롬프트 입력 + 취소
            st.markdown(f"""
            <div style="background:rgba(245,158,11,0.1); border:2px solid #f59e0b;
                        border-radius:10px; padding:0.6rem 1rem; margin:0.3rem 0;">
                <span style="color:#f59e0b; font-weight:700; font-size:0.85rem;">
                    🔄 PPT {slot_num} 다시 생성 대기 중
                </span>
                <span style="color:#94a3b8; font-size:0.7rem; margin-left:0.5rem;">
                    아래에 원하는 이미지 설명을 입력하세요 (선택사항)
                </span>
            </div>
            """, unsafe_allow_html=True)
            prompt_col, cancel_col = st.columns([5, 1])
            with prompt_col:
                prompt_key = f"prompt_{slot_num}"
                data_prompts = load_sel().get("prompts", {})
                default_val = data_prompts.get(slot_num, "")
                user_prompt = st.text_input(
                    "원하는 이미지 설명",
                    value=default_val,
                    placeholder="예: 더 밝은 톤, 여인 2명, 십자가 강조, 새벽빛...",
                    key=prompt_key,
                    label_visibility="collapsed",
                )
                if user_prompt != default_val:
                    d = load_sel()
                    d.setdefault("prompts", {})[slot_num] = user_prompt
                    save_sel(d)
            with cancel_col:
                def _cancel(s=slot_num):
                    cancel_regenerate(s)
                    d = load_sel()
                    d.get("prompts", {}).pop(s, None)
                    save_sel(d)
                st.button("↩️ 취소", key=f"rc_{slot_num}",
                          use_container_width=True, on_click=_cancel)
        else:
            _, rc = st.columns([5, 1])
            with rc:
                def _regen(s=slot_num):
                    request_regenerate(s)
                st.button("🔄 다시 생성", key=f"r_{slot_num}",
                          use_container_width=True, on_click=_regen)

    # ──────────────────────────────────────────
    # 하단: 최종 선택 이미지
    # ──────────────────────────────────────────
    st.divider()
    _render_final_images(selected, regen_list)

    # ──────────────────────────────────────────
    # 액션 버튼 영역
    # ──────────────────────────────────────────
    st.divider()
    data = load_sel()
    regen_list = data.get("regenerate", [])
    selected = data.get("selected", {})

    # all_done: 모든 이미지 슬롯(IMAGE_SLOTS)이 채워졌는지 검증
    # selected에 has_image=false 슬롯이 추가로 있어도 무시 (이미지 슬롯만 본다)
    all_done = all(s in selected for s in IMAGE_SLOTS) and not regen_list

    # 하단 버튼: 크게/작게 | 재생성/상태 | Claude 알림 | 최종 컨펌
    b1, b2, b3, b4 = st.columns([0.8, 2, 1.2, 1.5])

    with b1:
        zoom_level2 = st.session_state.get("zoom", 100)
        zz1, zz2, zz3 = st.columns(3)
        with zz1:
            if st.button("➖", key="zoom_out2"):
                st.session_state.zoom = max(40, zoom_level2 - 10)
                st.rerun()
        with zz2:
            st.markdown(f"<div style='text-align:center;font-size:0.75rem;color:#94a3b8;padding-top:0.4rem;'>{zoom_level2}%</div>", unsafe_allow_html=True)
        with zz3:
            if st.button("➕", key="zoom_in2"):
                st.session_state.zoom = min(200, zoom_level2 + 10)
                st.rerun()

    with b2:
        if regen_list:
            def _send_trigger():
                write_trigger(regen_list)
            st.button(f"🔄 새로 생성 요청 — PPT {', '.join(regen_list)}",
                      use_container_width=True,
                      on_click=_send_trigger)
        else:
            remaining = [s for s in IMAGE_SLOTS if s not in selected and s not in regen_list]
            if remaining:
                st.info(f"미선택: PPT {', '.join(remaining)}")
            else:
                st.success(f"전체 {total}개 슬롯 선택 완료")

    with b3:
        def _notify_claude_bottom():
            d = load_sel()
            d["status"] = "notify_claude"
            d["message"] = datetime.now().isoformat()
            save_sel(d)
        st.button("📨 Claude 알림", type="primary",
                  use_container_width=True, on_click=_notify_claude_bottom)

    with b4:
        if all_done:
            def _confirm():
                d = load_sel()
                d["status"] = "confirmed"
                save_sel(d)
            st.button("🎉 최종 컨펌",
                      use_container_width=True, on_click=_confirm)
        else:
            st.button("🎉 최종 컨펌", disabled=True,
                      use_container_width=True)

    # ──────────────────────────────────────────
    # 최하단: 전체 슬라이드 갤러리
    # ──────────────────────────────────────────
    st.divider()
    st.markdown("#### 🖼️ 전체 슬라이드 갤러리")
    st.caption("각 세트의 전체 이미지를 살펴보려면 클릭하세요")

    all_styles = get_all_images_by_style(styles)
    if all_styles:
        gal_cols = st.columns(min(len(all_styles), 7))

        def _open_gallery(p):
            st.session_state.gallery_set = p

        for i, (prefix, info) in enumerate(all_styles.items()):
            if i >= 7:
                break
            with gal_cols[i]:
                first_img = info["images"][0]
                st.markdown(f"""
                <div class="gal-card">
                    <img src="data:image/jpeg;base64,{_b64(str(first_img))}">
                    <div class="gal-label" style="color:{info['color']};">{info['label']}</div>
                    <div class="gal-sub">{len(info['images'])}장</div>
                </div>
                """, unsafe_allow_html=True)
                st.button(f"📂 전체보기", key=f"gal_{prefix}",
                          use_container_width=True,
                          on_click=_open_gallery, args=(prefix,))



# ──────────────────────────────────────────────
# 최종 선택 이미지 표시
# ──────────────────────────────────────────────
def _render_final_images(selected, regen_list):
    st.markdown("#### 🖼️ 최종 선택 이미지")
    cols = st.columns(len(IMAGE_SLOTS))
    for i, slot_num in enumerate(IMAGE_SLOTS):
        with cols[i]:
            ppt_img = IMAGES_DIR / f"ppt_{slot_num}.png"
            is_regen = slot_num in regen_list
            if ppt_img.exists() and not is_regen:
                st.image(str(ppt_img), use_container_width=True)
                st.caption(f"PPT {slot_num} ✅")
            elif is_regen:
                st.markdown(
                    f"<div style='text-align:center;padding:1rem 0;'>"
                    f"<div style='font-size:1.3rem;'>🔄</div>"
                    f"<div style='font-size:0.65rem;color:#f87171;'>PPT {slot_num}</div></div>",
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    f"<div style='text-align:center;padding:1rem 0;'>"
                    f"<div style='font-size:1.3rem;'>⬜</div>"
                    f"<div style='font-size:0.65rem;color:#64748b;'>PPT {slot_num}</div></div>",
                    unsafe_allow_html=True)


# ──────────────────────────────────────────────
# 갤러리 상세 뷰 — 컴팩트 그리드
# ──────────────────────────────────────────────
def render_gallery_detail(prefix):
    styles = detect_styles()
    all_styles = get_all_images_by_style(styles)
    if prefix not in all_styles:
        st.session_state.gallery_set = None
        st.rerun()
        return

    info = all_styles[prefix]
    images = info["images"]

    def _back():
        st.session_state.gallery_set = None
    st.button("← 뒤로가기", key="back_btn", on_click=_back)

    st.markdown(f"""
    <div style="background:#1e293b; border:1px solid #334155; border-radius:10px;
                padding:0.6rem 1.2rem; margin-bottom:0.8rem;
                display:flex; align-items:center; gap:0.8rem;">
        <span style="font-size:1.2rem; font-weight:900; color:{info['color']};">{info['label']}</span>
        <span style="font-size:0.8rem; color:#94a3b8;">세트 {prefix} · {len(images)}장</span>
    </div>
    """, unsafe_allow_html=True)

    grid_html = '<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(160px, 1fr)); gap:8px; padding:4px;">'
    for i, img_path in enumerate(images):
        grid_html += f'''
        <div style="background:#1e293b; border:1px solid #334155; border-radius:8px;
                    padding:4px; text-align:center;">
            <img src="data:image/jpeg;base64,{_b64(str(img_path))}"
                 style="width:100%; border-radius:6px; display:block;">
            <div style="font-size:0.65rem; color:#94a3b8; margin-top:3px;">
                #{i+1} · {img_path.stem}
            </div>
        </div>'''
    grid_html += '</div>'
    st.markdown(grid_html, unsafe_allow_html=True)

    st.divider()
    st.button("← 선택기로 돌아가기", key="back_bottom", use_container_width=True, on_click=_back)


# ──────────────────────────────────────────────
if __name__ == "__main__":
    main()
