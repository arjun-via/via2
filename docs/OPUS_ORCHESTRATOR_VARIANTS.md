# Dynamic System Variants

> **System**: Dynamic (one of three systems in Via2)
> **Type**: Adaptive model selection with learning
> **Key Feature**: Opus 4.5 as Meta-Orchestrator, dynamic worker model selection

## Overview

The **Dynamic** system uses **Opus 4.5 as the Meta-Orchestrator** (planner + validator) with adaptive selection of worker models based on task characteristics.

This is one of three systems in the Via2 repository:
- **ALO**: Multi-model pipeline (Gemini, GPT, GLM, Kimi)
- **Opus Orchestrator**: Single-model Docker loop (Claude Opus 4.5)
- **Dynamic**: Adaptive model selection with learning (this system)

**Baseline for comparison:** Opus-Baseline (single Opus call, no orchestration)

---

## Model Menu (Available for Opus to Select)

The Opus Meta-Orchestrator dynamically selects models from this menu based on:
- Task complexity (simple → complex)
- Domain requirements (algorithms, systems, ML, etc.)
- Speed vs quality tradeoffs
- Cost constraints

### Speed Test Results (November 2025)

| Model | Provider | API Endpoint | Speed | Status |
|-------|----------|--------------|-------|--------|
| **Qwen3-235B** | Cerebras Native | `/v1/chat/completions` | 735 tok/s | ✓ |
| **GLM-4.6** | Cerebras Native | `/v1/chat/completions` | 600 tok/s | ✓ |
| **Kimi K2** | Groq Native | `/v1/chat/completions` | 323 tok/s | ✓ |
| **Gemini 2.5 Pro** | OpenRouter | `/v1/chat/completions` | 90 tok/s | ✓ |
| **Sonnet 4.5** | OpenRouter | `/v1/chat/completions` | 77 tok/s | ✓ |
| **GPT-5.1** | OpenAI Native | `/v1/chat/completions` | 72 tok/s | ✓ |
| **Opus 4.5** | OpenRouter | `/v1/chat/completions` | 45 tok/s | ✓ |
| **Kimi K2 Thinking** | OpenRouter | `/v1/chat/completions` | 31 tok/s | ✓ |

### Model Selection Guidelines for Opus

Opus will select models based on these criteria:

**For Context Agent:**
| Task Type | Recommended Model | Rationale |
|-----------|-------------------|-----------|
| Simple context | GLM-4.6 (Cerebras) | Fast, cheap |
| Medium context | Gemini 2.5 Pro | 1M context window |
| Complex/large repo | Gemini 2.5 Pro | Best context understanding |

**For Engineering Agent:**
| Task Complexity | Recommended Model | Rationale |
|-----------------|-------------------|-----------|
| Simple (CRUD, utils) | Qwen3-235B (Cerebras) | 735 tok/s, very fast |
| Medium (algorithms) | GPT-5.1 (OpenAI) | Strong reasoning |
| Complex (systems) | Sonnet 4.5 | Best code quality |
| Expert (architecture) | Opus 4.5 | Maximum capability |

**For Review Agent:**
| Review Depth | Recommended Model | Rationale |
|--------------|-------------------|-----------|
| Quick sanity check | Kimi K2 (Groq) | 323 tok/s, fast |
| Standard review | Kimi K2 (Groq) | Good quality/speed |
| Deep analysis | Kimi K2 Thinking | Thorough reasoning |
| Security audit | Sonnet 4.5 | Best critical analysis |

### API Configuration

