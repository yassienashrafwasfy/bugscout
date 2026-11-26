<div align="center">

# 🐞 BugScout

**دع الذكاء الاصطناعي يصطاد الأخطاء — بأمان، داخل Docker، ومع الإثباتات.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · **العربية** · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [中文](README.zh.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

<div dir="rtl" align="right">


## لماذا تحتاج إليه

عندما تطلب من وكيل ذكاء اصطناعي «اختبر شيفرتي» ينتهي الأمر غالبًا بإحدى ثلاث نتائج: ينفّذ شيفرة غير موثوقة على جهازك، أو ينسى ما جرّبه فيكرر نفسه، أو يبلّغ عن «خطأ» لم يكن سوى اختبار متذبذب. BugScout هو الطبقة الناقصة:

| المشكلة مع الوكيل المجرّد | ما يفعله BugScout |
|---|---|
| ينفّذ شيفرة الهدف على جهازك | كل ما ينفّذ شيفرة الهدف يعمل داخل صندوق **Docker** مقيَّد (بلا شبكة، وصلاحيات مسحوبة، وحدود للمعالج والذاكرة) |
| ليست له ذاكرة فيكرر نفسه | **رسم بياني للأصول** و**شجرة استكشاف** تُضاف إليها العقد فقط داخل Postgres؛ والفكرة المكررة تعيد العقدة الموجودة |
| ينفّذ `DELETE /users` «ليرى ماذا يحدث» | **حواجز على الخادم**: النطاق، والعمليات المدمّرة، والميزانية، وكشف التعثر، وتأكيد بشري للأخطاء الخطيرة |
| يبلّغ عن أخطاء متذبذبة أو عابرة | يُعاد تشغيل أي فشل **قبل أن يُحتسب**؛ وما لا يتكرر يصبح `flaky`، والخطأ نفسه إذا وُجد 20 مرة فهو نتيجة واحدة |

> [!NOTE]
> أنت (أو بالأحرى النموذج المضيف: Claude Code وCodex) تتولى التخطيط. أما BugScout فيخزّن وينفّذ ويتحقق ويفرض القواعد.

## ماذا يفعل

* **يرسم الخريطة** لحزمة بايثون أو مواصفة OpenAPI: دوال وأصناف ونقاط نهاية وعلاقاتها.
* **المرحلة الساكنة:** التعقيد (radon)، التدقيق (ruff)، الأنواع (mypy)، الأمان (bandit)، النسخ واللصق، الشيفرة الميتة (vulture).
* **المرحلة الديناميكية:** pytest واختبارات Hypothesis وschemathesis وطلبات HTTP يدوية وقواعد يكتبها المستخدم.
* **المعايير:** الانهيار أو خطأ 5xx، ومطابقة المخطط، والفرق عن الإيداع السابق في git، وثوابتك الخاصة.
* **الجودة:** التغطية لكل دالة ولكل اختبار، ونتيجة الطفرات، وكشف الاختبارات المتذبذبة والمكررة.
* **الأداء:** التعقيد الزمني التجريبي (O(n²) مقابل O(n log n) المسموح)، وتراجع الأداء بين الإيداعات، ونقاط الاختناق، واستهلاك الذاكرة، وتحليل الواجهات.
* **يقدّم تقريرًا** منقّحًا من التكرار: الأخطاء والمشكلات الساكنة والتغطية ونقاط الاختناق والتراجعات.

42 أداة، و7 موارد للقراءة فقط (`run://{id}/…`)، و3 توجيهات (`testing_loop` و`write_charter` و`triage_bug`).

## كيف يعمل

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. يرسل المضيف **ميثاقًا** يحدد الهدف والنطاق والمعايير والقواعد والميزانية.
2. ثم يتبع حلقة `testing_loop`: رسم الخريطة ← المرحلة الساكنة ← تشغيل الاختبارات ← فحص المعايير ← تسجيل الأخطاء ← الأداء ← التقرير.
3. كل استدعاء ينفّذ شيئًا يمر أولًا عبر الحواجز. و**التصعيد** يوقف فرعه فقط ويواصل المضيف في غيره.
4. يعيد `record_bug` تشغيل خطوات التكرار، ويحسب بصمة الخطأ ويزيل التكرار. والأخطاء العالية والحرجة تنتظر إنسانًا.

## البدء السريع

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## الاستخدام

**Claude Code** — الملف `.mcp.json` في جذر المستودع (موجود مسبقًا):

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

ثم قل لوكيلك: *«استخدم التوجيه `testing_loop` من bugscout واختبر `./my_project`»*. (يساعدك `write_charter` على كتابة الميثاق.)

ميثاق بسيط:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

جرّبه على الأمثلة المزروعة فيها أخطاء داخل [`examples/`](../../examples) (`sample_lib` و`sample_api`).

## الحواجز الأمنية

| الحاجز | السلوك |
|---|---|
| النطاق | هدف خارج `scope.include/exclude` أو مضيف خارج `allowed_hosts` يعيد `escalation_required` |
| العمليات المدمّرة | `DELETE/PUT/PATCH` وبعض طلبات `POST` الخطرة تُصعَّد قبل إرسال أي شيء؛ وschemathesis يتخطاها ويذكر ذلك |
| الميزانية | الخطوات والطلبات والدقائق؛ تحذير عند 90٪ وإيقاف قاطع عند 100٪ |
| التعثر | غياب أي نتائج جديدة خلال نافذة من الخطوات يرفع تصعيدًا واحدًا |
| الأخطاء الخطيرة | `high` و`critical` تحتاج `answer_escalation` قبل أن تُعدّ مؤكَّدة |

## ما الذي تم التحقق منه

> [!WARNING]
> الأمانة في الحالة: الجدول الكامل لكل مرحلة في [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified).

* آلي: 39 اختبارًا على Postgres وحاويات Docker حقيقية، منها اختبار شامل بمضيف مبرمج عبر stdio يجد كل الأخطاء المزروعة في المثالين.
* جلسة Claude Code حقيقية (`claude -p` مع توجيه `testing_loop`) اتصلت بالخادم واختبرت الواجهة النموذجية ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## التوثيق

[`docs/REFERENCE.md`](../REFERENCE.md): كل الأدوات وحقول الميثاق وتفاصيل الصندوق · [`examples/`](../../examples): الأخطاء المزروعة · [`ci.yml`](../../.github/workflows/ci.yml): التكامل المستمر.

## المساهمة

المشكلات وطلبات الدمج مرحَّب بها. شغّل `uv run pytest -m "not docker"` للاختبارات السريعة، و`uv run pytest -m docker` (ملفًا ملفًا وعلى جهاز غير مشغول) لاختبارات الصندوق والمعايير والأداء.

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
