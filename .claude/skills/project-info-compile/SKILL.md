# 案件情報コンパイルスキル

企業名を受け取り、Googleカレンダー・議事録・メール・ローカルファイルから案件情報を自動収集し、`projects/{案件スラッグ}/` にREADME.mdと議事録を一括生成する。

---

## 1. 概要

「{企業名}の案件情報をまとめて」と依頼された時に実行するスキル。
以下の情報ソースから**漏れなく**情報を収集し、構造化された案件フォルダを作成する。

**情報ソース（この順番で必ずすべて確認する）:**
1. **Googleカレンダー** → 過去・未来のMTG一覧、参加者、添付ファイル（Geminiメモ）
2. **Google Drive** → カレンダー添付のGeminiメモ（議事録）をテキストとしてダウンロード
3. **Gmail** → 案件に関するメールのやり取り
4. **ローカルファイル** → 既存のデモフォルダ、提案書PDF、要件定義書など
5. **Web検索** → 企業売上・従業員数（README記載用）

## 2. インプット

| 項目 | 必須 | 説明 |
|------|------|------|
| **企業名** | 必須 | 日本語の企業名（例: 「三共舗道」「日本設備工業」） |
| **案件スラッグ** | 任意 | フォルダ名に使う英語スラッグ。未指定の場合は企業名から推測して提案 |

## 3. アウトプット

```
projects/{案件スラッグ}/
├── README.md              # 案件概要（下記テンプレートに従う）
├── minutes/               # 議事録（Geminiメモのテキストファイル）
│   ├── YYYYMMDD_gemini_memo.txt
│   └── ...
└── emails/                # 関連メール（gmail.py saveで自動保存）
    ├── YYYYMMDD_{件名}.md
    └── ...
```

## 4. 実行手順

### STEP 1: Googleカレンダーからmtg一覧を取得（過去+未来）

**目的**: この企業に関するMTGを漏れなく特定し、PJ経緯の全体像を把握する。

```bash
# 過去1年+未来1ヶ月の範囲で検索（範囲は状況に応じて調整）
.venv/bin/python scripts/gcal.py range {1年前のYYYY-MM-DD} {1ヶ月後のYYYY-MM-DD}
```

出力から**企業名を含む予定**をすべて抽出し、以下を記録する:
- **日時**（YYYY/MM/DD HH:MM）
- **タイトル**（MTGの種類を推定するヒント）
- **参加者**（カウンター・燈側メンバーの特定に使用）
- **添付ファイル**（Geminiメモの `fileUrl` からファイルIDを抽出 → STEP 2で使用）

**重要**:
- タイトルに企業名が含まれない予定もある（例: 「Hikari打合せ」等）。参加者の所属から判断すること
- カレンダー出力は1回で全予定を取得できないことがある。`max_results` を増やすか、期間を分割して検索

### STEP 2: 議事録（Geminiメモ）をDrive APIでダウンロード

**目的**: 各MTGのGeminiメモ（Google Docs形式の自動議事録）をテキストとして取得し、`minutes/` に保存する。

STEP 1で特定した各MTGの添付ファイルについて:

#### 方法A: gcal.py dl コマンドを使う（推奨）
```bash
# 指定日の添付ファイルをすべてダウンロード
.venv/bin/python scripts/gcal.py dl {YYYY-MM-DD} projects/{案件スラッグ}/minutes/
```

#### 方法B: Drive APIで直接取得（方法Aが使えない場合）
```python
# カレンダー添付のfileUrlからファイルIDを抽出
# 例: https://docs.google.com/document/d/{FILE_ID}/edit → FILE_IDを取得
.venv/bin/python3 -c "
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pathlib import Path

TOKEN_PATH = Path('token.json')
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
drive = build('drive', 'v3', credentials=creds)

file_id = '{FILE_ID}'
result = drive.files().export(fileId=file_id, mimeType='text/plain').execute()
text = result.decode('utf-8')

# minutes/に保存
with open('projects/{案件スラッグ}/minutes/{YYYYMMDD}_gemini_memo.txt', 'w') as f:
    f.write(text)
print('保存完了')
"
```

