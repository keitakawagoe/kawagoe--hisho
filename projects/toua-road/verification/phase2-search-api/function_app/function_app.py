"""
類似工事検索 Function App
Azure AI Search を使用した建設工事データベース検索API

6つの関数:
1. search_projects - 工事検索
2. search_details - 直接工事費明細検索
3. get_project_details - 工事の全明細取得
4. aggregate_by_project - 工事単位で集約
5. get_statistics - 統計情報取得
6. search_indirect_costs - 間接費検索
"""

import os
import json
import logging
from typing import Optional
import azure.functions as func
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import QueryType

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Azure AI Search設定
SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "")
SEARCH_KEY = os.environ.get("AZURE_SEARCH_KEY", "")
PROJECTS_INDEX = "toadoro-projects"
DIRECT_COSTS_INDEX = "toadoro-direct-costs"
INDIRECT_COSTS_INDEX = "toadoro-indirect-costs"


def get_search_client(index_name: str) -> SearchClient:
    """SearchClientを取得"""
    return SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=index_name,
        credential=AzureKeyCredential(SEARCH_KEY)
    )


def build_filter(filters: dict) -> Optional[str]:
    """フィルター条件を構築"""
    conditions = []

    for field, value in filters.items():
        if value is None:
            continue

        if isinstance(value, dict):
            # 範囲フィルタ
            if "gte" in value:
                conditions.append(f"{field} ge {value['gte']}")
            if "lte" in value:
                conditions.append(f"{field} le {value['lte']}")
            if "gt" in value:
                conditions.append(f"{field} gt {value['gt']}")
            if "lt" in value:
                conditions.append(f"{field} lt {value['lt']}")
            if "eq" in value:
                if isinstance(value["eq"], str):
                    conditions.append(f"{field} eq '{value['eq']}'")
                else:
                    conditions.append(f"{field} eq {value['eq']}")
            if "ne" in value:
                if isinstance(value["ne"], str):
                    conditions.append(f"{field} ne '{value['ne']}'")
                else:
                    conditions.append(f"{field} ne {value['ne']}")
        elif isinstance(value, str):
            # 完全一致
            conditions.append(f"{field} eq '{value}'")
        elif isinstance(value, (int, float)):
            conditions.append(f"{field} eq {value}")
        elif isinstance(value, bool):
            conditions.append(f"{field} eq {str(value).lower()}")

    if conditions:
        return " and ".join(conditions)
    return None


@app.route(route="search_projects", methods=["POST"])
def search_projects(req: func.HttpRequest) -> func.HttpResponse:
    """
    工事検索

    対象インデックス: toadoro-projects
    全文検索: search_text, project_name, item_keywords
    フィルタ: branch, location, folder, contract_amount, site_manager, tech_manager
    ソート: contract_amount, total_items, total_amount

    リクエストボディ:
    {
        "query": "検索クエリ",
        "filters": {
            "branch": "関西支社",
            "contract_amount": {"gte": 50000000}
        },
        "select": ["project_name", "branch", "contract_amount"],
        "orderby": "contract_amount desc",
        "top": 10
    }
    """
    try:
        body = req.get_json()
    except ValueError:
        body = {}

    query = body.get("query", "*")
    filters = body.get("filters", {})
    select = body.get("select")
    orderby = body.get("orderby")
    top = body.get("top", 20)

    client = get_search_client(PROJECTS_INDEX)

    results = client.search(
        search_text=query,
        search_fields=["search_text", "project_name", "item_keywords"],
        filter=build_filter(filters),
        select=select,
        order_by=orderby,
        top=top,
        query_type=QueryType.SIMPLE,
    )

    documents = [dict(doc) for doc in results]

    return func.HttpResponse(
        json.dumps({"results": documents, "count": len(documents)}, ensure_ascii=False),
        mimetype="application/json",
        status_code=200
    )


