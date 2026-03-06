#!/usr/bin/env python3
"""
Azure AI Search インデックス作成・データアップロードスクリプト

使い方:
    # 環境変数を設定してから実行
    export AZURE_SEARCH_ENDPOINT="https://your-search-service.search.windows.net"
    export AZURE_SEARCH_KEY="your-admin-key"

    python setup_azure_search.py

インデックス名:
    - toadoro-projects: 工事サマリ（61件）
    - toadoro-direct-costs: 直接工事費明細（11,313件）
    - toadoro-indirect-costs: 間接費明細
"""

import json
import os
import time
from pathlib import Path
import requests

# Azure AI Search設定
ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "")
API_KEY = os.environ.get("AZURE_SEARCH_KEY", "")
API_VERSION = "2024-07-01"

# データファイルパス
DATA_DIR = Path("/Users/kawagoekeita/Documents/Agent/★東亜PJ/data")

# インデックス名
PROJECTS_INDEX = "toadoro-projects"
DIRECT_COSTS_INDEX = "toadoro-direct-costs"
INDIRECT_COSTS_INDEX = "toadoro-indirect-costs"


def get_headers():
    return {
        "Content-Type": "application/json",
        "api-key": API_KEY,
    }


def create_projects_index():
    """工事サマリ用インデックスを作成"""
    index_schema = {
        "name": PROJECTS_INDEX,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "folder", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "filename", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "project_name", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "branch", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "location", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "work_days", "type": "Edm.String", "filterable": True, "sortable": True},
            {"name": "contract_amount", "type": "Edm.Int64", "filterable": True, "sortable": True},
            {"name": "contract_period", "type": "Edm.String", "searchable": True},
            {"name": "file_url", "type": "Edm.String"},
            {"name": "file_name", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "site_manager", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "tech_manager", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "project_number", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "item_keywords", "type": "Collection(Edm.String)", "searchable": True, "filterable": True},
            {"name": "total_items", "type": "Edm.Int32", "filterable": True, "sortable": True},
            {"name": "total_amount", "type": "Edm.Double", "filterable": True, "sortable": True},
            {"name": "search_text", "type": "Edm.String", "searchable": True},
        ],
    }

    url = f"{ENDPOINT}/indexes/{PROJECTS_INDEX}?api-version={API_VERSION}"
    response = requests.put(url, headers=get_headers(), json=index_schema)

    if response.status_code in [200, 201, 204]:
        print(f"インデックス作成成功: {PROJECTS_INDEX}")
        return True
    else:
        print(f"インデックス作成失敗: {response.status_code}")
        print(response.text)
        return False


def create_direct_costs_index():
    """直接工事費明細用インデックスを作成"""
    index_schema = {
        "name": DIRECT_COSTS_INDEX,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "project_id", "type": "Edm.String", "filterable": True},
            # 工事情報（非正規化）
            {"name": "folder", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "filename", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "project_name", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "branch", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "location", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "work_days", "type": "Edm.String"},
            {"name": "contract_amount", "type": "Edm.Int64", "filterable": True, "sortable": True},
            {"name": "contract_period", "type": "Edm.String"},
            {"name": "file_url", "type": "Edm.String"},
            {"name": "file_name", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "site_manager", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "tech_manager", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "project_number", "type": "Edm.String", "searchable": True, "filterable": True},
            # 直接工事費明細（列N-AF）
            {"name": "sort_order", "type": "Edm.Int32", "filterable": True, "sortable": True},
            {"name": "level", "type": "Edm.Int32", "filterable": True, "sortable": True},
            {"name": "cost_code", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "ledger_type", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "item_name", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "specification", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "unit", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "quantity", "type": "Edm.Double", "filterable": True, "sortable": True},
            {"name": "unit_price", "type": "Edm.Double", "filterable": True, "sortable": True},
            {"name": "amount", "type": "Edm.Double", "filterable": True, "sortable": True},
            {"name": "per_quantity", "type": "Edm.Double", "filterable": True},
            {"name": "composition_rate", "type": "Edm.Double", "filterable": True},
            {"name": "contractor", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "note", "type": "Edm.String", "searchable": True},
            {"name": "user_code", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "remarks", "type": "Edm.String", "searchable": True},
            # 費目別内訳（列AB-AF）
            {"name": "material_cost", "type": "Edm.Double", "filterable": True, "sortable": True},
            {"name": "labor_cost", "type": "Edm.Double", "filterable": True, "sortable": True},
            {"name": "outsource_cost", "type": "Edm.Double", "filterable": True, "sortable": True},
            {"name": "machine_cost", "type": "Edm.Double", "filterable": True, "sortable": True},
            {"name": "transport_cost", "type": "Edm.Double", "filterable": True, "sortable": True},
            # 検索用テキスト
            {"name": "search_text", "type": "Edm.String", "searchable": True},
        ],
    }

    url = f"{ENDPOINT}/indexes/{DIRECT_COSTS_INDEX}?api-version={API_VERSION}"
    response = requests.put(url, headers=get_headers(), json=index_schema)

    if response.status_code in [200, 201, 204]:
        print(f"インデックス作成成功: {DIRECT_COSTS_INDEX}")
        return True
    else:
        print(f"インデックス作成失敗: {response.status_code}")
        print(response.text)
        return False


