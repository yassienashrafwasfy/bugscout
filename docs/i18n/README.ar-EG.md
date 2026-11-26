<div align="center">

# 🐞 BugScout

**خلّي الذكاء الاصطناعي يصطاد البجز — بأمان، جوّه Docker، وبالدليل.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · **مصري** · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [中文](README.zh.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

<div dir="rtl" align="right">


## ليه محتاجه

لما تقول لوكيل ذكاء اصطناعي «اختبرلي الكود بتاعي» الموضوع غالبًا بيخلص بواحدة من تلات: يشغّل كود مش موثوق على جهازك، أو ينسى جرّب إيه فيكرر نفسه، أو يقولك «لقيت بج» وهو في الحقيقة اختبار بيفشل مرة وينجح مرة. BugScout هو الحتة الناقصة:

| المشكلة مع الوكيل لوحده | BugScout بيعمل إيه |
|---|---|
| بيشغّل كود الهدف على لابتوبك | أي حاجة بتشغّل كود الهدف بتتنفّذ جوّه صندوق **Docker** مقفول (من غير نت، وصلاحيات متشالة، وحدود للمعالج والرامات) |
| مالوش ذاكرة فبيكرر نفسه | **جراف للأصول** و**شجرة استكشاف** بتتضاف عليها بس جوّه Postgres؛ ولو الفكرة اتكررت بيرجّعلك العقدة الموجودة |
| بينفّذ `DELETE /users` «عشان يشوف هيحصل إيه» | **حواجز على السيرفر**: النطاق، والعمليات الخطيرة، والميزانية، وكشف التعليق، وتأكيد من إنسان للبجز الكبيرة |
| بيبلّغ عن بجز مش ثابتة | أي فشل بيتعاد **قبل ما يتحسب**؛ واللي مبيتكررش بيبقى `flaky`، ولو نفس البج اتلقى 20 مرة بيتحسب نتيجة واحدة |

> [!NOTE]
> انت (أو بمعنى أصح النموذج اللي بيشغّلك: Claude Code وCodex) اللي بتخطّط. وBugScout بيخزّن وينفّذ ويتأكد ويفرض القواعد.

## بيعمل إيه

* **بيرسم خريطة** لحزمة بايثون أو مواصفة OpenAPI: الدوال والكلاسات والـ endpoints وعلاقاتها.
* **المرحلة الساكنة:** التعقيد (radon)، والـ lint (ruff)، والأنواع (mypy)، والأمان (bandit)، والنسخ واللصق، والكود الميت (vulture).
* **المرحلة الديناميكية:** pytest واختبارات Hypothesis وschemathesis وطلبات HTTP يدوي وقواعد انت بتكتبها.
* **المعايير:** الكراش أو خطأ 5xx، ومطابقة الـ schema، والفرق عن الكوميت اللي قبله، وقواعدك انت.
* **الجودة:** التغطية لكل دالة ولكل اختبار، ونتيجة الطفرات، وكشف الاختبارات المتقلّبة والمكررة.
* **الأمان:** bandit والأسرار المكتوبة في الكود (وفي تاريخ git) والمكتبات اللي فيها ثغرات، وفحوصات نشطة للحقن وكسر الصلاحيات وCORS والـ headers، جوّه النطاق والميزانية.
* **الأداء:** التعقيد الزمني بالقياس (O(n²) بدل O(n log n) المسموح)، وتراجع الأداء بين الكوميتات، والأماكن البطيئة، واستهلاك الرامات، وتحليل الـ API.
* **بيطلّعلك تقرير** من غير تكرار: البجز والمشاكل الساكنة والتغطية والتراجعات.

47 أداة، و7 موارد للقراءة بس (`run://{id}/…`)، و3 prompts (`testing_loop` و`write_charter` و`triage_bug`).

## الوكلاء الفرعيون المتخصصون

BugScout جايب معاه تسع وكلاء فرعيين لـ Claude Code في [`.claude/agents/`](../../.claude/agents). كل واحد منهم مسؤول عن مرحلة واحدة من `testing_loop` ومعاه بس الأدوات اللي المرحلة دي محتاجاها. الجلسة الرئيسية بتنسّق بينهم وبتفضل ماسكة `start_run` و`end_run` وأي تصعيد محتاج إنسان.

| الوكيل | دوره | أهم الأدوات |
|---|---|---|
| [`bugscout-mapper`](../../.claude/agents/bugscout-mapper.md) | بيرسم خريطة الهدف ويرتّب إيه اللي يتختبر | `scan_python_code`, `import_openapi`, `get_untested`, `get_frontier` |
| [`bugscout-static-auditor`](../../.claude/agents/bugscout-static-auditor.md) | بيشغّل المحللات الساكنة ويسيب النتايج الحقيقية بس | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| [`bugscout-fuzzer`](../../.claude/agents/bugscout-fuzzer.md) | Hypothesis وschemathesis وطلبات HTTP وبيعيد إنتاج الفشل | `run_hypothesis`, `run_schemathesis`, `http_request`, `run_pytest`, `check_crash`, `check_schema`, `check_rule` |
| [`bugscout-diff-hunter`](../../.claude/agents/bugscout-diff-hunter.md) | التغيّر في السلوك والسرعة قدام كوميت أقدم | `compare_with_git_version`, `compare_benchmark_with_git_version` |
| [`bugscout-perf-analyst`](../../.claude/agents/bugscout-perf-analyst.md) | التعقيد الزمني والمعالج والرامات وزمن الاستجابة | `measure_time_complexity`, `run_benchmark`, `profile_cpu`, `profile_memory`, `profile_api` |
| [`bugscout-quality-auditor`](../../.claude/agents/bugscout-quality-auditor.md) | التغطية ونتيجة الطفرات والاختبارات المتقلّبة والمكررة | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| [`bugscout-security-auditor`](../../.claude/agents/bugscout-security-auditor.md) | دفاعي وساكن: bandit والأسرار في الكود وتاريخ git والمكتبات اللي فيها ثغرات | `run_bandit`, `run_secrets_scan`, `run_pip_audit` |
| [`bugscout-red-team`](../../.claude/agents/bugscout-red-team.md) | هجومي: فحوصات الحقن وكسر الصلاحيات والتحصين على الـ API وهو شغال | `probe_injection`, `probe_authz`, `probe_http_hardening`, `http_request` |
| [`bugscout-triager`](../../.claude/agents/bugscout-triager.md) | بيحكم على المرشّحين وهو الوحيد اللي بيسجّل البجز | `record_bug`, `fingerprint_bug`, `confirm_finding` |

> [!NOTE]
> الـ triager لوحده اللي يقدر ينادي `record_bug`؛ ومفيش وكيل فرعي يقدر يبدأ تشغيل أو ينهيه أو يرد على تصعيد. شغّل وكيلين منفّذين بالكتير في نفس الوقت، ومتجمعش اختبار الطفرات مع الأداء. الوكلاء الفرعيين ميزة في Claude Code (و Codex مبيقراش `.claude/agents/`).

## الأدوات

| المجموعة | الأدوات |
|---|---|
| إدارة التشغيل والرسم البياني | `start_run`, `end_run`, `get_status`, `get_report`, `query_graph`, `get_untested`, `get_frontier`, `add_test_idea`, `update_result`, `write_test`, `get_escalations`, `answer_escalation`, `ask_human` |
| رسم الخريطة | `scan_python_code`, `import_openapi` |
| التحليل الساكن | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| الاختبار الديناميكي | `run_pytest`, `run_hypothesis`, `run_schemathesis`, `http_request` |
| المعايير والمقارنات | `check_crash`, `check_schema`, `check_rule`, `compare_with_git_version` |
| جودة الاختبارات | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| الأداء | `measure_time_complexity`, `run_benchmark`, `compare_benchmark_with_git_version`, `profile_cpu`, `profile_memory`, `profile_api` |
| تقارير الأخطاء | `fingerprint_bug`, `record_bug`, `confirm_finding` |
| الأمان | `run_secrets_scan`, `run_pip_audit`, `probe_injection`, `probe_authz`, `probe_http_hardening` |

## بيشتغل إزاي

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. المضيف بيبعت **ميثاق**: الهدف والنطاق والمعايير والقواعد والميزانية.
2. وبعدين بيمشي ورا حلقة `testing_loop`: خريطة ← مرحلة ساكنة ← تشغيل الاختبارات ← فحص المعايير ← تسجيل البجز ← الأداء ← التقرير.
3. أي استدعاء بينفّذ حاجة بيعدّي على الحواجز الأول. و**التصعيد** بيوقف فرعه هو بس والمضيف بيكمّل في غيره.
4. `record_bug` بيعيد خطوات التكرار، ويطلّع بصمة للبج ويشيل المكرر. والبجز العالية والحرجة بتستنى إنسان.

## ابدأ بسرعة

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## الاستخدام

**Claude Code** — ملف `.mcp.json` في أول المشروع (موجود جاهز):

```json
{ "mcpServers": { "bugscout": { "command": "uv", "args": ["run", "bugscout"],
  "env": { "DATABASE_URL": "postgresql://test:test@localhost:5432/bugscout" } } } }
```

**Codex** — ملف `~/.codex/config.toml`:

```toml
[mcp_servers.bugscout]
command = "uv"
args = ["run", "--directory", "/path/to/bugscout", "bugscout"]
env = { DATABASE_URL = "postgresql://test:test@localhost:5432/bugscout" }
```

وبعدين قول للوكيل: *«استخدم الـ prompt اسمه `testing_loop` من bugscout واختبر `./my_project`»*. (و`write_charter` بيساعدك تكتب الميثاق.)

ميثاق بسيط:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

جرّبه على الأمثلة اللي فيها بجز مزروعة جوّه [`examples/`](../../examples) (`sample_lib` و`sample_api`).

## الحواجز

| الحاجز | بيعمل إيه |
|---|---|
| النطاق | أي هدف بره `scope.include/exclude` أو مضيف بره `allowed_hosts` بيرجّع `escalation_required` |
| العمليات الخطيرة | `DELETE/PUT/PATCH` وبعض الـ `POST` الخطيرة بتتصعّد قبل ما يتبعت أي حاجة؛ وschemathesis بيتخطاها ويقولك |
| الميزانية | الخطوات والطلبات والدقايق؛ تحذير عند 90٪ ووقف تام عند 100٪ |
| التعليق | لو مفيش أي نتيجة جديدة في نافذة من الخطوات بيطلع تصعيد واحد |
| البجز الخطيرة | `high` و`critical` لازم `answer_escalation` قبل ما تتحسب مؤكدة |

## اتأكدنا من إيه

> [!WARNING]
> بصراحة عن الحالة: الجدول الكامل لكل مرحلة في [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified).

* آلي: 39 اختبار على Postgres وحاويات Docker حقيقية، منهم اختبار شامل بمضيف مبرمج على stdio بيلاقي كل البجز المزروعة في المثالين.
* جلسة Claude Code حقيقية (`claude -p` مع الـ prompt بتاع `testing_loop`) اتوصّلت بالسيرفر واختبرت الـ API التجريبي ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## التوثيق

[`docs/REFERENCE.md`](../REFERENCE.md): كل الأدوات وحقول الميثاق وتفاصيل الصندوق · [`examples/`](../../examples): البجز المزروعة · [`ci.yml`](../../.github/workflows/ci.yml): الـ CI.

## شارك معانا

الـ issues والـ PRs أهلًا بيها. شغّل `uv run pytest -m "not docker"` للاختبارات السريعة، و`uv run pytest -m docker` (ملف ملف وعلى جهاز فاضي) لاختبارات الصندوق والمعايير والأداء.

## الرخصة

[رخصة Apache 2.0](../../LICENSE).

## تاريخ النجوم

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>

</div>