@app.route(route="search_details", methods=["POST"])
def search_details(req: func.HttpRequest) -> func.HttpResponse:
    """
    直接工事費明細検索

    対象インデックス: toadoro-direct-costs
    全文検索: search_text, item_name, specification
    フィルタ: branch, folder, level, unit, quantity, unit_price, amount, contractor
    ソート: quantity, unit_price, amount

    リクエストボディ:
    {
        "query": "集水桝 750",
        "filters": {
            "level": 3,
            "unit": "m2"
        },
        "select": ["project_name", "item_name", "quantity", "unit_price", "amount"],
        "orderby": "quantity desc",
        "top": 20
    }
    """
    try:
        body = req.get_json()
    except ValueError:
        body = {}

    query = body.get("query", "*")
    filters = body.get("filters", {})
    select = body.get("select")
    orderby = body.get("orderby")
    top = body.get("top", 20)

    client = get_search_client(DIRECT_COSTS_INDEX)

    results = client.search(
        search_text=query,
        search_fields=["search_text", "item_name", "specification"],
        filter=build_filter(filters),
        select=select,
        order_by=orderby,
        top=top,
        query_type=QueryType.SIMPLE,
    )

    documents = [dict(doc) for doc in results]

    return func.HttpResponse(
        json.dumps({"results": documents, "count": len(documents)}, ensure_ascii=False),
        mimetype="application/json",
        status_code=200
    )


@app.route(route="get_project_details", methods=["POST"])
def get_project_details(req: func.HttpRequest) -> func.HttpResponse:
    """
    工事の全明細取得

    対象インデックス: toadoro-direct-costs
    フィルタ: project_id, level
    ソート: level, id

    リクエストボディ:
    {
        "project_id": "project_xxx",
        "level": 4,  // オプション: 特定階層のみ取得
        "select": ["item_name", "specification", "quantity", "unit_price"],
        "top": 100
    }
    """
    try:
        body = req.get_json()
    except ValueError:
        body = {}

    project_id = body.get("project_id")
    if not project_id:
        return func.HttpResponse(
            json.dumps({"error": "project_id is required"}, ensure_ascii=False),
            mimetype="application/json",
            status_code=400
        )

    level = body.get("level")
    select = body.get("select")
    top = body.get("top", 500)

    filters = {"project_id": project_id}
    if level is not None:
        filters["level"] = level

    client = get_search_client(DIRECT_COSTS_INDEX)

    results = client.search(
        search_text="*",
        filter=build_filter(filters),
        select=select,
        order_by="level asc, id asc",
        top=top,
    )

    documents = [dict(doc) for doc in results]

    return func.HttpResponse(
        json.dumps({"results": documents, "count": len(documents)}, ensure_ascii=False),
        mimetype="application/json",
        status_code=200
    )


@app.route(route="aggregate_by_project", methods=["POST"])
def aggregate_by_project(req: func.HttpRequest) -> func.HttpResponse:
    """
    工事単位で集約

    複数の工種を検索し、project_idでグルーピングして
    指定した全工種を含む工事を返す

    対象インデックス: toadoro-direct-costs
    全文検索: search_text, item_name, specification
    フィルタ: branch, folder, level, unit
    集約: project_id

    リクエストボディ:
    {
        "queries": ["逆T型擁壁", "逆U型擁壁"],  // 複数の検索クエリ
        "operator": "AND",  // AND or OR
        "filters": {
            "branch": "関東支社"
        }
    }
    """
    try:
        body = req.get_json()
    except ValueError:
        body = {}

    queries = body.get("queries", [])
    operator = body.get("operator", "AND")
    filters = body.get("filters", {})

    if not queries:
        return func.HttpResponse(
            json.dumps({"error": "queries is required"}, ensure_ascii=False),
            mimetype="application/json",
            status_code=400
        )

    client = get_search_client(DIRECT_COSTS_INDEX)

    # 各クエリで検索し、project_idを収集
    project_results = {}  # project_id -> {matched_queries: set, details: list}

    for query in queries:
        results = client.search(
            search_text=query,
            search_fields=["search_text", "item_name", "specification"],
            filter=build_filter(filters),
            select=["project_id", "project_name", "branch", "item_name", "specification", "quantity", "unit", "amount"],
            top=1000,
        )

        for doc in results:
            pid = doc.get("project_id")
            if pid not in project_results:
                project_results[pid] = {
                    "project_id": pid,
                    "project_name": doc.get("project_name", ""),
                    "branch": doc.get("branch", ""),
                    "matched_queries": set(),
                    "details": [],
                }
            project_results[pid]["matched_queries"].add(query)
            project_results[pid]["details"].append({
                "item_name": doc.get("item_name", ""),
                "specification": doc.get("specification", ""),
                "quantity": doc.get("quantity"),
                "unit": doc.get("unit", ""),
                "amount": doc.get("amount"),
            })

    # AND/OR条件でフィルタリング
    query_set = set(queries)
    filtered_projects = []

    for pid, project in project_results.items():
        matched = project["matched_queries"]
        if operator == "AND":
            if matched == query_set:
                project["matched_queries"] = list(matched)
                filtered_projects.append(project)
        else:  # OR
            project["matched_queries"] = list(matched)
            filtered_projects.append(project)

    return func.HttpResponse(
        json.dumps({"results": filtered_projects, "count": len(filtered_projects)}, ensure_ascii=False),
        mimetype="application/json",
        status_code=200
    )


