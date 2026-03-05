# 川越秘書 - 営業支援システム設計図

## コンセプト

燈株式会社 生成AI事業部のBizDevが、散在する情報（Notion, Slack, Gmail, Google Meet, 電話）を
GitHub × Markdown に集約し、Claude Codeと対話して提案書PPTX生成まで通すシステム。

### 核心思想（「Claude Codeで開発プロジェクトのプロマネをぶん回す」より）
- **フォルダ構成がすべてのハブ** - 散在する情報の最終着地点
- **処理（skill）とドメイン知識（CLAUDE.md）の分離** - スキルは横展開可能、CLAUDE.mdはプロジェクト固有
- **ボトムアップで育てる** - ただし「ある程度の型」は最初から用意する
- **スナップショットを残す** - セッションが切れても再開可能

---

## ゴール

| レベル | ゴール | 状態 |
|--------|--------|------|
| 最初 | 営業フェーズの1案件で「情報集約→PPTX提案書生成」まで通す | 🔧 構築中 |
| 中期 | 全案件の情報をprojects/配下に集約、提案書生成を日常運用 | 未着手 |
| 最終 | 全PJ横断管理（優先順位付け、状況把握、日次ルーティン効率化） | 未着手 |

---

## アーキテクチャ

```
[情報源]                    [川越秘書]                     [アウトプット]
Notion ──┐                 ┌─ CLAUDE.md (脳)              提案書 PPTX
Slack ───┤  手動/MCP で   │  projects/{案件}/             商談メモ (構造化)
Gmail ───┤  集約 ───────→ │    README.md (案件概要)       日次レビュー
Meet ────┤                 │    minutes/ (商談メモ)        PJ横断ステータス
電話 ────┘                 │    proposals/ (提案書)
                           │  shared/ (会社情報・テンプレ)
                           │  scripts/ (生成パイプライン)
                           └─ .claude/skills/ (スキル)
```

### PPTX生成パイプライン

```
Claude Code: 案件情報を読み込み
    ↓
Claude Code: 過去提案書の構成を参考にスライド構成を提案 → ユーザー承認
    ↓
Claude Code: proposal_data.json を書き出し
    ↓
Python: generate_proposal.py が JSON + 燈テンプレート → PPTX
    ↓
出力: projects/{案件}/proposals/generated/proposal_v{N}.pptx
```

### proposal_data.json 仕様

```json
{
  "template": "shared/templates/pptx/tomoshi-base.pptx",
  "output": "projects/{案件}/proposals/generated/proposal_v1.pptx",
  "slides": [
    {"layout": "title", "title": "...", "subtitle": "..."},
    {"layout": "section", "title": "..."},
    {"layout": "content", "title": "...", "body": "- 項目1\n- **太字**項目2"},
    {"layout": "two_column", "title": "...", "left": "...", "right": "...", "left_title": "...", "right_title": "..."},
    {"layout": "table", "title": "...", "headers": [...], "rows": [[...], ...]},
    {"layout": "closing", "title": "...", "body": "..."}
  ]
}
```

### 燈テンプレートのレイアウト一覧

| layout指定 | テンプレート名 | 用途 |
|-----------|---------------|------|
| title | TITLE | タイトルスライド（CENTER_TITLE + SUBTITLE） |
| section | SECTION_HEADER | セクション区切り |
| content | TITLE_AND_BODY | タイトル + 本文（箇条書き対応） |
| two_column | TITLE_AND_TWO_COLUMNS | 2カラム比較 |
| table | TITLE_AND_BODY | テーブル（テキストボックスで生成） |
| closing | SECTION_HEADER | クロージング |

※ テンプレートは Google Slides 由来、スライドサイズ 10.0 x 5.6 inches

---

## ディレクトリ構造

