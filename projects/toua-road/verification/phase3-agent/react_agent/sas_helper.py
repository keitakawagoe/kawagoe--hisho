"""
Azure Blob Storage SASトークン生成ヘルパー
"""
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote, unquote
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions


def get_blob_service_client():
    """BlobServiceClientを取得"""
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if connection_string:
        return BlobServiceClient.from_connection_string(connection_string)
    return None


def generate_sas_url(blob_url: str, expiry_days: int = 3650) -> str:
    """
    BlobURLにSASトークンを付与

    Args:
        blob_url: Azure Blob Storage URL (https://<account>.blob.core.windows.net/<container>/<blob>)
        expiry_days: SASトークンの有効期限（日数）。デフォルトは約10年

    Returns:
        SASトークン付きのURL
    """
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        # 接続文字列がない場合はそのまま返す
        return blob_url

    try:
        # URLをパース
        parsed = urlparse(blob_url)
        if not parsed.netloc.endswith(".blob.core.windows.net"):
            # Blob URLでない場合はそのまま返す
            return blob_url

        # アカウント名を取得
        account_name = parsed.netloc.split(".")[0]

        # パスからコンテナとBlob名を取得
        path_parts = parsed.path.lstrip("/").split("/", 1)
        if len(path_parts) < 2:
            return blob_url

        container_name = path_parts[0]
        # URLエンコードされている場合はデコード
        blob_name = unquote(path_parts[1])

        # 接続文字列からアカウントキーを取得
        account_key = None
        for part in connection_string.split(";"):
            if part.startswith("AccountKey="):
                account_key = part[len("AccountKey="):]
                break

        if not account_key:
            return blob_url

        # SASトークン生成
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(days=expiry_days)
        )

        # URLを正しくエンコードして構築
        encoded_blob_name = quote(blob_name, safe="/")
        base_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{encoded_blob_name}"
        return f"{base_url}?{sas_token}"

    except Exception as e:
        # エラー時はそのまま返す
        print(f"SAS generation error: {e}")
        return blob_url


def add_sas_to_results(results: list) -> list:
    """
    検索結果のfile_urlにSASトークンを付与

    Args:
        results: 検索結果のリスト

    Returns:
        file_urlにSASトークンが付与された検索結果
    """
    for result in results:
        if result.get("file_url"):
            result["file_url"] = generate_sas_url(result["file_url"])
    return results
