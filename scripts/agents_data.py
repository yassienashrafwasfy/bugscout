"""Language-neutral data for the README 'Tools' and 'Subagents' sections, plus the translated labels."""

GROUPS = [  # key, tools (must equal the server registry; tests/test_subagents.py checks it)
    ("core", ["start_run", "end_run", "get_status", "get_report", "query_graph", "get_untested", "get_frontier", "add_test_idea",
              "update_result", "write_test", "get_escalations", "answer_escalation", "ask_human"]),
    ("map", ["scan_python_code", "import_openapi"]),
    ("static", ["run_radon", "run_ruff", "run_mypy", "run_bandit", "run_duplication", "run_vulture"]),
    ("dynamic", ["run_pytest", "run_hypothesis", "run_schemathesis", "http_request"]),
    ("oracle", ["check_crash", "check_schema", "check_rule", "compare_with_git_version"]),
    ("quality", ["run_coverage", "run_mutation", "check_flaky", "dedup_tests"]),
    ("perf", ["measure_time_complexity", "run_benchmark", "compare_benchmark_with_git_version", "profile_cpu", "profile_memory", "profile_api"]),
    ("report", ["fingerprint_bug", "record_bug", "confirm_finding"]),
]
AGENTS = [  # name, headline tools
    ("bugscout-mapper", ["scan_python_code", "import_openapi", "get_untested", "get_frontier"]),
    ("bugscout-static-auditor", ["run_radon", "run_ruff", "run_mypy", "run_bandit", "run_duplication", "run_vulture"]),
    ("bugscout-fuzzer", ["run_hypothesis", "run_schemathesis", "http_request", "run_pytest", "check_crash", "check_schema", "check_rule"]),
    ("bugscout-diff-hunter", ["compare_with_git_version", "compare_benchmark_with_git_version"]),
    ("bugscout-perf-analyst", ["measure_time_complexity", "run_benchmark", "profile_cpu", "profile_memory", "profile_api"]),
    ("bugscout-quality-auditor", ["run_coverage", "run_mutation", "check_flaky", "dedup_tests"]),
    ("bugscout-triager", ["record_bug", "fingerprint_bug", "confirm_finding"]),
]

# per language: tools heading, agents heading, intro, (col subagent, col role, col tools), 8 group labels, 7 roles, note
L = {}
L["en"] = dict(
    th="Tools", ah="Specialized subagents",
    ai="BugScout ships seven Claude Code subagents in [`.claude/agents/`](.claude/agents). Each owns one phase of the `testing_loop` and only the tools that phase needs. Your main session coordinates them and keeps `start_run`, `end_run` and every human escalation.",
    cols=("Subagent", "Role", "Main tools"), tcols=("Group", "Tools"),
    g="Run control & graph|Mapping|Static analysis|Dynamic testing|Oracles & diffs|Test quality|Performance|Bug reports",
    r="Maps the target and ranks what to test|Runs the static analysers and keeps the real findings|Hypothesis, schemathesis and HTTP probes; reproduces failures|Behaviour and speed changes against an older git ref|Time complexity, CPU, memory, API latency|Coverage, mutation score, flaky and duplicate tests|Judges candidates and is the only one that records bugs",
    note="Only the triager can call `record_bug`; no subagent can start or end a run or answer an escalation. Run at most two executing agents at a time and never mutation with performance. Subagents are a Claude Code feature (Codex ignores `.claude/agents/`).")
L["ar"] = dict(
    th="الأدوات", ah="الوكلاء الفرعيون المتخصصون",
    ai="يضم BugScout سبعة وكلاء فرعيين لـ Claude Code في [`.claude/agents/`](../../.claude/agents). يتولى كل منهم مرحلة واحدة من `testing_loop` ولا يملك إلا الأدوات التي تحتاجها تلك المرحلة. جلستك الرئيسية تنسّق بينهم وتحتفظ بـ `start_run` و`end_run` وكل تصعيد يحتاج إنسانًا.",
    cols=("الوكيل", "الدور", "أهم الأدوات"), tcols=("المجموعة", "الأدوات"),
    g="إدارة التشغيل والرسم البياني|رسم الخريطة|التحليل الساكن|الاختبار الديناميكي|المعايير والمقارنات|جودة الاختبارات|الأداء|تقارير الأخطاء",
    r="يرسم خريطة الهدف ويرتّب ما يُختبر|يشغّل المحللات الساكنة ويُبقي النتائج الحقيقية|Hypothesis وschemathesis وطلبات HTTP ويعيد إنتاج الإخفاقات|تغيّر السلوك والسرعة مقارنةً بإيداع git أقدم|التعقيد الزمني والمعالج والذاكرة وزمن الاستجابة|التغطية ونتيجة الطفرات والاختبارات المتذبذبة والمكررة|يحكم على المرشَّحين وهو الوحيد الذي يسجّل الأخطاء",
    note="وحده المُصنِّف (triager) يستطيع استدعاء `record_bug`؛ ولا يستطيع أي وكيل فرعي بدء تشغيل أو إنهاءه أو الإجابة عن تصعيد. شغّل وكيلين منفّذين على الأكثر في وقت واحد، ولا تجمع اختبار الطفرات مع الأداء. الوكلاء الفرعيون ميزة في Claude Code (ولا يقرأ Codex المجلد `.claude/agents/`).")
