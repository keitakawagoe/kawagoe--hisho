# ReAct Agent 詳細設計書

## 概要

ReAct (Reasoning + Acting) エージェントは、Claude Codeのように**自律的に思考し、行動する**AIエージェントです。
ユーザーの質問を受け取ると、自分で検索戦略を考え、複数回の検索を繰り返して最適な回答を返します。

```
ユーザー: 「切削オーバーレイ8000m2を含む工事を教えて」
    ↓
ReActエージェント:
    思考1: まず切削オーバーレイで広く検索してみよう
    行動1: search_direct_costs("切削オーバーレイ")
    結果1: 45件見つかった。数量は最大3000m2程度

    思考2: 8000m2は見つからない。データの傾向を確認しよう
    行動2: search_direct_costs("切削オーバーレイ", orderby="quantity desc")
    結果2: 最大は2,850m2だった

    思考3: 8000m2に近いものはないが、大きいものを報告しよう
    最終回答: 「8000m2に完全一致する工事はありませんでした。
               最も数量が多いのは○○工事の2,850m2です...」
```

---

## アーキテクチャ

### システム構成図

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Azure AI Foundry                                │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  大元のAIエージェント                                              │  │
│  │  - askReActAgent ツールを呼び出すだけ                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ POST /api/ask
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              Azure Function App (toadoro-react-agent)                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  function_app.py                                                  │  │
│  │  - HTTPトリガー (/api/ask)                                        │  │
│  │  - リクエスト受付 → agent_loop呼び出し → レスポンス返却            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                    │                                   │
│                                    ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  agent_loop.py (ReActループ本体)                                  │  │
│  │  ┌────────────────────────────────────────────────────────────┐  │  │
│  │  │  GPT-4.1 (Azure OpenAI)                                    │  │  │
│  │  │  - システムプロンプト: 自律行動の指示                        │  │  │
│  │  │  - ツール: 3つの検索関数                                    │  │  │
│  │  │  - temperature: 0.3 (安定した出力)                          │  │  │
│  │  └────────────────────────────────────────────────────────────┘  │  │
│  │                         │                                        │  │
│  │           ┌─────────────┼─────────────┐                         │  │
│  │           ▼             ▼             ▼                         │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │  │
│  │  │search_direct│ │search_      │ │search_      │               │  │
│  │  │_costs       │ │projects     │ │indirect_    │               │  │
│  │  │             │ │             │ │costs        │               │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                    │                                   │
│                                    ▼                                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  sas_helper.py                                                    │  │
│  │  - 検索結果のfile_urlにSASトークンを付与                          │  │
│  │  - 有効期限: 約10年 (3650日)                                      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Azure AI Search                                 │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐             │
│  │toadoro-projects│ │toadoro-direct- │ │toadoro-indirect│             │
│  │ (61件)         │ │costs (11,313件)│ │-costs (200件)  │             │
│  └────────────────┘ └────────────────┘ └────────────────┘             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ファイル構成

```
react_agent/
├── function_app.py      # HTTPトリガー (エントリーポイント)
├── agent_loop.py        # ReActループ本体
├── sas_helper.py        # SASトークン生成
├── requirements.txt     # 依存パッケージ
├── host.json           # Azure Functions設定
├── local.settings.json # ローカル環境変数 (git管理外)
└── openapi.json        # API仕様書 (AI Foundry連携用)
```

---

## ReActループの詳細

### 処理フロー

```python
def agent_loop(payload):
    # 1. 初期化
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query}
    ]

    # 2. ループ開始 (最大10回)
    for iteration in range(max_iterations):

        # 3. LLMに問い合わせ
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3
        )

        # 4. ツール呼び出しがなければ終了 (最終回答)
        if not assistant_message.tool_calls:
            return {
                "status": "completed",
                "final_answer": assistant_message.content,
                ...
            }

        # 5. ツールを実行
        for tool_call in assistant_message.tool_calls:
            result = execute_tool(tool_name, arguments)
            messages.append({"role": "tool", "content": result})

        # 6. 次のイテレーションへ

    # 7. 最大回数到達
    return {"status": "max_iterations_reached", ...}
```