```yaml
# All available model endpoints
model_registry:
  # Cerebras Native (fastest)
  cerebras:
    base_url: https://api.cerebras.ai/v1
    api_key_env: CEREBRAS_API_KEY
    models:
      - id: zai-glm-4.6
        speed: 600
      - id: qwen-3-235b-a22b-instruct-2507
        speed: 735

  # Groq Native (fast)
  groq:
    base_url: https://api.groq.com/openai/v1
    api_key_env: GROQ_API_KEY
    models:
      - id: moonshotai/kimi-k2-instruct-0905
        speed: 323

  # OpenAI Native (for ZDR compliance)
  openai:
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    models:
      - id: gpt-5.1
        speed: 72

  # OpenRouter (premium models)
  openrouter:
    base_url: https://openrouter.ai/api/v1
    api_key_env: OPENROUTER_API_KEY
    models:
      - id: anthropic/claude-opus-4
        speed: 45
      - id: anthropic/claude-sonnet-4
        speed: 77
      - id: google/gemini-2.5-pro-preview
        speed: 90
      - id: moonshotai/kimi-k2-thinking
        speed: 31
```

---

## Model Pricing Reference (November 2025)

### Anthropic Claude Models
| Model | Input $/1M | Output $/1M | Context |
|-------|------------|-------------|---------|
| **Claude Opus 4.5** | $5.00 | $25.00 | 200K |
| **Claude Sonnet 4.5** | $3.00 | $15.00 | 200K |
| **Claude Haiku 4.5** | $1.00 | $5.00 | 200K |

### Google Gemini Models
| Model | Input $/1M | Output $/1M | Context | Notes |
|-------|------------|-------------|---------|-------|
| **Gemini 3 Pro** | $2.00 | $12.00 | 1M | NEW! Best reasoning (>200K: $4/$18) |
| **Gemini 2.5 Pro** | $1.25 | $10.00 | 1M | (>200K: $2.50/$15) |
| **Gemini 2.5 Flash** | $0.30 | $2.50 | 1M | Fast & cheap |

### OpenAI GPT Models
| Model | Input $/1M | Output $/1M | Context | Notes |
|-------|------------|-------------|---------|-------|
| **GPT-5.1 Codex** | $1.25 | $10.00 | 272K | Best for code |
| **GPT-5.1** | $1.25 | $10.00 | 272K | Adaptive reasoning |
| **GPT-5 mini** | $0.25 | $2.00 | 272K | Fast & cheap |
| **GPT-4o** | $5.00 | $20.00 | 128K | Legacy |

### Open Source / OpenRouter Models
| Model | Input $/1M | Output $/1M | Context | Notes |
|-------|------------|-------------|---------|-------|
| **Qwen3 Coder Plus** | $1.20 | $6.00 | 256K | Alibaba proprietary |
| **Qwen3-235B** | $0.20 | $0.60 | 262K | Open weights, very cheap |
| **Kimi K2** | $1.00 | $3.00 | 131K | Best agentic tasks |
| **DeepSeek R1** | $0.20 | $4.50 | 164K | Open source reasoning |
| **GLM-4.6** | $0.60 | $2.00 | 128K | Open source |

### Fast Inference (Cerebras via OpenRouter) - APPROVED MODELS
| Model | Input $/1M | Output $/1M | Context | Speed | OpenRouter ID |
|-------|------------|-------------|---------|-------|---------------|
| **GLM-4.6** | $0.60 | $2.00 | 128K | ~1400 tok/s | `z-ai/glm-4.6` |
| **Qwen3-235B** | $0.60 | $1.20 | 262K | ~1400 tok/s | `qwen/qwen3-235b-a22b-2507` |
| **Kimi K2** | $1.00 | $3.00 | 131K | Fast | `moonshotai/kimi-k2-0905` |