L["ar-EG"] = dict(L["ar"],
    ai="BugScout جايب معاه سبع وكلاء فرعيين لـ Claude Code في [`.claude/agents/`](../../.claude/agents). كل واحد منهم مسؤول عن مرحلة واحدة من `testing_loop` ومعاه بس الأدوات اللي المرحلة دي محتاجاها. الجلسة الرئيسية بتنسّق بينهم وبتفضل ماسكة `start_run` و`end_run` وأي تصعيد محتاج إنسان.",
    cols=("الوكيل", "دوره", "أهم الأدوات"), tcols=("المجموعة", "الأدوات"),
    r="بيرسم خريطة الهدف ويرتّب إيه اللي يتختبر|بيشغّل المحللات الساكنة ويسيب النتايج الحقيقية بس|Hypothesis وschemathesis وطلبات HTTP وبيعيد إنتاج الفشل|التغيّر في السلوك والسرعة قدام كوميت أقدم|التعقيد الزمني والمعالج والرامات وزمن الاستجابة|التغطية ونتيجة الطفرات والاختبارات المتقلّبة والمكررة|بيحكم على المرشّحين وهو الوحيد اللي بيسجّل البجز",
    note="الـ triager لوحده اللي يقدر ينادي `record_bug`؛ ومفيش وكيل فرعي يقدر يبدأ تشغيل أو ينهيه أو يرد على تصعيد. شغّل وكيلين منفّذين بالكتير في نفس الوقت، ومتجمعش اختبار الطفرات مع الأداء. الوكلاء الفرعيين ميزة في Claude Code (و Codex مبيقراش `.claude/agents/`).")
L["ar-GULF"] = dict(L["ar"],
    ai="يجي BugScout مع سبع وكلاء فرعيين لـ Claude Code في [`.claude/agents/`](../../.claude/agents). كل واحد مسؤول عن مرحلة وحدة من `testing_loop` وما عنده إلا الأدوات اللي تحتاجها هالمرحلة. الجلسة الرئيسية تنسّق بينهم وتبقى ماسكة `start_run` و`end_run` وأي تصعيد يحتاج إنسان.",
    r="يرسم خريطة الهدف ويرتّب وش يتختبر|يشغّل المحللات الساكنة ويخلّي النتايج الحقيقية بس|Hypothesis وschemathesis وطلبات HTTP ويعيد إنتاج الفشل|تغيّر السلوك والسرعة مقارنة بكوميت أقدم|التعقيد الزمني والمعالج والذاكرة وزمن الاستجابة|التغطية ونتيجة الطفرات والاختبارات المتذبذبة والمكررة|يحكم على المرشّحين وهو الوحيد اللي يسجّل الأخطاء",
    note="الـ triager وحده يقدر ينادي `record_bug`؛ وما يقدر أي وكيل فرعي يبدأ تشغيل أو ينهيه أو يرد على تصعيد. شغّل وكيلين منفّذين على الأكثر بنفس الوقت، ولا تجمع اختبار الطفرات مع الأداء. الوكلاء الفرعيين ميزة في Claude Code (وCodex ما يقرأ `.claude/agents/`).")
