# 金融リサーチエージェント

<div align="center">

**商品先物向け多Agent型リサーチ自動化パイプライン**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com/)
[![Stars](https://img.shields.io/github/stars/Adkid-Zephyr/Financial-research-agent-QBT?style=social)](https://github.com/Adkid-Zephyr/Financial-research-agent-QBT)

[English](./README.md) | [中文](./README_CN.md) | 日本語

---

*データ収集から構造化レポートと品質審査まで——エンドツーエンドのリサーチ自動化システム*

</div>

---

## 🚀 プロジェクトストーリー

> **なぜこのプロジェクトを公開で构建しているのか**

従来の定量リサーチワークフローでは、アナリストは60-70%の時間を反復作業に費やしています：データ収集、レポート整形、イベント追跡、初期品質チェック。このプロジェクトは単純な実験から始まりました：

**「パイプライン作業を処理するシステムを构建し、リサーチャーが本当に重要な分析と意思決定に集中できるようにできないか？**

概念検証から始まり、完全なリサーチ自動化システムへと進化：
- 多Agentオーケストレーション（LangGraph）
- リアルタイムWebSocketイベントストリーミング
- 本番対応FastAPIバックエンド
- Docker Composeデプロイ
- 構造化ルーブリック品質審査

これは**AnnPoint（广州安点科技）**で勤務期間に開発した**個人ポートフォリオプロジェクト**です。会社はこれをオープンソースプロジェクトとして公開する完全な権利を私に授与し、 proprietaryデータソースは非公開としています。

---

## ✨ 主な機能

| 機能 | 説明 |
|------|------|
| 🔀 **多Agentパイプライン** | オーケストレーションワークフロー：集約 → 分析 → 撰写 → 審査 |
| 📊 **多源データ融合** | CTPスナップショット、Yahoo Finance、AkShare商品データ |
| 🔄 **審査ループ** | 最大2ラウンドの構造化ルーブリック品質審査 |
| 🌐 **FastAPI + WebSocket** | リアルタイムイベントストリーミング、タスク監視 |
| 📦 **PostgreSQLストレージ** | 永続レポートアーカイブ、クエリAPI |
| 🐳 **Docker Compose** | 一括デプロイ：app + postgres + nginx |
| 🖥️ **Webコンソール** | ヘルスチェック、タスクトリガー、イベントストリーム、レポートビューア |
| 📝 **レポート審査Agent** | 独立審査ツール、Markdown/PDF/JSONエクスポート |

---

## 🏗️ システムアーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────────┐ │
│  │ /runs   │  │/batches │  │/reports │  │ WebSocket /ws/events│ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     LangGraph Workflow                           │
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │ Aggregate│───▶│ Analyzer │───▶│  Writer  │───▶│ Reviewer │  │
│   │  集約器  │    │  分析器  │    │  撰写器  │    │  審査器  │  │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│        │              │               │               │         │
│        ▼              ▼               ▼               ▼         │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │              Data Source Registry                         │  │
│   │   CTP Snapshot │ Yahoo Finance │ AkShare │ Mock(dev)     │  │
│   └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Storage Layer                               │
│          PostgreSQL(本番) / SQLite(ローカル開発)                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 プロジェクト構造

```
.
├── futures_research/          # メインワークフロー & API
│   ├── api/                   # FastAPIルート & 静的フロントエンド
│   ├── agents/                # LangGraphノード
│   ├── data_sources/          # CTP、Yahoo、AkShareアダプター
│   ├── storage/               # PostgreSQLリポジトリ
│   └── events/                # WebSocketイベントバス
├── report_review_agent/       # 独立審査ツール
├── deploy/                    # Docker、Nginx、cronスクリプト
├── varieties/                 # 商品YAML設定
├── tests/                     # 40+単体テスト
└── memory/                    # 開発ハンドオフドキュメント
```

---

## ⚡ クイックスタート

### 前提条件
- Python 3.11+
- Docker & Docker Compose（デプロイ用）

### ローカル開発

```bash
# リポジトリをクローン
git clone https://github.com/Adkid-Zephyr/Financial-research-agent-QBT.git
cd Financial-research-agent-QBT

# 仮想環境を作成
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt

# APIサーバーを起動
uvicorn futures_research.api.app:app --reload --port 8025
```

アクセス：
- 🖥️ **フロントエンド**: http://127.0.0.1:8025/
- 🔧 **管理コンソール**: http://127.0.0.1:8025/admin
- 📖 **APIドキュメント**: http://127.0.0.1:8025/docs
- 🔌 **WebSocket**: ws://127.0.0.1:8025/ws/events

### Dockerデプロイ

```bash
# 環境テンプレートをコピー
cp .env.example .env

# 設定を構成（オプション：ANTHROPIC_API_KEYを追加でLLMモード有効化）
# エディタで.envを編集

# Docker Composeで起動
docker compose up --build -d

# ヘルスチェック
curl http://127.0.0.1:8080/healthz
```

デフォルトエンドポイント：
| サービス | URL |
|----------|-----|
| フロントエンド | http://127.0.0.1:8080/ |
| ヘルスチェック | http://127.0.0.1:8080/healthz |
| APIドキュメント | http://127.0.0.1:8080/docs |
| WebSocket | ws://127.0.0.1:8080/ws/events |

---

## 🔧 設定

### 環境変数

| 変数 | 説明 | デフォルト |
|------|------|------------|
| `ANTHROPIC_API_KEY` | LLM APIキー（オプション） | - |
| `ANTHROPIC_BASE_URL` | LLMエンドポイントURL | - |
| `LLM_MODEL` | モデルID | `kimi-k2.5` |
| `DATABASE_URL` | PostgreSQL DSN（オプション） | SQLiteフォールバック |
| `ANALYSIS_RENDER_MODE` | `deterministic` / `hybrid` / `llm` | `hybrid` |
| `REPORT_RENDER_MODE` | `deterministic` / `hybrid` / `llm` | `hybrid` |
| `ENABLE_YAHOO_MARKET_SOURCE` | Yahoo Financeデータを有効化 | `false` |
| `ENABLE_AKSHARE_COMMODITY_SOURCE` | AkShareデータを有効化 | `false` |

### 外部データソース有効化

```bash
ENABLE_YAHOO_MARKET_SOURCE=true \
ENABLE_AKSHARE_COMMODITY_SOURCE=true \
uvicorn futures_research.api.app:app --port 8025
```

---

## 📈 ロードマップ

> **公開で构建——ここを目指しています**

### Phase 2（計画中）
- [ ] 追加データソース統合（Wind、Bloomberg API）
- [ ] 高度スケジューリングとタスクオーケストレーション
- [ ] 詳細なレポートスコアリング
- [ ] フロントエンド履歴再生機能
- [ ] マルチユーザー認証
- [ ] GitHub Actions CI/CDパイプライン

### 現在の状態
- ✅ Phase 1完了：完全ワークフロー、API、WebSocket、ストレージ
- ✅ Docker Compose MVPデプロイ
- ✅ 多源データ融合（CTP + Yahoo + AkShare）
- ✅ 構造化ルーブリック審査ループ
- ✅ Web監視コンソール

---

## 🧪 テスト

```bash
# 全テスト実行
python -m unittest discover -s tests

# 特定モジュール実行
python -m unittest tests.test_workflow tests.test_api

# カバレッジレポート（オプション）
pip install coverage
coverage run -m unittest discover -s tests
coverage report
```

---

## 📜 ライセンスと帰属

```
Copyright 2026 FENGSHUO LIU (刘丰硕)

Licensed under the Apache License, Version 2.0
```

このプロジェクトは**AnnPoint 广州安点科技**勤務期間に開発されました。会社は作者に個人オープンソースプロジェクトとして公開する完全な権利を授与しています。

> ⚠️ **注記**：AnnPointがテスト用に提供したtick-levelデータソースはproprietaryであり、本プロジェクトには含まれていません。ユーザーは独自のデータソースを統合してテスト評価を行うことができます。

### 作者
**FENGSHUO LIU** ([@Adkid-Zephyr](https://github.com/Adkid-Zephyr))

### 謝辞
- **Kris77z** ([@Kris77z](https://github.com/Kris77z)) — CI/CDパイプライン設定とデプロイサポート
- **AnnPoint 广州安点科技** — テストインフラとデータソースサポート

---

## 🤝 コントリビューション

これは個人ポートフォリオプロジェクトですが、以下を歓迎します：
- 🐛 バグレポートとIssue議論
- 💡 機能提案とロードマップフィードバック
- 📖 ドキュメント改善
- 🔀 バグ修正のPull Request

Issueを開くかDiscussionを始めてください！

---

<div align="center">

**リサーチ自動化はオープンでアクセス可能であるべきと信じるquant-turned-developerによって构建 ❤️**

[⬆ トップに戻る](#金融リサーチエージェント)

</div>