"""
ReActエージェントの1やりとりあたりのトークン消費量を計測するスクリプト

現行版 vs 最適化版 の比較を行う
"""

import tiktoken
import json
import sys
import os

# GPT-4.1 は cl100k_base エンコーディング
enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(enc.encode(text))


# ================================================================
# 現行版のシステムプロンプト・ツール定義を読み込み
# ================================================================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent_loop as original
import agent_loop_optimized as optimized


# ================================================================
# サンプル検索結果データ
# ================================================================

# 現行版: direct_costs slimmed後の1レコード (12フィールド)
SAMPLE_DIRECT_ORIGINAL = {
    "project_id": "project_0048",
    "level": 5,
    "sort_order": 1234,
    "ledger_type": "労務費",
    "cost_code": "301-002",
    "item_name": "切削オーバーレイ工（夜間）",
    "specification": "t=50mm, W=3.5m",
    "unit": "m2",
    "quantity": 8200.0,
    "unit_price": 750,
    "amount": 6150000,
    "per_quantity": 1.0
}
SAMPLE_DIRECT_ORIGINAL_META = {
    **SAMPLE_DIRECT_ORIGINAL,
    "project_name": "令和5年度 国道16号 横浜地区舗装補修工事",
    "branch": "関東支社",
    "location": "神奈川県横浜市",
    "file_url": "https://toadorofilestorage.blob.core.windows.net/toadoro-files/project_0048_%E5%86%85%E8%A8%B3%E6%9B%B8.xlsx?se=2036-02-03&sp=r&sv=2026-02-06&sr=b&sig=XXXXXXXXX",
    "file_name": "project_0048_内訳書.xlsx"
}

# 最適化版: direct_costs slimmed後の1レコード (10フィールド: cost_code, per_quantity削除)
SAMPLE_DIRECT_OPTIMIZED = {
    "project_id": "project_0048",
    "level": 5,
    "sort_order": 1234,
    "ledger_type": "労務費",
    "item_name": "切削オーバーレイ工（夜間）",
    "specification": "t=50mm, W=3.5m",
    "unit": "m2",
    "quantity": 8200.0,
    "unit_price": 750,
    "amount": 6150000,
}
SAMPLE_DIRECT_OPTIMIZED_META = {
    **SAMPLE_DIRECT_OPTIMIZED,
    "project_name": "令和5年度 国道16号 横浜地区舗装補修工事",
    "branch": "関東支社",
    "location": "神奈川県横浜市",
    "file_url": "https://toadorofilestorage.blob.core.windows.net/toadoro-files/project_0048_%E5%86%85%E8%A8%B3%E6%9B%B8.xlsx?se=2036-02-03&sp=r&sv=2026-02-06&sr=b&sig=XXXXXXXXX",
    "file_name": "project_0048_内訳書.xlsx"
}

# 現行版: search_projects (スリムなし、全フィールド)
SAMPLE_PROJECT_ORIGINAL = {
    "id": "project_0048",
    "project_name": "令和5年度 国道16号 横浜地区舗装補修工事",
    "branch": "関東支社",
    "location": "神奈川県横浜市",
    "contract_amount": 150000000,
    "item_keywords": "切削オーバーレイ,区画線,排水構造物,ガードレール,防護柵,道路標識,舗装補修,クラック注入",
    "total_amount": 148500000,
    "contract_period": "2023/04/01〜2024/03/31",
    "work_days": 250,
    "file_url": "https://toadorofilestorage.blob.core.windows.net/toadoro-files/project_0048.xlsx?se=2036-02-03&sp=r&sv=2026-02-06&sr=b&sig=XXXXXXXXX",
    "file_name": "project_0048.xlsx"
}

# 最適化版: search_projects (スリム適用後)
SAMPLE_PROJECT_OPTIMIZED = {
    "project_name": "令和5年度 国道16号 横浜地区舗装補修工事",
    "branch": "関東支社",
    "location": "神奈川県横浜市",
    "contract_amount": 150000000,
    "contract_period": "2023/04/01〜2024/03/31",
}
SAMPLE_PROJECT_OPTIMIZED_META = {
    **SAMPLE_PROJECT_OPTIMIZED,
    "file_url": "https://toadorofilestorage.blob.core.windows.net/toadoro-files/project_0048.xlsx?se=2036-02-03&sp=r&sv=2026-02-06&sr=b&sig=XXXXXXXXX",
    "file_name": "project_0048.xlsx"
}

# 現行版: indirect_costs slimmed後 (14フィールド)
SAMPLE_INDIRECT_ORIGINAL = {
    "project_id": "project_0048",
    "level": 2,
    "sort_order": 50,
    "ledger_type": "内訳代価",
    "category": "共通仮設費",
    "item_name": "重機運搬費",
    "specification": "",
    "unit": "式",
    "quantity": 1,
    "unit_price": 530000,
    "amount": 530000,
    "per_quantity": 1.0,
    "composition_rate": 3.2,
    "contractor": "○○建機リース",
    "note": "10t級クレーン"
}