**ファイル命名規則**: `{YYYYMMDD}_gemini_memo.txt`（MTGの日付を使用）

**注意**:
- Google Docsの添付ファイルは `mimeType: application/vnd.google-apps.document` → `text/plain` でエクスポート
- 録画リンクやMP4はダウンロード不要（容量が大きすぎる）
- WebFetchやcurlでGoogle Docsにアクセスしてはいけない（認証エラーになる）。必ずDrive APIを使う

### STEP 3: Gmailから関連メールを検索・保存

**目的**: MTGの間で行われたメールのやり取りから、追加の文脈情報を把握し、`emails/` に保存する。

```bash
# メールを検索して emails/ に保存
.venv/bin/python scripts/gmail.py save "{企業名}" projects/{案件スラッグ}/emails/
```

メールから以下を読み取る:
- 提案資料の送付日・内容
- 先方からの質問・懸念事項
- 次回MTGの調整経緯
- 費用対効果資料などの追加資料の有無

**注意**: `search` ではなく `save` コマンドを使うこと。`save` はメールの内容をMarkdownファイルとして `emails/` に保存する。

### STEP 4: ローカルファイルの探索

**目的**: ローカルに存在する関連ファイル（デモコード、提案書PDF、要件定義書等）を特定する。

以下の場所を順に検索する:

```
# 1. 既存のプロジェクトフォルダ
Glob: projects/*{企業名の一部}*/**
Grep: "{企業名}" で projects/ 配下を検索

# 2. Documentsフォルダ内のデモ・開発フォルダ
Glob: /Users/kawagoekeita/Documents/Agent/*{企業名の一部}*/**

# 3. Downloadsフォルダ内の提案書PDF
Glob: /Users/kawagoekeita/Downloads/*{企業名の一部}*.*
```

見つかったファイルの種類:
| ファイルの種類 | 処理 |
|---------------|------|
| デモコード/開発フォルダ | README.mdにパスを記載 |
| 提案書PDF | README.mdの資料構成セクションにパスを記載 |
| 要件定義書/要件整理表 | 内容を読み取り、README.mdに反映 |
| 議事録（docx等） | 内容を読み取り、README.mdのPJ経緯に反映 |

### STEP 5: 企業情報をWeb検索

```
WebSearch: "{企業名} 売上高 従業員数 {直近年度}"
```

非上場で情報がない場合は「非公開」と記載。

### STEP 6: README.md を生成

STEP 1〜5で収集した情報を統合し、以下のテンプレートに従ってREADME.mdを生成する。

## 5. README.md テンプレート

```markdown
# {企業名} - {案件テーマ}

## 基本情報
- **顧客**: {企業名}（{業種}・{拠点}）
- **企業売上**: {売上高}（{年度}）
- **燈側リード**: {メンバー名}（{担当領域}）
- **フェーズ**: {現在のフェーズ}
- **開始日**: {初回接触時期}
- **想定契約金額**: {金額}
- **次回アクション**: {具体的な次のアクション}

## 背景・課題
{企業の事業内容と、AIエージェント導入を検討している背景・課題を記載}

**主な課題:**
- {課題1}
- {課題2}
- ...

**定量データ（MTGで確認済みの場合）:**
- {定量データ1}
- {定量データ2}

## カウンター
| 名前 | 役割 |
|------|------|
| {名前} | {役割} |

## 燈側
| 名前 | 担当領域 |
|------|----------|
| {名前} | {担当領域} |

## PJ経緯
1. **{YYYY/MM/DD}** - {MTGの内容・概要}
2. **{YYYY/MM/DD}** - {MTGの内容・概要}
3. ...
{※ STEP 1のカレンダー情報 + STEP 2の議事録内容から時系列で記載}

## 提案内容

### プロダクト概要
{提案しているプロダクト/サービスの概要}

### ステップ構成（提案済みの場合）
- **ステップ1**: {内容} - 費用: {金額}
- **ステップ2**: {内容} - 費用: {金額}

### 技術構成
- {技術要素1}
- {技術要素2}
- ...

## 要件整理状況（ヒアリング済みの場合）
{要件の整理状況をまとめる}

## 先方の温度感・リスク
- **温度感**: {前向き/慎重/保留 + 具体的な発言の引用}
- **費用懸念**: {費用に対する先方の反応}
- **決裁フロー**: {稟議の流れ}
- **競合リスク**: {他社検討の状況}

## 資料構成
- `minutes/` - 議事録
  - {ファイル一覧と概要}
- 提案資料:
  - {ファイルパスと概要}
- デモコード:
  - {ファイルパスと概要}

## メモ
- {重要な補足事項}
- {技術的な注意点}
- {先方から得た重要な情報}
```