L["ar-LEV"] = dict(L["ar"],
    ai="بيجي BugScout مع سبع وكلاء فرعيين لـ Claude Code بـ [`.claude/agents/`](../../.claude/agents). كل واحد مسؤول عن مرحلة وحدة من `testing_loop` وما معه إلا الأدوات اللي بتحتاجها هالمرحلة. الجلسة الرئيسية بتنسّق بينهم وبتضل ماسكة `start_run` و`end_run` وأي تصعيد بدو إنسان.",
    r="بيرسم خريطة الهدف وبيرتّب شو لازم ينختبر|بيشغّل المحللات الساكنة وبيخلّي النتايج الحقيقية بس|Hypothesis وschemathesis وطلبات HTTP وبيعيد إنتاج الفشل|تغيّر السلوك والسرعة مقارنة بكوميت أقدم|التعقيد الزمني والمعالج والذاكرة وزمن الاستجابة|التغطية ونتيجة الطفرات والاختبارات المتقلبة والمكررة|بيحكم عالمرشّحين وهو الوحيد اللي بيسجّل الأخطاء",
    note="الـ triager لحاله بيقدر ينادي `record_bug`؛ وما في أي وكيل فرعي بيقدر يبدأ تشغيل أو ينهيه أو يرد على تصعيد. شغّل وكيلين منفّذين على الأكتر بنفس الوقت، وما تجمع اختبار الطفرات مع الأداء. الوكلاء الفرعيين ميزة بـ Claude Code (وCodex ما بيقرا `.claude/agents/`).")
L["ar-MAG"] = dict(L["ar"],
    ai="BugScout جايب معاه سبعة د الوكلاء الفرعيين ديال Claude Code فـ [`.claude/agents/`](../../.claude/agents). كل واحد مسؤول على مرحلة وحدة من `testing_loop` وما عندو غير الأدوات اللي خاصها هاد المرحلة. الجلسة الرئيسية كتنسّق بيناتهم وكتبقى ماسكة `start_run` و`end_run` وأي تصعيد خاصو إنسان.",
    r="كيرسم خريطة الهدف وكيرتّب شنو غادي يتجرّب|كيشغّل المحللات الساكنة وكيخلّي النتايج الحقيقية غير|Hypothesis وschemathesis وطلبات HTTP وكيعاود إنتاج الفشل|تبدّل السلوك والسرعة بالمقارنة مع كوميت أقدم|التعقيد الزمني والمعالج والذاكرة وزمن الاستجابة|التغطية ونتيجة الطفرات والاختبارات المتقلبة والمعاودة|كيحكم على المرشّحين وهو الوحيد اللي كيسجّل البوغات",
    note="الـ triager بوحدو اللي يقدر يعيّط على `record_bug`؛ وحتى وكيل فرعي ما يقدر يبدا تشغيل ولا ينهيه ولا يجاوب على تصعيد. دير وكيلين منفّذين فالكتر فنفس الوقت، وما تجمعش اختبار الطفرات مع الأداء. الوكلاء الفرعيين ميزة فـ Claude Code (وCodex ما كيقراش `.claude/agents/`).")
L["es"] = dict(
    th="Herramientas", ah="Subagentes especializados",
    ai="BugScout incluye siete subagentes de Claude Code en [`.claude/agents/`](../../.claude/agents). Cada uno se encarga de una fase del `testing_loop` y solo tiene las herramientas que esa fase necesita. Tu sesión principal los coordina y conserva `start_run`, `end_run` y toda escalada a una persona.",
    cols=("Subagente", "Función", "Herramientas principales"), tcols=("Grupo", "Herramientas"),
    g="Control de ejecución y grafo|Mapeo|Análisis estático|Pruebas dinámicas|Oráculos y diferencias|Calidad de las pruebas|Rendimiento|Informes de bugs",
    r="Mapea el objetivo y ordena qué probar|Ejecuta los analizadores estáticos y conserva los hallazgos reales|Hypothesis, schemathesis y sondas HTTP; reproduce fallos|Cambios de comportamiento y velocidad frente a una referencia git|Complejidad temporal, CPU, memoria, latencia de API|Cobertura, mutación, pruebas inestables y duplicadas|Juzga los candidatos y es el único que registra bugs",
    note="Solo el triager puede llamar a `record_bug`; ningún subagente puede iniciar ni terminar una ejecución ni responder una escalada. Ejecuta como máximo dos agentes que ejecuten código a la vez y nunca mutación junto con rendimiento. Los subagentes son una función de Claude Code (Codex ignora `.claude/agents/`).")
