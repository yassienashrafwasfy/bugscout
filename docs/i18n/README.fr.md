<div align="center">

# 🐞 BugScout

**Laissez votre IA traquer les bugs — en sécurité, dans Docker, avec preuves.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · **Français** · [Deutsch](README.de.md) · [Português](README.pt.md) · [中文](README.zh.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

---

## Pourquoi en avez-vous besoin

Quand on demande à un agent IA de « tester mon code », cela finit souvent de trois façons : il exécute du code non fiable sur votre machine, il oublie ce qu'il a déjà essayé et se répète, ou il signale un « bug » qui n'était qu'un test instable. BugScout est la pièce manquante :

| Problème d'un agent seul | Ce que fait BugScout |
|---|---|
| Il exécute le code cible sur votre portable | Tout ce qui exécute du code cible tourne dans un bac à sable **Docker** verrouillé (pas de réseau, capacités retirées, limites CPU/mémoire) |
| Il n'a pas de mémoire et se répète | Un **graphe d'actifs** et un **arbre d'exploration** en ajout seul dans Postgres ; une idée en double renvoie le nœud existant |
| Il lance `DELETE /users` « pour voir » | **Garde-fous côté serveur** : périmètre, actions destructrices, budget, détection de blocage, confirmation humaine pour les bugs graves |
| Il signale des échecs instables comme des bugs | Un échec est **rejoué avant d'être compté** ; s'il ne se reproduit pas il devient `flaky`, et le même bug trouvé 20 fois n'est qu'un seul résultat |

> [!NOTE]
> Vous (ou plutôt l'hôte LLM : Claude Code, Codex) planifiez. BugScout stocke, exécute, vérifie et fait respecter les règles.

## Ce qu'il fait

* **Cartographie** un paquet Python ou une spécification OpenAPI en graphe de fonctions, classes, endpoints et relations.
* **Étape statique :** complexité (radon), lint (ruff), types (mypy), sécurité (bandit), copier-coller et code mort (vulture).
* **Étape dynamique :** pytest, tests de propriétés Hypothesis, schemathesis, requêtes HTTP manuelles et règles personnalisées.
* **Oracles :** plantage / HTTP 5xx, schéma de réponse, différence de comportement avec le commit précédent, vos invariants.
* **Qualité :** couverture par fonction et par test, score de mutation, détection des tests instables et en double.
* **Performance :** complexité temporelle empirique (O(n²) contre O(n log n) autorisé), régressions entre commits, points chauds CPU, mémoire, profilage d'API.
* **Rapporte** le résultat dédupliqué : bugs, problèmes statiques, couverture, points chauds, régressions.

42 tools · 7 read-only resources (`run://{id}/…`) · 3 prompts (`testing_loop`, `write_charter`, `triage_bug`)

## Sous-agents spécialisés

BugScout fournit sept sous-agents Claude Code dans [`.claude/agents/`](../../.claude/agents). Chacun prend en charge une phase du `testing_loop` avec uniquement les outils nécessaires. Votre session principale les coordonne et garde `start_run`, `end_run` et toute escalade vers un humain.

| Sous-agent | Rôle | Outils principaux |
|---|---|---|
| [`bugscout-mapper`](../../.claude/agents/bugscout-mapper.md) | Cartographie la cible et classe ce qu'il faut tester | `scan_python_code`, `import_openapi`, `get_untested`, `get_frontier` |
| [`bugscout-static-auditor`](../../.claude/agents/bugscout-static-auditor.md) | Lance les analyseurs statiques et garde les vrais résultats | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| [`bugscout-fuzzer`](../../.claude/agents/bugscout-fuzzer.md) | Hypothesis, schemathesis et sondes HTTP ; reproduit les échecs | `run_hypothesis`, `run_schemathesis`, `http_request`, `run_pytest`, `check_crash`, `check_schema`, `check_rule` |
| [`bugscout-diff-hunter`](../../.claude/agents/bugscout-diff-hunter.md) | Changements de comportement et de vitesse face à une référence git | `compare_with_git_version`, `compare_benchmark_with_git_version` |
| [`bugscout-perf-analyst`](../../.claude/agents/bugscout-perf-analyst.md) | Complexité temporelle, CPU, mémoire, latence d'API | `measure_time_complexity`, `run_benchmark`, `profile_cpu`, `profile_memory`, `profile_api` |
| [`bugscout-quality-auditor`](../../.claude/agents/bugscout-quality-auditor.md) | Couverture, mutation, tests instables et en double | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| [`bugscout-triager`](../../.claude/agents/bugscout-triager.md) | Juge les candidats et seul à enregistrer les bugs | `record_bug`, `fingerprint_bug`, `confirm_finding` |

> [!NOTE]
> Seul le triager peut appeler `record_bug` ; aucun sous-agent ne peut démarrer ou terminer un run ni répondre à une escalade. Deux agents exécutants au maximum en même temps, et jamais de mutation avec la performance. Les sous-agents sont une fonction de Claude Code (Codex ignore `.claude/agents/`).

## Outils

| Groupe | Outils |
|---|---|
| Pilotage du run et graphe | `start_run`, `end_run`, `get_status`, `get_report`, `query_graph`, `get_untested`, `get_frontier`, `add_test_idea`, `update_result`, `write_test`, `get_escalations`, `answer_escalation`, `ask_human` |
| Cartographie | `scan_python_code`, `import_openapi` |
| Analyse statique | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| Tests dynamiques | `run_pytest`, `run_hypothesis`, `run_schemathesis`, `http_request` |
| Oracles et différences | `check_crash`, `check_schema`, `check_rule`, `compare_with_git_version` |
| Qualité des tests | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| Performance | `measure_time_complexity`, `run_benchmark`, `compare_benchmark_with_git_version`, `profile_cpu`, `profile_memory`, `profile_api` |
| Rapports de bugs | `fingerprint_bug`, `record_bug`, `confirm_finding` |

## Comment ça marche

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. L'hôte envoie une **charte** : cible, périmètre, oracles, règles, budget.
2. Il suit la boucle du prompt `testing_loop` : carte → statique → tests → oracles → enregistrer les bugs → performance → rapport.
3. Tout appel qui exécute quelque chose passe d'abord par les garde-fous. Une **escalade** met en pause sa seule branche ; l'hôte continue ailleurs.
4. `record_bug` rejoue la reproduction, calcule l'empreinte et déduplique. Les bugs élevés et critiques attendent un humain.

## Démarrage rapide

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## Utilisation

**Claude Code** — `.mcp.json` à la racine du dépôt (déjà fourni) :

```json
{ "mcpServers": { "bugscout": { "command": "uv", "args": ["run", "bugscout"],
  "env": { "DATABASE_URL": "postgresql://test:test@localhost:5432/bugscout" } } } }
```

**Codex** — `~/.codex/config.toml` :

```toml
[mcp_servers.bugscout]
command = "uv"
args = ["run", "--directory", "/path/to/bugscout", "bugscout"]
env = { DATABASE_URL = "postgresql://test:test@localhost:5432/bugscout" }
```

Dites ensuite à votre agent : *« Utilise le prompt `testing_loop` de bugscout et teste `./my_project` »*. (`write_charter` aide à rédiger la charte.)

Une charte minimale :

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

Essayez-le sur les exemples à bugs plantés dans [`examples/`](../../examples) (`sample_lib`, `sample_api`).

## Garde-fous

| Garde-fou | Comportement |
|---|---|
| Périmètre | Une cible hors `scope.include/exclude` ou un hôte hors `allowed_hosts` renvoie `escalation_required` |
| Destructif | `DELETE/PUT/PATCH` et les `POST` risqués escaladent avant tout envoi ; schemathesis les saute et le dit |
| Budget | Étapes, requêtes, minutes ; alerte à 90 %, arrêt net à 100 % |
| Blocage | Aucun nouveau résultat sur une fenêtre d'étapes déclenche une escalade |
| Bug grave | `high` / `critical` exigent `answer_escalation` avant d'être confirmés |

## Ce qui a été vérifié

> [!WARNING]
> Voir [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified) pour le tableau par phase.

* Automatique : 39 tests avec Postgres et de vrais conteneurs Docker, dont un e2e à hôte scripté via stdio qui trouve tous les bugs plantés.
* Une vraie session Claude Code (`claude -p` suivant `testing_loop`) a trouvé les deux bugs plantés de `sample_api` pour environ 0,22 $. Pas encore testé en réel : `sample_lib` et Codex. ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## Documentation

[`docs/REFERENCE.md`](../REFERENCE.md) : outils, champs de la charte, sandbox · [`examples/`](../../examples) : bugs plantés · [`ci.yml`](../../.github/workflows/ci.yml) : CI.

## Contribuer

Issues et PR bienvenues. `uv run pytest -m "not docker"` pour la suite rapide, `uv run pytest -m docker` (un fichier à la fois, machine au repos) pour le sandbox, les oracles et la performance.

## Licence

[Licence Apache 2.0](../../LICENSE).

## Historique des étoiles

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>
