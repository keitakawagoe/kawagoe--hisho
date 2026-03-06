"""
Claude Code のように自律的に検索を行うエージェントループ（最適化版）

LLMに検索ツールを与えて、結果を見ながら自分で判断・行動させる

最適化内容:
- Phase 1: 検索結果フィールドの削減（cost_code, per_quantity, contractor, note除去 + search_projectsにslim適用）
- Phase 2: システムプロンプト圧縮（重複排除・冗長例の圧縮）
- Phase 3: ツール定義の圧縮（重複する階層説明を削除）
"""
import os
import json
import time
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from sas_helper import add_sas_to_results


# ============================================================
# Phase 2: システムプロンプト圧縮
# - 階層構造の説明を1箇所に統合（3箇所→1箇所）
# - テーブル例を圧縮（8行→3行 + 指示）
# - ユースケースBの手順を要約
# - 自律ルール1-3を1文に要約（ルール4,5は精度維持のため残す）
# - OData例を1行に圧縮
# ============================================================
SYSTEM_PROMPT = """あなたは建設工事の過去事例を検索するAIエージェントです。

## あなたの役割
ユーザーの質問に答えるために、検索ツールを使って自律的に情報を集めます。
**ユーザーの指示を待たずに、自分で判断して行動してください。**

## 思考を言語化する
ツール呼び出し前に: (1)現状分析 (2)次のアクションと理由 (3)検索条件 を述べる。

## 利用可能なツール
- search_direct_costs: 直接工事費の明細を検索
- search_projects: プロジェクト概要を検索（工期、契約金額など）
- search_indirect_costs: 間接工事費の詳細明細を検索（共通仮設費、現場経費）

## データの階層構造

### 直接工事費（search_direct_costs）
- level=0: 工事全体 / level=1: 直接工事費合計 / level=2: 費目行（集計行）
- level=3: 工種（内訳書）— 歩掛りの親 / level=4: 内訳代価（工区別）/ level=5: 詳細明細（労務費、機械費、材料費等）
- ledger_type: 帳票種別（集計行、内訳書、内訳代価、労務費、機械費、運搬費、材料費など）
- sort_order順に並べるとExcelの表と同じツリー構造を再現できる

### 間接工事費（search_indirect_costs）
- level=0: 総括 / level=1: 集計行 / level=2: 大項目 / level=3: 詳細明細
- sort_order順で階層再現。category: '共通仮設費' or '現場経費'

## 歩掛りの検索手順
1. search_direct_costs(query="キーワード") で対象を検索
2. ヒットしたproject_idとsort_orderを確認
3. search_direct_costs(filter="project_id eq 'project_XXXX'", orderby="sort_order asc", top=200) で同工事の全明細を取得
4. sort_orderを遡り、親工種（level=3）を特定
5. 親工種から次のlevel=3の直前まで全行を抽出（全工区・全明細を含む）
6. テーブル出力:
   | level | 帳票 | 項目名 | 規格 | 単位 | 数量 | 単価 | 金額 |
   | 3 | 内訳書 | 切削OL工 | | 式 | 1 | | 48,925,250 |
   | 5 | 労務費 | ワールド夜間 | t=50mm | m2 | 8,200 | 750 | 6,150,000 |
**重要: テーブルは全行を省略せず出力すること。「以下省略」等で省略しない。**

## 間接費の検索手順
### 特定工事の内訳
1. search_projectsで対象工事のproject_idを特定
2. search_indirect_costs(query="*", filter="project_id eq 'project_XXXX' and category eq '共通仮設費'", orderby="sort_order asc", top=50)
3. level=0を除外し、テーブル出力: | 階層 | 帳票 | 工種・種別・細別 | 規格 | 単位 | 数量 | 単価 | 金額 | 構成率 |

### 複数工事の比較
工事ごとにindirect_costsを取得し、大項目(level=2)で金額比較テーブルを作成。**中央値の列を必ず含める。**

## 自律ルール
- 結果0件 → 自分でフィルタ緩和して再検索（まず広く → 絞り込み）
- **item_nameが質問の工種名と一致するか必ず確認**。関連性の低い結果は除外
- 十分な情報が集まったら最終回答: 事例を整理、データ傾向（最大値等）、file_urlがあればリンクも含める

## ODataフィルタ
branch eq '値' / quantity ge N / quantity le N / AND複合可

## 重要
- **ユーザーに「どうしますか？」と聞かない。自分で考えて行動する**
- 最低3〜5回は検索を試みてから結論を出す
- 最終回答には具体的な事例を含める
"""


