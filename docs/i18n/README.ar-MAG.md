<div align="center">

# 🐞 BugScout

**خلّي الذكاء الاصطناعي يصيد الأخطاء — بأمان، داخل Docker، وبالدليل.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · **الدارجة** · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [中文](README.zh.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

<div dir="rtl" align="right">


## علاش محتاجو

ملي كتقول لوكيل ذكاء اصطناعي «جرّب ليا الكود ديالي» غالبا كيسالي الأمر بوحدة من تلاتة: كيشغّل كود ماشي موثوق فالجهاز ديالك، ولا كينسى شنو جرّب وكيعاود نفس الشي، ولا كيقول ليك «لقيت بوغ» وهو غير اختبار مرة كيفشل ومرة كينجح. BugScout هو الجزء اللي ناقص:

| المشكل مع الوكيل بوحدو | شنو كيدير BugScout |
|---|---|
| كيشغّل كود الهدف فالجهاز ديالك | كولشي اللي كيشغّل كود الهدف كيتنفّذ داخل صندوق **Docker** مسدود (بلا أنترنيت، وصلاحيات مسحوبة، وحدود للمعالج والذاكرة) |
| ما عندو ذاكرة وكيعاود نفسو | **غراف ديال الأصول** و**شجرة استكشاف** كيتزادو غير فيها داخل Postgres؛ والفكرة المعاودة كترجّع ليك العقدة اللي كاينة |
| كينفّذ `DELETE /users` «باش يشوف شنو غادي يوقع» | **حواجز فالسيرفر**: النطاق، والعمليات الخطيرة، والميزانية، وكشف التعليق، وتأكيد من إنسان للبوغات الكبار |
| كيبلّغ على بوغات ماشي ثابتين | أي فشل كيتعاود **قبل ما يتحسب**؛ اللي ما كيتعاودش كيولي `flaky`، ونفس البوغ إلا تلقى 20 مرة كيتحسب نتيجة وحدة |

> [!NOTE]
> نتا (ولا بالأحرى النموذج المضيف: Claude Code وCodex) اللي كيخطّط. وBugScout كيخزّن وكينفّذ وكيتأكد وكيفرض القواعد.

## شنو كيدير

* **كيرسم خريطة** ديال حزمة بايثون ولا مواصفة OpenAPI: الدوال والكلاسات ونقط النهاية والعلاقات ديالهم.
* **المرحلة الساكنة:** التعقيد (radon)، والـ lint (ruff)، والأنواع (mypy)، والأمان (bandit)، والنسخ واللصق، والكود الميت (vulture).
* **المرحلة الديناميكية:** pytest واختبارات Hypothesis وschemathesis وطلبات HTTP يدوية وقواعد كتكتبها نتا.
* **المعايير:** الانهيار ولا خطأ 5xx، ومطابقة الـ schema، والفرق مع الكوميت اللي قبل، والقواعد ديالك نتا.
* **الجودة:** التغطية لكل دالة ولكل اختبار، ونتيجة الطفرات، وكشف الاختبارات المتقلبة والمعاودة.
* **الأداء:** التعقيد الزمني بالقياس (O(n²) بدل O(n log n) المسموح)، وتراجع الأداء بين الكوميتات، والنقط البطيئة، واستهلاك الذاكرة، وتحليل الـ API.
* **كيعطيك تقرير** بلا تكرار: البوغات والمشاكل الساكنة والتغطية والتراجعات.

42 أداة، و7 موارد للقراءة فقط (`run://{id}/…`)، و3 prompts (`testing_loop` و`write_charter` و`triage_bug`).

## الوكلاء الفرعيون المتخصصون

BugScout جايب معاه سبعة د الوكلاء الفرعيين ديال Claude Code فـ [`.claude/agents/`](../../.claude/agents). كل واحد مسؤول على مرحلة وحدة من `testing_loop` وما عندو غير الأدوات اللي خاصها هاد المرحلة. الجلسة الرئيسية كتنسّق بيناتهم وكتبقى ماسكة `start_run` و`end_run` وأي تصعيد خاصو إنسان.

| الوكيل | الدور | أهم الأدوات |
|---|---|---|
| [`bugscout-mapper`](../../.claude/agents/bugscout-mapper.md) | كيرسم خريطة الهدف وكيرتّب شنو غادي يتجرّب | `scan_python_code`, `import_openapi`, `get_untested`, `get_frontier` |
| [`bugscout-static-auditor`](../../.claude/agents/bugscout-static-auditor.md) | كيشغّل المحللات الساكنة وكيخلّي النتايج الحقيقية غير | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| [`bugscout-fuzzer`](../../.claude/agents/bugscout-fuzzer.md) | Hypothesis وschemathesis وطلبات HTTP وكيعاود إنتاج الفشل | `run_hypothesis`, `run_schemathesis`, `http_request`, `run_pytest`, `check_crash`, `check_schema`, `check_rule` |
| [`bugscout-diff-hunter`](../../.claude/agents/bugscout-diff-hunter.md) | تبدّل السلوك والسرعة بالمقارنة مع كوميت أقدم | `compare_with_git_version`, `compare_benchmark_with_git_version` |
| [`bugscout-perf-analyst`](../../.claude/agents/bugscout-perf-analyst.md) | التعقيد الزمني والمعالج والذاكرة وزمن الاستجابة | `measure_time_complexity`, `run_benchmark`, `profile_cpu`, `profile_memory`, `profile_api` |
| [`bugscout-quality-auditor`](../../.claude/agents/bugscout-quality-auditor.md) | التغطية ونتيجة الطفرات والاختبارات المتقلبة والمعاودة | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| [`bugscout-triager`](../../.claude/agents/bugscout-triager.md) | كيحكم على المرشّحين وهو الوحيد اللي كيسجّل البوغات | `record_bug`, `fingerprint_bug`, `confirm_finding` |

> [!NOTE]
> الـ triager بوحدو اللي يقدر يعيّط على `record_bug`؛ وحتى وكيل فرعي ما يقدر يبدا تشغيل ولا ينهيه ولا يجاوب على تصعيد. دير وكيلين منفّذين فالكتر فنفس الوقت، وما تجمعش اختبار الطفرات مع الأداء. الوكلاء الفرعيين ميزة فـ Claude Code (وCodex ما كيقراش `.claude/agents/`).

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

## كيفاش كيخدم

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. المضيف كيصيفط **ميثاق**: الهدف والنطاق والمعايير والقواعد والميزانية.
2. من بعد كيمشي على حلقة `testing_loop`: خريطة ← مرحلة ساكنة ← تشغيل الاختبارات ← فحص المعايير ← تسجيل البوغات ← الأداء ← التقرير.
3. أي استدعاء كينفّذ شي حاجة كيدوز من الحواجز لول. و**التصعيد** كيوقّف الفرع ديالو غير والمضيف كيكمّل فشي فرع آخر.
4. `record_bug` كيعاود خطوات التكرار، وكيطلّع بصمة للبوغ وكيحيّد المعاود. والبوغات العاليين والحرجين كيتسناو إنسان.

## بدا بسرعة

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## الاستعمال

**Claude Code** — الملف `.mcp.json` فجذر المشروع (كاين واجد):

```json
{ "mcpServers": { "bugscout": { "command": "uv", "args": ["run", "bugscout"],
  "env": { "DATABASE_URL": "postgresql://test:test@localhost:5432/bugscout" } } } }
```

**Codex** — الملف `~/.codex/config.toml`:

```toml
[mcp_servers.bugscout]
command = "uv"
args = ["run", "--directory", "/path/to/bugscout", "bugscout"]
env = { DATABASE_URL = "postgresql://test:test@localhost:5432/bugscout" }
```

من بعد قول للوكيل: *«استعمل الـ prompt اللي سميتو `testing_loop` من bugscout وجرّب `./my_project`»*. (و`write_charter` كيعاونك تكتب الميثاق.)

ميثاق بسيط:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

جرّبو على الأمثلة اللي فيها بوغات مزروعين داخل [`examples/`](../../examples) (`sample_lib` و`sample_api`).

## الحواجز

| الحاجز | السلوك |
|---|---|
| النطاق | أي هدف برا `scope.include/exclude` ولا مضيف برا `allowed_hosts` كيرجّع `escalation_required` |
| العمليات الخطيرة | `DELETE/PUT/PATCH` وشي طلبات `POST` خطيرة كيتصعّدو قبل ما يتصيفط أي شي؛ وschemathesis كيتخطاهم وكيقولها ليك |
| الميزانية | الخطوات والطلبات والدقايق؛ تحذير عند 90٪ ووقف نهائي عند 100٪ |
| التعليق | إلا ما كاينة حتى نتيجة جديدة فنافذة ديال الخطوات كيطلع تصعيد واحد |
| البوغات الخطيرين | `high` و`critical` خاصهم `answer_escalation` قبل ما يتحسبو مؤكدين |

## شنو تأكدنا منو

> [!WARNING]
> بصراحة على الوضعية: الجدول الكامل ديال كل مرحلة فـ [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified).

* آلي: 39 اختبار على Postgres وحاويات Docker حقيقية، ومنهم اختبار شامل بمضيف مبرمج عبر stdio كيلقى كاع البوغات المزروعين فالمثالين.
* جلسة Claude Code حقيقية (`claude -p` مع الـ prompt ديال `testing_loop`) تّصلات بالسيرفر وجرّبات الـ API التجريبي ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## التوثيق

[`docs/REFERENCE.md`](../REFERENCE.md): كاع الأدوات وحقول الميثاق وتفاصيل الصندوق · [`examples/`](../../examples): البوغات المزروعين · [`ci.yml`](../../.github/workflows/ci.yml): الـ CI.

## شارك معانا

الـ issues والـ PRs مرحبا بيهم. دير `uv run pytest -m "not docker"` للاختبارات السريعة، و`uv run pytest -m docker` (ملف ملف وعلى جهاز خاوي) لاختبارات الصندوق والمعايير والأداء.

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
