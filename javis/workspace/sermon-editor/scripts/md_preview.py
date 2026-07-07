"""원고.md → HTML 프리뷰 생성 (이미지 base64 인라인 삽입 + 좌측 TOC)

사용법: python scripts/md_preview.py <설교폴더>
결과:   <설교폴더>/preview.html
"""

import sys
import re
import base64
from pathlib import Path


def image_to_data_uri(img_path: Path) -> str:
    """이미지 파일을 base64 data URI로 변환"""
    suffix = img_path.suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
    mime_type = mime.get(suffix.lstrip("."), "image/png")
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime_type};base64,{b64}"


def md_to_html(md_text: str, base_dir: Path):
    """마크다운을 HTML로 변환 (이미지 base64 인라인 + 헤더 id + TOC + 섹션 래핑)

    반환: (body_html, headers)  where headers = [(level, text, id), ...]
    """
    lines = md_text.split("\n")
    html_lines = []
    headers = []
    header_counter = [0]
    section_stack = []  # 현재 열린 섹션들의 레벨 스택

    # slots.json 로드 — TOC의 PP 라벨에 한국어 제목(desc) 사용
    slots_map = {}
    try:
        import json as _json
        _sp = base_dir / "slots.json"
        if _sp.exists():
            for _s in _json.loads(_sp.read_text(encoding="utf-8")):
                slots_map[str(_s.get("num", "")).zfill(2)] = _s
    except Exception:
        pass

    in_blockquote = False
    blockquote_lines = []

    def flush_blockquote():
        nonlocal blockquote_lines
        if not blockquote_lines:
            return ""
        content = "\n".join(blockquote_lines)
        blockquote_lines = []
        return f'<div class="scripture-box">{content}</div>'

    in_table = False
    table_lines_buf = []

    def flush_table():
        nonlocal table_lines_buf
        if not table_lines_buf:
            return ""

        def parse_row(row_str):
            cells = row_str.strip('|').split('|')
            return [c.strip() for c in cells]

        def fmt(text):
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
            return text

        rows = []
        has_header_sep = False
        for tl in table_lines_buf:
            if re.match(r'^\|[\s:]*-+[\s:]*(\|[\s:]*-+[\s:]*)*\|?\s*$', tl):
                has_header_sep = True
                continue
            rows.append(parse_row(tl))

        if not rows:
            table_lines_buf = []
            return ""

        # 기본틀 테이블 감지 (One Big Message 포함)
        is_basic_frame = any("One Big Message" in '|'.join(r) for r in rows)
        cls = "sermon-table basic-frame-table" if is_basic_frame else "sermon-table"

        out = f'<table class="{cls}">'
        start = 0
        if has_header_sep and rows:
            out += '<thead><tr>'
            for cell in rows[0]:
                out += f'<th>{fmt(cell)}</th>'
            out += '</tr></thead>'
            start = 1

        out += '<tbody>'
        for row in rows[start:]:
            row_text = '|'.join(row)
            rc = ''
            if 'One Big Message' in row_text:
                rc = ' class="obm-row"'
            elif '핵심 질문' in row_text:
                rc = ' class="question-row"'
            elif '핵심 원어' in row_text:
                rc = ' class="keyword-row"'
            out += f'<tr{rc}>'
            for cell in row:
                out += f'<td>{fmt(cell)}</td>'
            out += '</tr>'
        out += '</tbody></table>'

        table_lines_buf = []
        return out

    def make_header(text: str, level: int) -> str:
        hid = f"h-{header_counter[0]}"
        header_counter[0] += 1
        headers.append((level, text, hid))
        return f'<h{level} id="{hid}">{text}</h{level}>'

    def open_section(level: int, text: str) -> str:
        """새 섹션 열기: 같거나 낮은 레벨의 열린 섹션들 닫고 새로 시작"""
        close_html = ""
        while section_stack and section_stack[-1] >= level:
            close_html += '</div></section>'
            section_stack.pop()
        header_html = make_header(text, level)
        section_stack.append(level)
        return (
            close_html +
            f'<section class="section section-level-{level}">'
            f'<div class="section-header">'
            f'<button class="section-toggle" onclick="toggleSection(this)" title="접기/펼치기">▼</button>'
            f'{header_html}'
            f'</div>'
            f'<div class="section-content">'
        )

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 인용 블록 (> ...) — 성경 말씀 박스
        if stripped.startswith(">"):
            quote_text = stripped[1:].strip()
            quote_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', quote_text)
            quote_text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', quote_text)
            if not in_blockquote:
                in_blockquote = True
            blockquote_lines.append(f"<p style='margin:2px 0;'>{quote_text}</p>" if quote_text else "<br>")
            continue
        else:
            if in_blockquote:
                html_lines.append(flush_blockquote())
                in_blockquote = False

        # 마크다운 테이블 (| ... | 형식)
        if stripped.startswith("|") and "|" in stripped[1:]:
            if not in_table:
                in_table = True
            table_lines_buf.append(stripped)
            continue
        else:
            if in_table:
                html_lines.append(flush_table())
                in_table = False

        # ▶PP{n} 슬라이드 마커 — TOC 레벨 4로 등록 + 본문에 앵커 삽입
        pp_m = re.match(r'^▶PP(\d+)\s*$', stripped)
        if pp_m:
            pp_num = pp_m.group(1)
            pp_hid = f'pp-{pp_num}'
            label = f"PP{pp_num}"
            # 1순위: slots.json의 한국어 제목(desc) — "PP2 · 🖼 저울 실물"
            _slot = slots_map.get(pp_num.zfill(2))
            if _slot:
                _title = (_slot.get("desc") or "").split("—")[0].strip()[:24]
                _icon = "🖼" if _slot.get("has_image") else "📖"
                label = f"PP{pp_num} · {_icon} {_title}" if _title else f"PP{pp_num} · {_icon}"
            else:
                # 2순위(폴백): 원고 [이미지]/[본문] 설명에서 추출 (음표 표기 제거)
                for j in range(i + 1, min(i + 4, len(lines))):
                    nxt = lines[j].strip()
                    if not nxt:
                        continue
                    br_m = re.match(r'^\[([^\]]+)\]\s*(.*)', nxt)
                    if br_m:
                        kind = br_m.group(1)
                        desc = br_m.group(2).strip()
                        if '이미지' in kind:
                            short_kind = '🖼 이미지'
                        elif '본문' in kind:
                            short_kind = '📖 본문'
                        elif '원어' in kind:
                            short_kind = '🔤 원어'
                        else:
                            short_kind = kind
                        label = f"PP{pp_num} · {short_kind} — {desc[:18]}" if desc else f"PP{pp_num} · {short_kind}"
                    break
            headers.append((4, label, pp_hid))
            # 본문 마커에도 TOC와 동일한 제목 표시 (목차↔본문 일치)
            _ltitle = label.split(" · ", 1)[1] if " · " in label else ""
            _title_span = f'<span class="pp-marker-title">{_ltitle}</span>' if _ltitle else ''
            html_lines.append(
                f'<div id="{pp_hid}" class="pp-marker">'
                f'<span class="pp-num-box">▶ PP{pp_num}</span>'
                f'{_title_span}'
                f'</div>'
            )
            continue

        # 이미지: ![alt](path)
        img_match = re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', line)
        if img_match:
            for alt, src in img_match:
                img_path = base_dir / src
                if img_path.exists():
                    data_uri = image_to_data_uri(img_path)
                    img_tag = f'<img src="{data_uri}" alt="{alt}" style="max-width:100%; border-radius:8px; margin:8px 0 0 0; display:block;">'
                else:
                    img_tag = f'<span style="color:#f87171;">[이미지 없음: {src}]</span>'
                line = line.replace(f"![{alt}]({src})", img_tag)

        # 헤더 (id 부여 + TOC 수집 + 섹션 래핑)
        if stripped.startswith("### "):
            line = open_section(3, stripped[4:])
        elif stripped.startswith("## "):
            line = open_section(2, stripped[3:])
        elif stripped.startswith("# "):
            line = open_section(1, stripped[2:])
        # 수평선
        elif stripped == "---":
            line = '<hr style="border-color:#334155; margin:1.5rem 0;">'
        elif stripped.startswith("───"):
            line = '<div style="border-top:2px solid #f59e0b; margin:1.5rem 0;"></div>'
        # 코드블록 (간단 처리)
        elif stripped.startswith("```"):
            line = ""
        # 빈 줄
        elif stripped == "":
            line = "<br>"
        # 슬라이드 설명 [이미지]/[본문슬라이드] — 본문과 구분되게 차분한 회색 이탤릭
        elif stripped.startswith("[이미지]") or stripped.startswith("[본문슬라이드]"):
            # 이미지 바로 아래 바짝 붙이기: 직전 빈 줄(<br>) 제거 + 위 마진 최소화
            while html_lines and html_lines[-1] == "<br>":
                html_lines.pop()
            line = f'<p style="color:#94a3b8; font-style:italic; font-size:0.92em; margin:3px 0 16px 0;">{stripped}</p>'
        else:
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            line = re.sub(r'\*(.+?)\*', r'<em>\1</em>', line)
            line = f"<p>{line}</p>"

        html_lines.append(line)

    if in_blockquote:
        html_lines.append(flush_blockquote())
    if in_table:
        html_lines.append(flush_table())

    # 마지막: 열려있는 모든 섹션 닫기
    while section_stack:
        html_lines.append('</div></section>')
        section_stack.pop()

    return "\n".join(html_lines), headers