### 状態遷移図

```
┌─────────┐
│  開始   │
└────┬────┘
     │
     ▼
┌─────────────────────────────────────┐
│  LLMに問い合わせ                     │◄──────────────┐
│  (システムプロンプト + 会話履歴)      │               │
└────────────────┬────────────────────┘               │
                 │                                    │
     ┌───────────┴───────────┐                       │
     │                       │                       │
     ▼                       ▼                       │
┌─────────┐           ┌─────────────┐               │
│ツール   │           │ツール呼び出し│               │
│呼び出し │           │なし         │               │
│あり     │           │(最終回答)    │               │
└────┬────┘           └──────┬──────┘               │
     │                       │                       │
     ▼                       ▼                       │
┌─────────────┐        ┌─────────┐                  │
│ツール実行   │        │  終了   │                  │
│(検索など)   │        │completed│                  │
└────┬────────┘        └─────────┘                  │
     │                                              │
     ▼                                              │
┌─────────────────┐                                 │
│結果をmessagesに │                                 │
│追加             │                                 │
└────────┬────────┘                                 │
         │                                          │
         │  iteration < max_iterations              │
         └──────────────────────────────────────────┘
         │
         │  iteration >= max_iterations
         ▼
    ┌─────────────────┐
    │      終了       │
    │max_iterations   │
    │_reached         │
    └─────────────────┘
```

---

## システムプロンプト

ReActエージェントの行動を制御する核心部分です。

```python
SYSTEM_PROMPT = """あなたは建設工事の過去事例を検索するAIエージェントです。

## あなたの役割
ユーザーの質問に答えるために、検索ツールを使って自律的に情報を集めます。
**ユーザーの指示を待たずに、自分で判断して行動してください。**

## 重要：思考を言語化する
**ツールを呼び出す前に、必ず以下を述べてください：**
1. 現状の分析（何が分かっていて、何が分かっていないか）
2. 次に何をしようとしているか、その理由
3. どんな検索条件で試すか

## 自律的に行動するためのルール

### 1. 結果が0件の場合
→ **ユーザーに聞かずに、自分でフィルタを緩めて再検索**

### 2. まず広く検索してデータの傾向を把握
→ 最初はフィルタなしで検索して、どんなデータがあるか確認

### 3. 諦めずに複数の方法を試す
→ 最低でも3〜5回は検索を試みてから結論を出す

## 重要
- **ユーザーに「どうしますか？」と聞かない**
- **自分で考えて、自分で行動する**
"""
```

### プロンプト設計のポイント

| 項目 | 意図 |
|------|------|
| 「ユーザーの指示を待たずに」 | 受動的なAIにならないよう強制 |
| 「思考を言語化する」 | 検索戦略の可視化、デバッグ容易性 |
| 「フィルタを緩めて再検索」 | 0件で終わらせない自己回復 |
| 「3〜5回は試みる」 | 安易な諦めを防止 |
| 「どうしますか？と聞かない」 | Claude的な確認癖を抑制 |

---

## LLMへのツール定義の渡し方

ReActエージェントでは、OpenAI Function Calling形式でツールをLLMに渡しています。

### ツール定義の構造

```python
# agent_loop.py 190-270行目

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_direct_costs",
            "description": "直接工事費の明細を検索します。工種名、数量、単価、支店などで検索できます。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "検索キーワード（工種名など）。例: '切削オーバーレイ', '区画線', '殻運搬'"
                    },
                    "filter": {
                        "type": "string",
                        "description": "ODataフィルター式。例: \"branch eq '関東支社'\", \"quantity ge 1000\""
                    },
                    "top": {
                        "type": "integer",
                        "description": "取得件数（デフォルト20）",
                        "default": 20
                    }
                },
                "required": ["query"]
            }
        }
    },
    // ... 他の2つのツールも同様の形式
]
```

### LLM呼び出し時の渡し方

```python
# agent_loop.py 325-331行目

response = client.chat.completions.create(
    model="gpt-4.1",
    messages=messages,
    tools=TOOLS,           # ← ここでツール定義を渡す
    tool_choice="auto",    # ← LLMが自動で使うか決める
    temperature=0.3
)
```