# 最適化版: indirect_costs slimmed後 (11フィールド: per_quantity, contractor, note削除)
SAMPLE_INDIRECT_OPTIMIZED = {
    "project_id": "project_0048",
    "level": 2,
    "sort_order": 50,
    "ledger_type": "内訳代価",
    "category": "共通仮設費",
    "item_name": "重機運搬費",
    "specification": "",
    "unit": "式",
    "quantity": 1,
    "unit_price": 530000,
    "amount": 530000,
    "composition_rate": 3.2,
}

# LLM応答のサンプル
SAMPLE_THINKING = """切削オーバーレイで検索してデータの全体像を確認します。まずフィルタなしで広く検索し、どのプロジェクトにどの程度の数量があるか把握します。"""

SAMPLE_FINAL_ANSWER = """## 検索結果

切削オーバーレイ工 8,000m²に近い事例を検索しました。

### 見つかった事例

| # | 工事名 | 支店 | 数量(m²) | 単価(円) | 金額(円) |
|---|--------|------|----------|----------|----------|
| 1 | 令和5年度 国道16号 横浜地区舗装補修工事 | 関東支社 | 8,200 | 750 | 6,150,000 |
| 2 | 令和4年度 国道1号 静岡地区舗装工事 | 中部支社 | 7,500 | 800 | 6,000,000 |
| 3 | 令和5年度 国道246号 厚木補修工事 | 関東支社 | 6,800 | 780 | 5,304,000 |

### データの傾向
- 8,000m²前後の事例は3件見つかりました
- 単価帯: 750〜800円/m²
- 最大数量: 8,200m²（横浜地区）

### 関連ファイル
- [project_0048_内訳書.xlsx](https://...)
- [project_0032_内訳書.xlsx](https://...)"""


# ================================================================
# 比較計算
# ================================================================

def build_result_json(records_with_meta, records, count):
    result = {"success": True, "count": count, "results": [records_with_meta] + [records] * (count - 1)}
    return json.dumps(result, ensure_ascii=False, indent=2)


def estimate(label, system_prompt, tools, direct_result_tokens, project_result_tokens, indirect_result_tokens):
    """固定コスト + シナリオ別の推定"""
    sys_tokens = count_tokens(system_prompt)
    tools_json = json.dumps(tools, ensure_ascii=False)
    tools_tokens = int(count_tokens(tools_json) * 1.1)
    fixed = sys_tokens + tools_tokens

    thinking_tokens = count_tokens(SAMPLE_THINKING)
    tool_call_tokens = count_tokens(json.dumps({"query": "切削オーバーレイ", "filter": "quantity ge 5000", "top": 50}, ensure_ascii=False))
    final_tokens = count_tokens(SAMPLE_FINAL_ANSWER)

    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  システムプロンプト:    {sys_tokens:>6,} tokens")
    print(f"  ツール定義:           {tools_tokens:>6,} tokens")
    print(f"  固定コスト合計:       {fixed:>6,} tokens")
    print(f"  ---")
    print(f"  direct_costs (50件):  {direct_result_tokens:>6,} tokens")
    print(f"  projects     (10件):  {project_result_tokens:>6,} tokens")
    print(f"  indirect_costs(50件): {indirect_result_tokens:>6,} tokens")

    # 代表的な検索結果トークン（direct_costsが最も多く使われる）
    avg_result = direct_result_tokens
    user_query_tokens = 30

    results = {}
    for scenario_name, iters in [("3回検索", 3), ("5回検索", 5), ("8回検索", 8), ("10回検索", 10)]:
        total_input = 0
        total_output = 0
        cumulative = 0
        for i in range(iters):
            total_input += fixed + user_query_tokens + cumulative
            if i < iters - 1:
                out = thinking_tokens + tool_call_tokens
                total_output += out
                cumulative += out + avg_result
            else:
                total_output += final_tokens

        cost_input = total_input / 1_000_000 * 3.50
        cost_output = total_output / 1_000_000 * 14.00
        cost_total = cost_input + cost_output
        cost_yen = cost_total * 154.6

        results[scenario_name] = {
            "input": total_input, "output": total_output,
            "cost_usd": cost_total, "cost_yen": cost_yen
        }

        print(f"\n  【{scenario_name}】 Input: {total_input:>8,} / Output: {total_output:>8,} → ${cost_total:.4f} (約{cost_yen:.1f}円)")

    return results


# --- 現行版 ---
orig_direct_50 = build_result_json(SAMPLE_DIRECT_ORIGINAL_META, SAMPLE_DIRECT_ORIGINAL, 50)
orig_project_10 = build_result_json(SAMPLE_PROJECT_ORIGINAL, SAMPLE_PROJECT_ORIGINAL, 10)
orig_indirect_50 = build_result_json(SAMPLE_INDIRECT_ORIGINAL, SAMPLE_INDIRECT_ORIGINAL, 50)