L["fr"] = dict(
    th="Outils", ah="Sous-agents spécialisés",
    ai="BugScout fournit sept sous-agents Claude Code dans [`.claude/agents/`](../../.claude/agents). Chacun prend en charge une phase du `testing_loop` avec uniquement les outils nécessaires. Votre session principale les coordonne et garde `start_run`, `end_run` et toute escalade vers un humain.",
    cols=("Sous-agent", "Rôle", "Outils principaux"), tcols=("Groupe", "Outils"),
    g="Pilotage du run et graphe|Cartographie|Analyse statique|Tests dynamiques|Oracles et différences|Qualité des tests|Performance|Rapports de bugs",
    r="Cartographie la cible et classe ce qu'il faut tester|Lance les analyseurs statiques et garde les vrais résultats|Hypothesis, schemathesis et sondes HTTP ; reproduit les échecs|Changements de comportement et de vitesse face à une référence git|Complexité temporelle, CPU, mémoire, latence d'API|Couverture, mutation, tests instables et en double|Juge les candidats et seul à enregistrer les bugs",
    note="Seul le triager peut appeler `record_bug` ; aucun sous-agent ne peut démarrer ou terminer un run ni répondre à une escalade. Deux agents exécutants au maximum en même temps, et jamais de mutation avec la performance. Les sous-agents sont une fonction de Claude Code (Codex ignore `.claude/agents/`).")
L["de"] = dict(
    th="Werkzeuge", ah="Spezialisierte Subagenten",
    ai="BugScout liefert sieben Claude-Code-Subagenten in [`.claude/agents/`](../../.claude/agents) mit. Jeder ist für eine Phase des `testing_loop` zuständig und erhält nur die dafür nötigen Werkzeuge. Deine Hauptsitzung koordiniert sie und behält `start_run`, `end_run` und jede Eskalation an Menschen.",
    cols=("Subagent", "Rolle", "Wichtigste Werkzeuge"), tcols=("Gruppe", "Werkzeuge"),
    g="Lauf-Steuerung und Graph|Kartierung|Statische Analyse|Dynamisches Testen|Orakel und Diffs|Testqualität|Performance|Bug-Berichte",
    r="Kartiert das Ziel und priorisiert, was getestet wird|Führt die statischen Analysatoren aus und behält die echten Funde|Hypothesis, schemathesis und HTTP-Proben; reproduziert Fehler|Verhaltens- und Tempoänderungen gegenüber einer älteren Git-Referenz|Zeitkomplexität, CPU, Speicher, API-Latenz|Abdeckung, Mutation, instabile und doppelte Tests|Beurteilt Kandidaten und erfasst als Einziger Bugs",
    note="Nur der Triager darf `record_bug` aufrufen; kein Subagent kann einen Lauf starten oder beenden oder eine Eskalation beantworten. Höchstens zwei ausführende Agenten gleichzeitig und nie Mutation zusammen mit Performance. Subagenten sind ein Claude-Code-Feature (Codex ignoriert `.claude/agents/`).")
L["pt"] = dict(
    th="Ferramentas", ah="Subagentes especializados",
    ai="O BugScout inclui sete subagentes do Claude Code em [`.claude/agents/`](../../.claude/agents). Cada um cuida de uma fase do `testing_loop` e tem só as ferramentas que ela precisa. Sua sessão principal os coordena e mantém `start_run`, `end_run` e toda escalada para uma pessoa.",
    cols=("Subagente", "Função", "Principais ferramentas"), tcols=("Grupo", "Ferramentas"),
    g="Controle da execução e grafo|Mapeamento|Análise estática|Testes dinâmicos|Oráculos e diferenças|Qualidade dos testes|Desempenho|Relatórios de bugs",
    r="Mapeia o alvo e ordena o que testar|Roda os analisadores estáticos e mantém os achados reais|Hypothesis, schemathesis e sondas HTTP; reproduz falhas|Mudanças de comportamento e velocidade contra uma referência git|Complexidade de tempo, CPU, memória, latência da API|Cobertura, mutação, testes instáveis e duplicados|Julga os candidatos e é o único que registra bugs",
    note="Só o triager pode chamar `record_bug`; nenhum subagente pode iniciar ou encerrar uma execução nem responder a uma escalada. No máximo dois agentes que executam código ao mesmo tempo, e nunca mutação junto com desempenho. Subagentes são um recurso do Claude Code (o Codex ignora `.claude/agents/`).")