def search_direct_costs(query: str, filter_expr: str = None, top: int = 50, orderby: str = None) -> dict:
    """直接工事費の明細を検索"""
    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    api_key = os.environ["AZURE_SEARCH_API_KEY"]

    client = SearchClient(
        endpoint=endpoint,
        index_name="toadoro-direct-costs",
        credential=AzureKeyCredential(api_key)
    )

    search_kwargs = {
        "search_text": query,
        "select": [
            "id", "project_id", "project_name", "branch", "location",
            "sort_order", "level", "cost_code", "ledger_type",
            "item_name", "specification", "unit",
            "quantity", "unit_price", "amount", "per_quantity",
            "file_url", "file_name",
        ],
        "top": top,
        "include_total_count": True
    }

    if filter_expr:
        search_kwargs["filter"] = filter_expr
    if orderby:
        search_kwargs["order_by"] = orderby

    try:
        results = list(client.search(**search_kwargs))
        results_list = [dict(r) for r in results]
        # SASトークン付与
        results_list = add_sas_to_results(results_list)
        return {
            "success": True,
            "count": len(results_list),
            "results": results_list
        }
    except Exception as e:
        return {"success": False, "error": str(e), "results": []}


def search_projects(query: str, filter_expr: str = None, top: int = 10) -> dict:
    """プロジェクト概要を検索"""
    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    api_key = os.environ["AZURE_SEARCH_API_KEY"]

    client = SearchClient(
        endpoint=endpoint,
        index_name="toadoro-projects",
        credential=AzureKeyCredential(api_key)
    )

    search_kwargs = {
        "search_text": query,
        "select": ["id", "project_name", "branch", "location", "contract_amount",
                   "item_keywords", "total_amount", "contract_period", "work_days",
                   "file_url", "file_name"],
        "top": top,
        "include_total_count": True
    }

    if filter_expr:
        search_kwargs["filter"] = filter_expr

    try:
        results = list(client.search(**search_kwargs))
        results_list = [dict(r) for r in results]
        # SASトークン付与
        results_list = add_sas_to_results(results_list)
        return {
            "success": True,
            "count": len(results_list),
            "results": results_list
        }
    except Exception as e:
        return {"success": False, "error": str(e), "results": []}


def search_indirect_costs(query: str, filter_expr: str = None, top: int = 50, orderby: str = None) -> dict:
    """間接工事費（共通仮設費、現場経費）の詳細明細を検索"""
    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    api_key = os.environ["AZURE_SEARCH_API_KEY"]

    client = SearchClient(
        endpoint=endpoint,
        index_name="toadoro-indirect-costs",
        credential=AzureKeyCredential(api_key)
    )

    search_kwargs = {
        "search_text": query,
        "select": [
            "id", "project_id", "project_name", "branch", "location",
            "contract_amount", "file_url", "file_name",
            "category", "sort_order", "level", "ledger_type",
            "item_name", "specification", "unit",
            "quantity", "unit_price", "amount",
            "per_quantity", "composition_rate", "contractor", "note",
        ],
        "top": top,
        "include_total_count": True
    }

    if filter_expr:
        search_kwargs["filter"] = filter_expr
    if orderby:
        search_kwargs["order_by"] = orderby

    try:
        results = list(client.search(**search_kwargs))
        results_list = [dict(r) for r in results]
        # SASトークン付与
        results_list = add_sas_to_results(results_list)
        return {
            "success": True,
            "count": len(results_list),
            "results": results_list
        }
    except Exception as e:
        return {"success": False, "error": str(e), "results": []}


