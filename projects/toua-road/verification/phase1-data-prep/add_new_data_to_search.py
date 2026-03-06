#!/usr/bin/env python3
"""
新規データ（岩手・宮城フォルダ）をAzure AI Searchに追加するスクリプト

使い方:
    python add_new_data_to_search.py

前提条件:
    - parse_xlsm_files.py を実行済み
    - data/projects_new.json, direct_costs_new.json, indirect_costs_new.json が存在
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


def get_index_count(index_name: str) -> int:
    """インデックスのドキュメント数を取得"""
    url = f"{ENDPOINT}/indexes/{index_name}/docs/$count?api-version={API_VERSION}"
    response = requests.get(url, headers=get_headers())
    if response.status_code == 200:
        return int(response.text)
    return -1


def main():
    if not ENDPOINT or not API_KEY:
        print("エラー: 環境変数を設定してください")
        print("  export AZURE_SEARCH_ENDPOINT='https://your-search-service.search.windows.net'")
        print("  export AZURE_SEARCH_KEY='your-admin-key'")
        return

    print(f"Azure AI Search: {ENDPOINT}")
    print()

    # 現在のインデックス状態を確認
    print("=== 現在のインデックス状態 ===")
    for index_name in [PROJECTS_INDEX, DIRECT_COSTS_INDEX, INDIRECT_COSTS_INDEX]:
        count = get_index_count(index_name)
        print(f"  {index_name}: {count}件")
    print()

    # 新規データ読み込み
    print("=== 新規データ読み込み ===")

    projects_file = DATA_DIR / "projects_new.json"
    direct_costs_file = DATA_DIR / "direct_costs_new.json"
    indirect_costs_file = DATA_DIR / "indirect_costs_new.json"

    if not projects_file.exists():
        print(f"エラー: {projects_file} が見つかりません")
        print("先に parse_xlsm_files.py を実行してください")
        return

    with open(projects_file, "r", encoding="utf-8") as f:
        projects = json.load(f)
    print(f"新規工事データ: {len(projects)}件")

    with open(direct_costs_file, "r", encoding="utf-8") as f:
        direct_costs = json.load(f)
    print(f"新規直接工事費明細: {len(direct_costs)}件")

    with open(indirect_costs_file, "r", encoding="utf-8") as f:
        indirect_costs = json.load(f)
    print(f"新規間接費明細: {len(indirect_costs)}件")

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

    # アップロード後のインデックス状態を確認
    print("=== アップロード後のインデックス状態 ===")
    time.sleep(2)  # インデックス更新を待つ
    for index_name in [PROJECTS_INDEX, DIRECT_COSTS_INDEX, INDIRECT_COSTS_INDEX]:
        count = get_index_count(index_name)
        print(f"  {index_name}: {count}件")

    print()
    print("=== 完了 ===")
    print("岩手・宮城フォルダのデータがAI Searchに追加されました")


if __name__ == "__main__":
    main()
