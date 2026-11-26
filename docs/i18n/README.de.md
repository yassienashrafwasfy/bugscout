<div align="center">

# 🐞 BugScout

**Lass deine KI Bugs jagen — sicher, in Docker, mit Belegen.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · [Français](README.fr.md) · **Deutsch** · [Português](README.pt.md) · [中文](README.zh.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

---

## Warum du das brauchst

Wenn man einen KI-Agenten bittet, „meinen Code zu testen“, endet das meist auf eine von drei Arten: Er führt nicht vertrauenswürdigen Code auf deinem Rechner aus, vergisst, was er schon probiert hat, und wiederholt sich, oder er meldet einen „Bug“, der nur ein instabiler Test war. BugScout ist das fehlende Stück:

| Problem mit einem bloßen Agenten | Was BugScout dagegen tut |
|---|---|
| Er führt Zielcode auf deinem Laptop aus | Alles, was Zielcode ausführt, läuft in einer abgeriegelten **Docker**-Sandbox (kein Netzwerk, entzogene Capabilities, CPU-/Speicherlimits) |
| Er hat kein Gedächtnis und wiederholt sich | Ein **Asset-Graph** und ein nur anhängbarer **Explorationsbaum** in Postgres; eine doppelte Idee liefert den vorhandenen Knoten |
| Er ruft `DELETE /users` auf, „um zu sehen, was passiert“ | **Serverseitige Schutzmechanismen**: Scope, destruktive Aktionen, Budget, Stuck-Erkennung, menschliche Bestätigung bei schweren Bugs |
| Er meldet instabile Fehlschläge als Bugs | Ein Fehlschlag wird **erneut ausgeführt, bevor er zählt**; reproduziert er nicht, wird er `flaky`, und derselbe Bug, 20-mal gefunden, ist ein einziger Fund |

> [!NOTE]
> Du (genauer: der LLM-Host Claude Code oder Codex) planst. BugScout speichert, führt aus, prüft und setzt Regeln durch.

## Was es tut

* **Kartiert** ein Python-Paket oder eine OpenAPI-Spezifikation als Graph aus Funktionen, Klassen, Endpunkten und Beziehungen.
* **Statische Stufe:** Komplexität (radon), Lint (ruff), Typen (mypy), Sicherheit (bandit), Copy-Paste und toter Code (vulture).
* **Dynamische Stufe:** pytest, Hypothesis-Property-Tests, schemathesis, handgemachte HTTP-Anfragen und eigene Regeln.
* **Orakel:** Absturz / HTTP 5xx, Antwortschema, Verhaltensdifferenz zum vorherigen Commit, deine eigenen Invarianten.
* **Qualität:** Abdeckung pro Funktion und Test, Mutationsscore, Erkennung instabiler und doppelter Tests.
* **Sicherheit:** bandit, fest eingebaute Geheimnisse (Code und Git-Verlauf), verwundbare Abhängigkeiten sowie aktive Proben auf Injection, kaputte Autorisierung und CORS/Header, innerhalb von Scope und Budget.
* **Performance:** empirische Zeitkomplexität (O(n²) gegen erlaubtes O(n log n)), Regressionen zwischen Commits, CPU-Hotspots, Speicherfresser, API-Profiling.
* **Berichtet** das deduplizierte Ergebnis: Bugs, statische Probleme, Abdeckung, Hotspots, Regressionen.

47 tools · 7 read-only resources (`run://{id}/…`) · 3 prompts (`testing_loop`, `write_charter`, `triage_bug`)

## Spezialisierte Subagenten

BugScout liefert neun Claude-Code-Subagenten in [`.claude/agents/`](../../.claude/agents) mit. Jeder ist für eine Phase des `testing_loop` zuständig und erhält nur die dafür nötigen Werkzeuge. Deine Hauptsitzung koordiniert sie und behält `start_run`, `end_run` und jede Eskalation an Menschen.

| Subagent | Rolle | Wichtigste Werkzeuge |
|---|---|---|
| [`bugscout-mapper`](../../.claude/agents/bugscout-mapper.md) | Kartiert das Ziel und priorisiert, was getestet wird | `scan_python_code`, `import_openapi`, `get_untested`, `get_frontier` |
| [`bugscout-static-auditor`](../../.claude/agents/bugscout-static-auditor.md) | Führt die statischen Analysatoren aus und behält die echten Funde | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| [`bugscout-fuzzer`](../../.claude/agents/bugscout-fuzzer.md) | Hypothesis, schemathesis und HTTP-Proben; reproduziert Fehler | `run_hypothesis`, `run_schemathesis`, `http_request`, `run_pytest`, `check_crash`, `check_schema`, `check_rule` |
| [`bugscout-diff-hunter`](../../.claude/agents/bugscout-diff-hunter.md) | Verhaltens- und Tempoänderungen gegenüber einer älteren Git-Referenz | `compare_with_git_version`, `compare_benchmark_with_git_version` |
| [`bugscout-perf-analyst`](../../.claude/agents/bugscout-perf-analyst.md) | Zeitkomplexität, CPU, Speicher, API-Latenz | `measure_time_complexity`, `run_benchmark`, `profile_cpu`, `profile_memory`, `profile_api` |
| [`bugscout-quality-auditor`](../../.claude/agents/bugscout-quality-auditor.md) | Abdeckung, Mutation, instabile und doppelte Tests | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| [`bugscout-security-auditor`](../../.claude/agents/bugscout-security-auditor.md) | Defensiv und passiv: bandit, Geheimnisse in Code und Git-Verlauf, verwundbare Abhängigkeiten | `run_bandit`, `run_secrets_scan`, `run_pip_audit` |
| [`bugscout-red-team`](../../.claude/agents/bugscout-red-team.md) | Adversarial: Injection-, Autorisierungs- und Härtungs-Proben gegen die laufende API | `probe_injection`, `probe_authz`, `probe_http_hardening`, `http_request` |
| [`bugscout-triager`](../../.claude/agents/bugscout-triager.md) | Beurteilt Kandidaten und erfasst als Einziger Bugs | `record_bug`, `fingerprint_bug`, `confirm_finding` |

> [!NOTE]
> Nur der Triager darf `record_bug` aufrufen; kein Subagent kann einen Lauf starten oder beenden oder eine Eskalation beantworten. Höchstens zwei ausführende Agenten gleichzeitig und nie Mutation zusammen mit Performance. Subagenten sind ein Claude-Code-Feature (Codex ignoriert `.claude/agents/`).

## Werkzeuge

| Gruppe | Werkzeuge |
|---|---|
| Lauf-Steuerung und Graph | `start_run`, `end_run`, `get_status`, `get_report`, `query_graph`, `get_untested`, `get_frontier`, `add_test_idea`, `update_result`, `write_test`, `get_escalations`, `answer_escalation`, `ask_human` |
| Kartierung | `scan_python_code`, `import_openapi` |
| Statische Analyse | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| Dynamisches Testen | `run_pytest`, `run_hypothesis`, `run_schemathesis`, `http_request` |
| Orakel und Diffs | `check_crash`, `check_schema`, `check_rule`, `compare_with_git_version` |
| Testqualität | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| Performance | `measure_time_complexity`, `run_benchmark`, `compare_benchmark_with_git_version`, `profile_cpu`, `profile_memory`, `profile_api` |
| Bug-Berichte | `fingerprint_bug`, `record_bug`, `confirm_finding` |
| Sicherheit | `run_secrets_scan`, `run_pip_audit`, `probe_injection`, `probe_authz`, `probe_http_hardening` |

## Wie es funktioniert

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. Der Host sendet eine **Charta**: Ziel, Scope, Orakel, Regeln, Budget.
2. Er arbeitet die Schleife des Prompts `testing_loop` ab: Karte → statisch → Tests → Orakel → Bugs erfassen → Performance → Bericht.
3. Jeder ausführende Aufruf läuft zuerst durch die Schutzmechanismen. Eine **Eskalation** pausiert nur ihren eigenen Zweig; der Host macht anderswo weiter.
4. `record_bug` wiederholt die Reproduktion, bildet den Fingerabdruck und dedupliziert. Hohe und kritische Bugs warten auf einen Menschen.

## Schnellstart

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## Verwendung

**Claude Code** — `.mcp.json` im Repo-Root (liegt bereits bei):

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

Sag dann deinem Agenten: *„Nutze den Prompt `testing_loop` von bugscout und teste `./my_project`.“* (`write_charter` hilft beim Verfassen der Charta.)

Eine minimale Charta:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

Probiere es an den Beispielen mit eingebauten Bugs in [`examples/`](../../examples) (`sample_lib`, `sample_api`).

## Schutzmechanismen

| Schutz | Verhalten |
|---|---|
| Scope | Ein Ziel außerhalb von `scope.include/exclude` oder ein Host außerhalb von `allowed_hosts` liefert `escalation_required` |
| Destruktiv | `DELETE/PUT/PATCH` und riskante `POST`s eskalieren vor dem Senden; schemathesis überspringt sie und sagt es |
| Budget | Schritte, Anfragen, Minuten; Warnung bei 90 %, harter Stopp bei 100 % |
| Stuck | Keine neuen Funde über ein Schrittfenster löst eine Eskalation aus |
| Schwerer Bug | `high` / `critical` brauchen `answer_escalation`, bevor sie als bestätigt gelten |

## Was verifiziert wurde

> [!WARNING]
> Die Tabelle pro Phase steht in [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified).

* Automatisiert: 39 Tests gegen echtes Postgres und echte Docker-Container, darunter ein E2E mit geskriptetem Host über stdio, der alle eingebauten Bugs findet.
* Eine echte Claude-Code-Sitzung (`claude -p` mit `testing_loop`) fand beide eingebauten Bugs in `sample_api` für ca. 0,22 $. Noch nicht live getestet: `sample_lib` und Codex. ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## Dokumentation

[`docs/REFERENCE.md`](../REFERENCE.md): Tools, Charta-Felder, Sandbox · [`examples/`](../../examples): eingebaute Bugs · [`ci.yml`](../../.github/workflows/ci.yml): CI.

## Mitmachen

Issues und PRs sind willkommen. `uv run pytest -m "not docker"` für die schnelle Suite, `uv run pytest -m docker` (eine Datei nach der anderen, auf einem ruhigen Rechner) für Sandbox, Orakel und Performance.

## Lizenz

[Apache-2.0-Lizenz](../../LICENSE).

## Star-Verlauf

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>
