# Via2 Version Comparison Guide

This document provides a comprehensive side-by-side comparison of all system variants in the Via2 repository.

**Last Updated:** 2025-11-30

---

## Quick Reference Matrix

| System | Variant | Config File | Entry Point | Cost | Quality | Speed |
|--------|---------|-------------|-------------|------|---------|-------|
| ALO | Default | `config.yaml` | `main.py` | $$ | High | Medium |
| ALO | Optimized | `config_alo_optimized.yaml` | `main.py` | $$ | High | Medium |
| ALO | BestInClass | `config_alo_bestinclass.yaml` | `main.py` | $$$ | Highest | Slow |
| ALO | Open | `config_alo_open.yaml` | `main.py` | $ | Moderate | Medium |
| ALO | Sonnet | `config_alo_sonnet.yaml` | `main.py` | $$ | High | Medium |
| ALO | Opus | `config_alo_opus.yaml` | `main.py` | $$$ | Highest | Slow |
| Opus Orch | Standard | N/A | `run_opus_agentic.py` | $$$ | Highest | Slow |
| Dynamic | BestInClass | `config_opus_meta_bestinclass.yaml` | Meta-orchestrator | $$$ | Highest | 45-90 tok/s |
| Dynamic | Optimized | `config_opus_meta_optimized.yaml` | Meta-orchestrator | $$ | High | 90-735 tok/s |
| Dynamic | Full | `config_opus_meta_full.yaml` | Meta-orchestrator | $$$ | Highest | Variable |
| Dynamic | Open | `config_opus_meta_open.yaml` | Meta-orchestrator | $ | Moderate | Variable |

---

## System 1: ALO (Agentic Loops Orchestrator)

### Architecture
Multi-model 4-stage pipeline where each stage uses a specialized model:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   CONTEXT   │───▶│    REPRO    │───▶│ ENGINEERING │───▶│   REVIEW    │
│   (Gemini)  │    │   (GPT)     │    │ (GLM/Qwen)  │    │   (Kimi)    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### Entry Point
```bash
python main.py --issue "Bug description" --repo /path/to/repo
```

### Variants

#### ALO Default
- **Config:** `config/config.yaml`
- **Models:**
  - Context: Gemini 2.5 Flash (OpenRouter)
  - Repro: GPT-5.1 (OpenAI)
  - Engineering: GLM-4.6 (Cerebras)
  - Review: Kimi K2 (OpenRouter)
- **Best For:** Production baseline
- **Cost:** ~$0.50-2.00 per task

#### ALO Optimized
- **Config:** `config/config_alo_optimized.yaml`
- **Models:**
  - Context: Gemini 2.5 Flash (OpenRouter) - Fast, cheap
  - Repro: GPT-5.1 (OpenAI)
  - Engineering: Qwen3-Coder (OpenRouter) - 20x cheaper than GLM
  - Review: Kimi K2-Thinking (OpenRouter)
- **Best For:** Cost/quality balance (RECOMMENDED for most tasks)
- **Cost:** ~40% reduction vs BestInClass

#### ALO BestInClass
- **Config:** `config/config_alo_bestinclass.yaml`
- **Models:**
  - Context: Gemini 3 Pro (OpenRouter) - Best context understanding
  - Repro: GPT-5.1 (OpenAI) - Most reliable
  - Engineering: Claude Sonnet 4.5 (Anthropic) - Premium
  - Review: Premium reasoning models
- **Best For:** Complex architecture, critical systems, high-stakes tasks
- **Cost:** HIGH (premium models throughout)

#### ALO Open
- **Config:** `config/config_alo_open.yaml`
- **Models:**
  - All open-source/commodity models
  - Kimi K2 orchestrator
  - GLM-4.6 for engineering
  - Qwen3-Coder alternatives
- **Best For:** On-premise deployment, cost minimization, regulatory constraints
- **Cost:** LOW

#### ALO Sonnet
- **Config:** `config/config_alo_sonnet.yaml`
- **Models:**
  - All stages: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
  - Single provider simplification
- **Best For:** Simplified testing, single-provider deployments
- **Cost:** MODERATE

#### ALO Opus
- **Config:** `config/config_alo_opus.yaml`
- **Models:**
  - All stages: Claude Opus 4.5 (claude-opus-4-5-20251101)
  - Premium single-model approach
- **Best For:** Maximum quality when cost is not a constraint
- **Cost:** HIGH

---

## System 2: Opus Orchestrator

### Architecture
Single-model iterative loop with real Docker execution:

```
┌────────────────────────────────────────────────────────────────┐
│                    AGENTIC LOOP CYCLE                          │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────────┐   │
│  │  THINK   │────▶│     ACT      │────▶│    OBSERVE       │   │
│  │  Claude  │     │  Execute ONE │     │  Get real output │   │
│  │  Opus    │     │  bash command│     │  from Docker     │   │
│  └──────────┘     └──────────────┘     └──────────────────┘   │
│       ▲                                         │              │
│       └─────── Iterate until SUBMIT ────────────┘              │
└────────────────────────────────────────────────────────────────┘
```

