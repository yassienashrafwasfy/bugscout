<div align="center">

# 🐞 BugScout

**Пусть ваш ИИ охотится на баги — безопасно, в Docker, с доказательствами.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [中文](README.zh.md) · [日本語](README.ja.md) · **Русский** · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

---

## Зачем это нужно

Когда вы просите ИИ-агента «протестировать мой код», обычно получается одно из трёх: он запускает недоверенный код на вашей машине, забывает, что уже пробовал, и повторяется, либо сообщает о «баге», который был просто нестабильным тестом. BugScout — недостающая основа:

| Проблема голого агента | Что делает BugScout |
|---|---|
| Запускает целевой код на вашем ноутбуке | Всё, что исполняет целевой код, работает в закрытой **Docker**-песочнице (без сети, без привилегий, с лимитами CPU и памяти) |
| Не помнит и повторяется | **Граф активов** и **дерево исследования** только на добавление в Postgres; дублирующаяся идея возвращает существующий узел |
| Вызывает `DELETE /users` «посмотреть, что будет» | **Серверные ограничения**: область, разрушительные действия, бюджет, обнаружение зависания, подтверждение человеком для серьёзных багов |
| Выдаёт нестабильные падения за баги | Падение **перезапускается, прежде чем засчитаться**; не воспроизвелось — станет `flaky`, а один и тот же баг, найденный 20 раз, — это одна находка |

> [!NOTE]
> Планируете вы (точнее, LLM-хост: Claude Code, Codex). BugScout хранит, исполняет, проверяет и принудительно соблюдает правила.

## Что делает

* **Строит карту** Python-пакета или спецификации OpenAPI: граф функций, классов, эндпоинтов и связей.
* **Статический этап:** сложность (radon), линтер (ruff), типы (mypy), безопасность (bandit), копипаст и мёртвый код (vulture).
* **Динамический этап:** pytest, property-тесты Hypothesis, schemathesis, ручные HTTP-запросы и собственные правила.
* **Оракулы:** падение / HTTP 5xx, схема ответа, разница в поведении с предыдущим коммитом, ваши инварианты.
* **Качество:** покрытие по функциям и по тестам, мутационный балл, поиск нестабильных и дублирующихся тестов.
* **Производительность:** эмпирическая временная сложность (O(n²) против допустимого O(n log n)), регрессии между коммитами, горячие точки CPU, память, профилирование API.
* **Отчёт** без дубликатов: баги, статические проблемы, покрытие, горячие точки, регрессии.

42 tools · 7 read-only resources (`run://{id}/…`) · 3 prompts (`testing_loop`, `write_charter`, `triage_bug`)

## Как работает

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. Хост отправляет **хартию** (charter): цель, область, оракулы, правила, бюджет.
2. Он идёт по циклу промпта `testing_loop`: карта → статика → тесты → оракулы → запись багов → производительность → отчёт.
3. Каждый вызов, что-то исполняющий, сначала проходит защитные механизмы. **Эскалация** приостанавливает только свою ветку; хост продолжает в другой.
4. `record_bug` повторно запускает воспроизведение, считает отпечаток и убирает дубли. Высокие и критические баги ждут человека.

## Быстрый старт

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## Использование

**Claude Code** — `.mcp.json` в корне репозитория (уже есть):

```json
{ "mcpServers": { "bugscout": { "command": "uv", "args": ["run", "bugscout"],
  "env": { "DATABASE_URL": "postgresql://test:test@localhost:5432/bugscout" } } } }
```

**Codex** — `~/.codex/config.toml`:

```toml
[mcp_servers.bugscout]
command = "uv"
args = ["run", "--directory", "/path/to/bugscout", "bugscout"]
env = { DATABASE_URL = "postgresql://test:test@localhost:5432/bugscout" }
```

Затем скажите агенту: *«Используй промпт `testing_loop` из bugscout и протестируй `./my_project`»*. (`write_charter` поможет составить хартию.)

Минимальная хартия:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

Попробуйте на примерах с заложенными багами в [`examples/`](../../examples) (`sample_lib`, `sample_api`).

## Защитные механизмы

| Механизм | Поведение |
|---|---|
| Область | Цель вне `scope.include/exclude` или хост вне `allowed_hosts` возвращает `escalation_required` |
| Разрушительные | `DELETE/PUT/PATCH` и рискованные `POST` эскалируются до отправки; schemathesis их пропускает и сообщает об этом |
| Бюджет | Шаги, запросы, минуты; предупреждение на 90 %, жёсткая остановка на 100 % |
| Зависание | Отсутствие новых находок в окне шагов вызывает одну эскалацию |
| Серьёзный баг | `high` / `critical` требуют `answer_escalation`, прежде чем считаться подтверждёнными |

## Что проверено

> [!WARNING]
> Таблица по фазам — в [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified).

* Автоматически: 39 тестов с настоящим Postgres и настоящими Docker-контейнерами, включая e2e со скриптовым хостом через stdio, который находит все заложенные баги в обоих примерах.
* Настоящая сессия Claude Code (`claude -p` по `testing_loop`) нашла оба заложенных бага в `sample_api` примерно за 0,22 $. Вживую ещё не проверялись: `sample_lib` и Codex. ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## Документация

[`docs/REFERENCE.md`](../REFERENCE.md): инструменты, поля хартии, песочница · [`examples/`](../../examples): заложенные баги · [`ci.yml`](../../.github/workflows/ci.yml): CI.

## Участие

Issues и PR приветствуются. `uv run pytest -m "not docker"` — быстрый набор, `uv run pytest -m docker` (по одному файлу, на свободной машине) — песочница, оракулы и производительность.

## Лицензия

[Лицензия Apache 2.0](../../LICENSE).

## История звёзд

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>