L["zh"] = dict(
    th="工具", ah="专业子代理",
    ai="BugScout 在 [`.claude/agents/`](../../.claude/agents) 中附带七个 Claude Code 子代理。每个子代理负责 `testing_loop` 的一个阶段，只拥有该阶段所需的工具。你的主会话负责协调它们，并保留 `start_run`、`end_run` 以及所有需要人工处理的升级。",
    cols=("子代理", "职责", "主要工具"), tcols=("分组", "工具"),
    g="运行控制与图|映射|静态分析|动态测试|判定与差异|测试质量|性能|Bug 报告",
    r="映射目标并排序待测内容|运行静态分析器，保留真实问题|Hypothesis、schemathesis 和 HTTP 探测；复现失败|相对旧 git 引用的行为与速度变化|时间复杂度、CPU、内存、API 延迟|覆盖率、变异得分、不稳定与重复测试|评判候选项，是唯一可记录 Bug 的角色",
    note="只有 triager 可以调用 `record_bug`；任何子代理都不能开始或结束运行，也不能回答升级。同一时间最多运行两个会执行代码的代理，且绝不同时做变异测试和性能测试。子代理是 Claude Code 的功能（Codex 会忽略 `.claude/agents/`）。")
L["ja"] = dict(
    th="ツール", ah="専門サブエージェント",
    ai="BugScout は [`.claude/agents/`](../../.claude/agents) に Claude Code 用のサブエージェントを 7 つ同梱しています。それぞれが `testing_loop` の 1 フェーズを担当し、そのフェーズに必要なツールだけを持ちます。メインセッションが調整役となり、`start_run`、`end_run`、人手が必要なエスカレーションはすべてメインが保持します。",
    cols=("サブエージェント", "役割", "主なツール"), tcols=("グループ", "ツール"),
    g="実行制御とグラフ|マッピング|静的解析|動的テスト|オラクルと差分|テスト品質|パフォーマンス|バグレポート",
    r="対象をマップし、テストの優先順位を付ける|静的解析を実行し、本物の指摘だけを残す|Hypothesis・schemathesis・HTTP プローブ。失敗を再現する|古い git 参照との挙動・速度の変化|時間計算量、CPU、メモリ、API レイテンシ|カバレッジ、ミューテーション、不安定・重複テスト|候補を判定し、バグを記録できる唯一の役",
    note="`record_bug` を呼べるのは triager だけです。どのサブエージェントも実行の開始・終了やエスカレーションへの回答はできません。コードを実行するエージェントは同時に 2 つまで、ミューテーションとパフォーマンスは同時に走らせないでください。サブエージェントは Claude Code の機能です（Codex は `.claude/agents/` を無視します）。")
L["ru"] = dict(
    th="Инструменты", ah="Специализированные субагенты",
    ai="BugScout поставляет семь субагентов Claude Code в [`.claude/agents/`](../../.claude/agents). Каждый отвечает за одну фазу `testing_loop` и получает только нужные ей инструменты. Ваша основная сессия координирует их и оставляет за собой `start_run`, `end_run` и все эскалации к человеку.",
    cols=("Субагент", "Роль", "Основные инструменты"), tcols=("Группа", "Инструменты"),
    g="Управление запуском и граф|Картирование|Статический анализ|Динамическое тестирование|Оракулы и различия|Качество тестов|Производительность|Отчёты о багах",
    r="Строит карту цели и ранжирует, что тестировать|Запускает статические анализаторы и оставляет реальные находки|Hypothesis, schemathesis и HTTP-пробы; воспроизводит сбои|Изменения поведения и скорости относительно старого git-ref|Временная сложность, CPU, память, задержка API|Покрытие, мутации, нестабильные и дублирующиеся тесты|Оценивает кандидатов и единственный записывает баги",
    note="Вызывать `record_bug` может только triager; ни один субагент не может начать или завершить запуск и отвечать на эскалации. Одновременно — не больше двух исполняющих агентов, и никогда мутации вместе с производительностью. Субагенты — функция Claude Code (Codex игнорирует `.claude/agents/`).")
