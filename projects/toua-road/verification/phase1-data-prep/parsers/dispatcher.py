"""ファイル探索・パターン検出・振り分け・JSON出力"""

import json
from pathlib import Path

from .detector import ExcelPattern, detect_pattern
from . import regional_budget, kiriyama_simple

PARSER_REGISTRY = {
    ExcelPattern.REGIONAL_BUDGET: regional_budget.parse,
    ExcelPattern.KIRIYAMA_SIMPLE: kiriyama_simple.parse,
}

BASE_DIR = Path("/Users/kawagoekeita/Documents/Agent/★東亜PJ")
OUTPUT_DIR = BASE_DIR / "data"

DEFAULT_FOLDERS = [
    "202510_事前提供データ",
    "202601_提供データ（金塚）/厚木",
    "202601_提供データ（金塚）/横浜",
    "岩手",
    "宮城",
    "中部",
    "202601_提供データ（桐山）",
]


def discover_files(base_dir=None, folders=None):
    """指定フォルダから.xlsx/.xlsmファイルを収集"""
    base = Path(base_dir) if base_dir else BASE_DIR
    folder_list = folders or DEFAULT_FOLDERS

    files = []
    for folder in folder_list:
        folder_path = base / folder
        if not folder_path.exists():
            print(f"  スキップ（存在しない）: {folder}")
            continue
        for ext in ("*.xlsx", "*.xlsm"):
            files.extend(folder_path.glob(ext))

    return sorted(files, key=lambda p: str(p))


def parse_all_files(base_dir=None, folders=None, dry_run=False):
    """全ファイルを detect → dispatch → merge して JSON 出力"""
    print("=== ファイル探索 ===")
    files = discover_files(base_dir, folders)
    print(f"検出ファイル数: {len(files)}\n")

    # パターン検出
    print("=== パターン検出 ===")
    detection_results = []
    for f in files:
        pattern = detect_pattern(str(f))
        detection_results.append((f, pattern))
        status = "OK" if pattern != ExcelPattern.UNKNOWN else "??"
        print(f"  [{status}] {pattern.value:20s} {f.parent.name}/{f.name}")

    # サマリ
    counts = {}
    for _, pattern in detection_results:
        counts[pattern.value] = counts.get(pattern.value, 0) + 1
    print(f"\nパターン別集計:")
    for p, c in sorted(counts.items()):
        print(f"  {p}: {c}件")
    print(f"  合計: {len(detection_results)}件")

    if dry_run:
        print("\n--dry-run: 解析はスキップしました")
        return

    # 解析
    print(f"\n=== 解析開始 ===")
    all_projects = []
    all_direct_costs = []
    all_indirect_costs = []

    project_index = 0
    dc_index = 0
    ic_index = 0
    errors = []

    for file_path, pattern in detection_results:
        parser = PARSER_REGISTRY.get(pattern)
        if parser is None:
            print(f"  スキップ（未対応）: {file_path.name}")
            continue

        try:
            project_index += 1
            result = parser(
                str(file_path),
                project_index,
                dc_index,
                ic_index,
            )

            all_projects.append(result.project)
            all_direct_costs.extend(result.direct_costs)
            all_indirect_costs.extend(result.indirect_costs)

            dc_index += len(result.direct_costs)
            ic_index += len(result.indirect_costs)

            print(f"  解析完了: {file_path.parent.name}/{file_path.name}"
                  f" (直接工事費: {len(result.direct_costs)}件,"
                  f" 間接費: {len(result.indirect_costs)}件)")

        except Exception as e:
            errors.append((file_path, str(e)))
            print(f"  エラー: {file_path.name} - {e}")
            project_index -= 1

    # JSON出力
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    projects_path = OUTPUT_DIR / "projects.json"
    dc_path = OUTPUT_DIR / "direct_costs.json"
    ic_path = OUTPUT_DIR / "indirect_costs.json"

    with open(projects_path, "w", encoding="utf-8") as f:
        json.dump(all_projects, f, ensure_ascii=False, indent=2)

    with open(dc_path, "w", encoding="utf-8") as f:
        json.dump(all_direct_costs, f, ensure_ascii=False, indent=2)

    with open(ic_path, "w", encoding="utf-8") as f:
        json.dump(all_indirect_costs, f, ensure_ascii=False, indent=2)

    # 結果サマリ
    print(f"\n=== 解析完了 ===")
    print(f"  工事数: {len(all_projects)}件")
    print(f"  直接工事費明細数: {len(all_direct_costs)}件")
    print(f"  間接費明細数: {len(all_indirect_costs)}件")
    print(f"\n出力ファイル:")
    print(f"  {projects_path}")
    print(f"  {dc_path}")
    print(f"  {ic_path}")

    if errors:
        print(f"\n=== エラー ({len(errors)}件) ===")
        for fp, err in errors:
            print(f"  {fp.name}: {err}")

    return all_projects, all_direct_costs, all_indirect_costs
