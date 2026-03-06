# 東亜道路工業 - 検証進捗管理

## 概要
建設工事実行予算データの AI 検索システム構築に向けた検証プロジェクト。

## フェーズ一覧

| フェーズ | 名称 | ステータス | 概要 |
|---------|------|-----------|------|
| Phase 1 | データ整備・ETL | 完了 | Excel→JSON変換、Azure AI Search インデックス構築 |
| Phase 2 | 検索API構築 | 完了 | 6つの検索API（Azure Functions）を構築・デプロイ |
| Phase 3 | ReAct Agent | 検証中 | 自律型AIエージェントによる複合検索の実現 |

---

## Phase 1: データ整備・ETL (`phase1-data-prep/`)

**目的**: 東亜道路の実行予算書（Excel）を構造化データに変換し、Azure AI Search に投入する

**成果物**:
- 61プロジェクト、11,313件の直接工事費明細、200件超の間接費明細をJSON化
- 3つの Azure AI Search インデックス構築（projects, direct_costs, indirect_costs）
- 岩手・宮城・中部等の地域データも追加投入済み

**主要スクリプト**:
- `convert_excel_to_json.py` - メインのExcel→JSON変換
- `parse_xlsm_files.py` - XLSM形式のパース
- `parsers/` - フォーマット検出・振り分けモジュール
- `setup_azure_search.py` - インデックス作成
- `upload_to_blob.py` - Azure Blob Storage へのアップロード

**ステータス**: 完了

---

## Phase 2: 検索API構築 (`phase2-search-api/`)

**目的**: Azure Functions 上に6つの検索APIを構築

**成果物**:
| API | 機能 |
|-----|------|
| `/search_projects` | プロジェクト検索（支店・地域・金額フィルタ） |
| `/search_details` | 原価明細のフルテキスト検索 |
| `/get_project_details` | プロジェクト全明細の取得 |
| `/aggregate_by_project` | 複数工種を持つプロジェクトの検索 |
| `/get_statistics` | 集計統計（min/max/avg/sum） |
| `/search_indirect_costs` | 間接費の検索 |

**ステータス**: 完了

---

## Phase 3: ReAct Agent (`phase3-agent/`)

**目的**: 自律型AIエージェントが検索APIを駆使して、ユーザーの質問に回答する

**成果物**:
- ReAct（Reasoning + Acting）ループの実装
- Azure AI Foundry との連携
- OpenAPI仕様に基づくツール呼び出し

**課題・次のアクション**:
- [ ] 全角/半角カタカナの正規化（グレーチング vs ｸﾞﾚｰﾁﾝｸﾞ）
- [ ] 表記揺れ対応（現場打ち vs 現場打）
- [ ] 同義語辞書の構築（バックホウ vs BH0.15）
- [ ] ベクトル検索の導入検討

**ステータス**: 検証中

---

## 既知の課題（PoC検証まとめより）

| 課題 | 重要度 | 対応策 | 工数目安 |
|------|--------|--------|---------|
| 全角/半角カタカナ不一致 | 高 | ETL時の正規化 | 1日 |
| 送り仮名・表記揺れ | 中 | 同義語辞書 + 部分一致 | 2-3日 |
| 漢字の異字体（升 vs 桝） | 中 | 同義語辞書 | 2-3日 |
| 同義語（バックホウ vs BH0.15） | 高 | 同義語辞書 or ベクトル検索 | 1週間+ |

---

## 更新履歴

- 2026-03-06: PROGRESS.md 作成、★東亜PJ から kawagoe-hisho リポジトリに移行
