# Via2 - Autonomous Software Engineering Agent Systems

This repository contains three distinct autonomous agent systems for solving software engineering tasks, particularly SWE-bench bug fixes.

## Three Systems Overview

| System | Description | Models Used | Best For |
|--------|-------------|-------------|----------|
| **ALO** | Multi-model pipeline with specialized agents | Gemini, GPT, GLM, Kimi | Complex multi-step tasks |
| **Opus Orchestrator** | Single-model iterative loop with Docker | Claude Opus 4.5 only | SWE-bench bug fixes |
| **Dynamic** | Adaptive model selection with learning | Multiple models, dynamically selected | Cost-optimized execution |

---

## 1. ALO (Agentic Loops Orchestrator)

Multi-model pipeline that coordinates four specialized agent loops:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────────┐    ┌─────────────┐
│  CONTEXT    │───▶│   REPRO     │───▶│  ENGINEERING    │───▶│   REVIEW    │
│  (Gemini)   │    │   (GPT)     │    │    (GLM)        │    │   (Kimi)    │
└─────────────┘    └─────────────┘    └─────────────────┘    └─────────────┘
```

**Components:**
- `alo/agentic_loops/context_loop/` - Analyzes full repo with massive context window
- `alo/agentic_loops/repro_loop/` - Creates reproduction scripts (ReAct pattern)
- `alo/agentic_loops/engineering_loop/` - Writes code fixes
- `alo/agentic_loops/review_loop/` - Reviews fixes for security/correctness

**Usage:**
```bash
python main.py --issue "Describe the bug" --repo /path/to/repo
```

**Config:** `config/config.yaml` and variants (`config_alo_*.yaml`)

---

## 2. Opus Orchestrator

Single-model system using Claude Opus 4.5 in an iterative THINK → ACT → OBSERVE loop with Docker execution.

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

**Key Techniques:**
- One command per LLM response (prevents hallucination)
- Docker-based execution in SWE-bench containers
- Patch validation ensures source file changes (not just test files)

**Components:**
- `alo/agentic_loops/opus_orchestrator/agentic_loop.py` - Core loop
- `alo/agentic_loops/opus_orchestrator/docker_executor.py` - Docker execution
- `benchmark/run_opus_agentic.py` - SWE-bench runner

**Usage:**
```bash
python benchmark/run_opus_agentic.py --num 25 --random --output results.jsonl
```

**Model:** `claude-opus-4-5-20251101` (Opus 4.5)

---

## 3. Dynamic (Model Selection & Compounding)

Adaptive system that learns optimal model selection based on task characteristics.

**Components:**
- `alo/agentic_loops/opus_orchestrator/model_selection_learner.py` - Learns model-task mappings
- `alo/agentic_loops/opus_orchestrator/compounding_learner.py` - Knowledge compounding
- `alo/agentic_loops/opus_orchestrator/meta_orchestrator.py` - Orchestrates with dynamic selection

**Variants:**
- BestInClass - Top models per role
- Optimized - Cost/performance balanced
- Open - Open-source models only

**Config:** `config/config_opus_meta_*.yaml`

---

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Add API keys to `.env` (see `.env.example`):
   ```
   ANTHROPIC_API_KEY=...
   OPENAI_API_KEY=...
   GEMINI_API_KEY=...
   ```

3. Run the desired system:
   ```bash
   # ALO multi-model pipeline
   python main.py --issue "Bug description" --repo /path/to/repo

   # Opus Orchestrator single-model
   python benchmark/run_opus_agentic.py --num 5 --output test.jsonl
   ```

## Directory Structure

```
Via2/
├── alo/
│   ├── agentic_loops/
│   │   ├── core/           # Shared: state, tools, logging, costs
│   │   ├── context_loop/   # ALO: Context agent
│   │   ├── repro_loop/     # ALO: Reproduction agent
│   │   ├── engineering_loop/ # ALO: Engineering agent
│   │   ├── review_loop/    # ALO: Review agent
│   │   ├── prompt_loop/    # ALO: Prompt agent
│   │   └── opus_orchestrator/ # Opus Orchestrator + Dynamic
│   ├── backend/clients/    # API clients (OpenAI, Gemini)
│   └── config/             # Config loader
├── benchmark/              # Benchmark runners and analysis
├── config/                 # YAML configurations
├── docs/                   # Documentation
└── tests/                  # Unit tests
```

## Testing

```bash
# Run all tests
pytest

# Model connectivity smoke test
PYTHONPATH=. python scripts/model_smoketest.py
```

## Documentation

- `docs/OPUS_AGENTIC_OVERVIEW.md` - Opus Orchestrator details
- `docs/OPUS_ORCHESTRATOR_VARIANTS.md` - Dynamic system variants
- `CLAUDE.md` - Development instructions for Claude Code

---

*Last Updated: 2025-11-28*
