# AI Vendor Rules

按 AI 模型厂商分类、可持续自动更新的 Clash/Mihomo 与 Quantumult X 规则集。

本仓库不是 OpenAI、Anthropic、Google、xAI 或其他厂商的官方项目。域名数据主要同步自
[`v2fly/domain-list-community`](https://github.com/v2fly/domain-list-community)，本仓库负责厂商映射、格式转换、校验与发布。

## 特点

- 每个 AI 厂商拥有独立规则文件，便于分别选择出口线路。
- 同时发布 Clash/Mihomo classical YAML 和 Quantumult X 原生规则。
- 提供 `all-ai`、`all-ai-global`、`all-ai-cn` 三个兜底聚合规则。
- 自动排除上游标记为 `@ads` 的域名。
- GitHub Actions 定期同步并在提交前校验生成结果。
- 生成清单记录上游提交、规则数量及格式差异。

## 目录

```text
generated/
├── clash/          # Clash/Mihomo classical YAML
├── quantumultx/    # Quantumult X HOST/HOST-SUFFIX 规则
└── manifest.json   # 上游版本、厂商与规则统计
examples/           # 可直接复制的客户端配置示例
sources/            # 厂商映射与补充域名
scripts/            # 生成和校验工具
```

## Clash / Mihomo

下面以 Claude、OpenAI、Grok、Gemini 为例。具体厂商规则必须排在 `all-ai` 之前。

```yaml
proxy-groups:
  - name: Claude
    type: select
    proxies: [代理选择, DIRECT]
  - name: OpenAI
    type: select
    proxies: [代理选择, DIRECT]
  - name: Grok
    type: select
    proxies: [代理选择, DIRECT]
  - name: Gemini
    type: select
    proxies: [代理选择, DIRECT]
  - name: AI
    type: select
    proxies: [代理选择, DIRECT]

rule-providers:
  claude:
    type: http
    behavior: classical
    format: yaml
    interval: 86400
    url: https://raw.githubusercontent.com/TannayeJ/ai-vendor-rules/main/generated/clash/claude.yaml
    path: ./ruleset/ai/claude.yaml
  openai:
    type: http
    behavior: classical
    format: yaml
    interval: 86400
    url: https://raw.githubusercontent.com/TannayeJ/ai-vendor-rules/main/generated/clash/openai.yaml
    path: ./ruleset/ai/openai.yaml
  grok:
    type: http
    behavior: classical
    format: yaml
    interval: 86400
    url: https://raw.githubusercontent.com/TannayeJ/ai-vendor-rules/main/generated/clash/grok.yaml
    path: ./ruleset/ai/grok.yaml
  gemini:
    type: http
    behavior: classical
    format: yaml
    interval: 86400
    url: https://raw.githubusercontent.com/TannayeJ/ai-vendor-rules/main/generated/clash/gemini.yaml
    path: ./ruleset/ai/gemini.yaml
  all-ai:
    type: http
    behavior: classical
    format: yaml
    interval: 86400
    url: https://raw.githubusercontent.com/TannayeJ/ai-vendor-rules/main/generated/clash/all-ai.yaml
    path: ./ruleset/ai/all-ai.yaml

rules:
  - RULE-SET,claude,Claude
  - RULE-SET,openai,OpenAI
  - RULE-SET,grok,Grok
  - RULE-SET,gemini,Gemini
  - RULE-SET,all-ai,AI
```

完整片段见 [`examples/clash-rule-providers.yaml`](examples/clash-rule-providers.yaml)。

## Quantumult X

在 `[filter_remote]` 中加入所需厂商：

```ini
https://raw.githubusercontent.com/TannayeJ/ai-vendor-rules/main/generated/quantumultx/claude.list, tag=Claude, force-policy=Claude, enabled=true
https://raw.githubusercontent.com/TannayeJ/ai-vendor-rules/main/generated/quantumultx/openai.list, tag=OpenAI, force-policy=OpenAI, enabled=true
https://raw.githubusercontent.com/TannayeJ/ai-vendor-rules/main/generated/quantumultx/grok.list, tag=Grok, force-policy=Grok, enabled=true
https://raw.githubusercontent.com/TannayeJ/ai-vendor-rules/main/generated/quantumultx/gemini.list, tag=Gemini, force-policy=Gemini, enabled=true
https://raw.githubusercontent.com/TannayeJ/ai-vendor-rules/main/generated/quantumultx/all-ai.list, tag=AI-Fallback, force-policy=AI, enabled=true
```

Quantumult X 按远程规则排列顺序匹配，因此厂商规则应位于 `all-ai` 兜底之前。完整片段见
[`examples/quantumult-x.conf`](examples/quantumult-x.conf)。

## 支持的厂商

当前厂商与规则数量以 [`generated/manifest.json`](generated/manifest.json) 为准。首版覆盖：

- 海外模型与助手：Claude、OpenAI、Grok、Gemini、Perplexity、Groq、Mistral、Meta AI、Cohere 等。
- 编程与 Agent：GitHub Copilot、Microsoft Copilot、Cursor、Windsurf、Devin、CodeRabbit、Dify 等。
- 图像、视频和语音：Midjourney、Stability AI、Runway、Pika、Suno、ElevenLabs 等。
- 国内模型与助手：DeepSeek、豆包、Qwen、Kimi、智谱、腾讯混元/元宝、MiniMax、Kling 等。
- 聚合兜底：国际、国内、俄语区的全部上游 AI 分类。

## 自动更新

手动生成：

```bash
git clone --depth 1 https://github.com/v2fly/domain-list-community.git upstream
python3 scripts/generate.py --source-root upstream/data
python3 scripts/validate.py
```

校验已提交结果是否与上游一致：

```bash
python3 scripts/generate.py --source-root upstream/data --check
```

定时任务会自动提交上游变化。单独新增厂商时，请修改 `sources/vendors.json`，不要直接编辑
`generated/`。

## 格式说明

- Clash 输出采用 `behavior: classical`，兼容 `DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-KEYWORD` 和 `DOMAIN-REGEX`。
- Quantumult X 输出采用 `HOST`、`HOST-SUFFIX` 和 `HOST-KEYWORD`。
- 上游正则无法无损转换为 Quantumult X 时，会保留为 `# UNSUPPORTED-REGEXP` 注释并记录在 manifest 中；聚合兜底仍覆盖其余规则。

## 许可证与数据来源

生成器、厂商目录和文档使用 MIT License。生成规则包含来自上游社区项目的数据；使用或再分发时也应遵守对应上游项目的许可证与归属要求。

