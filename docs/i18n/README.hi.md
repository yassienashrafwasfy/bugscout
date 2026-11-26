<div align="center">

# 🐞 BugScout

**अपने AI को बग खोजने दें — सुरक्षित रूप से, Docker में, सबूतों के साथ।**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [中文](README.zh.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · **हिन्दी** · [Türkçe](README.tr.md) · [한국어](README.ko.md)

</div>

---

## इसकी ज़रूरत क्यों

जब आप किसी AI एजेंट से «मेरा कोड टेस्ट करो» कहते हैं, तो आमतौर पर तीन में से एक होता है: वह आपकी मशीन पर अविश्वसनीय कोड चलाता है, जो पहले आज़मा चुका है उसे भूलकर दोहराता है, या किसी अस्थिर टेस्ट को «बग» बताकर रिपोर्ट कर देता है। BugScout वही कमी पूरी करता है:

| सिर्फ़ एजेंट की समस्या | BugScout क्या करता है |
|---|---|
| लक्ष्य कोड आपके लैपटॉप पर चलाता है | लक्ष्य कोड चलाने वाली हर चीज़ एक बंद **Docker** सैंडबॉक्स में चलती है (नेटवर्क नहीं, अधिकार हटे हुए, CPU/मेमोरी सीमाएँ) |
| याददाश्त नहीं, इसलिए खुद को दोहराता है | Postgres में **एसेट ग्राफ़** और केवल-जोड़ने वाला **एक्सप्लोरेशन ट्री**; दोहराया गया विचार मौजूदा नोड लौटाता है |
| «देखें क्या होता है» कहकर `DELETE /users` चला देता है | **सर्वर-साइड सुरक्षा**: दायरा, विनाशकारी क्रियाएँ, बजट, अटकना पकड़ना, गंभीर बग के लिए इंसानी पुष्टि |
| अस्थिर विफलताओं को बग बता देता है | हर विफलता **गिनने से पहले दोबारा चलाई जाती है**; दोहराई न जाए तो `flaky`, और एक ही बग 20 बार मिले तो भी एक ही नतीजा |

> [!NOTE]
> योजना आप (या कहें LLM होस्ट: Claude Code, Codex) बनाते हैं। BugScout स्टोर करता है, चलाता है, जाँचता है और नियम लागू करता है।

## यह क्या करता है

* **मैप करता है**: Python पैकेज या OpenAPI स्पेक को फ़ंक्शन, क्लास, एंडपॉइंट और उनके संबंधों के ग्राफ़ में।
* **स्थैतिक चरण:** जटिलता (radon), लिंट (ruff), टाइप (mypy), सुरक्षा (bandit), कॉपी-पेस्ट और मृत कोड (vulture)।
* **गतिशील चरण:** pytest, Hypothesis प्रॉपर्टी टेस्ट, schemathesis, हाथ से बने HTTP अनुरोध और अपने नियम।
* **ऑरेकल:** क्रैश / HTTP 5xx, रिस्पॉन्स स्कीमा, पिछले git कमिट से व्यवहार का अंतर, आपके अपने इनवेरिएंट।
* **गुणवत्ता:** हर फ़ंक्शन और हर टेस्ट की कवरेज, म्यूटेशन स्कोर, अस्थिर और दोहराए गए टेस्ट की पहचान।
* **प्रदर्शन:** अनुभवजन्य समय-जटिलता (अनुमत O(n log n) के मुक़ाबले O(n²)), कमिट के बीच गिरावट, CPU हॉटस्पॉट, मेमोरी खपत, API प्रोफ़ाइलिंग।
* **रिपोर्ट** बिना दोहराव के: बग, स्थैतिक समस्याएँ, कवरेज, हॉटस्पॉट, रिग्रेशन।

42 tools · 7 read-only resources (`run://{id}/…`) · 3 prompts (`testing_loop`, `write_charter`, `triage_bug`)

## विशेषज्ञ सबएजेंट

BugScout [`.claude/agents/`](../../.claude/agents) में Claude Code के सात सबएजेंट के साथ आता है। हर एक `testing_loop` का एक चरण संभालता है और उसके पास सिर्फ़ उसी चरण के टूल होते हैं। आपका मुख्य सत्र इन्हें समन्वित करता है और `start_run`, `end_run` तथा इंसान की ज़रूरत वाले हर एस्केलेशन को अपने पास रखता है।

| सबएजेंट | भूमिका | मुख्य टूल |
|---|---|---|
| [`bugscout-mapper`](../../.claude/agents/bugscout-mapper.md) | लक्ष्य का नक्शा बनाता है और तय करता है क्या टेस्ट हो | `scan_python_code`, `import_openapi`, `get_untested`, `get_frontier` |
| [`bugscout-static-auditor`](../../.claude/agents/bugscout-static-auditor.md) | स्थैतिक विश्लेषक चलाता है और असली नतीजे रखता है | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| [`bugscout-fuzzer`](../../.claude/agents/bugscout-fuzzer.md) | Hypothesis, schemathesis और HTTP प्रोब; विफलताएँ दोहराता है | `run_hypothesis`, `run_schemathesis`, `http_request`, `run_pytest`, `check_crash`, `check_schema`, `check_rule` |
| [`bugscout-diff-hunter`](../../.claude/agents/bugscout-diff-hunter.md) | पुराने git संदर्भ की तुलना में व्यवहार और गति में बदलाव | `compare_with_git_version`, `compare_benchmark_with_git_version` |
| [`bugscout-perf-analyst`](../../.claude/agents/bugscout-perf-analyst.md) | समय-जटिलता, CPU, मेमोरी, API विलंब | `measure_time_complexity`, `run_benchmark`, `profile_cpu`, `profile_memory`, `profile_api` |
| [`bugscout-quality-auditor`](../../.claude/agents/bugscout-quality-auditor.md) | कवरेज, म्यूटेशन, अस्थिर और दोहराए गए टेस्ट | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| [`bugscout-triager`](../../.claude/agents/bugscout-triager.md) | उम्मीदवारों को परखता है और अकेला बग दर्ज करता है | `record_bug`, `fingerprint_bug`, `confirm_finding` |

> [!NOTE]
> सिर्फ़ triager `record_bug` बुला सकता है; कोई सबएजेंट रन शुरू या ख़त्म नहीं कर सकता और न एस्केलेशन का जवाब दे सकता है। एक समय में अधिकतम दो कोड चलाने वाले एजेंट, और म्यूटेशन कभी प्रदर्शन के साथ नहीं। सबएजेंट Claude Code की सुविधा है (Codex `.claude/agents/` को अनदेखा करता है)।

## टूल

| समूह | टूल |
|---|---|
| रन नियंत्रण और ग्राफ़ | `start_run`, `end_run`, `get_status`, `get_report`, `query_graph`, `get_untested`, `get_frontier`, `add_test_idea`, `update_result`, `write_test`, `get_escalations`, `answer_escalation`, `ask_human` |
| मैपिंग | `scan_python_code`, `import_openapi` |
| स्थैतिक विश्लेषण | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| गतिशील परीक्षण | `run_pytest`, `run_hypothesis`, `run_schemathesis`, `http_request` |
| ऑरेकल और अंतर | `check_crash`, `check_schema`, `check_rule`, `compare_with_git_version` |
| टेस्ट की गुणवत्ता | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| प्रदर्शन | `measure_time_complexity`, `run_benchmark`, `compare_benchmark_with_git_version`, `profile_cpu`, `profile_memory`, `profile_api` |
| बग रिपोर्ट | `fingerprint_bug`, `record_bug`, `confirm_finding` |

## यह कैसे काम करता है

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. होस्ट एक **चार्टर** भेजता है: लक्ष्य, दायरा, ऑरेकल, नियम, बजट।
2. फिर `testing_loop` प्रॉम्प्ट का चक्र चलता है: मैप → स्थैतिक → टेस्ट → ऑरेकल → बग दर्ज → प्रदर्शन → रिपोर्ट।
3. कुछ भी चलाने वाली हर कॉल पहले सुरक्षा नियमों से गुज़रती है। **एस्केलेशन** सिर्फ़ अपनी शाखा रोकता है; होस्ट बाकी पर आगे बढ़ता है।
4. `record_bug` रीप्रो दोबारा चलाता है, फ़िंगरप्रिंट बनाता है और डुप्लिकेट हटाता है। high और critical बग इंसान का इंतज़ार करते हैं।

## जल्दी शुरू करें

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## उपयोग

**Claude Code** — रिपॉज़िटरी की रूट में `.mcp.json` (पहले से मौजूद):

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

फिर अपने एजेंट से कहें: *«bugscout का `testing_loop` प्रॉम्प्ट इस्तेमाल करो और `./my_project` टेस्ट करो»*। (`write_charter` चार्टर लिखने में मदद करता है।)

एक न्यूनतम चार्टर:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

[`examples/`](../../examples) में जानबूझकर बग वाले उदाहरणों (`sample_lib`, `sample_api`) पर आज़माएँ।

## सुरक्षा नियम

| सुरक्षा | व्यवहार |
|---|---|
| दायरा | `scope.include/exclude` से बाहर का लक्ष्य या `allowed_hosts` से बाहर का होस्ट `escalation_required` लौटाता है |
| विनाशकारी | `DELETE/PUT/PATCH` और जोखिम भरे `POST` कुछ भी भेजने से पहले एस्केलेट होते हैं; schemathesis उन्हें छोड़कर बता देता है |
| बजट | स्टेप, अनुरोध, मिनट; 90% पर चेतावनी, 100% पर पूरी तरह रोक |
| अटकना | कुछ स्टेप तक कोई नई खोज न हो तो एक एस्केलेशन उठता है |
| गंभीर बग | `high` / `critical` को पुष्ट माने जाने से पहले `answer_escalation` चाहिए |

## क्या सत्यापित हुआ

> [!WARNING]
> चरण-वार तालिका के लिए [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified) देखें।

* स्वचालित: असली Postgres और असली Docker कंटेनरों के साथ 39 टेस्ट, जिनमें stdio पर स्क्रिप्टेड होस्ट वाला e2e भी है जो दोनों उदाहरणों के सभी जानबूझकर डाले गए बग ढूँढता है।
* एक असली Claude Code सत्र (`claude -p`, `testing_loop` के अनुसार) ने लगभग $0.22 में `sample_api` के दोनों बग ढूँढ लिए। अभी लाइव टेस्ट नहीं हुए: `sample_lib` और Codex। ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## दस्तावेज़

[`docs/REFERENCE.md`](../REFERENCE.md): टूल, चार्टर फ़ील्ड, सैंडबॉक्स · [`examples/`](../../examples): डाले गए बग · [`ci.yml`](../../.github/workflows/ci.yml): CI।

## योगदान

Issue और PR का स्वागत है। तेज़ टेस्ट के लिए `uv run pytest -m "not docker"`, सैंडबॉक्स/ऑरेकल/प्रदर्शन के लिए `uv run pytest -m docker` (एक बार में एक फ़ाइल, खाली मशीन पर)।

## लाइसेंस

[Apache 2.0 लाइसेंस](../../LICENSE)।

## स्टार इतिहास

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>