@app.route(route="get_statistics", methods=["POST"])
def get_statistics(req: func.HttpRequest) -> func.HttpResponse:
    """
    統計情報取得

    特定の工種について、単価・数量・金額の統計を計算

    対象インデックス: toadoro-direct-costs
    全文検索: search_text, item_name
    フィルタ: branch, unit, level
    集計: quantity, unit_price, amount

    リクエストボディ:
    {
        "query": "切削オーバーレイ",
        "filters": {
            "unit": "m2"
        },
        "aggregate_fields": ["unit_price", "quantity", "amount"]
    }
    """
    try:
        body = req.get_json()
    except ValueError:
        body = {}

    query = body.get("query", "*")
    filters = body.get("filters", {})
    aggregate_fields = body.get("aggregate_fields", ["unit_price", "quantity", "amount"])

    client = get_search_client(DIRECT_COSTS_INDEX)

    results = client.search(
        search_text=query,
        search_fields=["search_text", "item_name"],
        filter=build_filter(filters),
        select=["project_name", "item_name", "specification", "unit"] + aggregate_fields,
        top=1000,
    )

    documents = [dict(doc) for doc in results]

    # 統計計算
    statistics = {}
    for field in aggregate_fields:
        values = [doc.get(field) for doc in documents if doc.get(field) is not None]
        if values:
            statistics[field] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "sum": sum(values),
            }
        else:
            statistics[field] = None

    return func.HttpResponse(
        json.dumps({
            "query": query,
            "total_records": len(documents),
            "statistics": statistics,
            "sample_records": documents[:5],
        }, ensure_ascii=False),
        mimetype="application/json",
        status_code=200
    )


@app.route(route="search_indirect_costs", methods=["POST"])
def search_indirect_costs(req: func.HttpRequest) -> func.HttpResponse:
    """
    間接費検索

    対象インデックス: toadoro-indirect-costs
    全文検索: search_text, item_name, category
    フィルタ: branch, project_id, category
    ソート: amount, quantity

    リクエストボディ:
    {
        "query": "重機運搬",
        "filters": {
            "category": "共通仮設費",
            "branch": "関西支社"
        },
        "select": ["project_name", "category", "item_name", "unit", "quantity", "amount"],
        "orderby": "amount desc",
        "top": 20
    }
    """
    try:
        body = req.get_json()
    except ValueError:
        body = {}

    query = body.get("query", "*")
    filters = body.get("filters", {})
    select = body.get("select")
    orderby = body.get("orderby")
    top = body.get("top", 20)

    client = get_search_client(INDIRECT_COSTS_INDEX)

    results = client.search(
        search_text=query,
        search_fields=["search_text", "item_name", "category"],
        filter=build_filter(filters),
        select=select,
        order_by=orderby,
        top=top,
        query_type=QueryType.SIMPLE,
    )

    documents = [dict(doc) for doc in results]

    return func.HttpResponse(
        json.dumps({"results": documents, "count": len(documents)}, ensure_ascii=False),
        mimetype="application/json",
        status_code=200
    )


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """ヘルスチェック"""
    return func.HttpResponse(
        json.dumps({"status": "healthy"}, ensure_ascii=False),
        mimetype="application/json",
        status_code=200
    )
