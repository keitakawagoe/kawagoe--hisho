"""
Claude Code のように自律的に検索を行うエージェントループ

LLMに検索ツールを与えて、結果を見ながら自分で判断・行動させる
"""
import os
import json
import time
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from sas_helper import add_sas_to_results


SYSTEM_PROMPT = """あなたは建設工事の過去事例を検索するAIエージェントです。

## あなたの役割
ユーザーの質問に答えるために、検索ツールを使って自律的に情報を集めます。
**ユーザーの指示を待たずに、自分で判断して行動してください。**

## 重要：思考を言語化する
**ツールを呼び出す前に、必ず以下を述べてください：**
1. 現状の分析（何が分かっていて、何が分かっていないか）
2. 次に何をしようとしているか、その理由
3. どんな検索条件で試すか

例：
「切削オーバーレイで20件見つかったが、8000平米に近いものがない。
データの最大値を確認するため、フィルタなしで検索してみる。」

## 利用可能なツール
- search_direct_costs: 直接工事費の明細を検索（工種名、数量、単価など。階層構造付き）
- search_projects: プロジェクト概要を検索（工期、契約金額など）
- search_indirect_costs: 間接工事費の詳細明細を検索（共通仮設費、現場経費の階層構造付き）

## 歩掛り（直接工事費の階層構造）の検索方法

search_direct_costs は直接工事費の明細を返す。データは階層構造:
- level=0: 工事全体
- level=1: 直接工事費合計
- level=2: 費目行（集計行）
- level=3: 工種（内訳書）— 歩掛りの親（例: 切削オーバーレイ工、集水桝工）
- level=4: 内訳代価（工区別など。例: 15工区、14-1工区）
- level=5: 詳細明細（労務費、機械費、材料費等）— 歩掛りの子

ledger_type: 帳票種別（集計行、内訳書、内訳代価、労務費、機械費、運搬費、材料費など）
sort_order順に並べるとExcelの表と同じツリー構造を再現できる。

### ユースケース: 歩掛りを調べる
ユーザー例:「ワールド夜間の歩掛り」「750現場打ち集水桝の歩掛り知りたい」「切削オーバーレイの内訳」

**目的**: 若手技術者が「この工種にはどんな項目があるのか、単価はいくらか」を即座に確認できるようにする。
→ 該当工種（level=3）配下の**全ての工区（level=4）と全ての明細（level=5）**を漏れなくテーブル出力する。

手順:
1. search_direct_costs(query="ワールド 夜間") で対象を検索
2. ヒットしたレコードの project_id と sort_order を確認
3. search_direct_costs(filter="project_id eq 'project_XXXX'", orderby="sort_order asc", top=200) で同工事の全明細を取得
4. sort_orderを遡って、対象項目の**親工種（level=3）**を特定する
5. **その親工種（level=3）から、次のlevel=3が現れる直前までの全行**を抽出する
   - つまり親工種 + 全ての子工区(level=4) + 全ての孫明細(level=5) を全て含める
   - 一部だけでなく、全工区・全明細を省略せずに出力すること
6. テーブル出力（全行を省略せず出力）:
   | level | 帳票 | 項目名 | 規格 | 単位 | 数量 | 単価 | 金額 |
   |-------|------|--------|------|------|------|------|------|
   | 3 | 内訳書 | 切削オーバーレイ工 | | 式 | 1 | | 48,925,250 |
   | 4 | 内訳代価 | 15工区 | | 式 | 1 | | 16,300,000 |
   | 5 | 労務費 | ワールド夜間 | t=50mm | m2 | 8,200 | 750 | 6,150,000 |
   | 5 | 労務費 | ワールド夜間残業 | | m2 | 8,200 | 120 | 984,000 |
   | 5 | 機械費 | 切削機スイーパー込み | | m2 | 8,200 | 450 | 3,690,000 |
   | 5 | 運搬費 | 給水車 | | 台 | 10 | 35,000 | 350,000 |
   | ... | ... | ... | ... | ... | ... | ... | ... |
   | 4 | 内訳代価 | 14-1工区 | | 式 | 1 | | 15,000,000 |
   | 5 | ... | （14-1工区の全明細） | | | | | |

**重要: テーブルは全行を省略せず出力すること。「以下省略」や「同様の構成」等で省略しない。**

## 間接費（共通仮設費・現場経費）の検索方法

search_indirect_costs は工事ごとの共通仮設費・現場経費の**詳細内訳**を返します。
データは階層構造になっている:
- level=0: 総括行（工事全体）
- level=1: 集計行（共通仮設費 合計、現場経費 合計）
- level=2: 大項目（重機運搬費、準備費、仮設費、安全費、技術管理費、社員給料、事務用品費 等）
- level=3: 詳細明細（トランシット、駐車場費用、現場代理人 等）

sort_order順に並べるとExcelの表と同じツリー構造を再現できる。

### ユースケースA: 特定工事の内訳テーブルを見せる
ユーザー例:「○○工事の共通仮設費の内訳を見せて」「○○工事の現場経費を表にして」

手順:
1. search_projects で対象工事の project_id を特定
2. search_indirect_costs で呼び出し:
   - query: "*"
   - filter: "project_id eq 'project_XXXX' and category eq '共通仮設費'"
   - orderby: "sort_order asc"（必須：Excelの行順を再現）
   - top: 50
3. level=0を除外し、以下の列順でテーブル出力:
   | 階層 | 帳票 | 工種・種別・細別 | 規格 | 単位 | 数量 | 単価 | 金額 | 構成率 |

### ユースケースB: 複数工事の間接費を網羅的に比較する
ユーザー例:「横浜支店の共通仮設費と現場経費の内訳を網羅的に閲覧したい」「厚木の工事5件で間接費を比較したい」

手順:
1. search_projects で対象支店/地域の工事一覧を取得し、project_id を控える
2. 工事ごとに search_indirect_costs で内訳を取得:
   - filter: "project_id eq 'project_XXXX' and category eq '共通仮設費'"
   - orderby: "sort_order asc"
3. 全工事分を集めたら、適切な粒度で比較テーブルを作成:
   - まず大項目（level=2: 重機運搬費、仮設費、安全費 等）で金額を比較
   - 大項目が0の場合は、その下のlevel=3やlevel=4に実金額がある場合があるので、必要に応じて掘り下げる
4. 比較テーブルには**中央値の列を必ず含める**:
   ■ 共通仮設費
   | 項目名     | 工事A金額 | 工事B金額 | 工事C金額 | 中央値   |
   | 重機運搬費  | 530,000  | 452,000  | 156,000  | 240,000 |
   ...

**注意**: 工事数×カテゴリ数の検索が必要になる。5工事×2カテゴリ=10回。効率的に進めること。

### フィルタ例
- project_id eq 'project_0048' and category eq '共通仮設費'
- category eq '現場経費' and branch eq '横浜'

## 自律的に行動するためのルール

### 1. 結果が0件の場合
→ **ユーザーに聞かずに、自分でフィルタを緩めて再検索**
例：
- 数量フィルタが厳しすぎる → 範囲を広げる（ge 7000 → ge 1000）
- 支店フィルタで0件 → 支店フィルタを外す
- 両方同時に厳しい → 片方ずつ試す

### 2. まず広く検索してデータの傾向を把握
→ 最初はフィルタなしで検索して、どんなデータがあるか確認する
→ その後、条件を絞り込む

### 3. 検索結果を分析して次のアクションを決める
→ 「〇〇が見つかった」「△△が見つからない」を整理
→ 見つからないものは別の検索戦略を試す
→ **諦めずに複数の方法を試す**

### 4. 検索結果の検証
→ **item_nameが質問の工種名と一致するか確認**
→ 関連性の低い結果は除外して報告
→ 「該当なし」の場合は明確に伝える

### 5. 十分な情報が集まったら最終回答
→ 見つかった事例を整理して報告
→ 見つからなかったものも正直に報告
→ データの傾向（最大値、平均的な数量など）も報告
→ **file_urlフィールドがあれば、ファイルリンクも含める**

## フィルタの書式（OData）
- branch eq '関東支社'  （支店で絞り込み）
- quantity ge 1000  （数量1000以上）
- quantity le 5000  （数量5000以下）
- 複合条件: branch eq '関東支社' and quantity ge 1000

## 重要
- **ユーザーに「どうしますか？」と聞かない**
- **自分で考えて、自分で行動する**
- 最低でも3〜5回は検索を試みてから結論を出す
- 最終回答には、見つかった具体的な事例を含める
- **検索結果のitem_nameが質問内容と一致するか必ず確認**
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


# ツール定義（OpenAI Function Calling形式）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_direct_costs",
            "description": "直接工事費の明細を検索します。工種名、数量、単価、支店などで検索できます。階層構造(level: 0=工事全体, 1=直接工事費, 2=費目行, 3=工種, 4=内訳代価, 5=詳細明細)と帳票種別(ledger_type)を持ち、sort_order順に並べるとExcelの表を再現できます。歩掛り検索ではproject_idでフィルタしてsort_order asc で取得してください。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索キーワード（工種名など）。例: '切削オーバーレイ', '区画線', '殻運搬', '*'（全件）"
                    },
                    "filter": {
                        "type": "string",
                        "description": "ODataフィルター式。例: \"branch eq '関東支社'\", \"project_id eq 'project_0001'\", \"quantity ge 1000\""
                    },
                    "orderby": {
                        "type": "string",
                        "description": "並び替え。歩掛り表示時は 'sort_order asc' を指定するとExcelの行順を再現できる"
                    },
                    "top": {
                        "type": "integer",
                        "description": "取得件数（デフォルト50）",
                        "default": 50
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
            "description": "プロジェクト概要を検索します。工事名、支店、場所、契約期間（実施工期）、工期日数などで検索できます。工期や期間を知りたい場合はこのツールを使ってください。",
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
                        "description": "取得件数（デフォルト10）",
                        "default": 10
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
            "description": "間接工事費（共通仮設費・現場経費）の詳細明細を検索します。階層構造(level: 0=総括, 1=集計行, 2=内訳代価, 3=詳細明細)と帳票種別(ledger_type)を持ち、sort_order順に並べるとExcelの表を再現できます。project_idでフィルタすると1工事分を取得できます。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索キーワード（項目名など）。例: '仮設', '経費', '重機運搬', '*'（全件）"
                    },
                    "filter": {
                        "type": "string",
                        "description": "ODataフィルター式。例: \"project_id eq 'project_0048' and category eq '共通仮設費'\", \"level eq 2 and category eq '現場経費'\""
                    },
                    "orderby": {
                        "type": "string",
                        "description": "並び替え。テーブル表示時は 'sort_order asc' を指定するとExcelの行順を再現できる"
                    },
                    "top": {
                        "type": "integer",
                        "description": "取得件数（デフォルト50）",
                        "default": 50
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


def execute_tool(tool_name: str, arguments: dict) -> str:
    """ツールを実行して結果を返す"""
    if tool_name == "search_direct_costs":
        result = search_direct_costs(
            query=arguments.get("query", "*"),
            filter_expr=arguments.get("filter"),
            top=arguments.get("top", 50),
            orderby=arguments.get("orderby"),
        )
        result = _slim_results(result,
            keep_fields=["project_id", "level", "sort_order", "ledger_type", "cost_code",
                         "item_name", "specification", "unit", "quantity", "unit_price", "amount", "per_quantity"],
            meta_fields=["project_name", "branch", "location", "file_url", "file_name"])
    elif tool_name == "search_projects":
        result = search_projects(
            query=arguments.get("query", "*"),
            filter_expr=arguments.get("filter"),
            top=arguments.get("top", 10)
        )
    elif tool_name == "search_indirect_costs":
        result = search_indirect_costs(
            query=arguments.get("query", "*"),
            filter_expr=arguments.get("filter"),
            top=arguments.get("top", 50),
            orderby=arguments.get("orderby"),
        )
        result = _slim_results(result,
            keep_fields=["project_id", "level", "sort_order", "ledger_type", "category",
                         "item_name", "specification", "unit", "quantity", "unit_price", "amount",
                         "per_quantity", "composition_rate", "contractor", "note"],
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