def build_toc_html(headers):
    """헤더 리스트를 중첩 <ul> 트리 HTML로 변환. 모든 항목에 본문 섹션 제어 토글 부여."""
    if not headers:
        return ""

    def render(start_idx: int, parent_level: int):
        parts = []
        i = start_idx
        while i < len(headers):
            level, text, hid = headers[i]
            if level <= parent_level:
                break
            # PP 항목(레벨4)은 번호 박스 + 제목으로 2분할 (본문 마커와 동일 컨셉)
            if level == 4 and text.startswith("PP") and " · " in text:
                _num, _ttl = text.split(" · ", 1)
                disp = f'<span class="toc-pp-num">{_num}</span><span class="toc-pp-title">{_ttl}</span>'
            else:
                disp = text
            has_children = (i + 1 < len(headers) and headers[i + 1][0] > level)
            # 모든 항목에 토글 버튼 — 본문 섹션 + TOC 자녀를 함께 접기/펼치기
            toggle_btn = (
                f'<span class="toc-toggle" '
                f'onclick="toggleTocSection(event, this, \'{hid}\')">▼</span>'
            )
            if has_children:
                children_html, new_i = render(i + 1, level)
                parts.append(
                    f'<li class="toc-item toc-level-{level}" data-target="{hid}">'
                    f'<div class="toc-row">'
                    f'{toggle_btn}'
                    f'<a href="#{hid}">{disp}</a>'
                    f'</div>'
                    f'<ul class="toc-children">{children_html}</ul>'
                    f'</li>'
                )
                i = new_i
            else:
                parts.append(
                    f'<li class="toc-item toc-level-{level}" data-target="{hid}">'
                    f'<div class="toc-row">'
                    f'{toggle_btn}'
                    f'<a href="#{hid}">{disp}</a>'
                    f'</div>'
                    f'</li>'
                )
                i += 1
        return "".join(parts), i

    tree_html, _ = render(0, 0)
    return f'<ul class="toc-root">{tree_html}</ul>'


