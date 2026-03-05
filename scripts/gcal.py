#!/usr/bin/env python3
"""Google Calendar API スクリプト（公式SDK使用）

使い方:
    # 今日の予定を表示
    python scripts/calendar.py today

    # 今週の予定を表示
    python scripts/calendar.py week

    # 指定日の予定を表示
    python scripts/calendar.py date 2026-03-10

    # 指定期間の予定を表示
    python scripts/calendar.py range 2026-03-01 2026-03-31

初回セットアップ:
    1. Google Cloud Console で OAuth 2.0 クライアント ID を作成（デスクトップアプリ）
    2. credentials.json をプロジェクトルートに配置
    3. python scripts/calendar.py today を実行 → ブラウザ認証
    4. token.json が自動生成される（以降はブラウザ不要）

必要なスコープ: calendar.events.readonly（読み取りのみ）
"""

import io
import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent

# 読み取り専用スコープ（最小権限）
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# 認証ファイルのパス
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"


def get_service():
    """認証済みのCalendar APIサービスを取得する。"""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                print(f"エラー: {CREDENTIALS_PATH} が見つかりません。")
                print("Google Cloud Console からOAuth 2.0クライアントIDを作成し、")
                print("credentials.json をプロジェクトルートに配置してください。")
                print("https://developers.google.com/workspace/calendar/api/quickstart/python")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # トークンを保存
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
        print(f"認証トークンを保存: {TOKEN_PATH}")

    return creds


def get_events(cal_service, time_min, time_max, max_results=50):
    """指定期間のイベントを取得する。"""
    events_result = cal_service.events().list(
        calendarId="primary",
        timeMin=time_min.isoformat() + "Z",
        timeMax=time_max.isoformat() + "Z",
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return events_result.get("items", [])


def download_attachment(drive_service, file_id, dest_path):
    """Google DriveからファイルをダウンロードしてMeet文字起こし等を保存する。"""
    # まずファイル情報を取得
    file_meta = drive_service.files().get(fileId=file_id, fields="name,mimeType").execute()
    name = file_meta["name"]
    mime = file_meta.get("mimeType", "")

    # Google Docs系はエクスポート、それ以外は直接DL
    export_map = {
        "application/vnd.google-apps.document": ("text/plain", ".txt"),
        "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
        "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    }

    dest = Path(dest_path)
    dest.mkdir(parents=True, exist_ok=True)

    if mime in export_map:
        export_mime, ext = export_map[mime]
        request = drive_service.files().export_media(fileId=file_id, mimeType=export_mime)
        filename = dest / (Path(name).stem + ext)
    else:
        request = drive_service.files().get_media(fileId=file_id)
        filename = dest / name

    with open(filename, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    print(f"  ダウンロード完了: {filename}")
    return str(filename)


def format_event(event):
    """イベントを見やすい文字列にフォーマットする。"""
    start = event["start"].get("dateTime", event["start"].get("date"))
    end = event["end"].get("dateTime", event["end"].get("date"))

    # 終日イベントかどうか
    if "T" in start:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        time_str = f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
    else:
        time_str = "終日"

    summary = event.get("summary", "(タイトルなし)")
    location = event.get("location", "")
    meet_link = ""

    # Google Meet リンクを取得
    conference = event.get("conferenceData", {})
    for entry in conference.get("entryPoints", []):
        if entry.get("entryPointType") == "video":
            meet_link = entry.get("uri", "")
            break

    # 参加者
    attendees = event.get("attendees", [])
    attendee_names = [a.get("displayName", a.get("email", "")) for a in attendees[:5]]

    # 添付ファイル
    attachments = event.get("attachments", [])

    result = f"  {time_str}  {summary}"
    if location:
        result += f"\n           場所: {location}"
    if meet_link:
        result += f"\n           Meet: {meet_link}"
    if attendee_names:
        result += f"\n           参加者: {', '.join(attendee_names)}"
    for att in attachments:
        att_title = att.get("title", "(不明)")
        att_url = att.get("fileUrl", "")
        result += f"\n           添付: {att_title} ({att_url})"

    return result


def format_events_markdown(events, date_label):
    """イベントリストをMarkdown形式で出力する。"""
    if not events:
        return f"## {date_label}\n\n予定はありません。\n"

    lines = [f"## {date_label}\n"]

    current_date = None
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        event_date = start[:10]

        if event_date != current_date:
            current_date = event_date
            dt = datetime.fromisoformat(event_date)
            weekday = ["月", "火", "水", "木", "金", "土", "日"][dt.weekday()]
            lines.append(f"\n### {event_date} ({weekday})\n")

        lines.append(format_event(event))

    return "\n".join(lines)


def cmd_today(cal_service):
    """今日の予定を表示"""
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = now + timedelta(days=1)
    events = get_events(cal_service, now, end)
    print(format_events_markdown(events, "今日の予定"))


def cmd_week(cal_service):
    """今週の予定を表示"""
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=7)
    events = get_events(cal_service, monday, sunday)
    print(format_events_markdown(events, "今週の予定"))


def cmd_date(cal_service, date_str):
    """指定日の予定を表示"""
    dt = datetime.fromisoformat(date_str)
    end = dt + timedelta(days=1)
    events = get_events(cal_service, dt, end)
    print(format_events_markdown(events, f"{date_str} の予定"))


def cmd_range(cal_service, start_str, end_str):
    """指定期間の予定を表示"""
    start = datetime.fromisoformat(start_str)
    end = datetime.fromisoformat(end_str) + timedelta(days=1)
    events = get_events(cal_service, start, end)
    print(format_events_markdown(events, f"{start_str} ~ {end_str} の予定"))


def cmd_dl(cal_service, drive_service, date_str, dest_path):
    """指定日の予定の添付ファイルをすべてダウンロードする。"""
    dt = datetime.fromisoformat(date_str)
    end = dt + timedelta(days=1)
    events = get_events(cal_service, dt, end)

    count = 0
    for event in events:
        attachments = event.get("attachments", [])
        if not attachments:
            continue
        summary = event.get("summary", "(タイトルなし)")
        print(f"\n{summary}:")
        for att in attachments:
            file_id = att.get("fileId")
            if file_id:
                download_attachment(drive_service, file_id, dest_path)
                count += 1

    if count == 0:
        print("添付ファイルのある予定はありませんでした。")
    else:
        print(f"\n合計 {count} ファイルをダウンロードしました → {dest_path}")


def main():
    if len(sys.argv) < 2:
        print("使い方:")
        print("  python scripts/gcal.py today                              # 今日の予定")
        print("  python scripts/gcal.py week                               # 今週の予定")
        print("  python scripts/gcal.py date 2026-03-10                    # 指定日")
        print("  python scripts/gcal.py range 2026-03-01 2026-03-31        # 期間")
        print("  python scripts/gcal.py dl 2026-03-05 projects/koden/docs/ # 添付DL")
        sys.exit(1)

    creds = get_service()
    cal_service = build("calendar", "v3", credentials=creds)
    cmd = sys.argv[1]

    if cmd == "today":
        cmd_today(cal_service)
    elif cmd == "week":
        cmd_week(cal_service)
    elif cmd == "date" and len(sys.argv) >= 3:
        cmd_date(cal_service, sys.argv[2])
    elif cmd == "range" and len(sys.argv) >= 4:
        cmd_range(cal_service, sys.argv[2], sys.argv[3])
    elif cmd == "dl" and len(sys.argv) >= 4:
        drive_service = build("drive", "v3", credentials=creds)
        cmd_dl(cal_service, drive_service, sys.argv[2], sys.argv[3])
    else:
        print(f"不明なコマンド: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
