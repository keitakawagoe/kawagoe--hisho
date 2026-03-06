#!/usr/bin/env python3
"""間接費データのローカル検証スクリプト

検証1: 特定工事の共通仮設費・現場経費テーブル表示（Excelの列順そのまま）
検証2: 複数工事の項目別中央値算出

Usage:
    python verify_indirect.py
"""

import json
from pathlib import Path
from statistics import median

DATA_DIR = Path("/Users/kawagoekeita/Documents/Agent/★東亜PJ/data")


def load_data():
    with open(DATA_DIR / "indirect_costs.json", "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_num(val, width=12):
    """数値をカンマ区切りでフォーマット"""
    if val is None or val == "":
        return " " * width
    if isinstance(val, float):
        if val == int(val):
            return f"{int(val):>{width},}"
        return f"{val:>{width},.3f}"
    return f"{val:>{width},}"


def fmt_rate(val, width=7):
    """構成率をパーセント表示"""
    if val is None or val == "":
        return " " * width
    return f"{val * 100:>{width}.1f}%"


def verify_table(data, project_id, category):
    """特定工事・カテゴリのテーブルを表示"""
    records = [
        d for d in data
        if d["project_id"] == project_id and d["category"] == category
    ]
    records.sort(key=lambda x: x["sort_order"])

    if not records:
        print(f"  データなし: {project_id} / {category}")
        return

    project_name = records[0]["project_name"]
    print(f"\n  工事名: {project_name}")
    print(f"  カテゴリ: {category} ({len(records)}行)")
    print()

    # ヘッダー
    header = (
        f"{'階層':>4} | {'原価工種ｺｰﾄﾞ':>14} | {'帳票':<8} | {'工種・種別・細別':<30} | "
        f"{'規格':<20} | {'単位':<4} | {'数量':>12} | {'単価':>12} | {'金額':>12} | "
        f"{'当り数量':>10} | {'構成率':>7} | {'業者名':<10} | {'摘要':<10}"
    )
    print(f"  {header}")
    print(f"  {'─' * len(header)}")

    for r in records:
        line = (
            f"{r['level'] if r['level'] is not None else '':>4} | "
            f"{r['cost_code'] or '':>14} | "
            f"{r['ledger_type'] or '':<8} | "
            f"{r['item_name'] or '':<30} | "
            f"{r['specification'] or '':<20} | "
            f"{r['unit'] or '':<4} | "
            f"{fmt_num(r['quantity'])} | "
            f"{fmt_num(r['unit_price'])} | "
            f"{fmt_num(r['amount'])} | "
            f"{fmt_num(r['per_quantity'], 10)} | "
            f"{fmt_rate(r['composition_rate'])} | "
            f"{r['contractor'] or '':<10} | "
            f"{r['note'] or '':<10}"
        )
        print(f"  {line}")


def verify_median(data, project_ids, category, level=2):
    """複数工事の項目別中央値テーブル"""
    print(f"\n  カテゴリ: {category}  |  Level: {level}  |  対象工事: {len(project_ids)}件")

    # 工事ごとのLevel 2項目を収集
    project_items = {}
    project_names = {}
    for pid in project_ids:
        records = [
            d for d in data
            if d["project_id"] == pid and d["category"] == category and d.get("level") == level
        ]
        items = {}
        for r in records:
            name = r["item_name"]
            items[name] = r["amount"] or 0
        project_items[pid] = items
        if records:
            project_names[pid] = records[0]["project_name"][:15]
        else:
            project_names[pid] = pid

    # 全項目名を集める（出現順）
    all_items = []
    seen = set()
    for pid in project_ids:
        for name in project_items[pid]:
            if name not in seen:
                all_items.append(name)
                seen.add(name)

    # ヘッダー
    cols = [f"{'項目名':<20}"]
    for pid in project_ids:
        cols.append(f"{project_names[pid]:>16}")
    cols.append(f"{'中央値':>12}")
    header = " | ".join(cols)
    print(f"\n  {header}")
    print(f"  {'─' * len(header)}")

    for item_name in all_items:
        vals = []
        row = [f"{item_name:<20}"]
        for pid in project_ids:
            v = project_items[pid].get(item_name, 0)
            vals.append(v)
            row.append(fmt_num(v, 16))
        med = median(vals)
        row.append(fmt_num(med))
        print(f"  {' | '.join(row)}")


def main():
    data = load_data()
    print(f"間接費レコード数: {len(data)}")

    # プロジェクトIDの一覧取得
    projects = {}
    for d in data:
        pid = d["project_id"]
        if pid not in projects:
            projects[pid] = {
                "name": d["project_name"],
                "folder": d["folder"],
                "filename": d["filename"],
            }

    print(f"間接費を持つ工事数: {len(projects)}件\n")

    # === 検証1: 多摩市鶴牧3丁目のテーブル表示 ===
    print("=" * 80)
    print("検証1: 特定工事のテーブル表示")
    print("=" * 80)

    # 多摩市鶴牧 = 横浜/2220710229.xlsm を探す
    target_pid = None
    for pid, info in projects.items():
        if "2220710229" in info["filename"]:
            target_pid = pid
            break

    if target_pid:
        verify_table(data, target_pid, "共通仮設費")
        verify_table(data, target_pid, "現場経費")
    else:
        print("多摩市鶴牧の工事が見つかりません")

    # === 検証2: 横浜支店の工事で中央値 ===
    print("\n" + "=" * 80)
    print("検証2: 複数工事の項目別中央値")
    print("=" * 80)

    # 横浜フォルダの工事を取得
    yokohama_pids = [
        pid for pid, info in projects.items()
        if info["folder"] == "横浜"
    ]
    yokohama_pids.sort()

    if len(yokohama_pids) >= 2:
        print(f"\n  対象: 横浜支店 {len(yokohama_pids)}工事")
        for pid in yokohama_pids:
            print(f"    {pid}: {projects[pid]['name'][:40]} ({projects[pid]['filename']})")
        verify_median(data, yokohama_pids, "共通仮設費", level=2)
        verify_median(data, yokohama_pids, "現場経費", level=2)
    else:
        print("横浜支店の工事が不足しています")

    # 厚木でも検証（17工事）
    atsugi_pids = [
        pid for pid, info in projects.items()
        if info["folder"] == "厚木"
    ]
    atsugi_pids.sort()

    if len(atsugi_pids) >= 3:
        # 最初の5件だけ
        sample = atsugi_pids[:5]
        print(f"\n  対象: 厚木支店 {len(sample)}工事（先頭5件）")
        for pid in sample:
            print(f"    {pid}: {projects[pid]['name'][:40]} ({projects[pid]['filename']})")
        verify_median(data, sample, "共通仮設費", level=2)


if __name__ == "__main__":
    main()