def extract_header_info(md_text: str) -> dict:
    """원고 상단에서 날짜/본문/제목 추출 (사이드바 고정 블록용)"""
    head = "\n".join(md_text.split("\n")[:40])

    # 날짜: 2026.04.19 / 2026-04-19 / 2026년 4월 19일
    date_pat = re.compile(
        r'\d{4}\s*[.\-년]\s*\d{1,2}\s*[.\-월]\s*\d{1,2}\s*일?'
    )
    # 성경책 이름 + 장:절
    book_names = (
        r'(?:창세기|출애굽기|레위기|민수기|신명기|여호수아|사사기|룻기|'
        r'사무엘상|사무엘하|열왕기상|열왕기하|역대상|역대하|에스라|느헤미야|에스더|'
        r'욥기|시편|잠언|전도서|아가|'
        r'이사야|예레미야|예레미야애가|애가|에스겔|다니엘|'
        r'호세아|요엘|아모스|오바댜|요나|미가|나훔|하박국|스바냐|학개|스가랴|말라기|'
        r'마태복음|마가복음|누가복음|요한복음|사도행전|로마서|'
        r'고린도전서|고린도후서|갈라디아서|에베소서|빌립보서|골로새서|'
        r'데살로니가전서|데살로니가후서|디모데전서|디모데후서|디도서|빌레몬서|'
        r'히브리서|야고보서|베드로전서|베드로후서|요한일서|요한이서|요한삼서|유다서|'
        r'요한계시록|계시록|'
        r'창|출|레|민|신|수|삿|룻|삼상|삼하|왕상|왕하|대상|대하|스|느|에|'
        r'욥|시|잠|전|아|사|렘|애|겔|단|'
        r'호|욜|암|옵|욘|미|나|합|습|학|슥|말|'
        r'마|막|눅|요|행|롬|고전|고후|갈|엡|빌|골|살전|살후|딤전|딤후|딛|몬|'
        r'히|약|벧전|벧후|요일|요이|요삼|유|계)'
    )
    scripture_pat = re.compile(
        book_names + r'\s*\d+\s*[:·편장]?\s*\d*(?:\s*[\-–~]\s*\d+)?(?:\s*절)?'
    )
    title_pat = re.compile(r'제목\s*[:：]\s*([^,，\n]+)')

    date = None
    scripture = None
    title = None

    m = date_pat.search(head)
    if m:
        date = m.group(0).strip()
    m = scripture_pat.search(head)
    if m:
        scripture = m.group(0).strip()
    m = title_pat.search(head)
    if m:
        title = m.group(1).strip()

    # title 없으면 첫 H1에서 추출 (대괄호 제거, 날짜 제거)
    if not title:
        for line in md_text.split("\n")[:10]:
            stripped = line.strip()
            if stripped.startswith("# "):
                raw = stripped[2:]
                cleaned = re.sub(r'\[[^\]]*\]', '', raw)
                cleaned = date_pat.sub('', cleaned).strip()
                if cleaned:
                    title = cleaned
                    break

    return {"date": date, "scripture": scripture, "title": title}


def build_fixed_info_html(info: dict) -> str:
    """사이드바 상단 고정 정보 블록 HTML"""
    rows = []
    if info.get("date"):
        rows.append(
            f'<div class="info-row">'
            f'<span class="info-label">날짜</span>'
            f'<span class="info-value">{info["date"]}</span>'
            f'</div>'
        )
    if info.get("scripture"):
        rows.append(
            f'<div class="info-row">'
            f'<span class="info-label">본문</span>'
            f'<span class="info-value">{info["scripture"]}</span>'
            f'</div>'
        )
    if info.get("title"):
        rows.append(
            f'<div class="info-row">'
            f'<span class="info-label">제목</span>'
            f'<span class="info-value">{info["title"]}</span>'
            f'</div>'
        )
    if not rows:
        return ""
    return f'<div class="toc-fixed-info">{"".join(rows)}</div>'