orig_results = estimate(
    "【現行版】agent_loop.py",
    original.SYSTEM_PROMPT,
    original.TOOLS,
    count_tokens(orig_direct_50),
    count_tokens(orig_project_10),
    count_tokens(orig_indirect_50),
)

# --- 最適化版 ---
opt_direct_50 = build_result_json(SAMPLE_DIRECT_OPTIMIZED_META, SAMPLE_DIRECT_OPTIMIZED, 50)
opt_project_10 = build_result_json(SAMPLE_PROJECT_OPTIMIZED_META, SAMPLE_PROJECT_OPTIMIZED, 10)
opt_indirect_50 = build_result_json(SAMPLE_INDIRECT_OPTIMIZED, SAMPLE_INDIRECT_OPTIMIZED, 50)

opt_results = estimate(
    "【最適化版】agent_loop_optimized.py",
    optimized.SYSTEM_PROMPT,
    optimized.TOOLS,
    count_tokens(opt_direct_50),
    count_tokens(opt_project_10),
    count_tokens(opt_indirect_50),
)

# --- 差分比較 ---
print(f"\n\n{'=' * 60}")
print(f"  ■ 現行版 vs 最適化版 比較")
print(f"{'=' * 60}")
print(f"\n  {'シナリオ':<12} {'現行Input':>12} {'最適Input':>12} {'削減':>8} {'削減率':>6}  {'現行コスト':>8} {'最適コスト':>8} {'差額':>6}")
print(f"  {'-' * 80}")

for scenario in ["3回検索", "5回検索", "8回検索", "10回検索"]:
    o = orig_results[scenario]
    n = opt_results[scenario]
    diff_input = o["input"] - n["input"]
    pct = diff_input / o["input"] * 100
    diff_yen = o["cost_yen"] - n["cost_yen"]
    print(f"  {scenario:<12} {o['input']:>10,}t {n['input']:>10,}t {diff_input:>7,}t {pct:>5.1f}%  {o['cost_yen']:>6.1f}円 {n['cost_yen']:>6.1f}円 {diff_yen:>+5.1f}円")

# --- 固定コストの差分詳細 ---
orig_sys = count_tokens(original.SYSTEM_PROMPT)
opt_sys = count_tokens(optimized.SYSTEM_PROMPT)
orig_tools = int(count_tokens(json.dumps(original.TOOLS, ensure_ascii=False)) * 1.1)
opt_tools = int(count_tokens(json.dumps(optimized.TOOLS, ensure_ascii=False)) * 1.1)

print(f"\n  ■ 固定コスト内訳")
print(f"  {'項目':<24} {'現行':>8} {'最適化':>8} {'削減':>8} {'削減率':>6}")
print(f"  {'-' * 60}")
print(f"  {'システムプロンプト':<16} {orig_sys:>6,}t {opt_sys:>6,}t {orig_sys - opt_sys:>6,}t {(orig_sys - opt_sys) / orig_sys * 100:>5.1f}%")
print(f"  {'ツール定義':<20} {orig_tools:>6,}t {opt_tools:>6,}t {orig_tools - opt_tools:>6,}t {(orig_tools - opt_tools) / orig_tools * 100:>5.1f}%")
print(f"  {'固定合計':<22} {orig_sys + orig_tools:>6,}t {opt_sys + opt_tools:>6,}t {(orig_sys + orig_tools) - (opt_sys + opt_tools):>6,}t")

# --- 検索結果の差分詳細 ---
orig_d = count_tokens(orig_direct_50)
opt_d = count_tokens(opt_direct_50)
orig_p = count_tokens(orig_project_10)
opt_p = count_tokens(opt_project_10)
orig_i = count_tokens(orig_indirect_50)
opt_i = count_tokens(opt_indirect_50)

print(f"\n  ■ 検索結果(toolメッセージ) 1回あたり")
print(f"  {'ツール':<28} {'現行':>8} {'最適化':>8} {'削減':>8} {'削減率':>6}")
print(f"  {'-' * 64}")
print(f"  {'direct_costs (50件)':<22} {orig_d:>6,}t {opt_d:>6,}t {orig_d - opt_d:>6,}t {(orig_d - opt_d) / orig_d * 100:>5.1f}%")
print(f"  {'projects (10件)':<22} {orig_p:>6,}t {opt_p:>6,}t {orig_p - opt_p:>6,}t {(orig_p - opt_p) / orig_p * 100:>5.1f}%")
print(f"  {'indirect_costs (50件)':<22} {orig_i:>6,}t {opt_i:>6,}t {orig_i - opt_i:>6,}t {(orig_i - opt_i) / orig_i * 100:>5.1f}%")
