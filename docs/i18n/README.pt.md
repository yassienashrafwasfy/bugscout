<div align="center">

# 🐞 BugScout

**Deixe sua IA caçar bugs — com segurança, no Docker, com provas.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · **Português** · [中文](README.zh.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

---

## Por que você precisa disto

Quando você pede a um agente de IA para «testar meu código», o resultado costuma ser um destes três: ele executa código não confiável na sua máquina, esquece o que já tentou e se repete, ou relata um «bug» que era só um teste instável. O BugScout é a peça que faltava:

| Problema de um agente sozinho | O que o BugScout faz |
|---|---|
| Executa o código-alvo no seu notebook | Tudo que executa código-alvo roda num sandbox **Docker** restrito (sem rede, capacidades removidas, limites de CPU e memória) |
| Não tem memória e se repete | Um **grafo de ativos** e uma **árvore de exploração** somente de acréscimo no Postgres; uma ideia duplicada devolve o nó existente |
| Dispara `DELETE /users` «para ver o que acontece» | **Proteções no servidor**: escopo, ações destrutivas, orçamento, detecção de travamento e confirmação humana para bugs graves |
| Relata falhas instáveis como bugs | Toda falha é **reexecutada antes de contar**; se não reproduz, vira `flaky`, e o mesmo bug achado 20 vezes é um único achado |

> [!NOTE]
> Você (ou melhor, o host LLM: Claude Code, Codex) planeja. O BugScout armazena, executa, verifica e impõe as regras.

## O que faz

* **Mapeia** um pacote Python ou uma especificação OpenAPI em um grafo de funções, classes, endpoints e relações.
* **Etapa estática:** complexidade (radon), lint (ruff), tipos (mypy), segurança (bandit), copia-e-cola e código morto (vulture).
* **Etapa dinâmica:** pytest, testes de propriedade com Hypothesis, schemathesis, requisições HTTP manuais e regras próprias.
* **Oráculos:** falha / HTTP 5xx, esquema da resposta, diferença de comportamento em relação ao commit anterior, suas invariantes.
* **Qualidade:** cobertura por função e por teste, pontuação de mutação, detecção de testes instáveis e duplicados.
* **Desempenho:** complexidade de tempo empírica (O(n²) contra O(n log n) permitido), regressões entre commits, pontos quentes de CPU, memória e perfil de API.
* **Relata** o resultado sem duplicatas: bugs, problemas estáticos, cobertura, pontos quentes, regressões.

42 tools · 7 read-only resources (`run://{id}/…`) · 3 prompts (`testing_loop`, `write_charter`, `triage_bug`)

## Subagentes especializados

O BugScout inclui sete subagentes do Claude Code em [`.claude/agents/`](../../.claude/agents). Cada um cuida de uma fase do `testing_loop` e tem só as ferramentas que ela precisa. Sua sessão principal os coordena e mantém `start_run`, `end_run` e toda escalada para uma pessoa.

| Subagente | Função | Principais ferramentas |
|---|---|---|
| [`bugscout-mapper`](../../.claude/agents/bugscout-mapper.md) | Mapeia o alvo e ordena o que testar | `scan_python_code`, `import_openapi`, `get_untested`, `get_frontier` |
| [`bugscout-static-auditor`](../../.claude/agents/bugscout-static-auditor.md) | Roda os analisadores estáticos e mantém os achados reais | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| [`bugscout-fuzzer`](../../.claude/agents/bugscout-fuzzer.md) | Hypothesis, schemathesis e sondas HTTP; reproduz falhas | `run_hypothesis`, `run_schemathesis`, `http_request`, `run_pytest`, `check_crash`, `check_schema`, `check_rule` |
| [`bugscout-diff-hunter`](../../.claude/agents/bugscout-diff-hunter.md) | Mudanças de comportamento e velocidade contra uma referência git | `compare_with_git_version`, `compare_benchmark_with_git_version` |
| [`bugscout-perf-analyst`](../../.claude/agents/bugscout-perf-analyst.md) | Complexidade de tempo, CPU, memória, latência da API | `measure_time_complexity`, `run_benchmark`, `profile_cpu`, `profile_memory`, `profile_api` |
| [`bugscout-quality-auditor`](../../.claude/agents/bugscout-quality-auditor.md) | Cobertura, mutação, testes instáveis e duplicados | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| [`bugscout-triager`](../../.claude/agents/bugscout-triager.md) | Julga os candidatos e é o único que registra bugs | `record_bug`, `fingerprint_bug`, `confirm_finding` |

> [!NOTE]
> Só o triager pode chamar `record_bug`; nenhum subagente pode iniciar ou encerrar uma execução nem responder a uma escalada. No máximo dois agentes que executam código ao mesmo tempo, e nunca mutação junto com desempenho. Subagentes são um recurso do Claude Code (o Codex ignora `.claude/agents/`).

## Ferramentas

| Grupo | Ferramentas |
|---|---|
| Controle da execução e grafo | `start_run`, `end_run`, `get_status`, `get_report`, `query_graph`, `get_untested`, `get_frontier`, `add_test_idea`, `update_result`, `write_test`, `get_escalations`, `answer_escalation`, `ask_human` |
| Mapeamento | `scan_python_code`, `import_openapi` |
| Análise estática | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| Testes dinâmicos | `run_pytest`, `run_hypothesis`, `run_schemathesis`, `http_request` |
| Oráculos e diferenças | `check_crash`, `check_schema`, `check_rule`, `compare_with_git_version` |
| Qualidade dos testes | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| Desempenho | `measure_time_complexity`, `run_benchmark`, `compare_benchmark_with_git_version`, `profile_cpu`, `profile_memory`, `profile_api` |
| Relatórios de bugs | `fingerprint_bug`, `record_bug`, `confirm_finding` |

## Como funciona

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. O host envia uma **carta** (charter): alvo, escopo, oráculos, regras e orçamento.
2. Segue o laço do prompt `testing_loop`: mapa → estático → testes → oráculos → registrar bugs → desempenho → relatório.
3. Toda chamada que executa algo passa antes pelas proteções. Uma **escalada** pausa só o seu ramo; o host segue em outro.
4. `record_bug` repete a reprodução, calcula a impressão digital e deduplica. Bugs altos e críticos esperam por uma pessoa.

## Início rápido

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## Uso

**Claude Code** — `.mcp.json` na raiz do repositório (já incluído):

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

Depois diga ao seu agente: *«Use o prompt `testing_loop` do bugscout e teste `./my_project`»*. (`write_charter` ajuda a montar a carta.)

Uma carta mínima:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

Experimente nos exemplos com bugs plantados em [`examples/`](../../examples) (`sample_lib`, `sample_api`).

## Proteções

| Proteção | Comportamento |
|---|---|
| Escopo | Alvo fora de `scope.include/exclude` ou host fora de `allowed_hosts` devolve `escalation_required` |
| Destrutivas | `DELETE/PUT/PATCH` e `POST`s arriscados escalam antes de enviar qualquer coisa; o schemathesis os pula e avisa |
| Orçamento | Passos, requisições, minutos; aviso aos 90 %, parada total aos 100 % |
| Travamento | Sem achados novos numa janela de passos gera uma escalada |
| Bug grave | `high` / `critical` precisam de `answer_escalation` antes de contar como confirmados |

## O que foi verificado

> [!WARNING]
> Veja [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified) para a tabela por fase.

* Automático: 39 testes com Postgres e contêineres Docker reais, incluindo um e2e com host roteirizado via stdio que encontra todos os bugs plantados.
* Uma sessão real do Claude Code (`claude -p` seguindo `testing_loop`) achou os dois bugs plantados em `sample_api` por cerca de US$ 0,22. Ainda sem teste ao vivo: `sample_lib` e Codex. ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## Documentação

[`docs/REFERENCE.md`](../REFERENCE.md): ferramentas, campos da carta, sandbox · [`examples/`](../../examples): bugs plantados · [`ci.yml`](../../.github/workflows/ci.yml): CI.

## Contribuir

Issues e PRs são bem-vindos. `uv run pytest -m "not docker"` para a suíte rápida e `uv run pytest -m docker` (um arquivo por vez, numa máquina ociosa) para sandbox, oráculos e desempenho.

## Licença

[Licença Apache 2.0](../../LICENSE).

## Histórico de estrelas

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>
