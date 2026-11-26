<div align="center">

# 🐞 BugScout

**让你的 AI 去抓 Bug —— 安全、在 Docker 中运行、有据可查。**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · **中文** · [日本語](README.ja.md) · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

---

## 为什么需要它

让 AI 代理“测试我的代码”，通常会出现三种结果之一：在你的机器上运行不可信代码；忘记已经试过什么而不断重复；或者把一个不稳定的测试当成“Bug”上报。BugScout 补上的正是这块缺失的基础设施：

| 单独使用代理的问题 | BugScout 的做法 |
|---|---|
| 在你的笔记本上执行目标代码 | 所有运行目标代码的操作都在受限的 **Docker** 沙箱中进行（无网络、移除权限、限制 CPU 与内存） |
| 没有记忆，反复做同样的事 | Postgres 中的**资产图**和只追加的**探索树**；重复的测试想法会返回已有节点 |
| 为了“看看会怎样”而调用 `DELETE /users` | **服务端防护**：范围、破坏性操作、预算、卡住检测，以及严重 Bug 的人工确认 |
| 把不稳定的失败当作 Bug 上报 | 失败会**先重跑再计数**；无法复现的标记为 `flaky`，同一个 Bug 发现 20 次也只算一条结果 |

> [!NOTE]
> 由你（确切地说是 LLM 宿主：Claude Code、Codex）负责规划，BugScout 负责存储、执行、检查和强制执行规则。

## 它做什么

* **映射**：把 Python 包或 OpenAPI 规范转成函数、类、端点及其关系的图。
* **静态阶段：**复杂度（radon）、代码风格（ruff）、类型（mypy）、安全（bandit）、复制粘贴检测、死代码（vulture）。
* **动态阶段：**pytest、Hypothesis 属性测试、schemathesis、手写 HTTP 请求和自定义规则。
* **判定准则（oracle）：**崩溃 / HTTP 5xx、响应 schema、与上一个 git 提交的行为差异、你自己的不变量。
* **质量：**按函数和按测试的覆盖率、变异得分、不稳定测试与重复测试检测。
* **性能：**经验时间复杂度（O(n²) 对比允许的 O(n log n)）、提交间的性能回归、CPU 热点、内存大户、API 剖析。
* **报告：**去重后的结果：Bug、静态问题、覆盖率、热点、回归。

42 tools · 7 read-only resources (`run://{id}/…`) · 3 prompts (`testing_loop`, `write_charter`, `triage_bug`)

## 工作原理

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. 宿主发送一份**章程（charter）**：目标、范围、判定准则、规则、预算。
2. 按 `testing_loop` 提示词的循环工作：建图 → 静态阶段 → 运行测试 → 检查判定 → 记录 Bug → 性能 → 报告。
3. 每个会执行代码的调用都会先经过防护。**升级（escalation）**只暂停自己的分支，宿主继续处理其他分支。
4. `record_bug` 会重跑复现步骤、计算指纹并去重。高危和严重级别的 Bug 需要人工确认。

## 快速开始

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## 使用方法

**Claude Code** —— 仓库根目录的 `.mcp.json`（已包含）：

```json
{ "mcpServers": { "bugscout": { "command": "uv", "args": ["run", "bugscout"],
  "env": { "DATABASE_URL": "postgresql://test:test@localhost:5432/bugscout" } } } }
```

**Codex** —— `~/.codex/config.toml`：

```toml
[mcp_servers.bugscout]
command = "uv"
args = ["run", "--directory", "/path/to/bugscout", "bugscout"]
env = { DATABASE_URL = "postgresql://test:test@localhost:5432/bugscout" }
```

然后对你的代理说：*“使用 bugscout 的 `testing_loop` 提示词，测试 `./my_project`。”*（`write_charter` 可帮你一起编写章程。）

一份最小章程：

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

可以在 [`examples/`](../../examples) 中带有预埋 Bug 的示例上试用（`sample_lib`、`sample_api`）。

## 安全防护

| 防护 | 行为 |
|---|---|
| 范围 | 目标超出 `scope.include/exclude`，或主机不在 `allowed_hosts` 中，会返回 `escalation_required` |
| 破坏性操作 | `DELETE/PUT/PATCH` 和有风险的 `POST` 在发送前先升级；schemathesis 会跳过它们并说明 |
| 预算 | 步数、请求数、分钟数；达到 90% 警告，100% 强制停止 |
| 卡住 | 在一段步数窗口内没有新发现会触发一次升级 |
| 严重 Bug | `high` / `critical` 需要 `answer_escalation` 之后才算确认 |

## 已验证的内容

> [!WARNING]
> 各阶段的详细表格见 [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified)。

* 自动化：39 个测试，使用真实的 Postgres 和 Docker 容器，其中包括通过 stdio 由脚本化宿主驱动的端到端测试，能找到两个示例中所有预埋的 Bug。
* 一次真实的 Claude Code 会话（`claude -p` 按 `testing_loop` 执行）以约 0.22 美元找到了 `sample_api` 中两个预埋的 Bug。尚未实测：`sample_lib` 和 Codex。 ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## 文档

[`docs/REFERENCE.md`](../REFERENCE.md)：工具、章程字段、沙箱 · [`examples/`](../../examples)：预埋 Bug · [`ci.yml`](../../.github/workflows/ci.yml)：CI。

## 参与贡献

欢迎提交 Issue 和 PR。快速测试用 `uv run pytest -m "not docker"`；沙箱、判定和性能测试用 `uv run pytest -m docker`（一次一个文件，在空闲机器上）。

## 许可证

[Apache 2.0 许可证](../../LICENSE)。

## Star 历史

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>