### Entry Point
```bash
python benchmark/run_opus_agentic.py --num 25 --random --output results.jsonl
```

### Key Characteristics
- **Model:** Claude Opus 4.5 (claude-opus-4-5-20251101)
- **Execution:** Docker containers (real command output, no simulation)
- **Cost:** ~$2-4 per instance
- **Performance:** 75%+ SWE-bench resolution rate
- **Average Steps:** 12-21 per task

### Key Techniques
- **One command per response:** Prevents hallucination of command output
- **Real Docker execution:** Commands run in SWE-bench containers
- **Patch validation:** Ensures source file changes (not just test files)
- **Hallucination detection:** Catches when model imagines output

### Key Files
- `alo/agentic_loops/opus_orchestrator/agentic_loop.py` - Core `AgenticLoop` class
- `alo/agentic_loops/opus_orchestrator/docker_executor.py` - `DockerExecutor` class
- `benchmark/run_opus_agentic.py` - SWE-bench runner

---

## System 3: Dynamic (Opus Meta-Orchestrator)

### Architecture
Adaptive model selection with Opus as strategic orchestrator:

```
┌──────────────────────────────────────────────────────────────┐
│              OPUS META-ORCHESTRATOR (Strategic)              │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Planning   │  │ Model Selection │  │   Validation    │  │
│  │  & Strategy │  │   & Learning    │  │   & Retry       │  │
│  └─────────────┘  └─────────────────┘  └─────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
   ┌──────────┐       ┌──────────┐       ┌──────────┐
   │ CONTEXT  │       │ ENGINE   │       │ REVIEW   │
   │ (Selected│       │ (Selected│       │ (Selected│
   │  Model)  │       │  Model)  │       │  Model)  │
   └──────────┘       └──────────┘       └──────────┘
```

### Key Components
- `meta_orchestrator.py` - `OpusMetaOrchestrator` class
- `model_selection_learner.py` - Learns model-task mappings
- `compounding_learner.py` - Knowledge compounding from prior runs
- `strategic_planner.py` - Creates execution plans
- `adaptive_validator.py` - Validates solutions

### Variants

#### Dynamic BestInClass
- **Config:** `config/config_opus_meta_bestinclass.yaml`
- **Architecture:**
  - Meta-Orchestrator: Opus 4 (planning & validation)
  - Context: Gemini 2.5 Pro (1M context window)
  - Engineering: Premium models (GPT-5.1 or Sonnet)
  - Review: Premium reasoning models
- **Speed:** 45-90 tok/s (MODERATE)
- **Cost:** HIGH
- **Best For:** Complex architecture, critical systems

#### Dynamic Optimized (RECOMMENDED)
- **Config:** `config/config_opus_meta_optimized.yaml`
- **Architecture:**
  - Meta-Orchestrator: Opus 4 via OpenRouter
  - Context: Gemini 2.5 Pro (90 tok/s, 1M window)
  - Engineering: Qwen3-235B via Cerebras (735 tok/s - FASTEST)
  - Review: Diverse models for redundancy
- **Speed:** 90-735 tok/s (FAST)
- **Cost:** MODERATE
- **Best For:** Most production tasks, standard development

#### Dynamic Full
- **Config:** `config/config_opus_meta_full.yaml`
- **Architecture:**
  - All available premium models
  - Maximum model diversity
- **Speed:** Variable
- **Cost:** HIGH
- **Best For:** Research and evaluation

#### Dynamic Open
- **Config:** `config/config_opus_meta_open.yaml`
- **Architecture:**
  - Open-source models only
  - No proprietary APIs
- **Speed:** Variable
- **Cost:** LOW
- **Best For:** On-premise deployment, regulatory constraints

---

## Git Branches

| Branch | Focus | Status |
|--------|-------|--------|
| **OpusOrch** | Opus Orchestrator + Meta system development | Active (current) |
| **EvalPlus** | EvalPlus benchmark integration | Feature branch |
| **main** | Production baseline | Stable |

---

## Benchmark Scripts

### Primary Runners

| Script | System | Dataset | Usage |
|--------|--------|---------|-------|
| `run_opus_agentic.py` | Opus Orchestrator | SWE-bench Verified | `python benchmark/run_opus_agentic.py --num 25 --random --output results.jsonl` |
| `run_swebench_alo.py` | ALO (any variant) | SWE-bench | `python benchmark/run_swebench_alo.py --config config/config_alo_optimized.yaml` |
| `run_humaneval_alo.py` | ALO | HumanEval | `python benchmark/run_humaneval_alo.py` |
| `run_evalplus_alo_unsafe.py` | ALO | EvalPlus | `python benchmark/run_evalplus_alo_unsafe.py` |

### Comparison Benchmarks