```
川越秘書/
├── CLAUDE.md                      # プロジェクトの脳（ドメイン知識）
├── plan.md                        # この設計図
├── .env                           # APIキー（git管理外）
├── .env.example                   # APIキーのテンプレート
├── .gitignore
├── requirements.txt               # python-pptx
│
├── projects/                      # 案件ごとの情報
│   └── {project-slug}/            # 例: koden, toua-road
│       ├── README.md              # 案件概要
│       ├── minutes/               # 商談メモ・Meet文字起こし
│       │   └── YYYYMMDD.md
│       ├── emails/                # 重要メール
│       ├── code/                  # 検証コード・PoC
│       ├── proposals/             # 提案書
│       │   └── generated/         # PPTX出力先
│       └── docs/                  # その他資料
│
├── shared/                        # 全体共通リソース
│   ├── company/                   # 燈の情報
│   │   ├── overview.md            # 会社概要
│   │   └── genai-solutions.md     # ソリューション一覧
│   ├── templates/
│   │   ├── pptx/
│   │   │   ├── tomoshi-base.pptx  # 燈公式テンプレート（ベース）
│   │   │   └── bizdev-sozai.pptx  # BizDev素材集
│   │   └── project-readme.md      # 新規案件テンプレート
│   └── references/                # 過去提案書（参考用）
│
├── scripts/
│   ├── generate_proposal.py       # JSON→PPTX変換
│   └── utils.py                   # Markdown→PPTX変換ヘルパー
│
├── reports/                       # PJ横断アウトプット（将来用）
│   └── daily/
│
└── .claude/
    └── skills/                    # カスタムスキル
```

---

## Phase 1: 基盤構築 ✅ 完了

- [x] GitHubリポジトリ初期化（private）
- [x] ディレクトリ構造作成
- [x] CLAUDE.md 作成
- [x] PPTX生成スクリプト（generate_proposal.py + utils.py）
- [x] 燈テンプレート配置・レイアウト解析
- [x] サンプルPPTX生成テスト通過
- [x] .gitignore, .env.example, requirements.txt
- [x] shared/company/ プレースホルダ
- [x] shared/templates/project-readme.md

## Phase 2: 最初の案件で試す 🔜 次のステップ

- [ ] shared/company/overview.md に燈の情報を記入
- [ ] shared/company/genai-solutions.md にソリューション情報を記入
- [ ] 弘電社or別案件の資料を projects/{slug}/ に整理
- [ ] README.md に案件概要を記入
- [ ] 過去提案書を shared/references/ に配置（参考用）
- [ ] 提案書のスライド構成をClaude Codeと相談→承認→PPTX生成
- [ ] 生成PPTXの品質確認・フィードバック→スクリプト改善

## Phase 3: 運用改善（ボトムアップで育てる）

使いながら必要になったらスキル化する：

- [ ] `/new-project` - 新規案件フォルダ作成スキル
- [ ] `/transcribe` - Meet文字起こし取り込み・構造化スキル
- [ ] `/daily-review` - 毎晩の優先順位付けスキル
- [ ] `/status` - 全PJ横断の状況確認スキル
- [ ] Notion MCP連携（WBSの情報取得）
- [ ] Slack MCP連携（情報共有）

## Phase 4: 全PJ横断管理

- [ ] reports/daily/ に日次レビューを自動生成
- [ ] 全案件の優先順位付け・ネクストアクション整理
- [ ] ルーティン業務の効率化

---

## 既存案件データ（移行対象）

| フォルダ | 案件 | 資料数 | 備考 |
|---------|------|--------|------|
| 弘電社PJ/ | 弘電社 AIAgent API PJ | ~35ファイル | KO資料、月次報告、質問回答表等 |
| 東亜PJ/ | 東亜道路工業 AIAgent PJ | ~10ファイル | KO資料、週次/月次報告等 |

→ projects/koden/, projects/toua-road/ に整理予定

---

## ユーザーが手動で行うこと

- `.env` にAPIキー設定（必要時）
- Meet文字起こしを Google Drive からDLして minutes/ に配置
- 重要メールを emails/ にコピー
- 過去提案書を shared/references/ に配置（初回のみ）
