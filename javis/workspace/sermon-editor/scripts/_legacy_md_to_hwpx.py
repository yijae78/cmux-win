#!/usr/bin/env python3
"""Convert sermon 원고.md to HWPX format.

Reads a Markdown sermon manuscript and generates:
1. A custom header.xml with sermon-specific charPr/paraPr styles
2. A section0.xml with all content paragraphs
3. Calls build_hwpx.py to assemble the final HWPX file

Usage:
    python md_to_hwpx.py <sermon_dir>
    python md_to_hwpx.py <sermon_dir> --output <path.hwpx>

Example:
    python md_to_hwpx.py "20260329-마태복음26장47-56절"
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from lxml import etree

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
HWPX_SKILL_DIR = Path.home() / ".claude" / "skills" / "hwpx"
BUILD_HWPX = HWPX_SKILL_DIR / "scripts" / "build_hwpx.py"
VALIDATE_PY = HWPX_SKILL_DIR / "scripts" / "validate.py"
BASE_HEADER = HWPX_SKILL_DIR / "templates" / "base" / "Contents" / "header.xml"

# ---------------------------------------------------------------------------
# XML Namespaces
# ---------------------------------------------------------------------------
NS = {
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hhs": "http://www.hancom.co.kr/hwpml/2011/history",
    "hm": "http://www.hancom.co.kr/hwpml/2011/master-page",
    "hpf": "http://www.hancom.co.kr/schema/2011/hpf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "opf": "http://www.idpf.org/2007/opf/",
    "ooxmlchart": "http://www.hancom.co.kr/hwpml/2016/ooxmlchart",
    "hwpunitchar": "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar",
    "epub": "http://www.idpf.org/2007/ops",
    "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",
}

# Register all namespaces so lxml doesn't invent prefixes
for prefix, uri in NS.items():
    etree.register_namespace(prefix, uri)

# Shorthand QName helpers
def _qn(prefix: str, local: str) -> str:
    """Return Clark-notation QName, e.g. {uri}local."""
    return f"{{{NS[prefix]}}}{local}"


# ---------------------------------------------------------------------------
# charPr style IDs (defined in header.xml)
# ---------------------------------------------------------------------------
CHAR_DEFAULT = "0"      # 함초롬바탕 15pt default
CHAR_BOLD = "7"         # 함초롬바탕 15pt bold
CHAR_RED_BOLD = "8"     # 함초롬바탕 15pt bold red #FF0000
CHAR_BLUE_UL = "9"      # 함초롬바탕 15pt bold blue underline
CHAR_CODE = "10"        # 함초롬바탕 14pt (code blocks)
CHAR_ITALIC = "11"      # 함초롬바탕 12pt italic (* lines)
CHAR_TITLE = "12"       # 함초롬바탕 22pt bold (H1 title)
CHAR_TABLE = "13"       # 함초롬바탕 13pt (table cells)

# paraPr style IDs
PARA_DEFAULT = "0"      # JUSTIFY 160% line spacing
PARA_CENTER = "20"      # CENTER 160% line spacing

# Global paragraph ID counter
_para_id_counter = 1000000001


def _next_para_id() -> str:
    """Return next unique paragraph ID."""
    global _para_id_counter
    pid = str(_para_id_counter)
    _para_id_counter += 1
    return pid


# ===========================================================================
# Header.xml Generation
# ===========================================================================

def _make_charpr(parent, cid: str, height: str, text_color: str = "#000000",
                 font_ref: str = "1", bold: bool = False,
                 underline: bool = False, italic: bool = False,
                 border_fill: str = "2"):
    """Create a hh:charPr element with full sub-elements."""
    attrs = {
        "id": cid,
        "height": height,
        "textColor": text_color,
        "shadeColor": "none",
        "useFontSpace": "0",
        "useKerning": "0",
        "symMark": "NONE",
        "borderFillIDRef": border_fill,
    }
    if bold:
        attrs["bold"] = "1"
    if italic:
        attrs["italic"] = "1"

    cp = etree.SubElement(parent, _qn("hh", "charPr"), attrs)

    fr = font_ref
    etree.SubElement(cp, _qn("hh", "fontRef"), {
        "hangul": fr, "latin": fr, "hanja": fr,
        "japanese": fr, "other": fr, "symbol": fr, "user": fr,
    })
    for tag in ("ratio", "relSz"):
        etree.SubElement(cp, _qn("hh", tag), {
            "hangul": "100", "latin": "100", "hanja": "100",
            "japanese": "100", "other": "100", "symbol": "100", "user": "100",
        })
    etree.SubElement(cp, _qn("hh", "spacing"), {
        "hangul": "0", "latin": "0", "hanja": "0",
        "japanese": "0", "other": "0", "symbol": "0", "user": "0",
    })
    etree.SubElement(cp, _qn("hh", "offset"), {
        "hangul": "0", "latin": "0", "hanja": "0",
        "japanese": "0", "other": "0", "symbol": "0", "user": "0",
    })

    ul_type = "BOTTOM" if underline else "NONE"
    etree.SubElement(cp, _qn("hh", "underline"), {
        "type": ul_type, "shape": "SOLID", "color": text_color if underline else "#000000",
    })
    etree.SubElement(cp, _qn("hh", "strikeout"), {"shape": "NONE", "color": "#000000"})
    etree.SubElement(cp, _qn("hh", "outline"), {"type": "NONE"})
    etree.SubElement(cp, _qn("hh", "shadow"), {
        "type": "NONE", "color": "#C0C0C0", "offsetX": "10", "offsetY": "10",
    })
    return cp


def _make_parapr(parent, pid: str, align: str = "JUSTIFY",
                 line_spacing: str = "160", left: str = "0",
                 prev: str = "0", nxt: str = "0",
                 tab_pr: str = "0"):
    """Create a hh:paraPr element with hp:switch for margin/lineSpacing."""
    pp = etree.SubElement(parent, _qn("hh", "paraPr"), {
        "id": pid, "tabPrIDRef": tab_pr, "condense": "0",
        "fontLineHeight": "0", "snapToGrid": "1",
        "suppressLineNumbers": "0", "checked": "0", "textDir": "LTR",
    })
    etree.SubElement(pp, _qn("hh", "align"), {
        "horizontal": align, "vertical": "BASELINE",
    })
    etree.SubElement(pp, _qn("hh", "heading"), {
        "type": "NONE", "idRef": "0", "level": "0",
    })
    etree.SubElement(pp, _qn("hh", "breakSetting"), {
        "breakLatinWord": "KEEP_WORD", "breakNonLatinWord": "BREAK_WORD",
        "widowOrphan": "0", "keepWithNext": "0", "keepLines": "0",
        "pageBreakBefore": "0", "lineWrap": "BREAK",
    })
    etree.SubElement(pp, _qn("hh", "autoSpacing"), {
        "eAsianEng": "0", "eAsianNum": "0",
    })

    # hp:switch with case and default
    sw = etree.SubElement(pp, _qn("hp", "switch"))
    case = etree.SubElement(sw, _qn("hp", "case"))
    case.set(_qn("hp", "required-namespace"),
             "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar")

    def _add_margin_ls(parent_el, l=left, p=prev, n=nxt, ls=line_spacing):
        mg = etree.SubElement(parent_el, _qn("hh", "margin"))
        etree.SubElement(mg, _qn("hc", "intent"), {"value": "0", "unit": "HWPUNIT"})
        etree.SubElement(mg, _qn("hc", "left"), {"value": l, "unit": "HWPUNIT"})
        etree.SubElement(mg, _qn("hc", "right"), {"value": "0", "unit": "HWPUNIT"})
        etree.SubElement(mg, _qn("hc", "prev"), {"value": p, "unit": "HWPUNIT"})
        etree.SubElement(mg, _qn("hc", "next"), {"value": n, "unit": "HWPUNIT"})
        etree.SubElement(parent_el, _qn("hh", "lineSpacing"), {
            "type": "PERCENT", "value": ls, "unit": "HWPUNIT",
        })

    _add_margin_ls(case)
    default = etree.SubElement(sw, _qn("hp", "default"))
    _add_margin_ls(default)

    etree.SubElement(pp, _qn("hh", "border"), {
        "borderFillIDRef": "2", "offsetLeft": "0", "offsetRight": "0",
        "offsetTop": "0", "offsetBottom": "0", "connect": "0", "ignoreMargin": "0",
    })
    return pp


def generate_header_xml(output_path: Path) -> None:
    """Generate a custom header.xml with sermon-specific styles."""
    # Parse base header
    tree = etree.parse(str(BASE_HEADER))
    root = tree.getroot()

    # --- Modify charProperties: replace existing + add new ---
    char_props = root.find(f".//{_qn('hh', 'charProperties')}")

    # Remove all existing charPr elements
    for cp in char_props.findall(_qn("hh", "charPr")):
        char_props.remove(cp)

    # charPr 0: 함초롬바탕 15pt default (fontRef=1)
    _make_charpr(char_props, "0", "1500", "#000000", "1")
    # charPr 1: 함초롬돋움 10pt (page number style, fontRef=0) - keep original
    _make_charpr(char_props, "1", "1000", "#000000", "0")
    # charPr 2: 함초롬돋움 9pt (header style)
    _make_charpr(char_props, "2", "900", "#000000", "0")
    # charPr 3: 함초롬바탕 9pt (footnote style)
    _make_charpr(char_props, "3", "900", "#000000", "1")
    # charPr 4: 함초롬돋움 9pt spacing -5 (memo style)
    _make_charpr(char_props, "4", "900", "#000000", "0")
    # charPr 5: 함초롬돋움 16pt blue (TOC heading)
    _make_charpr(char_props, "5", "1600", "#2E74B5", "0")
    # charPr 6: 함초롬돋움 11pt (TOC entries)
    _make_charpr(char_props, "6", "1100", "#000000", "0")
    # charPr 7: 함초롬바탕 15pt bold
    _make_charpr(char_props, "7", "1500", "#000000", "1", bold=True)
    # charPr 8: 함초롬바탕 15pt bold red
    _make_charpr(char_props, "8", "1500", "#FF0000", "1", bold=True)
    # charPr 9: 함초롬바탕 15pt bold blue underline
    _make_charpr(char_props, "9", "1500", "#0000FF", "1", bold=True, underline=True)
    # charPr 10: 함초롬바탕 14pt (code blocks)
    _make_charpr(char_props, "10", "1400", "#000000", "1")
    # charPr 11: 함초롬바탕 12pt italic (* lines)
    _make_charpr(char_props, "11", "1200", "#000000", "1", italic=True)
    # charPr 12: 함초롬바탕 22pt bold (H1 title, center)
    _make_charpr(char_props, "12", "2200", "#000000", "1", bold=True)
    # charPr 13: 함초롬바탕 13pt (table cells)
    _make_charpr(char_props, "13", "1300", "#000000", "1")

    # Update itemCnt
    char_props.set("itemCnt", "14")

    # --- Add paraPr 20 (CENTER) if it doesn't exist ---
    para_props = root.find(f".//{_qn('hh', 'paraProperties')}")
    existing_ids = {pp.get("id") for pp in para_props.findall(_qn("hh", "paraPr"))}

    # Modify paraPr 0 to ensure 함초롬바탕 at 160% JUSTIFY (already there)
    # Add paraPr 20: CENTER 160% line spacing
    if "20" not in existing_ids:
        _make_parapr(para_props, "20", align="CENTER", line_spacing="160")
        # Update itemCnt
        current_cnt = int(para_props.get("itemCnt", "20"))
        para_props.set("itemCnt", str(current_cnt + 1))

    # --- Add borderFill 3 for code block background (grey) ---
    border_fills = root.find(f".//{_qn('hh', 'borderFills')}")
    existing_bf_ids = {bf.get("id") for bf in border_fills.findall(_qn("hh", "borderFill"))}

    if "3" not in existing_bf_ids:
        bf3 = etree.SubElement(border_fills, _qn("hh", "borderFill"), {
            "id": "3", "threeD": "0", "shadow": "0",
            "centerLine": "NONE", "breakCellSeparateLine": "0",
        })
        etree.SubElement(bf3, _qn("hh", "slash"), {
            "type": "NONE", "Crooked": "0", "isCounter": "0",
        })
        etree.SubElement(bf3, _qn("hh", "backSlash"), {
            "type": "NONE", "Crooked": "0", "isCounter": "0",
        })
        for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
            etree.SubElement(bf3, _qn("hh", side), {
                "type": "SOLID", "width": "0.12 mm", "color": "#CCCCCC",
            })
        etree.SubElement(bf3, _qn("hh", "diagonal"), {
            "type": "SOLID", "width": "0.1 mm", "color": "#000000",
        })
        fb = etree.SubElement(bf3, _qn("hc", "fillBrush"))
        etree.SubElement(fb, _qn("hc", "winBrush"), {
            "faceColor": "#F0F0F0", "hatchColor": "#999999", "alpha": "0",
        })
        border_fills.set("itemCnt", str(int(border_fills.get("itemCnt", "2")) + 1))

    # Also add borderFill 4 for table cells (thin black borders)
    if "4" not in existing_bf_ids:
        bf4 = etree.SubElement(border_fills, _qn("hh", "borderFill"), {
            "id": "4", "threeD": "0", "shadow": "0",
            "centerLine": "NONE", "breakCellSeparateLine": "0",
        })
        etree.SubElement(bf4, _qn("hh", "slash"), {
            "type": "NONE", "Crooked": "0", "isCounter": "0",
        })
        etree.SubElement(bf4, _qn("hh", "backSlash"), {
            "type": "NONE", "Crooked": "0", "isCounter": "0",
        })
        for side in ("leftBorder", "rightBorder", "topBorder", "bottomBorder"):
            etree.SubElement(bf4, _qn("hh", side), {
                "type": "SOLID", "width": "0.12 mm", "color": "#000000",
            })
        etree.SubElement(bf4, _qn("hh", "diagonal"), {
            "type": "SOLID", "width": "0.1 mm", "color": "#000000",
        })
        border_fills.set("itemCnt", str(int(border_fills.get("itemCnt", "3")) + 1))

    # Write
    etree.indent(root, space="  ")
    tree.write(str(output_path), pretty_print=True, xml_declaration=True, encoding="UTF-8")


# ===========================================================================
# Markdown Parser
# ===========================================================================

class MdElement:
    """Represents a parsed Markdown element."""
    pass

class MdParagraph(MdElement):
    """A paragraph with inline runs."""
    def __init__(self, runs: list, para_pr: str = PARA_DEFAULT, char_pr: str = CHAR_DEFAULT):
        self.runs = runs  # list of (text, charPrIDRef)
        self.para_pr = para_pr
        self.char_pr = char_pr  # default charPr for the paragraph

class MdEmpty(MdElement):
    """An empty paragraph."""
    pass

class MdCodeBlock(MdElement):
    """A code block (``` ... ```)."""
    def __init__(self, lines: list):
        self.lines = lines

class MdTable(MdElement):
    """A Markdown table."""
    def __init__(self, headers: list, rows: list):
        self.headers = headers
        self.rows = rows


def parse_inline(text: str, default_char_pr: str = CHAR_DEFAULT) -> list:
    """Parse inline **bold** markers and return list of (text, charPrIDRef) runs.

    Only handles **bold** for now. Other inline markers are kept as-is.
    """
    runs = []
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            inner = part[2:-2]
            runs.append((inner, CHAR_BOLD))
        else:
            runs.append((part, default_char_pr))
    return runs


def parse_markdown(md_text: str) -> list:
    """Parse Markdown text into a list of MdElement objects."""
    lines = md_text.split("\n")
    elements = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # --- Code block ---
        if line.strip().startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            elements.append(MdCodeBlock(code_lines))
            continue

        # --- Empty / separator lines ---
        stripped = line.strip()

        if stripped == "" or stripped == "&nbsp;":
            elements.append(MdEmpty())
            i += 1
            continue

        if stripped == "---":
            elements.append(MdEmpty())
            i += 1
            continue

        # --- Image lines (skip) ---
        if stripped.startswith("!["):
            i += 1
            continue

        # --- H1 title: # Title ---
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title_text = stripped[2:].strip()
            elements.append(MdParagraph(
                [(title_text, CHAR_TITLE)],
                para_pr=PARA_CENTER,
            ))
            i += 1
            continue

        # --- H2 header: ## Title ---
        if stripped.startswith("## "):
            h2_text = stripped[3:].strip()
            elements.append(MdParagraph(
                [(h2_text, CHAR_RED_BOLD)],
                para_pr=PARA_DEFAULT,
            ))
            i += 1
            continue

        # --- H3 header: ### Title ---
        if stripped.startswith("### "):
            h3_text = stripped[4:].strip()
            elements.append(MdParagraph(
                [(h3_text, CHAR_BLUE_UL)],
                para_pr=PARA_DEFAULT,
            ))
            i += 1
            continue

        # --- Table ---
        if "|" in stripped and stripped.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            # Parse table
            if len(table_lines) >= 2:
                # First line = headers
                headers = [c.strip() for c in table_lines[0].split("|")[1:-1]]
                # Second line = separator (skip)
                rows = []
                for tl in table_lines[2:]:
                    cells = [c.strip() for c in tl.split("|")[1:-1]]
                    rows.append(cells)
                elements.append(MdTable(headers, rows))
            continue

        # --- ▶ directive lines ---
        if stripped.startswith("▶"):
            elements.append(MdParagraph(
                [(stripped, CHAR_RED_BOLD)],
                para_pr=PARA_DEFAULT,
            ))
            i += 1
            continue

        # --- * italic/info lines (hymn info etc.) ---
        if stripped.startswith("*") and not stripped.startswith("**"):
            # Remove leading *
            text = stripped.lstrip("*").strip()
            elements.append(MdParagraph(
                [(text, CHAR_ITALIC)],
                para_pr=PARA_DEFAULT,
            ))
            i += 1
            continue

        # --- Image placeholder **[이미지N]...** ---
        if stripped.startswith("**[이미지"):
            # Skip image placeholders
            i += 1
            continue

        # --- Regular paragraph with inline bold ---
        runs = parse_inline(stripped)
        elements.append(MdParagraph(runs, para_pr=PARA_DEFAULT))
        i += 1

    return elements


# ===========================================================================
# section0.xml Generation
# ===========================================================================

def _make_run(parent, char_pr: str, text: str | None = None):
    """Create hp:run with hp:t."""
    run = etree.SubElement(parent, _qn("hp", "run"), {"charPrIDRef": char_pr})
    t = etree.SubElement(run, _qn("hp", "t"))
    if text:
        t.text = text
    return run


def _make_paragraph(parent, para_pr: str, runs: list, style_id: str = "0"):
    """Create hp:p element with multiple runs.

    Args:
        runs: list of (text, charPrIDRef) tuples
    """
    p = etree.SubElement(parent, _qn("hp", "p"), {
        "id": _next_para_id(),
        "paraPrIDRef": para_pr,
        "styleIDRef": style_id,
        "pageBreak": "0",
        "columnBreak": "0",
        "merged": "0",
    })
    if not runs:
        _make_run(p, CHAR_DEFAULT)
    else:
        for text, char_pr in runs:
            _make_run(p, char_pr, text)
    return p


def _make_empty_paragraph(parent, para_pr: str = PARA_DEFAULT):
    """Create an empty paragraph."""
    return _make_paragraph(parent, para_pr, [])


def _make_first_paragraph(root):
    """Create the first paragraph with secPr and colPr (copied from base template)."""
    p = etree.SubElement(root, _qn("hp", "p"), {
        "id": _next_para_id(),
        "paraPrIDRef": PARA_DEFAULT,
        "styleIDRef": "0",
        "pageBreak": "0",
        "columnBreak": "0",
        "merged": "0",
    })

    # First run contains secPr and colPr (ctrl)
    run1 = etree.SubElement(p, _qn("hp", "run"), {"charPrIDRef": CHAR_DEFAULT})

    # secPr
    sec_pr = etree.SubElement(run1, _qn("hp", "secPr"), {
        "id": "",
        "textDirection": "HORIZONTAL",
        "spaceColumns": "1134",
        "tabStop": "8000",
        "tabStopVal": "4000",
        "tabStopUnit": "HWPUNIT",
        "outlineShapeIDRef": "1",
        "memoShapeIDRef": "0",
        "textVerticalWidthHead": "0",
        "masterPageCnt": "0",
    })

    etree.SubElement(sec_pr, _qn("hp", "grid"), {
        "lineGrid": "0", "charGrid": "0", "wonggojiFormat": "0",
    })
    etree.SubElement(sec_pr, _qn("hp", "startNum"), {
        "pageStartsOn": "BOTH", "page": "0", "pic": "0",
        "tbl": "0", "equation": "0",
    })
    etree.SubElement(sec_pr, _qn("hp", "visibility"), {
        "hideFirstHeader": "0", "hideFirstFooter": "0",
        "hideFirstMasterPage": "0", "border": "SHOW_ALL",
        "fill": "SHOW_ALL", "hideFirstPageNum": "0",
        "hideFirstEmptyLine": "0", "showLineNumber": "0",
    })
    etree.SubElement(sec_pr, _qn("hp", "lineNumberShape"), {
        "restartType": "0", "countBy": "0", "distance": "0", "startNumber": "0",
    })

    page_pr = etree.SubElement(sec_pr, _qn("hp", "pagePr"), {
        "landscape": "WIDELY", "width": "59528",
        "height": "84186", "gutterType": "LEFT_ONLY",
    })
    etree.SubElement(page_pr, _qn("hp", "margin"), {
        "header": "4252", "footer": "4252", "gutter": "0",
        "left": "8504", "right": "8504", "top": "5668", "bottom": "4252",
    })

    # footNotePr
    fn = etree.SubElement(sec_pr, _qn("hp", "footNotePr"))
    etree.SubElement(fn, _qn("hp", "autoNumFormat"), {
        "type": "DIGIT", "userChar": "", "prefixChar": "",
        "suffixChar": ")", "supscript": "0",
    })
    etree.SubElement(fn, _qn("hp", "noteLine"), {
        "length": "-1", "type": "SOLID", "width": "0.12 mm", "color": "#000000",
    })
    etree.SubElement(fn, _qn("hp", "noteSpacing"), {
        "betweenNotes": "283", "belowLine": "567", "aboveLine": "850",
    })
    etree.SubElement(fn, _qn("hp", "numbering"), {"type": "CONTINUOUS", "newNum": "1"})
    etree.SubElement(fn, _qn("hp", "placement"), {"place": "EACH_COLUMN", "beneathText": "0"})

    # endNotePr
    en = etree.SubElement(sec_pr, _qn("hp", "endNotePr"))
    etree.SubElement(en, _qn("hp", "autoNumFormat"), {
        "type": "DIGIT", "userChar": "", "prefixChar": "",
        "suffixChar": ")", "supscript": "0",
    })
    etree.SubElement(en, _qn("hp", "noteLine"), {
        "length": "14692344", "type": "SOLID", "width": "0.12 mm", "color": "#000000",
    })
    etree.SubElement(en, _qn("hp", "noteSpacing"), {
        "betweenNotes": "0", "belowLine": "567", "aboveLine": "850",
    })
    etree.SubElement(en, _qn("hp", "numbering"), {"type": "CONTINUOUS", "newNum": "1"})
    etree.SubElement(en, _qn("hp", "placement"), {"place": "END_OF_DOCUMENT", "beneathText": "0"})

    # pageBorderFill (3 copies: BOTH, EVEN, ODD)
    for bf_type in ("BOTH", "EVEN", "ODD"):
        pbf = etree.SubElement(sec_pr, _qn("hp", "pageBorderFill"), {
            "type": bf_type, "borderFillIDRef": "1", "textBorder": "PAPER",
            "headerInside": "0", "footerInside": "0", "fillArea": "PAPER",
        })
        etree.SubElement(pbf, _qn("hp", "offset"), {
            "left": "1417", "right": "1417", "top": "1417", "bottom": "1417",
        })

    # ctrl with colPr
    ctrl = etree.SubElement(run1, _qn("hp", "ctrl"))
    etree.SubElement(ctrl, _qn("hp", "colPr"), {
        "id": "", "type": "NEWSPAPER", "layout": "LEFT",
        "colCount": "1", "sameSz": "1", "sameGap": "0",
    })

    # Second run: empty
    _make_run(p, CHAR_DEFAULT)

    return p


def _make_table(parent, headers: list, rows: list):
    """Create a proper hp:tbl element for a Markdown table.

    Since HWPX tables are quite complex, we render tables as
    simple text paragraphs with tab-separated columns and borders.
    This is more reliable than full hp:tbl which requires precise
    cell sizing.
    """
    # For simplicity and reliability, render table rows as paragraphs
    # with charPr 13 (table cell size) separated by " | "
    num_cols = len(headers)

    # Header row
    header_runs = []
    for idx, h in enumerate(headers):
        header_runs.append((h, CHAR_BOLD))
        if idx < num_cols - 1:
            header_runs.append((" | ", CHAR_TABLE))
    _make_paragraph(parent, PARA_DEFAULT, header_runs)

    # Separator line
    sep_text = "─" * 40
    _make_paragraph(parent, PARA_DEFAULT, [(sep_text, CHAR_TABLE)])

    # Data rows
    for row in rows:
        row_runs = []
        for idx, cell in enumerate(row):
            row_runs.append((cell, CHAR_TABLE))
            if idx < len(row) - 1:
                row_runs.append((" | ", CHAR_TABLE))
        _make_paragraph(parent, PARA_DEFAULT, row_runs)

    # Empty line after table
    _make_empty_paragraph(parent)


def generate_section0_xml(elements: list, output_path: Path) -> None:
    """Generate section0.xml from parsed Markdown elements."""
    # Build root element
    root = etree.Element(_qn("hs", "sec"), nsmap={
        "ha": NS["ha"],
        "hp": NS["hp"],
        "hp10": NS["hp10"],
        "hs": NS["hs"],
        "hc": NS["hc"],
        "hh": NS["hh"],
        "hhs": NS["hhs"],
        "hm": NS["hm"],
        "hpf": NS["hpf"],
        "dc": NS["dc"],
        "opf": NS["opf"],
        "ooxmlchart": NS["ooxmlchart"],
        "hwpunitchar": NS["hwpunitchar"],
        "epub": NS["epub"],
        "config": NS["config"],
    })

    # First paragraph MUST contain secPr + colPr
    _make_first_paragraph(root)

    # Render each element
    for elem in elements:
        if isinstance(elem, MdEmpty):
            _make_empty_paragraph(root)

        elif isinstance(elem, MdParagraph):
            _make_paragraph(root, elem.para_pr, elem.runs)

        elif isinstance(elem, MdCodeBlock):
            # Code block: each line as a separate paragraph with charPr 10
            # and borderFill 3 (grey background)
            for code_line in elem.lines:
                text = code_line if code_line.strip() else ""
                if text:
                    _make_paragraph(root, PARA_DEFAULT, [(text, CHAR_CODE)])
                else:
                    _make_empty_paragraph(root)

        elif isinstance(elem, MdTable):
            _make_table(root, elem.headers, elem.rows)

    # Write XML
    tree = etree.ElementTree(root)
    etree.indent(root, space="  ")
    tree.write(
        str(output_path),
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    )


# ===========================================================================
# Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Convert sermon 원고.md to HWPX format"
    )
    parser.add_argument(
        "sermon_dir",
        help="Sermon directory name or path (relative to project root or absolute)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output HWPX file path (default: sermon_dir/output/<title>.hwpx)",
    )
    args = parser.parse_args()

    # Resolve sermon directory
    sermon_dir = Path(args.sermon_dir)
    if not sermon_dir.is_absolute():
        sermon_dir = PROJECT_DIR / sermon_dir
    sermon_dir = sermon_dir.resolve()

    if not sermon_dir.is_dir():
        print(f"ERROR: Sermon directory not found: {sermon_dir}", file=sys.stderr)
        sys.exit(1)

    # Find 원고.md
    md_path = sermon_dir / "원고.md"
    if not md_path.is_file():
        print(f"ERROR: 원고.md not found in {sermon_dir}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    output_path = args.output
    if output_path is None:
        output_dir = sermon_dir / "output"
        output_dir.mkdir(exist_ok=True)
        # Try to derive title from first ## line
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
        title = "sermon"
        for line in md_text.split("\n"):
            if line.strip().startswith("## 본문"):
                # Extract title from "## 본문 : ..., 제목 : XXX"
                m = re.search(r"제목\s*[:：]\s*(.+)", line)
                if m:
                    title = m.group(1).strip()
                    break
        # Extract bible reference
        ref = sermon_dir.name
        output_path = output_dir / f"{title}-{ref}.hwpx"
    else:
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[md_to_hwpx] Input:  {md_path}")
    print(f"[md_to_hwpx] Output: {output_path}")

    # Read markdown
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Parse markdown
    print("[md_to_hwpx] Parsing markdown...")
    elements = parse_markdown(md_text)
    print(f"[md_to_hwpx] Parsed {len(elements)} elements")

    # Generate temp files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Generate header.xml
        header_path = tmp / "header.xml"
        print("[md_to_hwpx] Generating header.xml...")
        generate_header_xml(header_path)

        # Generate section0.xml
        section_path = tmp / "section0.xml"
        print("[md_to_hwpx] Generating section0.xml...")
        generate_section0_xml(elements, section_path)

        # Verify XML well-formedness
        for xml_file in [header_path, section_path]:
            try:
                etree.parse(str(xml_file))
                print(f"[md_to_hwpx] XML OK: {xml_file.name}")
            except etree.XMLSyntaxError as e:
                print(f"ERROR: Malformed XML in {xml_file.name}: {e}", file=sys.stderr)
                sys.exit(1)

        # Call build_hwpx.py
        print("[md_to_hwpx] Building HWPX...")
        # Extract title for metadata
        doc_title = "이루어지리라 - 마태복음 26:47-56"
        for line in md_text.split("\n"):
            if line.strip().startswith("## 본문"):
                m = re.search(r"제목\s*[:：]\s*(.+)", line)
                if m:
                    doc_title = m.group(1).strip()
                break

        cmd = [
            sys.executable, str(BUILD_HWPX),
            "--header", str(header_path),
            "--section", str(section_path),
            "--title", doc_title,
            "--creator", "신이재",
            "--output", str(output_path),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.returncode != 0:
            print(f"ERROR: build_hwpx.py failed with return code {result.returncode}",
                  file=sys.stderr)
            sys.exit(1)

    # Validate
    print("[md_to_hwpx] Validating...")
    cmd_validate = [
        sys.executable, str(VALIDATE_PY),
        str(output_path),
    ]
    result = subprocess.run(
        cmd_validate,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if output_path.is_file():
        size_kb = output_path.stat().st_size / 1024
        print(f"\n[md_to_hwpx] SUCCESS: {output_path}")
        print(f"[md_to_hwpx] File size: {size_kb:.1f} KB")
    else:
        print(f"\nERROR: Output file not created: {output_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