| Script | Purpose |
|--------|---------|
| `run_final_5way.py` | Compare all 5 ALO variants |
| `run_complete_5way_benchmark.py` | Extended 5-way comparison |
| `run_final_4way.py` | 4-way comparison |
| `run_quick_4way_test.py` | Quick smoke test |

---

## Model Provider Ecosystem

| Provider | Models | Use Case |
|----------|--------|----------|
| **Anthropic** | Claude Sonnet 4.5, Claude Opus 4.5 | Premium quality |
| **OpenAI** | GPT-5.1 | Reliable code generation |
| **Google** | Gemini 2.5 Flash/Pro, Gemini 3 Pro | Large context (1M+ tokens) |
| **Cerebras** | Qwen3-235B, GLM-4.6 | Speed (735 tok/s) |
| **OpenRouter** | Multi-provider aggregation | Unified API |
| **Moonshot** | Kimi K2 variants | Deep reasoning |

### Model Role Specializations

| Role | Primary | Alternatives | Why |
|------|---------|--------------|-----|
| Context | Gemini | GLM, Qwen | Massive context window (1M tokens) |
| Repro | GPT-5.1 | Sonnet, Opus | Code generation accuracy |
| Engineering | Qwen3-Coder, GLM | Sonnet, Opus | Speed or quality trade-off |
| Review | Kimi K2 | Opus, Sonnet | Deep reasoning for code review |

---

## Decision Guide: Which System to Use?

### Use ALO When:
- Task requires multi-step specialized reasoning
- You want cost/quality optimization per stage
- Working on complex codebases with large context needs
- Need reproducible bug reproduction scripts

### Use Opus Orchestrator When:
- Solving SWE-bench style bug fixes
- Need real environment testing (Docker)
- Want highest single-model quality
- Hallucination prevention is critical

### Use Dynamic/Meta-Orchestrator When:
- Want adaptive model selection based on task type
- Need cost optimization with learning
- Running many similar tasks (benefits from learned patterns)
- Want Opus strategic planning with specialized executors

---

## Performance Benchmarks

### ALO System
- **Cost per task:** $0.50-2.00
- **Execution time:** Variable (multi-stage pipeline)
- **Success factors:** Stage-appropriate model selection

### Opus Orchestrator
- **Cost per instance:** ~$2-4
- **SWE-bench resolution:** 75%+
- **Average steps:** 12-21
- **Patch generation rate:** 64-100%

### Dynamic System (from model selection training)
| Model | Success Rate | Speed | Best At |
|-------|--------------|-------|---------|
| qwen3-235b | ~95% | Fastest (735 tok/s) | General tasks |
| glm-4.6 | ~88% | Fast | thread_pool concurrency |
| sonnet-4.5 | ~89% | Medium | Complex reasoning |
| gemini-3-pro | ~67% | Slow (20-45s) | Large context |

---

## File Locations

### Configuration Files
```
config/
├── config.yaml                      # ALO Default
├── config_alo_optimized.yaml        # ALO Optimized
├── config_alo_bestinclass.yaml      # ALO BestInClass
├── config_alo_open.yaml             # ALO Open
├── config_alo_sonnet.yaml           # ALO Sonnet
├── config_alo_opus.yaml             # ALO Opus
├── config_opus_baseline.yaml        # Opus Baseline
├── config_opus_meta_bestinclass.yaml # Dynamic BestInClass
├── config_opus_meta_optimized.yaml  # Dynamic Optimized
├── config_opus_meta_full.yaml       # Dynamic Full
└── config_opus_meta_open.yaml       # Dynamic Open
```

### Core Implementation
```
alo/agentic_loops/
├── core/
│   ├── orchestrator.py              # ALOOrchestrator
│   ├── state.py                     # LoopState
│   ├── tools.py                     # ToolRegistry
│   └── costs.py                     # CostTracker
├── context_loop/agent.py            # Context Agent
├── repro_loop/agent.py              # Repro Agent
├── engineering_loop/agent.py        # Engineering Agent
├── review_loop/agent.py             # Review Agent
└── opus_orchestrator/
    ├── agentic_loop.py              # AgenticLoop
    ├── docker_executor.py           # DockerExecutor
    ├── meta_orchestrator.py         # OpusMetaOrchestrator
    ├── model_selection_learner.py   # ModelSelectionLearner
    └── compounding_learner.py       # CompoundingLearner
```

---

## Quick Start Examples

### Run ALO Optimized on a bug
```bash
python main.py --issue "Fix race condition in cache.py" --repo /path/to/repo --config config/config_alo_optimized.yaml
```

### Run Opus Orchestrator on SWE-bench
```bash
python benchmark/run_opus_agentic.py --num 10 --random --output my_results.jsonl
```

### Compare all ALO variants
```bash
python benchmark/run_final_5way.py
```

### Run specific ALO variant on SWE-bench
```bash
python benchmark/run_swebench_alo.py --config config/config_alo_bestinclass.yaml --num 25
```

---

*This document is part of the Via2 autonomous agent repository.*