def generate_preview(sermon_dir: Path, md_filename: str = "원고.md", out_filename: str = "preview.html"):
    """원고.md (또는 지정한 파일)에서 HTML 프리뷰 생성 (좌측 TOC 포함)"""
    md_file = sermon_dir / md_filename
    if not md_file.exists():
        print(f"오류: {md_file} 파일이 없습니다.")
        sys.exit(1)

    md_text = md_file.read_text(encoding="utf-8")
    body_html, headers = md_to_html(md_text, sermon_dir)
    toc_html = build_toc_html(headers)
    header_info = extract_header_info(md_text)
    fixed_info_html = build_fixed_info_html(header_info)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>원고 프리뷰</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@300;400;500;700;900&display=swap');
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
        background: #0f172a;
        color: #e2e8f0;
        font-family: 'Noto Serif KR', serif;
        font-size: 16px;
        line-height: 1.9;
    }}

    /* ===== 좌측 TOC 사이드바 ===== */
    #toc-sidebar {{
        position: fixed;
        left: 0;
        top: 0;
        width: 300px;
        height: 100vh;
        overflow-y: auto;
        background: #111827;
        border-right: 1px solid #334155;
        padding: 1.2rem 1rem;
        z-index: 100;
        transition: transform 0.3s ease;
    }}
    #toc-sidebar.collapsed {{
        transform: translateX(calc(-100% + 10px));
    }}

    /* ===== 사이드바 리사이저 (드래그로 너비 조절) ===== */
    #toc-resizer {{
        position: fixed;
        left: 300px;
        top: 0;
        width: 6px;
        height: 100vh;
        cursor: col-resize;
        background: transparent;
        z-index: 102;
        transition: background 0.2s;
    }}
    #toc-resizer:hover,
    #toc-resizer.dragging {{
        background: #fbbf24;
    }}
    #toc-sidebar.collapsed ~ #toc-resizer {{
        display: none;
    }}
    body.resizing {{
        user-select: none;
        cursor: col-resize;
    }}
    body.resizing * {{
        cursor: col-resize !important;
    }}
    #toc-sidebar h4 {{
        color: #fbbf24;
        font-size: 0.95rem;
        margin-bottom: 0.8rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #334155;
        font-family: 'Noto Serif KR', serif;
    }}

    /* ===== 본문 상단 줌 컨트롤 (sticky) ===== */
    .zoom-controls {{
        position: sticky;
        top: 0;
        display: flex;
        gap: 8px;
        justify-content: flex-end;
        padding: 10px 2rem;
        margin: -2rem -2rem 1.2rem -2rem;
        background: rgba(15, 23, 42, 0.92);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        border-bottom: 1px solid #334155;
        z-index: 50;
    }}
    .zoom-btn {{
        flex: 0 0 auto;
        min-width: 92px;
        background: #1e293b;
        color: #fbbf24;
        border: 1px solid #475569;
        border-radius: 6px;
        padding: 7px 14px;
        font-size: 0.88rem;
        font-weight: 600;
        cursor: pointer;
        font-family: 'Noto Serif KR', serif;
        transition: background 0.2s, color 0.2s, transform 0.15s;
        user-select: none;
    }}
    .zoom-btn:hover {{
        background: #fbbf24;
        color: #0f172a;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(251, 191, 36, 0.3);
    }}
    .zoom-btn:active {{
        transform: translateY(0);
    }}
    .zoom-btn.zoom-reset {{
        min-width: 64px;
        padding: 7px 12px;
        font-size: 0.82rem;
    }}

    /* ===== 사이드바 상단 고정 정보 블록 ===== */
    .toc-fixed-info {{
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 0.7rem 0.8rem;
        margin-bottom: 1rem;
    }}
    .toc-fixed-info .info-row {{
        display: flex;
        gap: 0.5rem;
        font-size: 0.82rem;
        line-height: 1.6;
        padding: 2px 0;
    }}
    .toc-fixed-info .info-label {{
        color: #fbbf24;
        font-weight: 700;
        flex-shrink: 0;
        min-width: 36px;
    }}
    .toc-fixed-info .info-value {{
        color: #e2e8f0;
        word-break: keep-all;
    }}
    #toc-toggle-btn {{
        position: fixed;
        top: 12px;
        left: 305px;
        z-index: 101;
        background: #1e293b;
        color: #fbbf24;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 4px 10px;
        cursor: pointer;
        font-size: 14px;
        transition: left 0.3s ease;
    }}
    #toc-sidebar.collapsed ~ #toc-toggle-btn {{
        left: 15px;
    }}

    .toc-root, .toc-children {{
        list-style: none;
        padding-left: 0;
    }}
    .toc-children {{
        padding-left: 1.5rem;
        overflow: hidden;
        transition: max-height 0.25s ease;
    }}
    .toc-children.collapsed {{
        display: none;
    }}
    .toc-item {{
        margin: 2px 0;
    }}
    .toc-row {{
        display: flex;
        align-items: flex-start;
        gap: 4px;
        padding: 3px 4px;
        border-radius: 4px;
    }}
    .toc-row:hover {{
        background: #1e293b;
    }}
    .toc-toggle, .toc-toggle-placeholder {{
        display: inline-block;
        width: 14px;
        flex-shrink: 0;
        text-align: center;
        color: #64748b;
        font-size: 10px;
        cursor: pointer;
        user-select: none;
        transition: transform 0.2s;
    }}
    .toc-toggle.collapsed {{
        transform: rotate(-90deg);
    }}
    .toc-row a {{
        flex: 1;
        color: #e2e8f0;
        text-decoration: none;
        font-size: 0.88rem;
        line-height: 1.5;
        word-break: keep-all;
        overflow-wrap: break-word;
        white-space: normal;
    }}
    .toc-row a:hover {{
        color: #fbbf24;
    }}
    /* ===== TOC 계층별 가독성 차별화 ===== */
    /* Level 1 — 시리즈 배너 (가장 큼, 흰색 강조) */
    .toc-level-1 > .toc-row > a {{
        font-weight: 800;
        color: #f1f5f9;
        font-size: 1.05rem;
        letter-spacing: -0.3px;
    }}
    .toc-level-1 > .toc-row {{
        padding: 6px 4px 4px 4px;
        margin-top: 4px;
    }}

    /* Level 2 — 서두·본론·결론 (빨강 강조, 굵게) */
    .toc-level-2 > .toc-row > a {{
        color: #f87171;
        font-weight: 700;
        font-size: 0.98rem;
    }}
    .toc-level-2 > .toc-row {{
        padding: 5px 4px 4px 4px;
        margin-top: 8px;
        border-left: 3px solid #f87171;
        padding-left: 8px;
    }}

    /* Level 3 — 소주제 (중간 크기, 무게 보통) */
    .toc-level-3 > .toc-row > a {{
        color: #cbd5e1;
        font-size: 0.86rem;
        font-weight: 600;
    }}
    .toc-level-3 > .toc-row {{
        padding: 3px 4px;
        margin-top: 3px;
    }}

    /* Level 4 — PP 슬라이드 (가장 작고 옅게, 황금 / 추가 들여쓰기로 위계 강조) */
    .toc-level-4 {{
        margin-left: 18px;  /* 부모(H2/H3)보다 항상 한 단계 더 들여쓰기 */
        border-left: 1px dashed rgba(251, 191, 36, 0.25);
        padding-left: 6px;
    }}
    .toc-level-4 > .toc-row > a {{
        color: #fbbf24;
        font-size: 0.76rem;
        font-family: inherit;
        font-weight: 400;
        opacity: 0.92;
    }}
    .toc-level-4 > .toc-row {{
        padding: 1px 4px;
        line-height: 1.35;
    }}
    /* H3(소주제) 아래 있는 PP는 더 깊이 들여쓰기 */
    .toc-level-3 .toc-level-4 {{
        margin-left: 22px;
    }}
    .toc-level-4 > .toc-row > a:hover {{
        color: #fde68a;
        text-decoration: underline;
    }}
    /* PP 항목은 자식이 없지만 세모 장식은 유지 (클릭 비활성화, 황금색) */
    .toc-level-4 .toc-toggle {{
        pointer-events: none;
        cursor: default;
        color: #fbbf24;
        font-size: 9px;
    }}

    /* ===== PP 슬라이드 마커 (본문 내) ===== */
    .pp-marker {{
        display: inline-block;
        margin: 14px 0 6px 0;
        font-size: 0.95rem;
        font-family: inherit;
        letter-spacing: 0.3px;
        scroll-margin-top: 80px;
    }}
    .pp-marker .pp-num-box {{
        background: #fbbf24;
        color: #0f172a;
        font-weight: 800;
        padding: 4px 12px;
        border-radius: 6px 0 0 6px;
    }}
    .pp-marker .pp-marker-title {{
        background: rgba(251, 191, 36, 0.15);
        color: #fde68a;
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 0 6px 6px 0;
    }}
    /* 목차 PP 항목 — 본문과 동일 컨셉(번호 박스 진하게 + 제목), 사이즈만 축소 */
    .toc-pp-num {{
        background: #fbbf24;
        color: #0f172a;
        font-weight: 700;
        padding: 1px 6px;
        border-radius: 4px;
        font-size: 0.7rem;
        margin-right: 5px;
        white-space: nowrap;
    }}
    .toc-pp-title {{
        color: #fde68a;
    }}

    /* ===== 목차 전체 접기/펼치기 컨트롤 (뚜렷한 캡슐 버튼) ===== */
    .toc-expand-controls {{
        display: flex;
        gap: 6px;
        margin-bottom: 0.9rem;
    }}
    .toc-expand-btn {{
        flex: 1;
        background: linear-gradient(135deg, rgba(51, 65, 85, 0.85), rgba(30, 41, 59, 0.85));
        color: #f1f5f9;
        border: 1px solid rgba(251, 191, 36, 0.35);
        border-radius: 8px;
        padding: 7px 10px;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.3px;
        cursor: pointer;
        font-family: 'Noto Serif KR', serif;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        user-select: none;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 5px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }}
    .toc-expand-btn .icon {{
        font-size: 1em;
        color: #fbbf24;
        font-weight: 700;
        transition: transform 0.2s;
    }}
    .toc-expand-btn:hover {{
        background: linear-gradient(135deg, #fbbf24, #f59e0b);
        color: #0f172a;
        border-color: #fbbf24;
        box-shadow: 0 0 0 1px #fbbf24, 0 4px 14px rgba(251, 191, 36, 0.4);
        transform: translateY(-1px);
    }}
    .toc-expand-btn:hover .icon {{
        color: #0f172a;
        transform: scale(1.15);
    }}
    .toc-expand-btn:active {{
        transform: translateY(0);
        box-shadow: 0 0 0 1px #fbbf24, 0 1px 4px rgba(251, 191, 36, 0.3);
    }}
    .pp-marker .pp-marker-icon {{
        margin-right: 6px;
    }}
    .pp-marker .pp-marker-num {{
        font-weight: bold;
    }}

    /* ===== 본문 ===== */
    #content-main {{
        max-width: 800px;
        margin: 0 auto;
        margin-left: 340px;
        padding: 2rem;
        transition: margin-left 0.3s ease;
    }}
    body.toc-collapsed #content-main {{
        margin-left: 0;  /* 사이드바 숨김 시 본문을 왼쪽으로 이동 (auto는 가운데로 띄워 제자리처럼 보임) */
    }}

    h1 {{
        font-size: 1.6rem;
        color: #f1f5f9;
        border-bottom: 2px solid #3b82f6;
        padding-bottom: 0.5rem;
        margin: 0;
        scroll-margin-top: 80px;
        flex: 1;
    }}
    h2 {{
        font-size: 1.3rem;
        color: #f87171;
        font-weight: 700;
        margin: 0;
        scroll-margin-top: 80px;
        flex: 1;
    }}
    h3 {{
        font-size: 1.1rem;
        color: #f87171;
        font-weight: 700;
        text-decoration: underline;
        margin: 0;
        scroll-margin-top: 80px;
        flex: 1;
    }}

    /* ===== 본문 섹션 토글 ===== */
    .section {{
        margin: 1rem 0;
    }}
    .section-level-1 {{ margin-top: 2rem; }}
    .section-level-2 {{ margin-top: 1.5rem; }}
    .section-level-3 {{ margin-top: 1.2rem; }}

    .section-header {{
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding-bottom: 0.3rem;
    }}
    .section-level-1 > .section-header {{
        border-bottom: 2px solid #3b82f6;
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }}
    .section-level-1 > .section-header > h1 {{
        border-bottom: none;
        padding-bottom: 0;
    }}
    .section-toggle {{
        cursor: pointer;
        background: transparent;
        border: 1px solid #334155;
        color: #64748b;
        font-size: 11px;
        padding: 2px 7px;
        border-radius: 4px;
        transition: transform 0.2s, color 0.2s, background 0.2s;
        flex-shrink: 0;
        user-select: none;
    }}
    .section-toggle:hover {{
        color: #fbbf24;
        background: rgba(251, 191, 36, 0.1);
        border-color: #fbbf24;
    }}
    .section-toggle.collapsed {{
        transform: rotate(-90deg);
    }}
    .section-content {{
        padding-left: 0.2rem;
    }}
    .section-content.collapsed {{
        display: none;
    }}
    p {{ margin: 0.3rem 0; }}
    strong {{ color: #fbbf24; }}
    img {{
        display: block;
        max-width: 100%;
        border-radius: 8px;
        margin: 12px auto;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }}
    hr {{
        border: none;
        border-top: 1px solid #334155;
        margin: 1.5rem 0;
    }}
    br {{ line-height: 0.5; }}
    .scripture-box {{
        background: #1e293b;
        border: 1px solid #475569;
        border-left: 4px solid #3b82f6;
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin: 1rem 0;
        font-style: italic;
        line-height: 1.8;
        color: #cbd5e1;
    }}
    .scripture-box strong {{ color: #fbbf24; font-style: normal; }}
    .scripture-box em {{ color: #94a3b8; }}

    /* ===== 마크다운 테이블 ===== */
    .sermon-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        overflow: hidden;
        margin: 1rem 0;
        font-size: 0.95rem;
        line-height: 1.7;
    }}
    .sermon-table th {{
        background: rgba(251, 191, 36, 0.12);
        color: #fbbf24;
        font-weight: 700;
        padding: 10px 16px;
        text-align: left;
        border-bottom: 2px solid rgba(251, 191, 36, 0.25);
        font-size: 0.9rem;
    }}
    .sermon-table td {{
        padding: 10px 16px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        vertical-align: top;
        word-break: keep-all;
    }}
    .sermon-table td:first-child {{
        color: #94a3b8;
        font-weight: 600;
        white-space: nowrap;
        width: 110px;
    }}
    .sermon-table tr:last-child td {{ border-bottom: none; }}
    .sermon-table tr:hover {{ background: rgba(255, 255, 255, 0.03); }}
    .sermon-table strong {{ color: #fbbf24; }}

    /* 기본틀 테이블 (One Big Message 포함) */
    .basic-frame-table {{
        background: rgba(251, 191, 36, 0.04);
        border: 1px solid rgba(251, 191, 36, 0.2);
        box-shadow: 0 4px 20px rgba(251, 191, 36, 0.08);
    }}
    .basic-frame-table .obm-row {{
        background: rgba(251, 191, 36, 0.1);
    }}
    .basic-frame-table .obm-row td {{
        color: #fde68a;
        font-weight: 500;
        border-bottom: 2px solid rgba(251, 191, 36, 0.2);
        padding: 14px 16px;
    }}
    .basic-frame-table .obm-row td:first-child {{
        color: #fbbf24;
        font-weight: 700;
    }}
    .basic-frame-table .question-row {{
        background: rgba(59, 130, 246, 0.06);
    }}
    .basic-frame-table .keyword-row {{
        background: rgba(34, 197, 94, 0.06);
    }}

    #zoom-indicator {{
        position: fixed;
        top: 10px;
        right: 14px;
        background: rgba(15, 23, 42, 0.85);
        color: #fbbf24;
        padding: 4px 10px;
        border-radius: 6px;
        font-family: monospace;
        font-size: 13px;
        z-index: 9999;
        opacity: 0;
        transition: opacity 0.3s;
        pointer-events: none;
    }}
    #zoom-indicator.show {{ opacity: 1; }}

    /* ===== 우측 최상단/최하단 이동 버튼 ===== */
    .scroll-btn {{
        position: fixed;
        right: 16px;
        width: 44px;
        height: 44px;
        background: rgba(30, 41, 59, 0.92);
        color: #fbbf24;
        border: 1px solid #475569;
        border-radius: 50%;
        font-size: 20px;
        font-weight: bold;
        cursor: pointer;
        z-index: 9998;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        transition: background 0.2s, transform 0.2s, color 0.2s;
        user-select: none;
    }}
    .scroll-btn:hover {{
        background: #fbbf24;
        color: #0f172a;
        transform: scale(1.1);
    }}
    #scroll-top-btn {{ bottom: 80px; }}
    #scroll-bottom-btn {{ bottom: 24px; }}

    @media (min-width: 769px) and (max-width: 1024px) {{
        #toc-sidebar {{ width: 250px; }}
        #toc-resizer {{ left: 250px; }}
        #toc-toggle-btn {{ left: 255px; }}
        #content-main {{ margin-left: 280px; }}
    }}

    /* ===== 모바일 (≤768px) — 사이드바 오버레이 + 햄버거 메뉴 ===== */
    #mobile-menu-btn {{
        display: none;
        position: fixed; top: 10px; left: 10px; z-index: 210;
        background: #fbbf24; color: #0f172a; border: none;
        border-radius: 8px; width: 46px; height: 46px;
        font-size: 1.5rem; cursor: pointer;
        box-shadow: 0 2px 8px rgba(0,0,0,0.45);
    }}
    #mobile-overlay {{
        display: none; position: fixed; inset: 0;
        background: rgba(0,0,0,0.55); z-index: 150;
    }}
    @media (max-width: 768px) {{
        #toc-sidebar {{
            transform: translateX(-100%);
            width: 84vw; max-width: 340px;
            transition: transform 0.3s ease;
            z-index: 200;
            box-shadow: 2px 0 16px rgba(0,0,0,0.6);
        }}
        #toc-sidebar.mobile-open {{ transform: translateX(0); }}
        #content-main {{
            margin-left: 0 !important;
            max-width: 100%;
            padding: 3.2rem 1rem 4rem 1rem;
        }}
        #toc-toggle-btn, #toc-resizer {{ display: none !important; }}
        #mobile-menu-btn {{ display: block; }}
        #mobile-overlay.show {{ display: block; }}
        .zoom-controls {{ flex-wrap: wrap; gap: 5px; padding: 8px 10px; }}
        .zoom-btn {{ min-width: 0; padding: 6px 9px; font-size: 0.78rem; }}
        h1 {{ font-size: 1.3rem; }}
        h2 {{ font-size: 1.15rem; }}
        .scripture-box {{ padding: 0.8rem; }}
        .scroll-btn {{ width: 40px; height: 40px; }}
        .sermon-table td:first-child {{ white-space: normal; width: auto; }}
        .sermon-table th, .sermon-table td {{ padding: 8px 10px; font-size: 0.88rem; }}
    }}