L["hi"] = dict(
    th="टूल", ah="विशेषज्ञ सबएजेंट",
    ai="BugScout [`.claude/agents/`](../../.claude/agents) में Claude Code के सात सबएजेंट के साथ आता है। हर एक `testing_loop` का एक चरण संभालता है और उसके पास सिर्फ़ उसी चरण के टूल होते हैं। आपका मुख्य सत्र इन्हें समन्वित करता है और `start_run`, `end_run` तथा इंसान की ज़रूरत वाले हर एस्केलेशन को अपने पास रखता है।",
    cols=("सबएजेंट", "भूमिका", "मुख्य टूल"), tcols=("समूह", "टूल"),
    g="रन नियंत्रण और ग्राफ़|मैपिंग|स्थैतिक विश्लेषण|गतिशील परीक्षण|ऑरेकल और अंतर|टेस्ट की गुणवत्ता|प्रदर्शन|बग रिपोर्ट",
    r="लक्ष्य का नक्शा बनाता है और तय करता है क्या टेस्ट हो|स्थैतिक विश्लेषक चलाता है और असली नतीजे रखता है|Hypothesis, schemathesis और HTTP प्रोब; विफलताएँ दोहराता है|पुराने git संदर्भ की तुलना में व्यवहार और गति में बदलाव|समय-जटिलता, CPU, मेमोरी, API विलंब|कवरेज, म्यूटेशन, अस्थिर और दोहराए गए टेस्ट|उम्मीदवारों को परखता है और अकेला बग दर्ज करता है",
    note="सिर्फ़ triager `record_bug` बुला सकता है; कोई सबएजेंट रन शुरू या ख़त्म नहीं कर सकता और न एस्केलेशन का जवाब दे सकता है। एक समय में अधिकतम दो कोड चलाने वाले एजेंट, और म्यूटेशन कभी प्रदर्शन के साथ नहीं। सबएजेंट Claude Code की सुविधा है (Codex `.claude/agents/` को अनदेखा करता है)।")
L["tr"] = dict(
    th="Araçlar", ah="Uzmanlaşmış alt ajanlar",
    ai="BugScout, [`.claude/agents/`](../../.claude/agents) içinde yedi Claude Code alt ajanıyla gelir. Her biri `testing_loop`'un bir aşamasından sorumludur ve yalnızca o aşamanın araçlarına sahiptir. Ana oturumunuz onları koordine eder; `start_run`, `end_run` ve insan gerektiren her yükseltme ana oturumda kalır.",
    cols=("Alt ajan", "Rol", "Ana araçlar"), tcols=("Grup", "Araçlar"),
    g="Çalıştırma kontrolü ve graf|Haritalama|Statik analiz|Dinamik test|Oracle'lar ve farklar|Test kalitesi|Performans|Hata raporları",
    r="Hedefi haritalar, neyin test edileceğini sıralar|Statik analizörleri çalıştırır, gerçek bulguları tutar|Hypothesis, schemathesis ve HTTP probları; hataları yeniden üretir|Eski bir git referansına göre davranış ve hız değişimi|Zaman karmaşıklığı, CPU, bellek, API gecikmesi|Kapsama, mutasyon, kararsız ve yinelenen testler|Adayları değerlendirir ve hata kaydeden tek ajandır",
    note="`record_bug` yalnızca triager tarafından çağrılabilir; hiçbir alt ajan bir çalıştırmayı başlatamaz, bitiremez ya da yükseltmeyi yanıtlayamaz. Aynı anda en fazla iki çalıştırıcı ajan, mutasyon asla performansla birlikte değil. Alt ajanlar bir Claude Code özelliğidir (Codex `.claude/agents/` dizinini yok sayar).")
L["ko"] = dict(
    th="도구", ah="전문 서브에이전트",
    ai="BugScout는 [`.claude/agents/`](../../.claude/agents)에 Claude Code 서브에이전트 7개를 포함합니다. 각각 `testing_loop`의 한 단계를 맡고 그 단계에 필요한 도구만 가집니다. 메인 세션이 이들을 조율하며 `start_run`, `end_run`, 사람이 필요한 모든 에스컬레이션은 메인이 보유합니다.",
    cols=("서브에이전트", "역할", "주요 도구"), tcols=("그룹", "도구"),
    g="실행 제어와 그래프|매핑|정적 분석|동적 테스트|오라클과 차이|테스트 품질|성능|버그 리포트",
    r="대상을 매핑하고 테스트할 것의 순서를 정함|정적 분석기를 실행하고 실제 문제만 남김|Hypothesis, schemathesis, HTTP 프로브. 실패를 재현|이전 git 기준과 비교한 동작·속도 변화|시간 복잡도, CPU, 메모리, API 지연|커버리지, 뮤테이션, 불안정·중복 테스트|후보를 판정하며 버그를 기록할 수 있는 유일한 에이전트",
    note="`record_bug`는 triager만 호출할 수 있습니다. 어떤 서브에이전트도 실행을 시작·종료하거나 에스컬레이션에 답할 수 없습니다. 코드를 실행하는 에이전트는 동시에 최대 2개, 뮤테이션은 성능 작업과 절대 함께 돌리지 마세요. 서브에이전트는 Claude Code 기능입니다(Codex는 `.claude/agents/`를 무시합니다).")
