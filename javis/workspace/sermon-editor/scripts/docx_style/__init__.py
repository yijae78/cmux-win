"""DOCX v2 빌더 모듈 — MD → DOCX 변환 스타일 매핑."""

from .style import STYLE
from .oxml_helpers import (
    set_cell_shading,
    set_cell_border,
    set_run_scale,
    set_run_spacing,
    set_run_korean_font,
    add_paragraph_border_bottom,
    add_horizontal_rule,
)

__all__ = [
    "STYLE",
    "set_cell_shading",
    "set_cell_border",
    "set_run_scale",
    "set_run_spacing",
    "set_run_korean_font",
    "add_paragraph_border_bottom",
    "add_horizontal_rule",
]
