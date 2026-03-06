"""共通定義: ParseResult, ユーティリティ関数"""

import re
from dataclasses import dataclass, field
from datetime import datetime, date


@dataclass
class ParseResult:
    """パーサーの戻り値"""
    project: dict
    direct_costs: list
    indirect_costs: list
    source_file: str
    pattern: str


def safe_str(value) -> str:
    """値を安全に文字列に変換"""
    if value is None:
        return ""
    return str(value).strip()


def safe_number(value):
    """値を安全に数値に変換"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        cleaned = str(value).replace(",", "").strip()
        if cleaned == "" or cleaned == "-":
            return None
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def safe_int(value):
    """値を安全に整数に変換"""
    num = safe_number(value)
    if num is None:
        return None
    return int(num)


def clean_item_name(name: str) -> str:
    """工種名から階層表示記号を除去"""
    if not name:
        return ""
    return re.sub(r'^[｜|]+', '', name).strip()


def build_search_text(*fields) -> str:
    """検索用テキストを構築"""
    texts = [safe_str(f) for f in fields if f]
    return " ".join([t for t in texts if t])


def format_date_value(value) -> str:
    """datetime/文字列/Noneを統一的に日付文字列へ変換"""
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return f"{value.year}年{value.month}月{value.day}日"
    s = str(value).strip()
    return s if s else ""