Sources: [Anthropic](https://docs.claude.com/en/docs/about-claude/pricing), [Google AI](https://ai.google.dev/gemini-api/docs/pricing), [OpenAI](https://openai.com/api/pricing/), [OpenRouter](https://openrouter.ai/models), [GPT-5.1 Guide](https://alphacorp.ai/gpt-5-1-launch-everything-you-need-to-know/)

---

## Variant Matrix

| Variant | Meta-Orch | Context Agent | Engineering Agent | Review Agent | Est. Cost/Task |
|---------|-----------|---------------|-------------------|--------------|----------------|
| **Opus-Baseline** | None | None | Opus (direct) | None | ~$0.08-0.12 |
| **Opus-Opus** | Opus | Opus | Opus | Opus | ~$0.35-0.50 |
| **Opus-Sonnet** | Opus | Sonnet 4.5 | Sonnet 4.5 | Sonnet 4.5 | ~$0.20-0.30 |
| **Opus-Gemini** | Opus | Gemini 3 Pro | Gemini 3 Pro | Gemini 3 Pro | ~$0.18-0.28 |
| **Opus-Optimized** | Opus | Gemini 3 Pro | Qwen3-235B | Kimi-K2 | ~$0.12-0.18 |
| **Opus-Open** | Opus | GLM-4.6 (Cerebras Native) | Qwen3-235B (Cerebras Native) | Kimi-K2 + K2-Think (OpenRouter) | ~$0.10-0.15 |
| **Opus-BestInClass** | Opus | Gemini 3 Pro | GPT-5.1 Codex | Sonnet 4.5 | ~$0.22-0.35 |
| **NVIDIA-Orchestrator** | Orchestrator-8B (local) | Gemini 2.5 Pro | Qwen3-235B | Kimi-K2 | ~$0.05-0.10 |

**Opus-Open Speed Advantage:**
- GLM-4.6: 600 tok/s (Cerebras Native) vs 62 tok/s (OpenRouter) = **9.6x faster**
- Qwen3-235B: 735 tok/s (Cerebras Native) vs 121 tok/s (OpenRouter) = **6x faster**

---

## Variant Descriptions

### 1. Opus-Baseline (Control Group)
**Purpose:** Establish what Opus can do alone with no orchestration overhead.

```
┌─────────────────────────────────────┐
│           OPUS 4.5                  │
│    (Single call, full context)      │
│                                     │
│  Input: Prompt + Constraints        │
│  Output: Complete solution          │
└─────────────────────────────────────┘
```

**Config:** None (direct API call)
- No planning phase
- No validation loop
- No retry logic
- Just Opus + good system prompt with constraints

**Hypothesis:** This is surprisingly good. If Opus-Baseline beats orchestrated variants, orchestration adds no value.

---

### 2. Opus-Opus (Full Opus Stack)
**Purpose:** Test if Opus orchestrating Opus adds value over Opus alone.

```
┌─────────────────────────────────────────────────────────────┐
│                 OPUS META-ORCHESTRATOR                      │
│           (Planning + Validation + Retry)                   │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌─────────────┐     ┌─────────┐
   │ Context │  →   │ Engineering │  →  │ Review  │
   │  Opus   │      │    Opus     │     │  Opus   │
   └─────────┘      └─────────────┘     └─────────┘
```

**Config:** `config/config_opus_opus.yaml`
```yaml
meta_orchestrator:
  model: claude-opus-4-5-20251101

agents:
  context:
    model: claude-opus-4-5-20251101
  engineering:
    model: claude-opus-4-5-20251101
  review:
    model: claude-opus-4-5-20251101
```

**Hypothesis:** Most expensive but highest quality. Tests ceiling of orchestration value.

---

### 3. Opus-Sonnet (Balanced)
**Purpose:** Opus plans/validates, Sonnet executes. Good quality/cost balance.

```
┌─────────────────────────────────────────────────────────────┐
│                 OPUS META-ORCHESTRATOR                      │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌─────────────┐     ┌─────────┐
   │ Context │  →   │ Engineering │  →  │ Review  │
   │ Sonnet  │      │   Sonnet    │     │ Sonnet  │
   └─────────┘      └─────────────┘     └─────────┘
```

**Config:** `config/config_opus_sonnet.yaml`
```yaml
meta_orchestrator:
  model: claude-opus-4-5-20251101

agents:
  context:
    model: claude-sonnet-4-5-20250514
  engineering:
    model: claude-sonnet-4-5-20250514
  review:
    model: claude-sonnet-4-5-20250514
```

**Hypothesis:** Sweet spot - Opus intelligence for planning, Sonnet speed for execution.

---

### 4. Opus-Gemini (Google Stack)
**Purpose:** Test Google's newest Gemini 3 Pro across all agents with Opus orchestration.

```
┌─────────────────────────────────────────────────────────────┐
│                 OPUS META-ORCHESTRATOR                      │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌─────────────┐     ┌─────────┐
   │ Context │  →   │ Engineering │  →  │ Review  │
   │Gemini 3 │      │  Gemini 3   │     │Gemini 3 │
   │  Pro    │      │    Pro      │     │  Pro    │
   └─────────┘      └─────────────┘     └─────────┘
```

**Config:** `config/config_opus_gemini.yaml`
```yaml
meta_orchestrator:
  model: claude-opus-4-5-20251101
  provider: anthropic
  pricing:
    input: 5.00
    output: 25.00

agents:
  context:
    model: gemini-3-pro-preview
    provider: google
    pricing:
      input: 2.00
      output: 12.00
    rationale: "1M context, newest Google model ($2/$12)"

  engineering:
    model: gemini-3-pro-preview
    provider: google
    pricing:
      input: 2.00
      output: 12.00
    rationale: "Strong reasoning and code generation"

  review:
    model: gemini-3-pro-preview
    provider: google
    pricing:
      input: 2.00
      output: 12.00
    rationale: "Consistent quality across all phases"
```

**Hypothesis:** Tests if Gemini 3 Pro can compete with Anthropic/OpenAI for code generation.

---

### 5. Opus-Optimized (Production Target)
**Purpose:** Opus orchestrates best-value models per role. This is the target production config.

```
┌─────────────────────────────────────────────────────────────┐
│                 OPUS META-ORCHESTRATOR                      │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌─────────────┐     ┌─────────┐
   │ Context │  →   │ Engineering │  →  │ Review  │
   │Gemini 3 │      │ Qwen3-235B  │     │ Kimi-K2 │
   │  Pro    │      │             │     │         │
   └─────────┘      └─────────────┘     └─────────┘
```

**Config:** `config/config_opus_optimized.yaml`
```yaml
meta_orchestrator:
  model: claude-opus-4-5-20251101
  provider: anthropic
  pricing:
    input: 5.00   # $/1M tokens
    output: 25.00
  planning_temperature: 0
  validation_temperature: 0

agents:
  context:
    model: gemini-3-pro-preview
    provider: google
    pricing:
      input: 2.00
      output: 12.00
    temperature: 0
    rationale: "1M context, newest reasoning model ($2/$12)"

  engineering:
    model: qwen/qwen3-235b-a22b-instruct-2507
    provider: openrouter
    pricing:
      input: 0.20
      output: 0.60
    temperature: 0.3
    rationale: "262K context, very cheap ($0.20/$0.60), good code generation"

  review:
    model: moonshotai/kimi-k2
    provider: openrouter
    pricing:
      input: 1.00
      output: 3.00
    temperature: 0
    rationale: "131K context, thorough validation ($1/$3), catches edge cases"
```

**Hypothesis:** Best cost/quality ratio. Opus adds strategic value while cheap models do heavy lifting.

---

### 6. Opus-Open (Fast OSS - Native APIs Only)
**Purpose:** Opus orchestrates fast open-source models using **native APIs only** for maximum speed.

```
┌─────────────────────────────────────────────────────────────┐
│                 OPUS META-ORCHESTRATOR                      │
│                (OpenRouter - anthropic/claude-opus-4)       │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌─────────────┐     ┌─────────────────┐
   │ Context │  →   │ Engineering │  →  │     Review      │
   │ GLM-4.6 │      │  Qwen3-235B │     │    Kimi-K2      │
   │(Cerebras│      │ (Cerebras)  │     │ (Groq Native)   │
   │ Native) │      │  (Native)   │     │ K2-Think (OR)   │
   └─────────┘      └─────────────┘     └─────────────────┘
     600 tok/s         735 tok/s         323 tok/s
```

**Speed Test Results (November 2025):**
| Model | Provider | Speed | vs OpenRouter |
|-------|----------|-------|---------------|
| Qwen3-235B | Cerebras Native | 734.9 tok/s | **6x faster** |
| GLM-4.6 | Cerebras Native | 599.6 tok/s | **9.6x faster** |
| Kimi K2 | Groq Native | 322.8 tok/s | **5.4x faster** |
| Kimi K2 Thinking | OpenRouter (Baseten) | 30.7 tok/s | baseline |

**Config:** `config/config_opus_open.yaml`
```yaml
meta_orchestrator:
  model: anthropic/claude-opus-4
  provider: openrouter
  pricing:
    input: 5.00
    output: 25.00

agents:
  context:
    model: zai-glm-4.6
    provider: cerebras  # NATIVE - 9.6x faster than OpenRouter
    base_url: https://api.cerebras.ai/v1
    pricing:
      input: 0.60
      output: 2.00
    speed: 600 tok/s
    rationale: "GLM-4.6 on Cerebras NATIVE, 9.6x faster than OpenRouter"

  engineering:
    model: qwen-3-235b-a22b-instruct-2507
    provider: cerebras  # NATIVE - 6x faster than OpenRouter
    base_url: https://api.cerebras.ai/v1
    pricing:
      input: 0.60
      output: 1.20
    speed: 735 tok/s
    rationale: "Qwen3-235B on Cerebras NATIVE, 6x faster than OpenRouter"

  review:
    model: moonshotai/kimi-k2-instruct-0905
    provider: groq  # NATIVE Groq hosting - 5.4x faster than OpenRouter
    base_url: https://api.groq.com/openai/v1
    pricing:
      input: 0.20  # Groq pricing
      output: 0.20
    speed: 323 tok/s
    rationale: "Kimi K2 on Groq NATIVE, 5.4x faster than OpenRouter (323 vs 60 tok/s)"

  review_thinking:  # Alternative for complex reviews
    model: moonshotai/kimi-k2-thinking
    provider: openrouter  # Baseten backend (not on Groq)
    pricing:
      input: 1.00
      output: 3.00
    speed: 31 tok/s
    rationale: "Kimi K2 Thinking via Baseten for deep reasoning"
```

**Approved Models:**
| Model | Native ID | Provider | Base URL |
|-------|-----------|----------|----------|
| GLM-4.6 | `zai-glm-4.6` | Cerebras | `https://api.cerebras.ai/v1` |
| Qwen3-235B | `qwen-3-235b-a22b-instruct-2507` | Cerebras | `https://api.cerebras.ai/v1` |
| Kimi K2 | `moonshotai/kimi-k2-instruct-0905` | Groq | `https://api.groq.com/openai/v1` |
| Kimi K2 Thinking | `moonshotai/kimi-k2-thinking` | OpenRouter | `https://openrouter.ai/api/v1` |

**API Keys Required:**
- `CEREBRAS_API_KEY` - for GLM-4.6 and Qwen3-235B
- `GROQ_API_KEY` - for Kimi K2
- `OPENROUTER_API_KEY` - for Kimi K2 Thinking and Opus orchestrator

**Hypothesis:** Can Opus planning + all native APIs achieve maximum speed and quality?

---

### 7. Opus-BestInClass (Maximum Quality)
**Purpose:** Opus orchestrates best model for each specific role. Quality ceiling test.

```
┌─────────────────────────────────────────────────────────────┐
│                 OPUS META-ORCHESTRATOR                      │
│                (OpenRouter - anthropic/claude-opus-4)       │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌─────────────┐     ┌─────────┐
   │ Context │  →   │ Engineering │  →  │ Review  │
   │Gemini 3 │      │  GPT-5.1    │     │ Sonnet  │
   │  Pro    │      │   Codex     │     │  4.5    │
   │(OpenRtr)│      │(OpenAI Ntv) │     │(OpenRtr)│
   └─────────┘      └─────────────┘     └─────────┘
```

**Config:** `config/config_opus_bestinclass.yaml`
```yaml
meta_orchestrator:
  model: anthropic/claude-opus-4
  provider: openrouter
  pricing:
    input: 5.00
    output: 25.00

agents:
  context:
    model: google/gemini-2.5-pro-preview  # Gemini 3 Pro when available
    provider: openrouter
    pricing:
      input: 2.00
      output: 12.00
    rationale: "Best context understanding, 1M context ($2/$12)"

  engineering:
    model: gpt-5.1-codex
    provider: openai  # NATIVE - ZDR not available on OpenRouter
    base_url: https://api.openai.com/v1
    pricing:
      input: 1.25
      output: 10.00
    rationale: "Best code generation, 272K context, native OpenAI for ZDR ($1.25/$10)"

  review:
    model: anthropic/claude-sonnet-4
    provider: openrouter
    pricing:
      input: 3.00
      output: 15.00
    rationale: "Best critical analysis and security review ($3/$15)"
```

**API Routing:**
| Model | Provider | Reason |
|-------|----------|--------|
| Opus 4.5 | OpenRouter | Standard access |
| Gemini 3 Pro | OpenRouter | Standard access |
| GPT-5.1 Codex | OpenAI Native | ZDR (Zero Data Retention) not available on OpenRouter |
| Sonnet 4.5 | OpenRouter | Standard access |

**API Keys Required:**
- `OPENROUTER_API_KEY` - for Opus, Gemini, Sonnet
- `OPENAI_API_KEY` - for GPT-5.1 Codex (native)

**Hypothesis:** Maximum quality regardless of cost. Establishes quality ceiling.

---

### 8. NVIDIA-Orchestrator (Local 8B Meta-Orchestrator)
**Purpose:** Replace expensive Opus orchestration with free local 8B model while keeping quality cloud workers.

```
┌─────────────────────────────────────────────────────────────┐
│          NVIDIA ORCHESTRATOR-8B (LOCAL)                     │
│         (Planning + Validation + Retry)                     │
│     Running on M4 Max via mlx-lm @ ~50 tok/s               │
│                   FREE ($0/token)                           │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌─────────────┐     ┌─────────┐
   │ Context │  →   │ Engineering │  →  │ Review  │
   │Gemini   │      │  Qwen3-235B │     │ Kimi-K2 │
   │ 2.5 Pro │      │  (Cerebras) │     │ (Groq)  │
   └─────────┘      └─────────────┘     └─────────┘
     (Cloud)          (Cloud)           (Cloud)
```

**Key Innovation:**
- NVIDIA Orchestrator-8B achieves **37.1% on Humanity's Last Exam** (beats GPT-5 at 35.1%)
- 2.5x faster orchestration (no network latency)
- 70% cheaper overall (orchestration is free)
- Same quality workers for actual code generation

**Config:** `config/config_nvidia_orchestrator.yaml`
```yaml
meta_orchestrator:
  id: nvidia/Orchestrator-8B
  base_url: http://localhost:8000/v1  # Local inference server
  provider: local
  pricing:
    prompt: 0.00    # FREE - local inference
    completion: 0.00

agents:
  context:
    model: google/gemini-2.5-pro-preview
    provider: openrouter
    pricing:
      input: 2.00
      output: 12.00
    rationale: "1M context, best repo understanding"

  engineering:
    model: qwen-3-235b-a22b-instruct-2507
    provider: cerebras  # NATIVE - 735 tok/s
    pricing:
      input: 0.60
      output: 1.20
    rationale: "Very fast, good quality, cheap"

  review:
    model: moonshotai/kimi-k2-instruct-0905
    provider: groq  # NATIVE - 323 tok/s
    pricing:
      input: 0.20
      output: 0.20
    rationale: "Fast review, catches edge cases"
```

**Setup Requirements:**
```bash
# Install dependencies
pip install mlx-lm fastapi uvicorn

# Download model (~16GB)
huggingface-cli download nvidia/Orchestrator-8B

# Start local server
python scripts/local_orchestrator_server.py
```

**Cost Comparison vs Opus-Optimized:**

| Role | Opus-Optimized | NVIDIA-Orchestrator | Savings |
|------|----------------|---------------------|---------|
| Meta-Orchestrator | Opus ($5-25/M) | Local ($0) | **100%** |
| Context | Gemini ($2-12/M) | Gemini ($2-12/M) | 0% |
| Engineering | Qwen3 ($0.60-1.20/M) | Qwen3 ($0.60-1.20/M) | 0% |
| Review | Kimi ($0.20/M) | Kimi ($0.20/M) | 0% |
| **Total per task** | ~$0.12-0.18 | **~$0.05-0.10** | **~45%** |

**Hypothesis:** Can a specialized 8B orchestrator replace Opus 4.5 for planning/validation while maintaining quality through cloud workers?

---

## Benchmark Comparison Matrix

| Variant | LLM Judge | Code Eval | Combined | Execution | Cost | Time |
|---------|-----------|-----------|----------|-----------|------|------|
| Opus-Baseline | TBD | TBD | TBD | TBD | TBD | TBD |
| Opus-Opus | TBD | TBD | TBD | TBD | TBD | TBD |
| Opus-Sonnet | TBD | TBD | TBD | TBD | TBD | TBD |
| Opus-Gemini | TBD | TBD | TBD | TBD | TBD | TBD |
| Opus-Optimized | TBD | TBD | TBD | TBD | TBD | TBD |
| Opus-Open | TBD | TBD | TBD | TBD | TBD | TBD |
| Opus-BestInClass | TBD | TBD | TBD | TBD | TBD | TBD |
| NVIDIA-Orchestrator | TBD | TBD | TBD | TBD | TBD | TBD |

**Previous ALO Results (for reference):**
| Variant | LLM Judge | Code Eval | Combined | Execution | Cost |
|---------|-----------|-----------|----------|-----------|------|
| ALO-Opus | 8.50 | 6.00 | 7.25 | 2/10 | $1.43 |
| ALO-Optimized | 7.37 | 6.60 | 6.98 | 6/10 | $0.64 |

---

## Key Questions to Answer

1. **Does orchestration add value over baseline?**
   - Compare: Opus-Baseline vs all orchestrated variants
   - If baseline wins, orchestration is overhead

2. **Does Opus as orchestrator beat Opus as executor?**
   - Compare: Opus-Baseline vs Opus-Opus
   - Tests if planning/validation pattern works

3. **What's the optimal cost/quality tradeoff?**
   - Compare: Opus-Optimized vs Opus-BestInClass
   - Find the knee of the curve

4. **Can orchestration elevate weaker models?**
   - Compare: Opus-Open vs previous ALO-Open
   - Tests if Opus planning helps OSS models

5. **Is execution rate the key differentiator?**
   - Previous ALO-Opus: 8.50 LLM but 2/10 execution
   - Target: Can we get 8.5 LLM AND 8/10 execution?

---

## Implementation Priority

1. **Phase 1:** Opus-Baseline (control) + Opus-Opus (ceiling)
2. **Phase 2:** Opus-Optimized (target production) + Opus-Gemini
3. **Phase 3:** Opus-Sonnet + Opus-Open + Opus-BestInClass

---

## File Structure

```
config/
├── config_opus_baseline.yaml      # (none - direct API)
├── config_opus_opus.yaml
├── config_opus_sonnet.yaml
├── config_opus_gemini.yaml
├── config_opus_optimized.yaml
├── config_opus_open.yaml
├── config_opus_bestinclass.yaml
└── config_nvidia_orchestrator.yaml  # ✓ NEW - Local 8B orchestrator

scripts/
├── local_orchestrator_server.py   # ✓ NEW - Local inference server for Orchestrator-8B
└── ...

benchmark/runners/
├── opus_baseline_runner.py        # ✓ Created
├── opus_meta_runner.py            # Base class for orchestrated variants
├── opus_opus_runner.py
├── opus_sonnet_runner.py
├── opus_gemini_runner.py
├── opus_optimized_runner.py
├── opus_open_runner.py
├── opus_bestinclass_runner.py
└── nvidia_orchestrator_runner.py  # TBD - Local orchestrator runner
```