</style>
</head>
<body>
<nav id="toc-sidebar">
    {fixed_info_html}
    <h4>📖 목차</h4>
    <div class="toc-expand-controls">
        <button class="toc-expand-btn" onclick="expandAllToc()" title="목차 전체 펼치기"><span class="icon">⌄</span>펼치기</button>
        <button class="toc-expand-btn" onclick="collapseAllToc()" title="목차 전체 접기"><span class="icon">›</span>접기</button>
    </div>
    {toc_html}
</nav>
<div id="toc-resizer" title="드래그: 너비 조절 / 더블클릭: 기본값(300px) 복원"></div>
<button id="toc-toggle-btn" onclick="toggleSidebar()">◀</button>
<button id="mobile-menu-btn" onclick="toggleMobileSidebar()" title="목차 열기">☰</button>
<div id="mobile-overlay" onclick="closeMobileSidebar()"></div>

<div id="content-main">
<div id="zoom-indicator">100%</div>
<div class="zoom-controls">
    <button class="zoom-btn" onclick="zoomOut()" title="작게 보기 (Ctrl+-)">🔍− 작게</button>
    <button class="zoom-btn" onclick="zoomIn()" title="크게 보기 (Ctrl++)">🔍+ 크게</button>
    <button class="zoom-btn zoom-reset" onclick="zoomReset()" title="기본 크기 (Ctrl+0)">100%</button>
    <button class="zoom-btn" id="fullscreen-btn" onclick="toggleFullscreen()" title="전체화면 (F11)">⛶ 전체화면</button>