# ============================================================
# Phase 3: ツール定義の圧縮
# - 階層構造の説明はシステムプロンプトに集約済みなので削除
# - パラメータ例示を最小限に
# ============================================================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_direct_costs",
            "description": "直接工事費の明細を検索。工種名、数量、単価、支店で検索可。歩掛りはproject_id+sort_order ascで取得。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索キーワード。例: '切削オーバーレイ', '*'（全件）"
                    },
                    "filter": {
                        "type": "string",
                        "description": "ODataフィルター式。例: \"project_id eq 'project_0001' and quantity ge 1000\""
                    },
                    "orderby": {
                        "type": "string",
                        "description": "並び替え。歩掛り時は 'sort_order asc'"
                    },
                    "top": {
                        "type": "integer",
                        "description": "取得件数（デフォルト50）"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_projects",
            "description": "プロジェクト概要を検索。工事名、支店、場所、契約期間、工期日数で検索可。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索キーワード"
                    },
                    "filter": {
                        "type": "string",
                        "description": "ODataフィルター式"
                    },
                    "top": {
                        "type": "integer",
                        "description": "取得件数（デフォルト10）"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_indirect_costs",
            "description": "間接工事費（共通仮設費・現場経費）の詳細明細を検索。project_idでフィルタすると1工事分を取得可。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索キーワード。例: '仮設', '*'（全件）"
                    },
                    "filter": {
                        "type": "string",
                        "description": "ODataフィルター式。例: \"project_id eq 'project_0048' and category eq '共通仮設費'\""
                    },
                    "orderby": {
                        "type": "string",
                        "description": "並び替え。テーブル時は 'sort_order asc'"
                    },
                    "top": {
                        "type": "integer",
                        "description": "取得件数（デフォルト50）"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


def _slim_results(result: dict, keep_fields: list, meta_fields: list = None) -> dict:
    """LLMに渡す結果を軽量化: メタフィールドは1件目のみ残す"""
    if not result.get("success") or not result.get("results"):
        return result
    slimmed = []
    for i, r in enumerate(result["results"]):
        row = {k: r[k] for k in keep_fields if k in r}
        if i == 0 and meta_fields:
            for k in meta_fields:
                if k in r:
                    row[k] = r[k]
        slimmed.append(row)
    return {"success": True, "count": result["count"], "results": slimmed}


# ============================================================
# Phase 1: 検索結果フィールドの削減
# - search_direct_costs: cost_code, per_quantity を削除
# - search_indirect_costs: per_quantity, contractor, note を削除
# - search_projects: _slim_results()を新規適用（item_keywords, total_amount, work_days, id を削除）
# ============================================================
def execute_tool(tool_name: str, arguments: dict) -> str:
    """ツールを実行して結果を返す"""
    if tool_name == "search_direct_costs":
        result = search_direct_costs(
            query=arguments.get("query", "*"),
            filter_expr=arguments.get("filter"),
            top=arguments.get("top", 50),
            orderby=arguments.get("orderby"),
        )
        # Phase 1: cost_code, per_quantity を削除
        result = _slim_results(result,
            keep_fields=["project_id", "level", "sort_order", "ledger_type",
                         "item_name", "specification", "unit", "quantity", "unit_price", "amount"],
            meta_fields=["project_name", "branch", "location", "file_url", "file_name"])
    elif tool_name == "search_projects":
        result = search_projects(
            query=arguments.get("query", "*"),
            filter_expr=arguments.get("filter"),
            top=arguments.get("top", 10)
        )
        # Phase 1: _slim_results()を新規適用（item_keywords, total_amount, work_days, id を除外）
        result = _slim_results(result,
            keep_fields=["project_name", "branch", "location", "contract_amount", "contract_period"],
            meta_fields=["file_url", "file_name"])
    elif tool_name == "search_indirect_costs":
        result = search_indirect_costs(
            query=arguments.get("query", "*"),
            filter_expr=arguments.get("filter"),
            top=arguments.get("top", 50),
            orderby=arguments.get("orderby"),
        )
        # Phase 1: per_quantity, contractor, note を削除
        result = _slim_results(result,
            keep_fields=["project_id", "level", "sort_order", "ledger_type", "category",
                         "item_name", "specification", "unit", "quantity", "unit_price", "amount",
                         "composition_rate"],
            meta_fields=["project_name", "branch", "location", "file_url", "file_name", "contract_amount"])
    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return json.dumps(result, ensure_ascii=False, indent=2)


def agent_loop(payload: dict) -> dict:
    """
    Claude Code のような自律的エージェントループ

    LLMがツールを呼び出し、結果を見て、また呼び出す...を繰り返す
    """
    client = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2024-02-01",
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"]
    )

    user_query = payload.get("user_query", "")
    max_iterations = payload.get("max_iterations", 10)

    # 会話履歴
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query}
    ]

    # 思考とツール呼び出しの履歴
    thinking_history = []

    for iteration in range(max_iterations):
        # レートリミット回避: 2回目以降は2秒待機
        if iteration > 0:
            time.sleep(2)

        # LLMに問い合わせ
        response = client.chat.completions.create(
            model=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1"),
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3
        )

        assistant_message = response.choices[0].message
        messages.append(assistant_message.model_dump())

        # 思考（テキスト部分）を記録
        thinking = assistant_message.content or ""

        # ツール呼び出しがない場合は終了（最終回答）
        if not assistant_message.tool_calls:
            return {
                "status": "completed",
                "iterations": iteration + 1,
                "final_answer": assistant_message.content,
                "thinking_history": thinking_history
            }

        # このイテレーションの記録
        iteration_record = {
            "iteration": iteration + 1,
            "thinking": thinking,
            "tool_calls": []
        }

        # ツールを実行
        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            # ツール実行
            result = execute_tool(tool_name, arguments)
            result_json = json.loads(result)

            # ツール呼び出し記録（簡潔に）
            iteration_record["tool_calls"].append({
                "tool": tool_name,
                "arguments": arguments,
                "result_count": result_json.get("count", 0)
            })

            # 結果をメッセージに追加
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })

        thinking_history.append(iteration_record)

    # 最大イテレーション到達
    return {
        "status": "max_iterations_reached",
        "iterations": max_iterations,
        "final_answer": "最大イテレーション数に達しました。",
        "thinking_history": thinking_history
    }