### LLMへの入力と出力

```
┌─────────────────────────────────────────────────────────┐
│  GPT-4.1 への入力                                       │
│                                                         │
│  1. システムプロンプト (SYSTEM_PROMPT)                   │
│     → 「自律的に行動しろ」「思考を言語化しろ」など       │
│                                                         │
│  2. ツール定義 (TOOLS)                                  │
│     → 各ツールの名前、説明、パラメータ                  │
│     → LLMはこれを見て「どのツールをどう使うか」決める   │
│                                                         │
│  3. 会話履歴 (messages)                                 │
│     → ユーザーの質問                                    │
│     → 前回のツール呼び出し結果                          │
└─────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  GPT-4.1 の出力                                         │
│                                                         │
│  パターンA: ツール呼び出し                              │
│  {                                                      │
│    "content": "切削オーバーレイで検索してみます",       │
│    "tool_calls": [{                                     │
│      "id": "call_abc123",                               │
│      "function": {                                      │
│        "name": "search_direct_costs",                   │
│        "arguments": "{\"query\": \"切削オーバーレイ\"}" │
│      }                                                  │
│    }]                                                   │
│  }                                                      │
│                                                         │
│  パターンB: 最終回答（ツール呼び出しなし）              │
│  {                                                      │
│    "content": "検索結果をまとめると...",                │
│    "tool_calls": null                                   │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
```

### ツール実行結果のフィードバック

ツール呼び出し後、結果はmessagesに追加されてLLMに返されます。

```python
# ツール実行後
messages.append({
    "role": "tool",
    "tool_call_id": tool_call.id,  # どのツール呼び出しへの応答か
    "content": result              # 検索結果JSON
})
```

これにより、LLMは前回の検索結果を見て次のアクションを決定できます。

### tool_choice パラメータ

| 値 | 動作 |
|-----|------|
| `"auto"` | LLMが必要に応じてツールを使う（現在の設定） |
| `"none"` | ツールを使わない（テキスト応答のみ） |
| `"required"` | 必ずツールを使う |
| `{"type": "function", "function": {"name": "xxx"}}` | 特定のツールを強制 |

---

## 内部ツール

### 1. search_direct_costs

直接工事費の明細を検索します。

```python
{
    "name": "search_direct_costs",
    "description": "直接工事費の明細を検索します。工種名、数量、単価、支店などで検索できます。",
    "parameters": {
        "query": "検索キーワード（工種名など）",
        "filter": "ODataフィルター式",
        "top": "取得件数（デフォルト20）"
    }
}
```

**対応インデックス**: `toadoro-direct-costs` (11,313件)

**返却フィールド**:
- id, project_name, branch, location
- item_name, specification, unit, quantity, unit_price, amount
- file_url, file_name

### 2. search_projects

工事概要を検索します。

```python
{
    "name": "search_projects",
    "description": "プロジェクト概要を検索します。工事名、支店、場所、契約期間、工期日数などで検索できます。",
    "parameters": {
        "query": "検索キーワード",
        "filter": "ODataフィルター式",
        "top": "取得件数（デフォルト10）"
    }
}
```

**対応インデックス**: `toadoro-projects` (61件)

**返却フィールド**:
- id, project_name, branch, location
- contract_amount, item_keywords, total_amount
- contract_period, work_days
- file_url, file_name

### 3. search_indirect_costs

間接費を検索します。

```python
{
    "name": "search_indirect_costs",
    "description": "間接工事費を検索します。共通仮設費、現場経費などの内訳を調べられます。",
    "parameters": {
        "query": "検索キーワード（項目名など）",
        "filter": "ODataフィルター式",
        "top": "取得件数（デフォルト20）"
    }
}
```

**対応インデックス**: `toadoro-indirect-costs` (200件)

**返却フィールド**:
- id, project_name, branch, category
- item_name, unit, quantity, unit_price, amount
- file_url, file_name

---

## フィルター構文 (OData)

LLMが生成するフィルター式の例:

```
# 支店で絞り込み
branch eq '関東支社'

# 数量の範囲
quantity ge 1000 and quantity le 5000

# 複合条件
branch eq '関東支社' and quantity ge 1000

# カテゴリ絞り込み（間接費用）
category eq '共通仮設費'
```

