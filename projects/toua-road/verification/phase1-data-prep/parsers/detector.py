"""パターン検出: シート名ベースでExcelのフォーマットを判定"""

from enum import Enum
import openpyxl


class ExcelPattern(Enum):
    REGIONAL_BUDGET = "regional_budget"    # パターンA/B: 実行予算書鑑ベース
    KIRIYAMA_SIMPLE = "kiriyama_simple"    # パターンC: データ/内訳一覧
    UNKNOWN = "unknown"


def detect_pattern(file_path: str) -> ExcelPattern:
    """シート名のみ読み取り、Excelパターンを判定"""
    try:
        wb = openpyxl.load_workbook(file_path, read_only=True)
        sheets = wb.sheetnames
        wb.close()
    except Exception:
        return ExcelPattern.UNKNOWN

    if '実行予算書鑑' in sheets:
        return ExcelPattern.REGIONAL_BUDGET
    if 'データ' in sheets and '内訳一覧' in sheets:
        return ExcelPattern.KIRIYAMA_SIMPLE
    return ExcelPattern.UNKNOWN
