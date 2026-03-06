"""
JSONファイルのfile_urlをBlob URLに更新するスクリプト

前提: upload_to_blob.py を実行して blob_url_mapping.json が生成されていること

使い方:
    python update_file_urls.py
"""
import json
from pathlib import Path

BASE_DIR = Path("/Users/kawagoekeita/Documents/Agent/★東亜PJ")
DATA_DIR = BASE_DIR / "data"


def load_mapping():
    """blob_url_mapping.jsonを読み込み"""
    mapping_file = DATA_DIR / "blob_url_mapping.json"
    if not mapping_file.exists():
        print("Error: blob_url_mapping.json not found")
        print("Run upload_to_blob.py first")
        return None

    with open(mapping_file, "r") as f:
        return json.load(f)


def update_json_file(json_path: Path, mapping: dict) -> int:
    """JSONファイルのfile_urlを更新"""
    with open(json_path, "r") as f:
        data = json.load(f)

    updated_count = 0
    for item in data:
        old_url = item.get("file_url")
        if old_url and old_url in mapping:
            item["file_url"] = mapping[old_url]
            updated_count += 1

    # 上書き保存
    with open(json_path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return updated_count


def main():
    print("=== Update file_url to Blob URLs ===\n")

    # マッピングを読み込み
    mapping = load_mapping()
    if not mapping:
        return

    print(f"Loaded {len(mapping)} URL mappings\n")

    # 更新対象のJSONファイル
    json_files = [
        "projects.json",
        "direct_costs.json",
        "indirect_costs.json",
    ]

    for json_file in json_files:
        json_path = DATA_DIR / json_file
        if not json_path.exists():
            print(f"SKIP: {json_file} (not found)")
            continue

        updated = update_json_file(json_path, mapping)
        print(f"Updated: {json_file} ({updated} records)")

    print("\n=== Done ===")
    print("Now run setup_azure_search.py to re-upload data to Azure AI Search")


if __name__ == "__main__":
    main()
