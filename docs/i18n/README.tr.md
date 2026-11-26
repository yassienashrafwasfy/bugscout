<div align="center">

# 🐞 BugScout

**Yapay zekânın hata avlamasına izin ver — güvenle, Docker içinde, kanıtlarla.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](../../pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)](https://modelcontextprotocol.io)
[![FastMCP](https://img.shields.io/badge/built_with-FastMCP-orange)](https://gofastmcp.com)
[![Docker sandbox](https://img.shields.io/badge/runs_in-Docker-2496ED?logo=docker&logoColor=white)](../../sandbox/Dockerfile)
[![PostgreSQL](https://img.shields.io/badge/state-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](../../migrations)
[![CI](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml/badge.svg)](https://github.com/yassienashrafwasfy/bugscout/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yassienashrafwasfy/bugscout?style=social)](https://github.com/yassienashrafwasfy/bugscout/stargazers)

[English](../../README.md) · [العربية](README.ar.md) · [مصري](README.ar-EG.md) · [خليجي](README.ar-GULF.md) · [شامي](README.ar-LEV.md) · [الدارجة](README.ar-MAG.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt.md) · [中文](README.zh.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · [हिन्दी](README.hi.md) · **Türkçe** · [한국어](README.ko.md)

</div>

---

## Buna neden ihtiyacınız var

Bir yapay zekâ ajanından «kodumu test et» dediğinizde genelde üç şeyden biri olur: güvenilmeyen kodu makinenizde çalıştırır, daha önce denediklerini unutup kendini tekrar eder ya da kararsız bir testi «hata» diye raporlar. BugScout eksik olan altyapıdır:

| Yalnız bir ajanın sorunu | BugScout ne yapar |
|---|---|
| Hedef kodu dizüstünüzde çalıştırır | Hedef kodu çalıştıran her şey kısıtlı bir **Docker** sanal alanında çalışır (ağ yok, yetkiler kaldırılmış, CPU/bellek sınırları) |
| Belleği yoktur, kendini tekrar eder | Postgres'te **varlık grafı** ve yalnızca eklemeli **keşif ağacı**; yinelenen fikir mevcut düğümü döndürür |
| «Ne olacağına bakmak» için `DELETE /users` çağırır | **Sunucu tarafı korumalar**: kapsam, yıkıcı eylemler, bütçe, takılma tespiti, ciddi hatalar için insan onayı |
| Kararsız başarısızlıkları hata diye bildirir | Her başarısızlık **sayılmadan önce yeniden çalıştırılır**; tekrarlanmazsa `flaky` olur, aynı hata 20 kez bulunsa da tek bulgudur |

> [!NOTE]
> Planı siz (daha doğrusu LLM ana makinesi: Claude Code, Codex) yaparsınız. BugScout saklar, çalıştırır, denetler ve kuralları zorunlu kılar.

## Ne yapar

* **Haritalar:** bir Python paketini veya OpenAPI belirtimini fonksiyon, sınıf, uç nokta ve ilişkilerden oluşan grafa dönüştürür.
* **Statik aşama:** karmaşıklık (radon), lint (ruff), tipler (mypy), güvenlik (bandit), kopyala-yapıştır ve ölü kod (vulture).
* **Dinamik aşama:** pytest, Hypothesis özellik testleri, schemathesis, elle HTTP istekleri ve kendi kurallarınız.
* **Kehanetler (oracle):** çökme / HTTP 5xx, yanıt şeması, önceki git commit'iyle davranış farkı, kendi değişmezleriniz.
* **Kalite:** fonksiyon ve test başına kapsama, mutasyon skoru, kararsız ve yinelenen testlerin tespiti.
* **Performans:** ampirik zaman karmaşıklığı (izin verilen O(n log n)'e karşı O(n²)), commit'ler arası gerilemeler, CPU sıcak noktaları, bellek tüketimi, API profili.
* **Raporlar:** tekrarsız sonuç: hatalar, statik sorunlar, kapsama, sıcak noktalar, gerilemeler.

42 tools · 7 read-only resources (`run://{id}/…`) · 3 prompts (`testing_loop`, `write_charter`, `triage_bug`)

## Uzmanlaşmış alt ajanlar

BugScout, [`.claude/agents/`](../../.claude/agents) içinde yedi Claude Code alt ajanıyla gelir. Her biri `testing_loop`'un bir aşamasından sorumludur ve yalnızca o aşamanın araçlarına sahiptir. Ana oturumunuz onları koordine eder; `start_run`, `end_run` ve insan gerektiren her yükseltme ana oturumda kalır.

| Alt ajan | Rol | Ana araçlar |
|---|---|---|
| [`bugscout-mapper`](../../.claude/agents/bugscout-mapper.md) | Hedefi haritalar, neyin test edileceğini sıralar | `scan_python_code`, `import_openapi`, `get_untested`, `get_frontier` |
| [`bugscout-static-auditor`](../../.claude/agents/bugscout-static-auditor.md) | Statik analizörleri çalıştırır, gerçek bulguları tutar | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| [`bugscout-fuzzer`](../../.claude/agents/bugscout-fuzzer.md) | Hypothesis, schemathesis ve HTTP probları; hataları yeniden üretir | `run_hypothesis`, `run_schemathesis`, `http_request`, `run_pytest`, `check_crash`, `check_schema`, `check_rule` |
| [`bugscout-diff-hunter`](../../.claude/agents/bugscout-diff-hunter.md) | Eski bir git referansına göre davranış ve hız değişimi | `compare_with_git_version`, `compare_benchmark_with_git_version` |
| [`bugscout-perf-analyst`](../../.claude/agents/bugscout-perf-analyst.md) | Zaman karmaşıklığı, CPU, bellek, API gecikmesi | `measure_time_complexity`, `run_benchmark`, `profile_cpu`, `profile_memory`, `profile_api` |
| [`bugscout-quality-auditor`](../../.claude/agents/bugscout-quality-auditor.md) | Kapsama, mutasyon, kararsız ve yinelenen testler | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| [`bugscout-triager`](../../.claude/agents/bugscout-triager.md) | Adayları değerlendirir ve hata kaydeden tek ajandır | `record_bug`, `fingerprint_bug`, `confirm_finding` |

> [!NOTE]
> `record_bug` yalnızca triager tarafından çağrılabilir; hiçbir alt ajan bir çalıştırmayı başlatamaz, bitiremez ya da yükseltmeyi yanıtlayamaz. Aynı anda en fazla iki çalıştırıcı ajan, mutasyon asla performansla birlikte değil. Alt ajanlar bir Claude Code özelliğidir (Codex `.claude/agents/` dizinini yok sayar).

## Araçlar

| Grup | Araçlar |
|---|---|
| Çalıştırma kontrolü ve graf | `start_run`, `end_run`, `get_status`, `get_report`, `query_graph`, `get_untested`, `get_frontier`, `add_test_idea`, `update_result`, `write_test`, `get_escalations`, `answer_escalation`, `ask_human` |
| Haritalama | `scan_python_code`, `import_openapi` |
| Statik analiz | `run_radon`, `run_ruff`, `run_mypy`, `run_bandit`, `run_duplication`, `run_vulture` |
| Dinamik test | `run_pytest`, `run_hypothesis`, `run_schemathesis`, `http_request` |
| Oracle'lar ve farklar | `check_crash`, `check_schema`, `check_rule`, `compare_with_git_version` |
| Test kalitesi | `run_coverage`, `run_mutation`, `check_flaky`, `dedup_tests` |
| Performans | `measure_time_complexity`, `run_benchmark`, `compare_benchmark_with_git_version`, `profile_cpu`, `profile_memory`, `profile_api` |
| Hata raporları | `fingerprint_bug`, `record_bug`, `confirm_finding` |

## Nasıl çalışır

```
host (Claude Code / Codex)  ──MCP──▶  BugScout (FastMCP)
                                       ├─ Postgres  runs · asset graph · exploration tree · findings
                                       ├─ guards    scope · destructive · budget · stuck · serious-bug
                                       └─ Docker    bench · sut · ref
```

1. Ana makine bir **şart** (charter) gönderir: hedef, kapsam, oracle'lar, kurallar, bütçe.
2. `testing_loop` isteminin döngüsünü izler: harita → statik → testler → oracle'lar → hata kaydı → performans → rapor.
3. Bir şey çalıştıran her çağrı önce korumalardan geçer. **Yükseltme** yalnızca kendi dalını durdurur; ana makine diğerlerinde devam eder.
4. `record_bug` tekrar adımlarını yeniden çalıştırır, parmak izi çıkarır ve yinelenenleri eler. Yüksek ve kritik hatalar bir insanı bekler.

## Hızlı başlangıç

```bash
git clone https://github.com/yassienashrafwasfy/bugscout && cd bugscout
docker compose up -d postgres
docker build -t bugscout-sandbox:latest sandbox
uv sync
uv run bugscout
```

## Kullanım

**Claude Code** — depo kökündeki `.mcp.json` (hazır geliyor):

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

Sonra ajanınıza şunu söyleyin: *«bugscout'taki `testing_loop` istemini kullan ve `./my_project` projesini test et»*. (`write_charter` şartı yazmanıza yardım eder.)

En küçük şart:

```json
{ "target": {"kind": "python", "repo_path": "/path/to/repo", "package": "mypkg"},
  "scope": {"include": ["mypkg/*"], "exclude": []},
  "oracles": ["crash", "diff_git", "rule"],
  "reference": {"git_ref": "HEAD~1"},
  "budget": {"max_steps": 300, "max_requests": 1000, "max_minutes": 60} }
```

[`examples/`](../../examples) içindeki kasıtlı hatalı örneklerde deneyin (`sample_lib`, `sample_api`).

## Güvenlik önlemleri

| Koruma | Davranış |
|---|---|
| Kapsam | `scope.include/exclude` dışındaki bir hedef ya da `allowed_hosts` dışındaki bir ana makine `escalation_required` döndürür |
| Yıkıcı | `DELETE/PUT/PATCH` ve riskli `POST`'lar hiçbir şey gönderilmeden önce yükseltilir; schemathesis bunları atlar ve söyler |
| Bütçe | Adımlar, istekler, dakikalar; %90'da uyarı, %100'de kesin durdurma |
| Takılma | Bir adım penceresinde yeni bulgu olmaması tek bir yükseltme tetikler |
| Ciddi hata | `high` / `critical` onaylanmış sayılmadan önce `answer_escalation` gerektirir |

## Nelerin doğrulandığı

> [!WARNING]
> Aşama aşama tablo için [`docs/REFERENCE.md`](../REFERENCE.md#what-was-and-was-not-verified) dosyasına bakın.

* Otomatik: gerçek Postgres ve gerçek Docker kapsayıcılarıyla 39 test; bunların arasında iki örnekteki tüm kasıtlı hataları bulan, stdio üzerinden betikli ana makineli bir uçtan uca test var.
* Gerçek bir Claude Code oturumu (`testing_loop`'u izleyen `claude -p`) `sample_api` içindeki iki kasıtlı hatayı yaklaşık 0,22 $'a buldu. Henüz canlı denenmedi: `sample_lib` ve Codex. ([docs/LIVE_RUN.md](../LIVE_RUN.md))

## Dokümantasyon

[`docs/REFERENCE.md`](../REFERENCE.md): araçlar, şart alanları, sanal alan · [`examples/`](../../examples): kasıtlı hatalar · [`ci.yml`](../../.github/workflows/ci.yml): CI.

## Katkı

Issue ve PR'lar memnuniyetle karşılanır. Hızlı set için `uv run pytest -m "not docker"`, sanal alan/oracle/performans için `uv run pytest -m docker` (her seferinde tek dosya, boştaki bir makinede).

## Lisans

[Apache 2.0 Lisansı](../../LICENSE).

## Yıldız geçmişi

<a href="https://star-history.com/#yassienashrafwasfy/bugscout&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
    <img alt="Star history chart" src="https://api.star-history.com/svg?repos=yassienashrafwasfy/bugscout&type=Date" />
  </picture>
</a>
