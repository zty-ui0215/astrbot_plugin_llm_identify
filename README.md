# LLM Identify

**GitHub language links:** [中文](#中文) | [English](#english) | [日本語](#日本語)
请注意，不要在astrbot内点击以上三个语言切换键，会导致文档异常退出


<a id="中文"></a>

<details open>
<summary>中文</summary>

## 中文

### 这是什么

LLM Identify 是一个 AstrBot 插件，用来对 LLM 接口做概率式黑盒审计。它不会证明“真实模型一定是谁”，而是通过多种探测判断一个接口是否像它声称的模型、是否可能经过代理或包装、Token 计量是否可信、上下文能力是否和声明一致，以及多次请求是否可能被路由到不同后端。

它适合普通用户检查自己的模型配置，也适合开发者、API 中转服务使用者和需要定期核查模型供应链的人使用。

### 已实现功能

- 快速审计：用少量协议探测检查当前或指定 AstrBot 模型的基础接口行为。
- 完整审计：增加 Token 计量、指纹、上下文和多分支证据，输出更完整的风险报告。
- Web 面板：在插件页面中运行审计、选择模型、查看分数、候选概率、探测详情和文本报告。
- 模型选择：Page 面板可以从当前 AstrBot 已配置的所有模型中选择审计目标，不局限于当前对话模型。
- 直连审计：可以填写 Base URL、API Key 和模型名，审计 OpenAI 兼容端点。
- 多语言：页面默认跟随宿主语言；支持中文、日文、英文，其他语言回退为英文。
- 本地化报告：聊天指令和页面报告都可以输出中文、日文或英文。
- 可信参考语料：内置紧凑参考语料，也支持额外本地或远程 JSON 语料。
- 外部证据：可选接入公共指纹库、辅助 LLM 裁判和本地动态指纹记录。
- 隐私保护：以合成探测为主，持久化 trace 前会做脱敏。

### 快速使用

聊天指令：

```text
/llmid
/llmid full
/llmid help
/llmid zh
/llmid ja
/llmid full zh
```

- `/llmid`：快速审计当前对话模型。
- `/llmid full`：完整审计当前对话模型。
- `/llmid zh`、`/llmid ja`、`/llmid en`：指定本次报告语言。

Web 面板：

1. 打开插件详情页中的 LLM Identify 页面。
2. 选择页面语言。默认会跟随宿主语言。
3. 选择一个 AstrBot 已配置模型，或切换到直连 OpenAI 兼容端点。
4. 选择快速或完整审计。
5. 点击运行，查看风险等级、置信度、候选模型家族、探测证据和文本报告。

### 常用配置

- `default_timeout`：每个探测请求的超时时间。
- `page_provider_id`：Page 默认使用的 provider ID。留空时自动寻找可用模型。
- `enable_token_probe`：是否默认启用 Token 探测。完整审计始终启用。
- `enable_fingerprint_probe`：是否默认启用指纹探测。完整审计始终启用。
- `fingerprint_profile`：指纹探测广度，支持 `light`、`standard`、`exhaustive`。
- `fingerprint_repeats`：每个指纹探测的重复次数。更高值更稳，但请求更多。
- `strict_mode`：对失败探测施加更保守的置信度惩罚。
- `auxiliary_judge_provider_id` / `auxiliary_judge_provider_ids`：用一个或多个模型作为辅助裁判。
- `public_fingerprint_sources`：公共模型或指纹数据集，本地 JSON 或 HTTPS URL。
- `trusted_corpus_sources`：扩展可信参考语料，本地 JSON 或 HTTPS URL。
- `public_cache_dir`：远程语料和公共指纹源缓存目录。
- `local_fingerprint_libraries`：可选本地指纹库。默认包含免安装的 `bundled:llmmap`。

### 结果怎么看

重点看这些字段：

- `confidence`：综合证据置信度。
- `risk_level`：低、中、高风险。
- `provider_probabilities` / `identity_posterior`：更像哪些模型家族。
- `proxy_probability`：代理、包装或中转可能性。
- `mixture_probability`：混合路由可能性。
- `token_truth_score`：Token 计量是否可信。
- `fingerprint_confidence`：指纹证据强度。
- `spoofing_risk`：伪装或行为模仿风险。
- `findings`：主要发现。
- `probe_results`：每个探测的状态、分数和说明。

请把结果理解为“可观测证据下的风险判断”。如果接口有缓存、中转、RAG、安全层、量化、模型热更新或动态路由，结果可能波动。重要场景建议多次运行，并结合服务商日志一起判断。

### Page API

```text
GET  /astrbot_plugin_llm_identify/page/status
POST /astrbot_plugin_llm_identify/page/detect
GET  /astrbot_plugin_llm_identify/page/health
GET  /astrbot_plugin_llm_identify/page/audits
POST /astrbot_plugin_llm_identify/page/audits
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>/report
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>/events
POST /astrbot_plugin_llm_identify/page/baselines/refresh
GET  /astrbot_plugin_llm_identify/page/drift/<target_id>
POST /astrbot_plugin_llm_identify/page/export/<task_id>
```

当前页面会通过 `/status` 获取运行状态、可选模型列表和最近报告，通过 `/detect` 触发审计。

### 实现方法

插件采用“审计核心 + 宿主适配层”的结构：

- `main.py`：插件入口、聊天指令、Page API、provider 枚举和模型调用。
- `pages/模型检测面板/`：Web 面板 UI、语言切换、模型选择、审计触发和结果渲染。
- `llm_identify/adapters/`：宿主模型和直连 OpenAI 兼容端点适配器。
- `llm_identify/probes/`：协议、Token、上下文和指纹探测包。
- `llm_identify/capture/`：trace 捕获、请求/响应摘要和元数据记录。
- `llm_identify/features/`：Token 与指纹特征提取。
- `llm_identify/scoring/`：证据融合、风险计算、候选生成和文本报告。
- `llm_identify/corpus.py`：可信参考语料加载、缓存、降级和来源标注。
- `llm_identify/evidence.py`：外部证据源、公共指纹数据和辅助 LLM 裁判。
- `llm_identify/storage.py`：SQLite 任务、报告和 trace 持久化。
- `llm_identify/tasks.py`：任务状态和事件模型。
- `llm_identify/branches.py`：输出统计、上下文、时序、工具调用、Token 真实性和提示注入等分支证据。
- `llm_identify/cli.py`：独立命令行入口。

`core/` 是旧实现遗留目录，新入口不依赖它。

### 证据模型

插件不依赖单一“模型指纹”，而是融合多类弱证据：

- 协议证据：精确输出、JSON 输出、usage 元数据、流式/非流式表面。
- Token 证据：用量是否暴露、输入 Token 单调性、斜率合理性、恒定计数异常、Unicode 行为、缓存信号和输出长度一致性。
- 指纹证据：主动行为探测、知识边界、拒答风格、可见推理结构、分词/Unicode、采样分布、API side channel、静态和动态基线。
- 上下文证据：上下文窗口哨兵、长上下文能力、位置鲁棒性和中途切换迹象。
- 分支证据：输出统计、时序、上下文真实性、工具调用、Token 真实性和提示注入风险。
- 外部证据：可信参考语料、公共指纹库、辅助 LLM 裁判。

融合层会计算模型家族后验、真实性后验、安全风险后验、代理概率、混合路由概率和伪装风险。多方法一致时提高置信度；方法分歧时增加风险，而不是强行给出唯一结论。

### Token、指纹和上下文设计

Token 计量采用分层策略：优先使用 provider 原生计数或官方 tokenizer；没有官方计数时使用本地近似 tokenizer、动态探测和校准；对长文本使用分段、采样和边界修正。报告会区分“精确计数”“可用元数据”和“推断证据”。

指纹审计不只看回答风格，还会观察知识边界、输出结构稳定性、Unicode 和分词行为、拒答风格、流式元数据、finish reason、usage 形状，以及多次采样是否出现明显后端切换。

上下文审计关注实际可用上下文，而不是宣传的最大 token 数。它会区分正常长上下文退化、软摘要、截断和可疑后端切换。

### 可信语料、隐私和存储

内置可信语料保持小型、来源标注和可离线使用。额外语料可以通过本地文件或 HTTPS URL 加载，并缓存到本地。可信参考记录应经过 schema 校验、脱敏、官方端点确认、重复探测和维护者审查。插件不会自动上传数据。

审计默认使用合成探测，避免发送真实用户聊天内容。任务存储会把 trace、特征摘要和报告分开保存，并在持久化前脱敏：邮箱、电话样式文本、API key 样式 token、常见 JSON secret 字段，以及原始敏感值的确定性哈希。日志应只引用任务 ID、trace ID 和报告 ID。

### CLI 与自动化

```text
python -m llm_identify.cli scan --target-id relay-default --base-url https://example.com/v1 --api-key sk-... --model gpt-test --output reports/run-001
python -m llm_identify.cli baselines refresh --providers openai anthropic gemini
python -m llm_identify.cli report export --task-id aud_... --format json --data-dir reports/run-001
python -m llm_identify.cli report plot --out reports/run-001/figures
```

安装 FastAPI 后，`llm_identify.rest.create_app()` 可用于本地自动化服务。

### 限制

- 黑盒审计不能证明真实底层模型，只能给出风险和概率判断。
- 中转服务可以改写 prompt、usage、metadata、输出风格和路由策略。
- 缓存、RAG、安全层、量化、模型热更新和网络抖动都可能影响结果。
- 完整审计会产生更多请求，可能增加 API 成本。
- 辅助 LLM 裁判只作为证据之一，不是权威判断。

### 致谢与参考

本项目未直接复制第三方实现代码。当前实现中最直接使用的是 LLMmap 公开 supported-model metadata 的模型标识和家族信息，并将其作为带来源标注的轻量内置元数据使用；没有内置 LLMmap 的模型权重、训练数据或分类器。

对插件实现帮助最大的资料包括：

- **LLMmap: Fingerprinting for Large Language Models**：主动黑盒指纹探测和 supported-model metadata。
- **KBF: Knowledge Boundary as Fingerprint for Language Model and Black-Box API Auditing**：知识边界、替换审计和混合路由检测思路。
- **Behavioral Fingerprints for LLM Endpoint Stability and Identity**：持续监控、重复采样和端点漂移检测。
- **Are You Getting What You Pay For? Auditing Model Substitution in LLM APIs**：模型替换审计和服务完整性风险。
- **Your "Pro" LLM Subscription May Actually Be "Free"**：指纹伪装风险和静态指纹方法的局限。
- **RULER: What's the Real Context Size of Your Long-Context Language Models?**：长上下文合成探测设计。
- **Lost in the Middle: How Language Models Use Long Contexts**：长上下文位置偏差。
- **NoLiMa、LongBench v2、LongMemEval、LongFuncEval**：长上下文、长期记忆和长工具负载评估思路。
- **OpenAI tiktoken、Hugging Face Tokenizers、SentencePiece**：本地 tokenizer、Unicode 和 BPE/Unigram 计量参考。
- **OpenAI、Anthropic、Google/Gemini provider 文档**：Token 计数、usage metadata、OpenAI 兼容层、上下文窗口、缓存和流式事件行为。
- **GitHub issue forms、Actions secure use、CODEOWNERS、rulesets 文档**：可信参考语料的治理、校验和安全工作流参考。

</details>

<a id="english"></a>

<details>
<summary>English</summary>

## English

### What This Is

LLM Identify is an AstrBot plugin for probabilistic black-box audits of LLM endpoints. It does not prove the true model identity. Instead, it combines multiple probes to estimate whether an endpoint behaves like its claimed model, whether it may be proxied or wrapped, whether token accounting is trustworthy, whether context behavior matches the claim, and whether repeated requests may be routed to different backends.

It is useful for ordinary users checking their model configuration, as well as developers, API relay users, and anyone who needs periodic model supply-chain checks.

### Implemented Features

- Quick audit: uses a small protocol probe set to check the basic interface behavior of the current or selected AstrBot model.
- Full audit: adds token accounting, fingerprinting, context checks, and branch evidence for a more complete risk report.
- Web panel: runs audits, selects models, and displays scores, candidate probabilities, probe details, and text reports.
- Model selection: the Page panel can select any currently configured AstrBot model, not only the current chat model.
- Direct audit: accepts Base URL, API Key, and model name for OpenAI-compatible endpoints.
- Multilingual UI: the page follows the host language by default; Chinese, Japanese, and English are supported, and other languages fall back to English.
- Localized reports: chat commands and page reports can output Chinese, Japanese, or English.
- Trusted reference corpus: includes a compact built-in corpus and supports additional local or remote JSON corpora.
- External evidence: can optionally use public fingerprint sources, auxiliary LLM judges, and local dynamic fingerprint records.
- Privacy protection: uses synthetic probes by default and redacts traces before persistence.

### Quick Use

Chat commands:

```text
/llmid
/llmid full
/llmid help
/llmid zh
/llmid ja
/llmid full zh
```

- `/llmid`: quick audit for the current chat model.
- `/llmid full`: full audit for the current chat model.
- `/llmid zh`, `/llmid ja`, `/llmid en`: choose the report language for this run.

Web panel:

1. Open the LLM Identify page in the plugin detail view.
2. Choose a page language. By default it follows the host language.
3. Select a configured AstrBot model, or switch to a direct OpenAI-compatible endpoint.
4. Choose quick or full audit.
5. Run the audit and inspect the risk level, confidence, candidate model families, probe evidence, and text report.

### Common Configuration

- `default_timeout`: timeout for each probe request.
- `page_provider_id`: default provider ID used by the Page. Leave empty to discover an available model automatically.
- `enable_token_probe`: enables token probes by default. Full audits always enable them.
- `enable_fingerprint_probe`: enables fingerprint probes by default. Full audits always enable them.
- `fingerprint_profile`: fingerprint breadth, one of `light`, `standard`, or `exhaustive`.
- `fingerprint_repeats`: repeat count for each fingerprint probe. Higher values are steadier but cost more requests.
- `strict_mode`: applies a more conservative confidence penalty for failed probes.
- `auxiliary_judge_provider_id` / `auxiliary_judge_provider_ids`: use one or more models as auxiliary judges.
- `public_fingerprint_sources`: public model or fingerprint datasets, as local JSON files or HTTPS URLs.
- `trusted_corpus_sources`: extended trusted reference corpora, as local JSON files or HTTPS URLs.
- `public_cache_dir`: cache directory for remote corpora and public fingerprint sources.
- `local_fingerprint_libraries`: optional local fingerprint libraries. The no-install `bundled:llmmap` is included by default.

### Reading Results

Focus on these fields:

- `confidence`: overall confidence from fused evidence.
- `risk_level`: low, medium, or high risk.
- `provider_probabilities` / `identity_posterior`: which model families the endpoint resembles.
- `proxy_probability`: probability of proxying, wrapping, or relaying.
- `mixture_probability`: probability of mixed routing.
- `token_truth_score`: whether token accounting appears trustworthy.
- `fingerprint_confidence`: strength of fingerprint evidence.
- `spoofing_risk`: risk of spoofing or behavioral imitation.
- `findings`: primary findings.
- `probe_results`: status, score, and explanation for each probe.

Treat the result as a risk judgment from observable evidence. If the endpoint uses caching, relays, RAG, safety layers, quantization, model hot updates, or dynamic routing, results may vary. For important cases, run repeated audits and compare with provider-side logs.

### Page API

```text
GET  /astrbot_plugin_llm_identify/page/status
POST /astrbot_plugin_llm_identify/page/detect
GET  /astrbot_plugin_llm_identify/page/health
GET  /astrbot_plugin_llm_identify/page/audits
POST /astrbot_plugin_llm_identify/page/audits
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>/report
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>/events
POST /astrbot_plugin_llm_identify/page/baselines/refresh
GET  /astrbot_plugin_llm_identify/page/drift/<target_id>
POST /astrbot_plugin_llm_identify/page/export/<task_id>
```

The current page uses `/status` to fetch running state, selectable models, and the latest report, and uses `/detect` to trigger audits.

### Implementation

The plugin uses an audit core plus host adapter structure:

- `main.py`: plugin entrypoint, chat commands, Page API, provider enumeration, and model invocation.
- `pages/模型检测面板/`: Web panel UI, language switching, model selection, audit triggering, and result rendering.
- `llm_identify/adapters/`: host-model and direct OpenAI-compatible endpoint adapters.
- `llm_identify/probes/`: protocol, token, context, and fingerprint probe packs.
- `llm_identify/capture/`: trace capture, request/response summaries, and metadata recording.
- `llm_identify/features/`: token and fingerprint feature extraction.
- `llm_identify/scoring/`: evidence fusion, risk computation, candidate generation, and text reports.
- `llm_identify/corpus.py`: trusted reference corpus loading, caching, degraded fallback, and source attribution.
- `llm_identify/evidence.py`: external evidence sources, public fingerprint data, and auxiliary LLM judges.
- `llm_identify/storage.py`: SQLite persistence for tasks, reports, and traces.
- `llm_identify/tasks.py`: task status and event models.
- `llm_identify/branches.py`: branch evidence for output statistics, context, timing, tool calls, token truth, and prompt injection.
- `llm_identify/cli.py`: standalone command-line entrypoint.

`core/` is a legacy implementation directory and is not used by the new entrypoint.

### Evidence Model

The plugin does not rely on one model fingerprint. It fuses several classes of weak evidence:

- Protocol evidence: exact output, JSON output, usage metadata, streaming and non-streaming surfaces.
- Token evidence: usage availability, input-token monotonicity, slope plausibility, constant-count anomalies, Unicode behavior, cache signals, and output-length consistency.
- Fingerprint evidence: active behavioral probes, knowledge boundaries, refusal style, visible reasoning structure, tokenizer/Unicode behavior, sampling distribution, API side channels, and static and dynamic baselines.
- Context evidence: context-window sentinels, long-context ability, positional robustness, and mid-session switching signals.
- Branch evidence: output statistics, timing, context truth, tool calls, token truth, and prompt-injection risk.
- External evidence: trusted reference corpora, public fingerprint sources, and auxiliary LLM judges.

The fusion layer computes model-family posterior, authenticity posterior, security-risk posterior, proxy probability, mixed-routing probability, and spoofing risk. Agreement across methods raises confidence; disagreement raises risk instead of forcing a single answer.

### Token, Fingerprint, and Context Design

Token accounting uses a layered strategy: provider-native counters or official tokenizers first; local approximate tokenizers, dynamic probes, and calibration when no official counter exists; chunking, sampling, and boundary correction for long text. Reports distinguish exact counts, available metadata, and inferred evidence.

Fingerprint auditing does not only look at answer style. It also observes knowledge boundaries, output-structure stability, Unicode and tokenizer behavior, refusal style, streaming metadata, finish reasons, usage shapes, and whether repeated sampling shows backend switching.

Context auditing measures usable context rather than advertised maximum token limits. It separates normal long-context degradation, soft summarization, truncation, and suspicious backend switching.

### Trusted Corpus, Privacy, and Storage

The built-in trusted corpus is small, source-attributed, and usable offline. Additional corpora can be loaded from local files or HTTPS URLs and cached locally. Trusted reference records should pass schema validation, redaction, official-endpoint confirmation, repeated probes, and maintainer review. The plugin never uploads data automatically.

Audits use synthetic probes by default to avoid sending real user chats. Task storage keeps traces, feature summaries, and reports separately, and redacts before persistence: email-like text, phone-like text, API-key-like tokens, common JSON secret fields, and deterministic hashes of sensitive raw values. Logs should only reference task IDs, trace IDs, and report IDs.

### CLI and Automation

```text
python -m llm_identify.cli scan --target-id relay-default --base-url https://example.com/v1 --api-key sk-... --model gpt-test --output reports/run-001
python -m llm_identify.cli baselines refresh --providers openai anthropic gemini
python -m llm_identify.cli report export --task-id aud_... --format json --data-dir reports/run-001
python -m llm_identify.cli report plot --out reports/run-001/figures
```

After FastAPI is installed, `llm_identify.rest.create_app()` can be used for local automation.

### Limits

- Black-box auditing cannot prove the true underlying model; it only gives risk and probability judgments.
- Relays can rewrite prompts, usage, metadata, output style, and routing policies.
- Caching, RAG, safety layers, quantization, model hot updates, and network jitter can affect results.
- Full audits send more requests and may increase API cost.
- Auxiliary LLM judges are evidence sources, not authorities.

### Acknowledgements and References

This project has not directly copied third-party implementation code. The most direct external material used in the current implementation is LLMmap's public supported-model metadata, specifically model identifiers and family information, stored as lightweight source-attributed metadata. The plugin does not bundle LLMmap model weights, training data, or classifiers.

The most useful references for implementation are:

- **LLMmap: Fingerprinting for Large Language Models**: active black-box fingerprinting and supported-model metadata.
- **KBF: Knowledge Boundary as Fingerprint for Language Model and Black-Box API Auditing**: knowledge-boundary, substitution auditing, and mixed-routing detection.
- **Behavioral Fingerprints for LLM Endpoint Stability and Identity**: continuous monitoring, repeated sampling, and endpoint drift detection.
- **Are You Getting What You Pay For? Auditing Model Substitution in LLM APIs**: model-substitution auditing and service-integrity risk.
- **Your "Pro" LLM Subscription May Actually Be "Free"**: spoofing risk and limits of static fingerprinting.
- **RULER: What's the Real Context Size of Your Long-Context Language Models?**: synthetic long-context probe design.
- **Lost in the Middle: How Language Models Use Long Contexts**: positional bias in long context.
- **NoLiMa, LongBench v2, LongMemEval, and LongFuncEval**: long-context, long-memory, and long-tool-workload evaluation ideas.
- **OpenAI tiktoken, Hugging Face Tokenizers, and SentencePiece**: local tokenizer, Unicode, and BPE/Unigram token accounting references.
- **OpenAI, Anthropic, and Google/Gemini provider documentation**: token counting, usage metadata, OpenAI-compatible layers, context windows, caching, and streaming event behavior.
- **GitHub issue forms, Actions secure use, CODEOWNERS, and rulesets documentation**: governance, validation, and secure workflow references for trusted reference corpora.

</details>

<a id="日本語"></a>

<details>
<summary>日本語</summary>

## 日本語

### これは何か

LLM Identify は、LLM エンドポイントを確率的にブラックボックス監査する AstrBot プラグインです。真のモデル ID を証明するものではありません。複数のプローブを組み合わせ、エンドポイントが主張モデルらしく振る舞うか、プロキシや包装があり得るか、Token 計量が信頼できるか、コンテキスト挙動が主張と一致するか、反復リクエストが別バックエンドにルーティングされ得るかを推定します。

通常ユーザーのモデル設定確認にも、開発者、API 中継利用者、モデル供給経路を定期確認する人にも使えます。

### 実装済み機能

- 簡易監査: 少数のプロトコルプローブで、現在または選択した AstrBot モデルの基本インターフェース挙動を確認します。
- 完全監査: Token 計量、指紋、コンテキスト、分岐証拠を追加し、より完全なリスクレポートを出します。
- Web パネル: 監査実行、モデル選択、スコア、候補確率、プローブ詳細、テキストレポートを表示します。
- モデル選択: Page パネルでは、現在のチャットモデルだけでなく、現在設定済みのすべての AstrBot モデルから監査対象を選べます。
- 直接監査: Base URL、API Key、モデル名を入力して OpenAI 互換エンドポイントを監査できます。
- 多言語: ページは既定でホスト言語に従います。中国語、日本語、英語をサポートし、その他の言語は英語にフォールバックします。
- ローカライズ済みレポート: チャットコマンドとページレポートは中国語、日本語、英語で出力できます。
- 信頼参照コーパス: 小型の組み込みコーパスを含み、追加のローカルまたはリモート JSON コーパスにも対応します。
- 外部証拠: 公開指紋ソース、補助 LLM 判定、ローカル動的指紋記録を任意で利用できます。
- プライバシー保護: 既定では合成プローブを使い、永続化前に trace を redaction します。

### すぐ使う

チャットコマンド:

```text
/llmid
/llmid full
/llmid help
/llmid zh
/llmid ja
/llmid full zh
```

- `/llmid`: 現在のチャットモデルを簡易監査します。
- `/llmid full`: 現在のチャットモデルを完全監査します。
- `/llmid zh`、`/llmid ja`、`/llmid en`: 今回のレポート言語を選びます。

Web パネル:

1. プラグイン詳細ビューで LLM Identify ページを開きます。
2. ページ言語を選びます。既定ではホスト言語に従います。
3. 設定済み AstrBot モデルを選ぶか、直接 OpenAI 互換エンドポイントに切り替えます。
4. 簡易監査または完全監査を選びます。
5. 監査を実行し、リスクレベル、信頼度、候補モデルファミリー、プローブ証拠、テキストレポートを確認します。

### よく使う設定

- `default_timeout`: 各プローブ要求のタイムアウト。
- `page_provider_id`: Page が既定で使う provider ID。空の場合は利用可能なモデルを自動検出します。
- `enable_token_probe`: Token プローブを既定で有効にします。完全監査では常に有効です。
- `enable_fingerprint_probe`: 指紋プローブを既定で有効にします。完全監査では常に有効です。
- `fingerprint_profile`: 指紋の幅。`light`、`standard`、`exhaustive` のいずれか。
- `fingerprint_repeats`: 各指紋プローブの反復回数。高いほど安定しますが、要求数が増えます。
- `strict_mode`: 失敗プローブに、より保守的な信頼度ペナルティを適用します。
- `auxiliary_judge_provider_id` / `auxiliary_judge_provider_ids`: 1 つ以上のモデルを補助判定として使います。
- `public_fingerprint_sources`: 公開モデルまたは指紋データセット。ローカル JSON または HTTPS URL。
- `trusted_corpus_sources`: 拡張信頼参照コーパス。ローカル JSON または HTTPS URL。
- `public_cache_dir`: リモートコーパスと公開指紋ソースのキャッシュディレクトリ。
- `local_fingerprint_libraries`: 任意のローカル指紋ライブラリ。インストール不要の `bundled:llmmap` が既定で含まれます。

### 結果の読み方

主に見るフィールド:

- `confidence`: 融合証拠からの全体信頼度。
- `risk_level`: 低、中、高のリスク。
- `provider_probabilities` / `identity_posterior`: エンドポイントが似ているモデルファミリー。
- `proxy_probability`: プロキシ、包装、中継の可能性。
- `mixture_probability`: 混合ルーティングの可能性。
- `token_truth_score`: Token 計量が信頼できるか。
- `fingerprint_confidence`: 指紋証拠の強さ。
- `spoofing_risk`: 偽装または行動模倣のリスク。
- `findings`: 主要な検出事項。
- `probe_results`: 各プローブの状態、スコア、説明。

結果は「観測可能な証拠に基づくリスク判断」として扱ってください。エンドポイントがキャッシュ、中継、RAG、安全層、量子化、モデルホットアップデート、動的ルーティングを使う場合、結果は変動し得ます。重要なケースでは複数回監査し、provider 側ログと比較してください。

### Page API

```text
GET  /astrbot_plugin_llm_identify/page/status
POST /astrbot_plugin_llm_identify/page/detect
GET  /astrbot_plugin_llm_identify/page/health
GET  /astrbot_plugin_llm_identify/page/audits
POST /astrbot_plugin_llm_identify/page/audits
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>/report
GET  /astrbot_plugin_llm_identify/page/audits/<task_id>/events
POST /astrbot_plugin_llm_identify/page/baselines/refresh
GET  /astrbot_plugin_llm_identify/page/drift/<target_id>
POST /astrbot_plugin_llm_identify/page/export/<task_id>
```

現在のページは `/status` で実行状態、選択可能モデル、最新レポートを取得し、`/detect` で監査を開始します。

### 実装

プラグインは監査コアとホストアダプターの構造です:

- `main.py`: プラグイン入口、チャットコマンド、Page API、provider 列挙、モデル呼び出し。
- `pages/模型检测面板/`: Web パネル UI、言語切替、モデル選択、監査開始、結果描画。
- `llm_identify/adapters/`: ホストモデルと直接 OpenAI 互換エンドポイントのアダプター。
- `llm_identify/probes/`: プロトコル、Token、コンテキスト、指紋プローブパック。
- `llm_identify/capture/`: trace 捕捉、要求/応答サマリー、メタデータ記録。
- `llm_identify/features/`: Token と指紋の特徴抽出。
- `llm_identify/scoring/`: 証拠融合、リスク計算、候補生成、テキストレポート。
- `llm_identify/corpus.py`: 信頼参照コーパスの読み込み、キャッシュ、低下時フォールバック、ソース属性。
- `llm_identify/evidence.py`: 外部証拠ソース、公開指紋データ、補助 LLM 判定。
- `llm_identify/storage.py`: タスク、レポート、trace の SQLite 永続化。
- `llm_identify/tasks.py`: タスク状態とイベントモデル。
- `llm_identify/branches.py`: 出力統計、コンテキスト、時系列、ツール呼び出し、Token 真実性、プロンプト注入の分岐証拠。
- `llm_identify/cli.py`: スタンドアロン CLI 入口。

`core/` は旧実装ディレクトリで、新しい入口では使いません。

### 証拠モデル

プラグインは単一のモデル指紋に依存しません。複数種類の弱い証拠を融合します:

- プロトコル証拠: 厳密出力、JSON 出力、usage メタデータ、ストリーミング/非ストリーミング表面。
- Token 証拠: usage 可用性、入力 Token 単調性、傾き妥当性、一定カウント異常、Unicode 挙動、キャッシュ信号、出力長整合性。
- 指紋証拠: 能動的行動プローブ、知識境界、拒否スタイル、可視推論構造、tokenizer/Unicode 挙動、サンプリング分布、API side channel、静的/動的ベースライン。
- コンテキスト証拠: コンテキストウィンドウ番兵、長コンテキスト能力、位置ロバスト性、中途切替信号。
- 分岐証拠: 出力統計、時系列、コンテキスト真実性、ツール呼び出し、Token 真実性、プロンプト注入リスク。
- 外部証拠: 信頼参照コーパス、公開指紋ソース、補助 LLM 判定。

融合層は、モデルファミリー事後分布、真正性事後分布、セキュリティリスク事後分布、プロキシ確率、混合ルーティング確率、偽装リスクを計算します。手法間の一致は信頼度を上げ、不一致は単一回答を強制せずリスクを上げます。

### Token、指紋、コンテキスト設計

Token 計量は階層化戦略です。provider ネイティブカウンターまたは公式 tokenizer を優先し、公式カウンターがない場合はローカル近似 tokenizer、動的プローブ、校正を使います。長文にはチャンク化、サンプリング、境界補正を使います。レポートは厳密計数、利用可能メタデータ、推定証拠を区別します。

指紋監査は回答スタイルだけを見ません。知識境界、出力構造安定性、Unicode と tokenizer 挙動、拒否スタイル、ストリーミングメタデータ、finish reason、usage 形状、反復サンプリングでバックエンド切替が見えるかも観察します。

コンテキスト監査は宣伝上の最大 Token 数ではなく、実際に使えるコンテキストを測ります。通常の長コンテキスト劣化、ソフト要約、切り捨て、疑わしいバックエンド切替を分けます。

### 信頼コーパス、プライバシー、保存

組み込み信頼コーパスは小型で、ソース属性付き、オフライン利用可能です。追加コーパスはローカルファイルまたは HTTPS URL から読み込み、ローカルにキャッシュできます。信頼参照レコードは schema 検証、redaction、公式エンドポイント確認、反復プローブ、メンテナー審査を通すべきです。プラグインは自動アップロードしません。

監査は既定で合成プローブを使い、実ユーザーチャット送信を避けます。タスク保存では trace、特徴サマリー、レポートを分離し、永続化前に redaction します。対象はメール風テキスト、電話風テキスト、API key 風 token、一般的な JSON secret フィールド、敏感な生値の決定的ハッシュです。ログは task ID、trace ID、report ID のみを参照すべきです。

### CLI と自動化

```text
python -m llm_identify.cli scan --target-id relay-default --base-url https://example.com/v1 --api-key sk-... --model gpt-test --output reports/run-001
python -m llm_identify.cli baselines refresh --providers openai anthropic gemini
python -m llm_identify.cli report export --task-id aud_... --format json --data-dir reports/run-001
python -m llm_identify.cli report plot --out reports/run-001/figures
```

FastAPI をインストールすると、`llm_identify.rest.create_app()` をローカル自動化に使えます。

### 制限

- ブラックボックス監査は真の基盤モデルを証明できず、リスクと確率判断だけを返します。
- 中継は prompt、usage、metadata、出力スタイル、ルーティング方針を書き換えられます。
- キャッシュ、RAG、安全層、量子化、モデルホットアップデート、ネットワーク揺らぎは結果に影響します。
- 完全監査はより多くの要求を送るため、API コストが増える場合があります。
- 補助 LLM 判定は証拠ソースであり、権威ではありません。

### 謝辞と参考

本プロジェクトは第三者の実装コードを直接コピーしていません。現在の実装で最も直接使っている外部素材は、LLMmap の公開 supported-model metadata です。具体的にはモデル識別子とファミリー情報を、ソース属性付きの軽量メタデータとして保存しています。LLMmap のモデル重み、訓練データ、分類器は同梱していません。

実装に特に役立った資料は次のとおりです:

- **LLMmap: Fingerprinting for Large Language Models**: 能動的ブラックボックス指紋と supported-model metadata。
- **KBF: Knowledge Boundary as Fingerprint for Language Model and Black-Box API Auditing**: 知識境界、置換監査、混合ルーティング検出。
- **Behavioral Fingerprints for LLM Endpoint Stability and Identity**: 継続監視、反復サンプリング、エンドポイントドリフト検出。
- **Are You Getting What You Pay For? Auditing Model Substitution in LLM APIs**: モデル置換監査とサービス完全性リスク。
- **Your "Pro" LLM Subscription May Actually Be "Free"**: 偽装リスクと静的指紋の限界。
- **RULER: What's the Real Context Size of Your Long-Context Language Models?**: 合成長コンテキストプローブ設計。
- **Lost in the Middle: How Language Models Use Long Contexts**: 長コンテキストでの位置バイアス。
- **NoLiMa、LongBench v2、LongMemEval、LongFuncEval**: 長コンテキスト、長期記憶、長いツール負荷の評価アイデア。
- **OpenAI tiktoken、Hugging Face Tokenizers、SentencePiece**: ローカル tokenizer、Unicode、BPE/Unigram Token 計量の参考。
- **OpenAI、Anthropic、Google/Gemini provider 文書**: Token 計数、usage metadata、OpenAI 互換層、コンテキストウィンドウ、キャッシュ、ストリーミングイベント挙動。
- **GitHub issue forms、Actions secure use、CODEOWNERS、rulesets 文書**: 信頼参照コーパスのガバナンス、検証、安全なワークフローの参考。

</details>