def create_indirect_costs_index():
    """間接費明細用インデックスを作成（工事費一覧表(共通仮設費/現場経費)の全カラム対応）"""
    index_schema = {
        "name": INDIRECT_COSTS_INDEX,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "project_id", "type": "Edm.String", "filterable": True},
            # 工事情報（非正規化）
            {"name": "folder", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "filename", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "project_name", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "branch", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "location", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "work_days", "type": "Edm.String"},
            {"name": "contract_amount", "type": "Edm.Int64", "filterable": True, "sortable": True},
            {"name": "contract_period", "type": "Edm.String"},
            {"name": "file_url", "type": "Edm.String"},
            {"name": "file_name", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "site_manager", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "tech_manager", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "project_number", "type": "Edm.String", "searchable": True, "filterable": True},
            # 間接費固有フィールド
            {"name": "category", "type": "Edm.String", "searchable": True, "filterable": True},  # 共通仮設費 / 現場経費
            {"name": "sort_order", "type": "Edm.Int32", "filterable": True, "sortable": True},  # ツリー構造の行順
            # 明細カラム（直接工事費と同一構造）
            {"name": "level", "type": "Edm.Int32", "filterable": True, "sortable": True},
            {"name": "cost_code", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "ledger_type", "type": "Edm.String", "searchable": True, "filterable": True},  # 帳票
            {"name": "item_name", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "specification", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "unit", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "quantity", "type": "Edm.Double", "filterable": True, "sortable": True},
            {"name": "unit_price", "type": "Edm.Double", "filterable": True, "sortable": True},
            {"name": "amount", "type": "Edm.Double", "filterable": True, "sortable": True},
            {"name": "per_quantity", "type": "Edm.Double", "filterable": True},
            {"name": "composition_rate", "type": "Edm.Double", "filterable": True},
            {"name": "contractor", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "note", "type": "Edm.String", "searchable": True},
            # 検索用テキスト
            {"name": "search_text", "type": "Edm.String", "searchable": True},
        ],
    }

    url = f"{ENDPOINT}/indexes/{INDIRECT_COSTS_INDEX}?api-version={API_VERSION}"
    response = requests.put(url, headers=get_headers(), json=index_schema)

    if response.status_code in [200, 201, 204]:
        print(f"インデックス作成成功: {INDIRECT_COSTS_INDEX}")
        return True
    else:
        print(f"インデックス作成失敗: {response.status_code}")
        print(response.text)
        return False


def upload_documents(index_name: str, documents: list, batch_size: int = 500):
    """ドキュメントをバッチでアップロード"""
    url = f"{ENDPOINT}/indexes/{index_name}/docs/index?api-version={API_VERSION}"
    total = len(documents)
    uploaded = 0

    for i in range(0, total, batch_size):
        batch = documents[i:i + batch_size]
        payload = {
            "value": [{"@search.action": "upload", **doc} for doc in batch]
        }

        response = requests.post(url, headers=get_headers(), json=payload)

        if response.status_code in [200, 201]:
            uploaded += len(batch)
            print(f"  アップロード: {uploaded}/{total}")
        else:
            print(f"  アップロード失敗: {response.status_code}")
            print(response.text)
            return False

        # レート制限対策
        time.sleep(0.5)

    return True


def main():
    if not ENDPOINT or not API_KEY:
        print("エラー: 環境変数を設定してください")
        print("  export AZURE_SEARCH_ENDPOINT='https://your-search-service.search.windows.net'")
        print("  export AZURE_SEARCH_KEY='your-admin-key'")
        return

    print(f"Azure AI Search: {ENDPOINT}")
    print()

    # インデックス作成
    print("=== インデックス作成 ===")
    if not create_projects_index():
        return
    if not create_direct_costs_index():
        return
    if not create_indirect_costs_index():
        return

    print()

    # データ読み込み
    print("=== データ読み込み ===")
    with open(DATA_DIR / "projects.json", "r", encoding="utf-8") as f:
        projects = json.load(f)
    print(f"工事データ: {len(projects)}件")

    with open(DATA_DIR / "direct_costs.json", "r", encoding="utf-8") as f:
        direct_costs = json.load(f)
    print(f"直接工事費明細: {len(direct_costs)}件")

    with open(DATA_DIR / "indirect_costs.json", "r", encoding="utf-8") as f:
        indirect_costs = json.load(f)
    print(f"間接費明細: {len(indirect_costs)}件")

    print()

    # データアップロード
    print("=== データアップロード ===")
    print(f"工事データをアップロード中...")
    if not upload_documents(PROJECTS_INDEX, projects):
        return

    print(f"直接工事費明細をアップロード中...")
    if not upload_documents(DIRECT_COSTS_INDEX, direct_costs):
        return

    print(f"間接費明細をアップロード中...")
    if not upload_documents(INDIRECT_COSTS_INDEX, indirect_costs):
        return

    print()
    print("=== 完了 ===")
    print(f"インデックス: {PROJECTS_INDEX}, {DIRECT_COSTS_INDEX}, {INDIRECT_COSTS_INDEX}")


if __name__ == "__main__":
    main()
