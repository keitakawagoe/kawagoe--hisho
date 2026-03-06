"""
Excelファイルを Azure Blob Storage にアップロードするスクリプト

使い方:
1. 環境変数 AZURE_STORAGE_CONNECTION_STRING を設定
2. python upload_to_blob.py を実行
"""
import os
import json
from pathlib import Path
from azure.storage.blob import BlobServiceClient, ContentSettings

# 設定
CONTAINER_NAME = "toadoro-files"
BASE_DIR = Path("/Users/kawagoekeita/Documents/Agent/★東亜PJ")


def get_connection_string():
    """接続文字列を取得"""
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        # ファイルから読み込み
        settings_file = BASE_DIR / "react_agent" / "local.settings.json"
        if settings_file.exists():
            with open(settings_file, "r") as f:
                settings = json.load(f)
                conn_str = settings.get("Values", {}).get("AZURE_STORAGE_CONNECTION_STRING")
    return conn_str


def ensure_container_exists(blob_service_client):
    """コンテナが存在しない場合は作成"""
    try:
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        if not container_client.exists():
            container_client.create_container()
            print(f"Container '{CONTAINER_NAME}' created")
        else:
            print(f"Container '{CONTAINER_NAME}' already exists")
        return container_client
    except Exception as e:
        print(f"Error creating container: {e}")
        raise


def get_files_to_upload():
    """アップロードが必要なファイルのリストを取得"""
    files = set()

    # 既存および新規のJSONファイルからファイルパスを収集
    json_files = [
        "projects.json", "direct_costs.json", "indirect_costs.json",
        "projects_new.json", "direct_costs_new.json", "indirect_costs_new.json"
    ]
    for json_file in json_files:
        json_path = BASE_DIR / "data" / json_file
        if json_path.exists():
            with open(json_path, "r") as f:
                data = json.load(f)
                for item in data:
                    file_url = item.get("file_url")
                    if file_url:
                        files.add(file_url)

    return list(files)


def resolve_file_path(file_url: str) -> Path:
    """file_urlから実際のファイルパスを解決"""
    # Blob URLの場合、ローカルパスに変換
    blob_prefix = "https://toadorofilestorage.blob.core.windows.net/toadoro-files/"
    if file_url.startswith(blob_prefix):
        relative_path = file_url[len(blob_prefix):]
        return BASE_DIR / relative_path

    # 絶対パスの場合
    if file_url.startswith("/"):
        return Path(file_url)

    # 相対パスの場合
    return BASE_DIR / file_url


def get_blob_name(file_url: str) -> str:
    """BlobのBLOB名を生成（フォルダ構造を維持）"""
    # Blob URLの場合
    blob_prefix = "https://toadorofilestorage.blob.core.windows.net/toadoro-files/"
    if file_url.startswith(blob_prefix):
        return file_url[len(blob_prefix):]

    # 絶対パスの場合、BASE_DIRからの相対パスに変換
    if file_url.startswith("/Users/kawagoekeita/Documents/Agent/★東亜PJ/"):
        return file_url.replace("/Users/kawagoekeita/Documents/Agent/★東亜PJ/", "")

    return file_url


def get_content_type(filename: str) -> str:
    """ファイル拡張子に応じたContent-Typeを返す"""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    content_types = {
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'xlsm': 'application/vnd.ms-excel.sheet.macroEnabled.12',
        'xls': 'application/vnd.ms-excel',
        'pdf': 'application/pdf',
        'md': 'text/markdown',
        'txt': 'text/plain',
    }
    return content_types.get(ext, 'application/octet-stream')


def upload_files():
    """ファイルをアップロード"""
    conn_str = get_connection_string()
    if not conn_str:
        print("Error: AZURE_STORAGE_CONNECTION_STRING not set")
        print("Set it in environment variable or in react_agent/local.settings.json")
        return

    blob_service_client = BlobServiceClient.from_connection_string(conn_str)
    container_client = ensure_container_exists(blob_service_client)

    files_to_upload = get_files_to_upload()
    print(f"\nFound {len(files_to_upload)} unique files to upload")

    # アカウント名を取得
    account_name = blob_service_client.account_name

    uploaded = 0
    skipped = 0
    errors = 0

    # Blob URLマッピングを保存
    url_mapping = {}

    for file_url in files_to_upload:
        local_path = resolve_file_path(file_url)
        blob_name = get_blob_name(file_url)

        if not local_path.exists():
            print(f"  SKIP (not found): {local_path}")
            skipped += 1
            continue

        try:
            blob_client = container_client.get_blob_client(blob_name)

            # Content-Typeを拡張子に応じて設定
            content_type = get_content_type(str(local_path))

            # 既に存在する場合は削除して再アップロード（Content-Type修正のため）
            if blob_client.exists():
                blob_client.delete_blob()

            # アップロード
            with open(local_path, "rb") as data:
                content_settings = ContentSettings(content_type=content_type)
                blob_client.upload_blob(data, content_settings=content_settings)
            print(f"  UPLOADED: {blob_name} ({content_type})")

            # URLマッピングを記録
            blob_url = f"https://{account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}"
            url_mapping[file_url] = blob_url
            uploaded += 1

        except Exception as e:
            print(f"  ERROR: {blob_name} - {e}")
            errors += 1

    print(f"\n=== Summary ===")
    print(f"Uploaded/Exists: {uploaded}")
    print(f"Skipped (not found): {skipped}")
    print(f"Errors: {errors}")

    # URLマッピングを保存
    mapping_file = BASE_DIR / "data" / "blob_url_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(url_mapping, f, ensure_ascii=False, indent=2)
    print(f"\nURL mapping saved to: {mapping_file}")

    # Storage Account情報を表示
    print(f"\n=== Storage Account Info ===")
    print(f"Account Name: {account_name}")
    print(f"Container: {CONTAINER_NAME}")
    print(f"Base URL: https://{account_name}.blob.core.windows.net/{CONTAINER_NAME}/")


def main():
    print("=== Toadoro Files Uploader ===")
    print(f"Base directory: {BASE_DIR}")
    print(f"Container name: {CONTAINER_NAME}")
    print()

    upload_files()


if __name__ == "__main__":
    main()
