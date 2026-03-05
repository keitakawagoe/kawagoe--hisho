"""Markdown → python-pptx 変換ヘルパー"""

import re
from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN


# 燈ブランドカラー（必要に応じて調整）
COLOR_PRIMARY = RGBColor(0x33, 0x33, 0x33)   # 本文
COLOR_ACCENT = RGBColor(0x00, 0x70, 0xC0)    # アクセント
COLOR_LIGHT = RGBColor(0x66, 0x66, 0x66)     # 補足テキスト

FONT_NAME = "Meiryo"
FONT_SIZE_BODY = Pt(14)
FONT_SIZE_BULLET = Pt(13)
FONT_SIZE_SUB = Pt(11)


def parse_markdown_to_paragraphs(text):
    """Markdownテキストを段落リストに変換する。

    Returns:
        list of dict: [{"text": str, "level": int, "bold": bool, "type": "bullet"|"number"|"text"}]
    """
    if not text:
        return []

    paragraphs = []
    lines = text.strip().split("\n")

    for line in lines:
        line = line.rstrip()
        if not line:
            continue

        # 箇条書き（ネスト対応）
        bullet_match = re.match(r'^(\s*)[-*]\s+(.*)', line)
        if bullet_match:
            indent = len(bullet_match.group(1))
            level = indent // 2  # 2スペースで1レベル
            content = bullet_match.group(2)
            paragraphs.append({
                "runs": _parse_inline(content),
                "level": level,
                "type": "bullet",
            })
            continue

        # 番号付きリスト
        number_match = re.match(r'^(\s*)\d+[.)]\s+(.*)', line)
        if number_match:
            indent = len(number_match.group(1))
            level = indent // 2
            content = number_match.group(2)
            paragraphs.append({
                "runs": _parse_inline(content),
                "level": level,
                "type": "number",
            })
            continue

        # 通常テキスト
        paragraphs.append({
            "runs": _parse_inline(line),
            "level": 0,
            "type": "text",
        })

    return paragraphs


def _parse_inline(text):
    """インラインMarkdown（太字）をRunリストに変換する。

    Returns:
        list of dict: [{"text": str, "bold": bool}]
    """
    runs = []
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            runs.append({"text": part[2:-2], "bold": True})
        else:
            runs.append({"text": part, "bold": False})
    return runs


def apply_paragraphs_to_textframe(tf, paragraphs, font_name=FONT_NAME, font_size=FONT_SIZE_BULLET):
    """パースした段落リストをpython-pptxのTextFrameに適用する。"""
    tf.clear()

    for i, para_data in enumerate(paragraphs):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()

        p.level = para_data["level"]

        if para_data["type"] == "bullet":
            # python-pptxではlevelを設定すると自動で箇条書きになる
            pass
        elif para_data["type"] == "number":
            pass  # 番号リストはpython-pptxで直接制御が難しいため箇条書きとして扱う

        for run_data in para_data["runs"]:
            run = p.add_run()
            run.text = run_data["text"]
            run.font.name = font_name
            run.font.size = font_size
            run.font.color.rgb = COLOR_PRIMARY
            if run_data["bold"]:
                run.font.bold = True


def set_text_with_font(textframe, text, font_name=FONT_NAME, font_size=FONT_SIZE_BODY,
                       bold=False, color=COLOR_PRIMARY, alignment=None):
    """TextFrameにテキストを設定する（シンプルなテキスト用）。"""
    textframe.clear()
    p = textframe.paragraphs[0]
    if alignment:
        p.alignment = alignment
    run = p.add_run()
    run.text = text
    run.font.name = font_name
    run.font.size = font_size
    run.font.bold = bold
    run.font.color.rgb = color
