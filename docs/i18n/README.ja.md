<div align="center">

# 🐞 BugScout

**AI にバグを狩らせよう — 安全に、Docker の中で、証拠つきで。**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [中文](README.zh.md) · **日本語** · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

---

## なぜ必要か

AI エージェントに「私のコードをテストして」と頼むと、たいてい次のいずれかになります。信頼できないコードをあなたのマシンで実行する、すでに試したことを忘れて同じことを繰り返す、不安定なテストを「バグ」として報告する。BugScout はその欠けていた土台です。

| エージェント単体の問題 | BugScout の対処 |
|---|---|
| 対象コードをノート PC 上で実行する | 対象コードを実行するものはすべて、制限された **Docker** サンドボックス内で動きます（ネットワークなし、権限削除、CPU／メモリ制限） |
| 記憶がなく同じことを繰り返す | Postgres 上の**アセットグラフ**と追記専用の**探索ツリー**。重複したアイデアは既存ノードを返します |
| 「どうなるか見る」ために `DELETE /users` を叩く | **サーバー側ガード**：スコープ、破壊的操作、予算、行き詰まり検知、重大バグの人手確認 |
| 不安定な失敗をバグとして報告する | 失敗は**数える前に再実行**されます。再現しなければ `flaky`、同じバグが 20 回見つかっても 1 件です |

> [!NOTE]
> 計画はあなた（正確には LLM ホストの Claude Code や Codex）が行い、BugScout は保存・実行・検証・ルールの強制を担当します。

## 何をするか

* **マッピング**：Python パッケージや OpenAPI 仕様を、関数・クラス・エンドポイントとその関係のグラフにします。
* **静的ステージ：**複雑度（radon）、lint（ruff）、型（mypy）、セキュリティ（bandit）、コピペ、デッドコード（vulture）。
* **動的ステージ：**pytest、Hypothesis のプロパティテスト、schemathesis、手動の HTTP リクエスト、独自ルール。
* **オラクル：**クラッシュ / HTTP 5xx、レスポンススキーマ、直前の git コミットとの挙動差分、あなた自身の不変条件。
* **品質：**関数別・テスト別カバレッジ、ミューテーションスコア、不安定テストと重複テストの検出。
* **パフォーマンス：**経験的な時間計算量（許容 O(n log n) に対する O(n²)）、コミット間の性能劣化、CPU ホットスポット、メモリ消費、API プロファイル。
* **レポート：**重複を除いた結果（バグ、静的な問題、カバレッジ、ホットスポット、リグレッション）。

42 tools · 7 read-only resources (`run://{id}/…`) · 3 prompts (`testing_loop`, `write_charter`, `triage_bug`)

## 仕組み

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. ホストが**チャーター**（対象、スコープ、オラクル、ルール、予算）を送ります。
2. `testing_loop` プロンプトのループに従います：マップ → 静的 → テスト → オラクル → バグ記録 → 性能 → レポート。
3. 実行を伴う呼び出しは必ず先にガードを通ります。**エスカレーション**は自分のブランチだけを止め、ホストは他の作業を続けます。
4. `record_bug` は再現手順を再実行し、フィンガープリントを作って重複を排除します。high と critical は人の確認待ちになります。

## クイックスタート

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## 使い方

**Claude Code** — リポジトリ直下の `.mcp.json`（同梱済み）：

```json
{ "mcpServers": { "bugscout": { "command": "uv", "args": ["run", "bugscout"],
  "env": { "DATABASE_URL": "postgresql://test:test@localhost:5432/bugscout" } } } }
```

**Codex** — `~/.codex/config.toml`：

```toml
[mcp_servers.bugscout]
command = "uv"
args = ["run", "--directory", "/path/to/bugscout", "bugscout"]
env = { DATABASE_URL = "postgresql://test:test@localhost:5432/bugscout" }
```

その後、エージェントにこう伝えます：*「bugscout の `testing_loop` プロンプトを使って `./my_project` をテストして」*（`write_charter` でチャーター作成を手伝わせられます。）

最小のチャーター：

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

バグを仕込んだサンプル [`examples/`](../../examples)（`sample_lib`、`sample_api`）で試せます。

## ガードレール

| ガード | 挙動 |
|---|---|
| スコープ | `scope.include/exclude` 外の対象や `allowed_hosts` 外のホストは `escalation_required` を返します |
| 破壊的操作 | `DELETE/PUT/PATCH` と危険な `POST` は送信前にエスカレーション。schemathesis はそれらをスキップして明示します |
| 予算 | ステップ・リクエスト・分。90% で警告、100% で強制停止 |
| 行き詰まり | 一定ステップの間に新しい発見がなければ 1 回エスカレーションします |
| 重大バグ | `high` / `critical` は `answer_escalation` を経て初めて確定扱いになります |

## 検証したこと

> [!WARNING]
> フェーズ別の詳しい表は [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified) を参照してください。

* 自動テスト：実際の Postgres と Docker コンテナを使う 39 件。stdio 経由でスクリプト化したホストが両サンプルの仕込みバグをすべて見つける E2E を含みます。
* 実際の Claude Code セッション（`testing_loop` に従う `claude -p`）が、約 0.22 ドルで `sample_api` の仕込みバグ 2 件を見つけました。未実施：`sample_lib` と Codex の実機テスト。 ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## ドキュメント

[`docs/REFERENCE.md`](../REFERENCE.md)：ツール、チャーター項目、サンドボックス · [`examples/`](../../examples)：仕込みバグ · [`ci.yml`](../../.github/workflows/ci.yml)：CI。

## コントリビュート

Issue と PR を歓迎します。高速なテストは `uv run pytest -m "not docker"`、サンドボックス・オラクル・性能テストは `uv run pytest -m docker`（1 ファイルずつ、負荷のないマシンで）。

## ライセンス

[Apache License 2.0](../../LICENSE)。

## スター履歴

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>