## 6. 品質基準

### 必須チェックリスト
- [ ] カレンダーの過去の予定を**すべて**確認した（漏れているMTGがないか）
- [ ] 各MTGのGeminiメモを**すべて**ダウンロードしてminutes/に保存した
- [ ] Gmailで関連メールを検索した
- [ ] ローカルファイル（Documents/Agent/, Downloads/）を検索した
- [ ] PJ経緯が時系列で正確に記載されている
- [ ] 先方の発言・温度感が議事録の内容に基づいている（推測で書かない）
- [ ] 金額・スケジュール情報が最新のMTG内容を反映している
- [ ] 資料構成にローカルファイルのパスが正確に記載されている

### やってはいけないこと
- **カレンダーを確認せずにREADMEを作成する**（MTGの漏れが発生する）
- **WebFetch/curlでGoogle Docsにアクセスする**（認証エラーになる。Drive APIを使う）
- **議事録の内容を読まずにPJ経緯を書く**（不正確な情報になる）
- **金額や日程を推測で埋める**（「（要確認）」と明記する）
- **Web検索やNotionで情報を探す前にローカルファイルとメールを確認する**（ローカルにある情報をWebで探すのは非効率）

## 7. よくあるトラブルと対処

| トラブル | 原因 | 対処 |
|---------|------|------|
| Google Docsにアクセスできない | WebFetch/curlを使っている | Drive APIを使う（STEP 2参照） |
| カレンダーにMTGが見つからない | 検索範囲が狭い | rangeの期間を広げる。企業名以外のキーワードでも検索 |
| 議事録がHTML（ログインページ）になる | curlで取得した | Drive APIで再取得する |
| token.jsonが期限切れ | OAuthトークンの有効期限 | gmail.pyまたはgcal.pyを実行すると自動更新される |
| docxファイルが読めない | python-docxが未インストール | `.venv/bin/pip install python-docx` |

## 8. 実行例

```
ユーザー: 「三共舗道の案件情報をまとめて」

→ STEP 1: gcal.py range 2025-09-01 2026-04-30
   → 1/16, 1/22, 2/24 のMTGを特定（添付にGeminiメモあり）

→ STEP 2: 各日のGeminiメモをDrive APIでダウンロード
   → minutes/20260116_gemini_memo.txt
   → minutes/20260122_gemini_memo.txt
   → minutes/20260224_gemini_memo.txt

→ STEP 3: gmail.py save "三共舗道" projects/sankyo-hodo/emails/
   → 50件のメールをemails/に保存。提案書送付（2/13, 2/24）、費用対効果資料（2/27）、MTG調整等を把握

→ STEP 4: ローカル検索
   → /Documents/Agent/三共舗道様施工計画書demo/ にデモコード発見
   → /Downloads/ に提案書PDF3件発見
   → 三共舗道_要件整理表.xlsx 発見

→ STEP 5: WebSearch "三共舗道 売上高"
   → 非公開

→ STEP 6: README.md 生成
   → projects/sankyo-hodo/README.md に全情報を統合して出力
```
