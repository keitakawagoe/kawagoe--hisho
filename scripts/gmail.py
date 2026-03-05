#!/usr/bin/env python3
"""Gmail検索・保存スクリプト（公式SDK使用）

使い方:
    # キーワードで検索して表示
    python scripts/gmail.py search "弘電社"

    # キーワードで検索してemails/に保存
    python scripts/gmail.py save "弘電社" projects/koden/emails/

    # 複数キーワード（OR検索）
    python scripts/gmail.py save "東亜道路 OR 東亜道路工業" projects/toua-road/emails/

スコープ: gmail.readonly（読み取りのみ）
"""

import base64
import email
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

PROJECT_ROOT = Path(__file__).parent.parent

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]

CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"


def get_creds():
    """認証情報を取得する。"""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                print(f"エラー: {CREDENTIALS_PATH} が見つかりません。")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
        print(f"認証トークンを保存: {TOKEN_PATH}")

    return creds


def search_messages(gmail_service, query, max_results=50):
    """Gmailを検索してメッセージIDリストを返す。"""
    results = gmail_service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    return results.get("messages", [])


def get_message_detail(gmail_service, msg_id):
    """メッセージの詳細を取得する。"""
    msg = gmail_service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()

    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}

    subject = headers.get("Subject", "(件名なし)")
    from_addr = headers.get("From", "")
    to_addr = headers.get("To", "")
    date_str = headers.get("Date", "")
    cc_addr = headers.get("Cc", "")

    # 本文を取得
    body = _extract_body(msg["payload"])

    # 日付をパース
    try:
        # "Thu, 6 Mar 2026 10:00:00 +0900" のような形式
        parsed_date = email.utils.parsedate_to_datetime(date_str)
        date_formatted = parsed_date.strftime("%Y-%m-%d %H:%M")
        date_prefix = parsed_date.strftime("%Y%m%d")
    except Exception:
        date_formatted = date_str
        date_prefix = "unknown"

    return {
        "id": msg_id,
        "subject": subject,
        "from": from_addr,
        "to": to_addr,
        "cc": cc_addr,
        "date": date_formatted,
        "date_prefix": date_prefix,
        "body": body,
        "snippet": msg.get("snippet", ""),
    }


def _extract_body(payload):
    """メッセージペイロードからテキスト本文を抽出する。"""
    body = ""

    if payload.get("body", {}).get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    elif payload.get("parts"):
        for part in payload["parts"]:
            mime = part.get("mimeType", "")
            if mime == "text/plain" and part.get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                break
            elif mime.startswith("multipart/"):
                body = _extract_body(part)
                if body:
                    break

    return body


def format_email_markdown(detail):
    """メール詳細をMarkdown形式にフォーマットする。"""
    lines = [
        f"# {detail['subject']}",
        "",
        f"- **日時**: {detail['date']}",
        f"- **From**: {detail['from']}",
        f"- **To**: {detail['to']}",
    ]
    if detail["cc"]:
        lines.append(f"- **Cc**: {detail['cc']}")
    lines.extend([
        "",
        "---",
        "",
        detail["body"],
    ])
    return "\n".join(lines)


def sanitize_filename(name, max_len=80):
    """ファイル名をサニタイズする。"""
    safe = re.sub(r'[/\\:*?"<>|]', '-', name)
    safe = safe.replace("\u3000", " ").strip()
    if len(safe) > max_len:
        safe = safe[:max_len]
    return safe


def cmd_search(gmail_service, query):
    """メールを検索して一覧表示する。"""
    messages = search_messages(gmail_service, query)
    if not messages:
        print("該当するメールはありませんでした。")
        return

    print(f"## 検索結果: \"{query}\" ({len(messages)}件)\n")
    for msg_ref in messages:
        detail = get_message_detail(gmail_service, msg_ref["id"])
        print(f"  {detail['date']}  {detail['subject']}")
        print(f"           From: {detail['from']}")
        print()


def cmd_save(gmail_service, query, dest_path):
    """メールを検索してMarkdownファイルとして保存する。"""
    messages = search_messages(gmail_service, query)
    if not messages:
        print("該当するメールはありませんでした。")
        return

    dest = Path(dest_path)
    dest.mkdir(parents=True, exist_ok=True)

    print(f"## \"{query}\" → {dest_path} ({len(messages)}件)\n")
    for msg_ref in messages:
        detail = get_message_detail(gmail_service, msg_ref["id"])
        safe_subject = sanitize_filename(detail["subject"])
        filename = dest / f"{detail['date_prefix']}_{safe_subject}.md"

        md = format_email_markdown(detail)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(md)

        print(f"  保存: {filename}")

    print(f"\n合計 {len(messages)} 件保存しました。")


def main():
    if len(sys.argv) < 3:
        print("使い方:")
        print('  python scripts/gmail.py search "弘電社"')
        print('  python scripts/gmail.py save "弘電社" projects/koden/emails/')
        sys.exit(1)

    creds = get_creds()
    gmail_service = build("gmail", "v1", credentials=creds)
    cmd = sys.argv[1]

    if cmd == "search":
        cmd_search(gmail_service, sys.argv[2])
    elif cmd == "save" and len(sys.argv) >= 4:
        cmd_save(gmail_service, sys.argv[2], sys.argv[3])
    else:
        print(f"不明なコマンド: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
