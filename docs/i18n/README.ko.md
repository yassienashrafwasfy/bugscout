<div align="center">

# 🐞 BugScout

**AI가 버그를 사냥하게 하세요 — 안전하게, Docker 안에서, 증거와 함께.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [中文](README.zh.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · **한국어**

</div>

---

## 왜 필요한가

AI 에이전트에게 “내 코드를 테스트해 줘”라고 하면 보통 셋 중 하나가 됩니다. 신뢰할 수 없는 코드를 내 컴퓨터에서 실행하거나, 이미 해 본 것을 잊고 반복하거나, 불안정한 테스트를 “버그”로 보고합니다. BugScout는 빠져 있던 기반입니다.

| 에이전트만 쓸 때의 문제 | BugScout의 해결책 |
|---|---|
| 대상 코드를 노트북에서 실행 | 대상 코드를 실행하는 모든 것은 제한된 **Docker** 샌드박스에서 동작합니다(네트워크 없음, 권한 제거, CPU·메모리 제한) |
| 기억이 없어 같은 일을 반복 | Postgres의 **자산 그래프**와 추가 전용 **탐색 트리**. 중복된 아이디어는 기존 노드를 반환합니다 |
| “어떻게 되나 보려고” `DELETE /users` 호출 | **서버 측 가드**: 범위, 파괴적 동작, 예산, 정체 감지, 심각한 버그의 사람 확인 |
| 불안정한 실패를 버그로 보고 | 실패는 **집계 전에 재실행**됩니다. 재현되지 않으면 `flaky`, 같은 버그를 20번 찾아도 결과는 한 건입니다 |

> [!NOTE]
> 계획은 당신(정확히는 LLM 호스트인 Claude Code, Codex)이 세웁니다. BugScout는 저장하고, 실행하고, 검증하고, 규칙을 강제합니다.

## 무엇을 하는가

* **매핑**: Python 패키지나 OpenAPI 명세를 함수, 클래스, 엔드포인트와 그 관계의 그래프로 만듭니다.
* **정적 단계:** 복잡도(radon), 린트(ruff), 타입(mypy), 보안(bandit), 복붙 코드, 죽은 코드(vulture).
* **동적 단계:** pytest, Hypothesis 속성 테스트, schemathesis, 수동 HTTP 요청, 사용자 정의 규칙.
* **오라클:** 크래시 / HTTP 5xx, 응답 스키마, 이전 git 커밋과의 동작 차이, 직접 정한 불변 조건.
* **품질:** 함수별·테스트별 커버리지, 뮤테이션 점수, 불안정·중복 테스트 감지.
* **보안:** bandit, 코드와 git 기록 속 하드코딩된 비밀 값, 취약한 의존성, 인젝션·인가 결함·CORS/헤더에 대한 능동 프로브(범위와 예산 안에서).
* **성능:** 경험적 시간 복잡도(허용된 O(n log n) 대비 O(n²)), 커밋 간 성능 저하, CPU 핫스팟, 메모리 사용, API 프로파일링.
* **리포트:** 중복을 제거한 결과(버그, 정적 문제, 커버리지, 핫스팟, 회귀).

47 tools · 7 read-only resources (`run://{id}/…`) · 3 prompts (`testing_loop`, `write_charter`, `triage_bug`)

## 전문 서브에이전트

BugScout는 [`.claude/agents/`](../../.claude/agents)에 Claude Code 서브에이전트 9개를 포함합니다. 각각 `testing_loop`의 한 단계를 맡고 그 단계에 필요한 도구만 가집니다. 메인 세션이 이들을 조율하며 `start_run`, `end_run`, 사람이 필요한 모든 에스컬레이션은 메인이 보유합니다.

| 서브에이전트 | 역할 | 주요 도구 |
|---|---|---|
| [`bugscout-mapper`](../../.claude/agents/bugscout-mapper.md) | 대상을 매핑하고 테스트할 것의 순서를 정함 | `scan_python_code`, `import_openapi`, `get_untested`, `get_frontier` |
| [`bugscout-static-auditor`](../../.claude/agents/bugscout-static-auditor.md) | 정적 분석기를 실행하고 실제 문제만 남김 | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| [`bugscout-fuzzer`](../../.claude/agents/bugscout-fuzzer.md) | Hypothesis, schemathesis, HTTP 프로브. 실패를 재현 | `run_hypothesis`, `run_schemathesis`, `http_request`, `run_pytest`, `check_crash`, `check_schema`, `check_rule` |
| [`bugscout-diff-hunter`](../../.claude/agents/bugscout-diff-hunter.md) | 이전 git 기준과 비교한 동작·속도 변화 | `compare_with_git_version`, `compare_benchmark_with_git_version` |
| [`bugscout-perf-analyst`](../../.claude/agents/bugscout-perf-analyst.md) | 시간 복잡도, CPU, 메모리, API 지연 | `measure_time_complexity`, `run_benchmark`, `profile_cpu`, `profile_memory`, `profile_api` |
| [`bugscout-quality-auditor`](../../.claude/agents/bugscout-quality-auditor.md) | 커버리지, 뮤테이션, 불안정·중복 테스트 | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| [`bugscout-security-auditor`](../../.claude/agents/bugscout-security-auditor.md) | 방어적·수동적: bandit, 코드와 git 기록 속 비밀 값, 취약한 의존성 | `run_bandit`, `run_secrets_scan`, `run_pip_audit` |
| [`bugscout-red-team`](../../.claude/agents/bugscout-red-team.md) | 공격적: 실행 중인 API에 대한 인젝션·인가 결함·하드닝 프로브 | `probe_injection`, `probe_authz`, `probe_http_hardening`, `http_request` |
| [`bugscout-triager`](../../.claude/agents/bugscout-triager.md) | 후보를 판정하며 버그를 기록할 수 있는 유일한 에이전트 | `record_bug`, `fingerprint_bug`, `confirm_finding` |

> [!NOTE]
> `record_bug`는 triager만 호출할 수 있습니다. 어떤 서브에이전트도 실행을 시작·종료하거나 에스컬레이션에 답할 수 없습니다. 코드를 실행하는 에이전트는 동시에 최대 2개, 뮤테이션은 성능 작업과 절대 함께 돌리지 마세요. 서브에이전트는 Claude Code 기능입니다(Codex는 `.claude/agents/`를 무시합니다).

## 도구

| 그룹 | 도구 |
|---|---|
| 실행 제어와 그래프 | `start_run`, `end_run`, `get_status`, `get_report`, `query_graph`, `get_untested`, `get_frontier`, `add_test_idea`, `update_result`, `write_test`, `get_escalations`, `answer_escalation`, `ask_human` |
| 매핑 | `scan_python_code`, `import_openapi` |
| 정적 분석 | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| 동적 테스트 | `run_pytest`, `run_hypothesis`, `run_schemathesis`, `http_request` |
| 오라클과 차이 | `check_crash`, `check_schema`, `check_rule`, `compare_with_git_version` |
| 테스트 품질 | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| 성능 | `measure_time_complexity`, `run_benchmark`, `compare_benchmark_with_git_version`, `profile_cpu`, `profile_memory`, `profile_api` |
| 버그 리포트 | `fingerprint_bug`, `record_bug`, `confirm_finding` |
| 보안 | `run_secrets_scan`, `run_pip_audit`, `probe_injection`, `probe_authz`, `probe_http_hardening` |

## 어떻게 동작하는가

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. 호스트가 **차터**(대상, 범위, 오라클, 규칙, 예산)를 보냅니다.
2. `testing_loop` 프롬프트의 루프를 따릅니다: 맵 → 정적 → 테스트 → 오라클 → 버그 기록 → 성능 → 리포트.
3. 실행을 수반하는 모든 호출은 먼저 가드를 통과합니다. **에스컬레이션**은 해당 브랜치만 멈추고, 호스트는 다른 작업을 계속합니다.
4. `record_bug`는 재현을 다시 실행하고 지문을 만들어 중복을 제거합니다. high·critical 버그는 사람을 기다립니다.

## 빠른 시작

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## 사용법

**Claude Code** — 저장소 루트의 `.mcp.json`(이미 포함됨):

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

그런 다음 에이전트에게 말하세요: *“bugscout의 `testing_loop` 프롬프트를 사용해서 `./my_project`를 테스트해 줘.”* (`write_charter`가 차터 작성을 도와줍니다.)

최소 차터:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

버그가 심어진 예제 [`examples/`](../../examples)(`sample_lib`, `sample_api`)에서 시험해 보세요.

## 안전장치

| 가드 | 동작 |
|---|---|
| 범위 | `scope.include/exclude` 밖의 대상이나 `allowed_hosts` 밖의 호스트는 `escalation_required`를 반환합니다 |
| 파괴적 동작 | `DELETE/PUT/PATCH`와 위험한 `POST`는 전송 전에 에스컬레이션됩니다. schemathesis는 이를 건너뛰고 알려 줍니다 |
| 예산 | 스텝, 요청, 분. 90%에서 경고, 100%에서 강제 중지 |
| 정체 | 일정 스텝 동안 새 발견이 없으면 에스컬레이션을 한 번 올립니다 |
| 심각한 버그 | `high` / `critical`은 `answer_escalation`을 거쳐야 확정으로 집계됩니다 |

## 검증된 내용

> [!WARNING]
> 단계별 표는 [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified)를 참고하세요.

* 자동화: 실제 Postgres와 Docker 컨테이너를 쓰는 39개 테스트. stdio로 연결된 스크립트 호스트가 두 예제의 심어진 버그를 모두 찾는 E2E 포함.
* 실제 Claude Code 세션(`testing_loop`를 따르는 `claude -p`)이 약 0.22달러로 `sample_api`에 심어진 버그 2개를 찾았습니다. 아직 실사용 테스트 전: `sample_lib`, Codex. ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## 문서

[`docs/REFERENCE.md`](../REFERENCE.md): 도구, 차터 필드, 샌드박스 · [`examples/`](../../examples): 심어진 버그 · [`ci.yml`](../../.github/workflows/ci.yml): CI.

## 기여하기

이슈와 PR을 환영합니다. 빠른 테스트는 `uv run pytest -m "not docker"`, 샌드박스·오라클·성능 테스트는 `uv run pytest -m docker`(한 번에 한 파일, 여유 있는 머신에서).

## 라이선스

[Apache 2.0 라이선스](../../LICENSE).

## 스타 히스토리

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>