</div>
<div id="content-body">
{body_html}
</div>
</div>

<button id="scroll-top-btn" class="scroll-btn" title="최상단으로" onclick="scrollToTop()">▲</button>
<button id="scroll-bottom-btn" class="scroll-btn" title="최하단으로" onclick="scrollToBottom()">▼</button>

<script>
// 헬퍼: 섹션의 바로 자식인 .section-content 반환
function getDirectSectionContent(section) {{
    for (let i = 0; i < section.children.length; i++) {{
        const c = section.children[i];
        if (c.classList && c.classList.contains('section-content')) return c;
    }}
    return null;
}}

// 헬퍼: toc-item의 바로 자식인 .toc-children 반환
function getDirectTocChildren(li) {{
    for (let i = 0; i < li.children.length; i++) {{
        const c = li.children[i];
        if (c.classList && c.classList.contains('toc-children')) return c;
    }}
    return null;
}}

// 상태 동기화: 해당 targetId 본문 섹션과 TOC 항목을 동일한 state로 맞춤
function syncCollapseState(targetId, isCollapsed) {{
    // 본문 섹션
    const header = document.getElementById(targetId);
    if (header) {{
        const section = header.closest('.section');
        if (section) {{
            const content = getDirectSectionContent(section);
            const secToggle = section.querySelector(':scope > .section-header > .section-toggle');
            if (content) content.classList.toggle('collapsed', isCollapsed);
            if (secToggle) secToggle.classList.toggle('collapsed', isCollapsed);
        }}
    }}
    // TOC 항목
    const tocLi = document.querySelector(`.toc-item[data-target="${{targetId}}"]`);
    if (tocLi) {{
        const tocToggle = tocLi.querySelector(':scope > .toc-row > .toc-toggle');
        const tocChildren = getDirectTocChildren(tocLi);
        if (tocToggle) tocToggle.classList.toggle('collapsed', isCollapsed);
        if (tocChildren) tocChildren.classList.toggle('collapsed', isCollapsed);
    }}
}}

