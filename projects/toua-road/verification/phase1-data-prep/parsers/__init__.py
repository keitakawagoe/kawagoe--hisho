"""Excel パーサーディスパッチャー パッケージ"""

from .base import ParseResult, safe_str, safe_number, safe_int, clean_item_name, build_search_text, format_date_value
from .detector import ExcelPattern, detect_pattern
from .dispatcher import parse_all_files, discover_files