---

## SASトークン生成

### 処理フロー

```
検索結果
    ↓
file_url: "https://toadorofilestorage.blob.core.windows.net/toadoro-files/..."
    ↓
sas_helper.add_sas_to_results()
    ↓
file_url: "https://...?se=2036-02-03T06:53:24Z&sp=r&sv=2026-02-06&sr=b&sig=..."
```

### 設定

| 項目 | 値 |
|------|-----|
| 有効期限 | 約10年 (3650日) |
| 権限 | 読み取り専用 (r) |
| Storage Account | toadorofilestorage |
| Container | toadoro-files |

### 日本語パス名の処理

```python
# URLエンコードされた状態でパース
blob_name = unquote(path_parts[1])  # デコード

# SAS署名を生成後、再エンコード
encoded_blob_name = quote(blob_name, safe="/")
```

---

## API仕様

### エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| POST | /api/ask | 質問を投げる |
| GET | /api/health | ヘルスチェック |

### リクエスト

```json
POST /api/ask
{
    "user_query": "切削オーバーレイ8000m2を含む工事を教えて",
    "max_iterations": 10
}
```

### レスポンス

```json
{
    "status": "completed",
    "iterations": 3,
    "final_answer": "検索結果: ...",
    "thinking_history": [
        {
            "iteration": 1,
            "thinking": "まず切削オーバーレイで広く検索してみます",
            "tool_calls": [
                {
                    "tool": "search_direct_costs",
                    "arguments": {"query": "切削オーバーレイ"},
                    "result_count": 45
                }
            ]
        },
        ...
    ]
}
```

---

## 設定パラメータ

### 環境変数 (local.settings.json)

| 変数名 | 説明 |
|--------|------|
| AZURE_SEARCH_ENDPOINT | Azure AI Search エンドポイント |
| AZURE_SEARCH_API_KEY | Azure AI Search APIキー |
| AZURE_OPENAI_ENDPOINT | Azure OpenAI エンドポイント |
| AZURE_OPENAI_API_KEY | Azure OpenAI APIキー |
| AZURE_OPENAI_CHAT_DEPLOYMENT | デプロイメント名 (gpt-4.1) |
| AZURE_STORAGE_CONNECTION_STRING | Blob Storage 接続文字列 |

### チューニングパラメータ

| パラメータ | 現在値 | 説明 |
|-----------|--------|------|
| max_iterations | 10 | 最大ループ回数 |
| temperature | 0.3 | LLMの出力安定性 (低いほど安定) |
| top (direct_costs) | 20 | 1回の検索で取得する最大件数 |
| top (projects) | 10 | 工事概要の取得件数 |
| top (indirect_costs) | 20 | 間接費の取得件数 |

---

## デプロイ

### Azure Function Appへのデプロイ

```bash
cd react_agent
func azure functionapp publish toadoro-react-agent --python
```

### デプロイ先情報

| 項目 | 値 |
|------|-----|
| Function App名 | toadoro-react-agent |
| URL | https://toadoro-react-agent.azurewebsites.net |
| リージョン | Japan East |
| ランタイム | Python 3.11 |

---

## トラブルシューティング

### よくある問題

| 問題 | 原因 | 解決策 |
|------|------|--------|
| SASトークンエラー | 日本語パス名のエンコード | unquote/quoteで処理 |
| 検索結果0件 | フィルタが厳しすぎ | フィルタを緩める |
| 最大イテレーション到達 | 質問が複雑すぎ | max_iterationsを増やす |
| ハルシネーション | レスポンスに詳細を含めすぎ | result_previewを削除 |

### ログ確認

```bash
# Azure Functionsのログをストリーミング
func azure functionapp logstream toadoro-react-agent
```

---

## 今後の改善案

1. **ストリーミング対応**: 思考過程をリアルタイム表示
2. **キャッシュ機能**: 同一クエリの結果をキャッシュ
3. **フォールバック**: Azure OpenAIがダウンした場合の代替
4. **メトリクス収集**: 検索成功率、平均イテレーション数など