// TOC 토글 → 본문 섹션 + TOC 자녀 함께 접기/펼치기
function toggleTocSection(event, btn, targetId) {{
    event.preventDefault();
    event.stopPropagation();
    const willCollapse = !btn.classList.contains('collapsed');
    syncCollapseState(targetId, willCollapse);
}}

// 본문 섹션 토글 → TOC 항목도 함께 동기화
function toggleSection(btn) {{
    const section = btn.closest('.section');
    if (!section) return;
    const header = section.querySelector(':scope > .section-header > h1, :scope > .section-header > h2, :scope > .section-header > h3');
    if (!header) return;
    const willCollapse = !btn.classList.contains('collapsed');
    syncCollapseState(header.id, willCollapse);
}}

function toggleSidebar() {{
    const sb = document.getElementById('toc-sidebar');
    const btn = document.getElementById('toc-toggle-btn');
    const content = document.getElementById('content-main');
    sb.classList.toggle('collapsed');
    const collapsed = sb.classList.contains('collapsed');
    document.body.classList.toggle('toc-collapsed', collapsed);
    // 리사이저가 설정한 인라인 스타일이 CSS보다 우선이므로, 본문 margin과 토글버튼 left를 직접 갱신
    if (content) content.style.marginLeft = collapsed ? '0px' : (sb.offsetWidth + 40) + 'px';
    btn.style.left = collapsed ? '15px' : (sb.offsetWidth + 5) + 'px';
    btn.textContent = collapsed ? '▶' : '◀';
}}

function toggleFullscreen() {{
    if (!document.fullscreenElement) {{
        document.documentElement.requestFullscreen();
    }} else {{
        document.exitFullscreen();
    }}
}}
document.addEventListener('fullscreenchange', function() {{
    const fb = document.getElementById('fullscreen-btn');
    if (fb) fb.textContent = document.fullscreenElement ? '⛶ 해제' : '⛶ 전체화면';
}});

// ===== 모바일 사이드바(목차) 오버레이 토글 =====
function toggleMobileSidebar() {{
    document.getElementById('toc-sidebar').classList.toggle('mobile-open');
    document.getElementById('mobile-overlay').classList.toggle('show');
}}
function closeMobileSidebar() {{
    document.getElementById('toc-sidebar').classList.remove('mobile-open');
    document.getElementById('mobile-overlay').classList.remove('show');
}}
// 모바일에서 목차 링크 클릭 시 사이드바 자동 닫기
document.addEventListener('click', function(e) {{
    if (window.innerWidth <= 768 && e.target.closest('#toc-sidebar a')) {{
        closeMobileSidebar();
    }}
}});

