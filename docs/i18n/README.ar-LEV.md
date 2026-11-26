<div align="center">

# 🐞 BugScout

**خلّي الذكاء الاصطناعي يصطاد الأخطاء — بأمان، جوّا Docker، وبالدليل.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · **شامي** · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [中文](README.zh.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

<div dir="rtl" align="right">


## ليش بدك ياه

لما تقول لوكيل ذكاء اصطناعي «اختبرلي الكود تبعي» غالبًا بتخلص الحكاية بوحدة من تلاتة: بيشغّل كود مش موثوق على جهازك، أو بينسى شو جرّب فبيعيد نفسه، أو بيقلك «لقيت خطأ» وهو بالحقيقة اختبار مرة بيفشل ومرة بينجح. BugScout هو الجزء الناقص:

| المشكلة مع الوكيل لحاله | شو بيعمل BugScout |
|---|---|
| بيشغّل كود الهدف على جهازك | كل شي بيشغّل كود الهدف بيشتغل جوّا صندوق **Docker** مسكّر (بدون إنترنت، وصلاحيات مسحوبة، وحدود للمعالج والذاكرة) |
| ما عنده ذاكرة فبيعيد نفسه | **رسم للأصول** و**شجرة استكشاف** بتنضاف عليها بس جوّا Postgres؛ والفكرة المكررة بترجّعلك العقدة الموجودة |
| بينفّذ `DELETE /users` «ليشوف شو رح يصير» | **حواجز عالسيرفر**: النطاق، والعمليات الخطرة، والميزانية، وكشف التعليق، وتأكيد من إنسان للأخطاء الكبيرة |
| بيبلّغ عن أخطاء مش ثابتة | أي فشل بينعاد **قبل ما ينحسب**؛ واللي ما بيتكرر بيصير `flaky`، ولو نفس الخطأ انلقى 20 مرة بينحسب نتيجة وحدة |

> [!NOTE]
> إنت (أو بالأحرى النموذج المضيف: Claude Code وCodex) اللي بتخطط. وBugScout بيخزّن وبينفّذ وبيتأكد وبيفرض القواعد.

## شو بيعمل

* **بيرسم خريطة** لحزمة بايثون أو مواصفة OpenAPI: الدوال والكلاسات ونقاط النهاية وعلاقاتها.
* **المرحلة الساكنة:** التعقيد (radon)، والـ lint (ruff)، والأنواع (mypy)، والأمان (bandit)، والنسخ واللصق، والكود الميت (vulture).
* **المرحلة الديناميكية:** pytest واختبارات Hypothesis وschemathesis وطلبات HTTP يدوية وقواعد بتكتبها إنت.
* **المعايير:** الانهيار أو خطأ 5xx، ومطابقة الـ schema، والفرق عن الكوميت اللي قبله، وقواعدك إنت.
* **الجودة:** التغطية لكل دالة ولكل اختبار، ونتيجة الطفرات، وكشف الاختبارات المتقلبة والمكررة.
* **الأمان:** bandit والأسرار المكتوبة بالكود (وبتاريخ git) والمكتبات اللي فيها ثغرات، وفحوصات نشطة للحقن وكسر الصلاحيات وCORS والـ headers، ضمن النطاق والميزانية.
* **الأداء:** التعقيد الزمني بالقياس (O(n²) بدل O(n log n) المسموح)، وتراجع الأداء بين الكوميتات، والنقاط البطيئة، واستهلاك الذاكرة، وتحليل الـ API.
* **بيطلّعلك تقرير** بدون تكرار: الأخطاء والمشاكل الساكنة والتغطية والتراجعات.

47 أداة، و7 موارد للقراءة بس (`run://{id}/…`)، و3 prompts (`testing_loop` و`write_charter` و`triage_bug`).

## الوكلاء الفرعيون المتخصصون

بيجي BugScout مع تسع وكلاء فرعيين لـ Claude Code بـ [`.claude/agents/`](../../.claude/agents). كل واحد مسؤول عن مرحلة وحدة من `testing_loop` وما معه إلا الأدوات اللي بتحتاجها هالمرحلة. الجلسة الرئيسية بتنسّق بينهم وبتضل ماسكة `start_run` و`end_run` وأي تصعيد بدو إنسان.

| الوكيل | الدور | أهم الأدوات |
|---|---|---|
| [`bugscout-mapper`](../../.claude/agents/bugscout-mapper.md) | بيرسم خريطة الهدف وبيرتّب شو لازم ينختبر | `scan_python_code`, `import_openapi`, `get_untested`, `get_frontier` |
| [`bugscout-static-auditor`](../../.claude/agents/bugscout-static-auditor.md) | بيشغّل المحللات الساكنة وبيخلّي النتايج الحقيقية بس | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| [`bugscout-fuzzer`](../../.claude/agents/bugscout-fuzzer.md) | Hypothesis وschemathesis وطلبات HTTP وبيعيد إنتاج الفشل | `run_hypothesis`, `run_schemathesis`, `http_request`, `run_pytest`, `check_crash`, `check_schema`, `check_rule` |
| [`bugscout-diff-hunter`](../../.claude/agents/bugscout-diff-hunter.md) | تغيّر السلوك والسرعة مقارنة بكوميت أقدم | `compare_with_git_version`, `compare_benchmark_with_git_version` |
| [`bugscout-perf-analyst`](../../.claude/agents/bugscout-perf-analyst.md) | التعقيد الزمني والمعالج والذاكرة وزمن الاستجابة | `measure_time_complexity`, `run_benchmark`, `profile_cpu`, `profile_memory`, `profile_api` |
| [`bugscout-quality-auditor`](../../.claude/agents/bugscout-quality-auditor.md) | التغطية ونتيجة الطفرات والاختبارات المتقلبة والمكررة | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| [`bugscout-security-auditor`](../../.claude/agents/bugscout-security-auditor.md) | دفاعي وساكن: bandit والأسرار بالكود وتاريخ git والمكتبات اللي فيها ثغرات | `run_bandit`, `run_secrets_scan`, `run_pip_audit` |
| [`bugscout-red-team`](../../.claude/agents/bugscout-red-team.md) | هجومي: فحوصات الحقن وكسر الصلاحيات والتحصين عالـ API وهو شغال | `probe_injection`, `probe_authz`, `probe_http_hardening`, `http_request` |
| [`bugscout-triager`](../../.claude/agents/bugscout-triager.md) | بيحكم عالمرشّحين وهو الوحيد اللي بيسجّل الأخطاء | `record_bug`, `fingerprint_bug`, `confirm_finding` |

> [!NOTE]
> الـ triager لحاله بيقدر ينادي `record_bug`؛ وما في أي وكيل فرعي بيقدر يبدأ تشغيل أو ينهيه أو يرد على تصعيد. شغّل وكيلين منفّذين على الأكتر بنفس الوقت، وما تجمع اختبار الطفرات مع الأداء. الوكلاء الفرعيين ميزة بـ Claude Code (وCodex ما بيقرا `.claude/agents/`).

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

## كيف بيشتغل

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. المضيف بيبعت **ميثاق**: الهدف والنطاق والمعايير والقواعد والميزانية.
2. بعدين بيمشي على حلقة `testing_loop`: خريطة ← مرحلة ساكنة ← تشغيل الاختبارات ← فحص المعايير ← تسجيل الأخطاء ← الأداء ← التقرير.
3. أي استدعاء بينفّذ شي بيمرق عالحواجز أول. و**التصعيد** بيوقف فرعه بس والمضيف بيكمّل بغيره.
4. `record_bug` بيعيد خطوات التكرار، وبيطلّع بصمة للخطأ وبيشيل المكرر. والأخطاء العالية والحرجة بتستنى إنسان.

## ابدأ بسرعة

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## الاستخدام

**Claude Code** — ملف `.mcp.json` بجذر المشروع (موجود جاهز):

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

بعدين قول للوكيل: *«استخدم الـ prompt اسمه `testing_loop` من bugscout واختبر `./my_project`»*. (و`write_charter` بيساعدك تكتب الميثاق.)

ميثاق بسيط:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

جرّبه عالأمثلة اللي فيها أخطاء مزروعة جوّا [`examples/`](../../examples) (`sample_lib` و`sample_api`).

## الحواجز

| الحاجز | السلوك |
|---|---|
| النطاق | أي هدف برّا `scope.include/exclude` أو مضيف برّا `allowed_hosts` بيرجّع `escalation_required` |
| العمليات الخطرة | `DELETE/PUT/PATCH` وبعض طلبات `POST` الخطرة بتتصعّد قبل ما ينبعت أي شي؛ وschemathesis بيتخطاها وبيقلك |
| الميزانية | الخطوات والطلبات والدقايق؛ تحذير عند 90٪ ووقف تام عند 100٪ |
| التعليق | إذا ما في أي نتيجة جديدة خلال نافذة من الخطوات بيطلع تصعيد واحد |
| الأخطاء الخطيرة | `high` و`critical` بدها `answer_escalation` قبل ما تنحسب مؤكدة |

## شو تأكدنا منه

> [!WARNING]
> بصراحة عن الوضع: الجدول الكامل لكل مرحلة بـ [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified).

* آلي: 39 اختبار على Postgres وحاويات Docker حقيقية، منهم اختبار شامل بمضيف مبرمج عبر stdio بيلاقي كل الأخطاء المزروعة بالمثالين.
* جلسة Claude Code حقيقية (`claude -p` مع الـ prompt تبع `testing_loop`) اتوصلت بالسيرفر واختبرت الـ API التجريبي ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## التوثيق

[`docs/REFERENCE.md`](../REFERENCE.md): كل الأدوات وحقول الميثاق وتفاصيل الصندوق · [`examples/`](../../examples): الأخطاء المزروعة · [`ci.yml`](../../.github/workflows/ci.yml): الـ CI.

## شاركنا

الـ issues والـ PRs أهلين فيها. شغّل `uv run pytest -m "not docker"` للاختبارات السريعة، و`uv run pytest -m docker` (ملف ملف وعلى جهاز فاضي) لاختبارات الصندوق والمعايير والأداء.

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
