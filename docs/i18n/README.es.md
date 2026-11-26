<div align="center">

# 🐞 BugScout

**Deja que tu IA cace bugs — de forma segura, en Docker y con pruebas.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · **Español** · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [中文](README.zh.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

---

## Por qué lo necesitas

Cuando le pides a un agente de IA que «pruebe mi código», suele pasar una de tres cosas: ejecuta código no confiable en tu máquina, olvida lo que ya probó y se repite, o informa de un «bug» que era una prueba inestable. BugScout es la pieza que faltaba:

| Problema de un agente a secas | Qué hace BugScout |
|---|---|
| Ejecuta el código objetivo en tu portátil | Todo lo que ejecuta código objetivo corre en un sandbox **Docker** restringido (sin red, sin capacidades, con límites de CPU y memoria) |
| No tiene memoria y se repite | Un **grafo de activos** y un **árbol de exploración** de solo añadir en Postgres; una idea duplicada devuelve el nodo existente |
| Lanza `DELETE /users` «para ver qué pasa» | **Salvaguardas en el servidor**: alcance, acciones destructivas, presupuesto, detección de bloqueo y confirmación humana para bugs graves |
| Informa de fallos inestables como bugs | Un fallo se **vuelve a ejecutar antes de contar**; si no se reproduce queda como `flaky`, y el mismo bug hallado 20 veces es un solo hallazgo |

> [!NOTE]
> Tú (o más bien el host LLM: Claude Code, Codex) planificas. BugScout almacena, ejecuta, comprueba y hace cumplir las reglas.

## Qué hace

* **Mapea** un paquete Python o una especificación OpenAPI en un grafo de funciones, clases, endpoints y sus relaciones.
* **Etapa estática:** complejidad (radon), lint (ruff), tipos (mypy), seguridad (bandit), código copiado y código muerto (vulture).
* **Etapa dinámica:** pytest, pruebas de propiedades con Hypothesis, schemathesis, peticiones HTTP manuales y reglas propias.
* **Oráculos:** caída / HTTP 5xx, esquema de la respuesta, diferencia de comportamiento con el commit anterior, tus invariantes.
* **Calidad:** cobertura por función y por prueba, puntuación de mutación, detección de pruebas inestables y duplicadas.
* **Seguridad:** bandit, secretos en el código y el historial git, dependencias vulnerables y sondas activas de inyección, autorización rota y CORS/cabeceras, dentro del alcance y el presupuesto.
* **Rendimiento:** complejidad temporal empírica (O(n²) frente al O(n log n) permitido), regresiones entre commits, puntos calientes de CPU, memoria y perfilado de API.
* **Informa** del resultado sin duplicados: bugs, problemas estáticos, cobertura, puntos calientes, regresiones.

47 tools · 7 read-only resources (`run://{id}/…`) · 3 prompts (`testing_loop`, `write_charter`, `triage_bug`)

## Subagentes especializados

BugScout incluye nueve subagentes de Claude Code en [`.claude/agents/`](../../.claude/agents). Cada uno se encarga de una fase del `testing_loop` y solo tiene las herramientas que esa fase necesita. Tu sesión principal los coordina y conserva `start_run`, `end_run` y toda escalada a una persona.

| Subagente | Función | Herramientas principales |
|---|---|---|
| [`bugscout-mapper`](../../.claude/agents/bugscout-mapper.md) | Mapea el objetivo y ordena qué probar | `scan_python_code`, `import_openapi`, `get_untested`, `get_frontier` |
| [`bugscout-static-auditor`](../../.claude/agents/bugscout-static-auditor.md) | Ejecuta los analizadores estáticos y conserva los hallazgos reales | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| [`bugscout-fuzzer`](../../.claude/agents/bugscout-fuzzer.md) | Hypothesis, schemathesis y sondas HTTP; reproduce fallos | `run_hypothesis`, `run_schemathesis`, `http_request`, `run_pytest`, `check_crash`, `check_schema`, `check_rule` |
| [`bugscout-diff-hunter`](../../.claude/agents/bugscout-diff-hunter.md) | Cambios de comportamiento y velocidad frente a una referencia git | `compare_with_git_version`, `compare_benchmark_with_git_version` |
| [`bugscout-perf-analyst`](../../.claude/agents/bugscout-perf-analyst.md) | Complejidad temporal, CPU, memoria, latencia de API | `measure_time_complexity`, `run_benchmark`, `profile_cpu`, `profile_memory`, `profile_api` |
| [`bugscout-quality-auditor`](../../.claude/agents/bugscout-quality-auditor.md) | Cobertura, mutación, pruebas inestables y duplicadas | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| [`bugscout-security-auditor`](../../.claude/agents/bugscout-security-auditor.md) | Defensivo y pasivo: bandit, secretos en el código y el historial git, dependencias vulnerables | `run_bandit`, `run_secrets_scan`, `run_pip_audit` |
| [`bugscout-red-team`](../../.claude/agents/bugscout-red-team.md) | Adversarial: sondas de inyección, autorización rota y endurecimiento contra la API en ejecución | `probe_injection`, `probe_authz`, `probe_http_hardening`, `http_request` |
| [`bugscout-triager`](../../.claude/agents/bugscout-triager.md) | Juzga los candidatos y es el único que registra bugs | `record_bug`, `fingerprint_bug`, `confirm_finding` |

> [!NOTE]
> Solo el triager puede llamar a `record_bug`; ningún subagente puede iniciar ni terminar una ejecución ni responder una escalada. Ejecuta como máximo dos agentes que ejecuten código a la vez y nunca mutación junto con rendimiento. Los subagentes son una función de Claude Code (Codex ignora `.claude/agents/`).

## Herramientas

| Grupo | Herramientas |
|---|---|
| Control de ejecución y grafo | `start_run`, `end_run`, `get_status`, `get_report`, `query_graph`, `get_untested`, `get_frontier`, `add_test_idea`, `update_result`, `write_test`, `get_escalations`, `answer_escalation`, `ask_human` |
| Mapeo | `scan_python_code`, `import_openapi` |
| Análisis estático | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| Pruebas dinámicas | `run_pytest`, `run_hypothesis`, `run_schemathesis`, `http_request` |
| Oráculos y diferencias | `check_crash`, `check_schema`, `check_rule`, `compare_with_git_version` |
| Calidad de las pruebas | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| Rendimiento | `measure_time_complexity`, `run_benchmark`, `compare_benchmark_with_git_version`, `profile_cpu`, `profile_memory`, `profile_api` |
| Informes de bugs | `fingerprint_bug`, `record_bug`, `confirm_finding` |
| Seguridad | `run_secrets_scan`, `run_pip_audit`, `probe_injection`, `probe_authz`, `probe_http_hardening` |

## Cómo funciona

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. El host envía una **carta** (charter): objetivo, alcance, oráculos, reglas y presupuesto.
2. Recorre el bucle del prompt `testing_loop`: mapa → etapa estática → pruebas → oráculos → registrar bugs → rendimiento → informe.
3. Toda llamada que ejecuta algo pasa antes por las salvaguardas. Una **escalada** pausa solo su rama; el host sigue con otras.
4. `record_bug` repite la reproducción, calcula la huella y deduplica. Los bugs altos y críticos esperan a una persona.

## Inicio rápido

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## Uso

**Claude Code** — `.mcp.json` en la raíz del repositorio (ya incluido):

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

Luego dile a tu agente: *«Usa el prompt `testing_loop` de bugscout y prueba `./my_project`»*. (`write_charter` te ayuda a redactar la carta.)

Una carta mínima:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

Pruébalo con los ejemplos con bugs plantados en [`examples/`](../../examples) (`sample_lib`, `sample_api`).

## Salvaguardas

| Salvaguarda | Comportamiento |
|---|---|
| Alcance | Un objetivo fuera de `scope.include/exclude` o un host fuera de `allowed_hosts` devuelve `escalation_required` |
| Destructivas | `DELETE/PUT/PATCH` y los `POST` arriesgados escalan antes de enviar nada; schemathesis los omite y lo indica |
| Presupuesto | Pasos, peticiones, minutos; aviso al 90 %, parada total al 100 % |
| Bloqueo | Sin hallazgos nuevos durante una ventana de pasos se genera una escalada |
| Bug grave | `high` / `critical` necesitan `answer_escalation` antes de contar como confirmados |

## Qué se verificó

> [!WARNING]
> Consulta [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified) para la tabla por fase.

* Automático: 39 pruebas con Postgres y contenedores Docker reales, incluido un e2e con host guionizado sobre stdio que halla todos los bugs plantados.
* Una sesión real de Claude Code (`claude -p` siguiendo `testing_loop`) halló los dos bugs plantados en `sample_api` por unos 0,22 $. Aún sin probar en vivo: `sample_lib` y Codex. ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## Documentación

[`docs/REFERENCE.md`](../REFERENCE.md): herramientas, campos de la carta, sandbox · [`examples/`](../../examples): bugs plantados · [`ci.yml`](../../.github/workflows/ci.yml): CI.

## Contribuir

Se aceptan issues y PRs. `uv run pytest -m "not docker"` para la suite rápida y `uv run pytest -m docker` (un archivo cada vez, en una máquina libre) para sandbox, oráculos y rendimiento.

## Licencia

[Licencia Apache 2.0](../../LICENSE).

## Historial de estrellas

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>