(function() {{
    let zoom = 1.0;
    const indicator = document.getElementById('zoom-indicator');
    const contentBody = document.getElementById('content-body');
    let hideTimer = null;

    function applyZoom() {{
        // 본문(#content-body)만 확대/축소 — 좌측 사이드바와 줌 버튼은 크기 유지
        if (contentBody) contentBody.style.zoom = zoom;
        const pctText = Math.round(zoom * 100) + '%';
        indicator.textContent = pctText;
        indicator.classList.add('show');
        // 줌 리셋 버튼의 레이블도 현재 % 로 실시간 업데이트
        const resetBtn = document.querySelector('.zoom-btn.zoom-reset');
        if (resetBtn) resetBtn.textContent = pctText;
        if (hideTimer) clearTimeout(hideTimer);
        hideTimer = setTimeout(() => indicator.classList.remove('show'), 1200);
    }}

    // 사이드바 버튼에서 호출할 수 있도록 전역 노출
    window.zoomIn = function() {{
        zoom = Math.min(3.0, zoom + 0.1);
        applyZoom();
    }};
    window.zoomOut = function() {{
        zoom = Math.max(0.3, zoom - 0.1);
        applyZoom();
    }};
    window.zoomReset = function() {{
        zoom = 1.0;
        applyZoom();
    }};

    document.addEventListener('wheel', function(e) {{
        if (e.ctrlKey) {{
            e.preventDefault();
            const step = 0.05;
            if (e.deltaY < 0) zoom += step;
            else zoom -= step;
            zoom = Math.max(0.3, Math.min(3.0, zoom));
            applyZoom();
        }}
    }}, {{ passive: false }});

    document.addEventListener('keydown', function(e) {{
        if (e.ctrlKey && e.key === '0') {{
            e.preventDefault();
            zoom = 1.0;
            applyZoom();
        }}
        if (e.ctrlKey && (e.key === '=' || e.key === '+')) {{
            e.preventDefault();
            zoom = Math.min(3.0, zoom + 0.1);
            applyZoom();
        }}
        if (e.ctrlKey && e.key === '-') {{
            e.preventDefault();
            zoom = Math.max(0.3, zoom - 0.1);
            applyZoom();
        }}
    }});
}})();

// ===== 사이드바 드래그 리사이저 =====
(function() {{
    const sidebar = document.getElementById('toc-sidebar');
    const resizer = document.getElementById('toc-resizer');
    const toggleBtn = document.getElementById('toc-toggle-btn');
    const content = document.getElementById('content-main');
    if (!sidebar || !resizer) return;

    const MIN_WIDTH = 150;
    const MAX_WIDTH = 700;
    const STORAGE_KEY = 'sermon-sidebar-width';

    function applyWidth(w) {{
        w = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, w));
        sidebar.style.width = w + 'px';
        resizer.style.left = w + 'px';
        if (toggleBtn) toggleBtn.style.left = (w + 5) + 'px';
        if (content && !document.body.classList.contains('toc-collapsed')) {{
            content.style.marginLeft = (w + 40) + 'px';
        }}
        return w;
    }}

    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) applyWidth(parseInt(saved, 10));

    let dragging = false;

    resizer.addEventListener('mousedown', function(e) {{
        dragging = true;
        resizer.classList.add('dragging');
        document.body.classList.add('resizing');
        sidebar.style.transition = 'none';
        if (toggleBtn) toggleBtn.style.transition = 'none';
        if (content) content.style.transition = 'none';
        e.preventDefault();
    }});

    document.addEventListener('mousemove', function(e) {{
        if (!dragging) return;
        applyWidth(e.clientX);
    }});

    document.addEventListener('mouseup', function() {{
        if (!dragging) return;
        dragging = false;
        resizer.classList.remove('dragging');
        document.body.classList.remove('resizing');
        sidebar.style.transition = '';
        if (toggleBtn) toggleBtn.style.transition = '';
        if (content) content.style.transition = '';
        localStorage.setItem(STORAGE_KEY, sidebar.offsetWidth);
    }});

    // 더블클릭으로 기본값(300px) 복원
    resizer.addEventListener('dblclick', function() {{
        applyWidth(300);
        localStorage.setItem(STORAGE_KEY, 300);
    }});
}})();

// ===== 최상단/최하단 이동 =====
function scrollToTop() {{
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
}}
function scrollToBottom() {{
    window.scrollTo({{ top: document.documentElement.scrollHeight, behavior: 'smooth' }});
}}

// ===== 목차 전체 접기/펼치기 — 좌측 TOC에만 적용 (본문 섹션은 영향 X) =====
function expandAllToc() {{
    document.querySelectorAll('#toc-sidebar .toc-children.collapsed').forEach(el => el.classList.remove('collapsed'));
    document.querySelectorAll('#toc-sidebar .toc-toggle.collapsed').forEach(el => el.classList.remove('collapsed'));
}}
function collapseAllToc() {{
    document.querySelectorAll('#toc-sidebar .toc-children').forEach(el => el.classList.add('collapsed'));
    document.querySelectorAll('#toc-sidebar .toc-toggle').forEach(el => el.classList.add('collapsed'));
}}
</script>
</body>
</html>"""

    out_file = sermon_dir / out_filename
    out_file.write_text(html, encoding="utf-8")
    print(f"✅ 프리뷰 생성: {out_file}")
    return out_file


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/md_preview.py <설교폴더> [원고파일명] [출력html파일명]")
        sys.exit(1)
    sermon_dir = Path(sys.argv[1])
    md_filename = sys.argv[2] if len(sys.argv) >= 3 else "원고.md"
    out_filename = sys.argv[3] if len(sys.argv) >= 4 else "preview.html"
    generate_preview(sermon_dir, md_filename, out_filename)
