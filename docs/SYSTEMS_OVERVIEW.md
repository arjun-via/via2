# Via2 - Three Agent Systems Overview

This document is the master reference for the three autonomous agent systems in the Via2 repository.

---

## Quick Reference

| System | Models | Architecture | Entry Point | Best For |
|--------|--------|--------------|-------------|----------|
| **ALO** | Gemini, GPT, GLM, Kimi | Multi-model pipeline | `python main.py` | Complex multi-step tasks |
| **Opus Orchestrator** | Claude Opus 4.5 | Single-model Docker loop | `benchmark/run_opus_agentic.py` | SWE-bench bug fixes |
| **Dynamic** | Multiple (adaptive) | Model selection + learning | `config/config_opus_meta_*.yaml` | Cost-optimized execution |

---

## System 1: ALO (Agentic Loops Orchestrator)

### Overview
Multi-model pipeline that coordinates four specialized agent loops, each using a different LLM optimized for its specific role.

### Architecture
```
┌─────────────┐    ┌─────────────┐    ┌─────────────────┐    ┌─────────────┐
│  CONTEXT    │───▶│   REPRO     │───▶│  ENGINEERING    │───▶│   REVIEW    │
│  (Gemini)   │    │   (GPT)     │    │    (GLM)        │    │   (Kimi)    │
└─────────────┘    └─────────────┘    └─────────────────┘    └─────────────┘
```

### Agent Roles
| Agent | Model | Purpose |
|-------|-------|---------|
| **Context** | Gemini (1M+ context) | Analyzes full repository, identifies relevant files |
| **Reproduction** | GPT | Creates standalone reproduction scripts (ReAct pattern) |
| **Engineering** | GLM | Writes code fixes, iterates based on repro results |
| **Review** | Kimi K2 | Reviews for security/correctness, can reject |

### Key Components
- `alo/agentic_loops/core/orchestrator.py` - `ALOOrchestrator` class
- `alo/agentic_loops/{context,repro,engineering,review}_loop/agent.py` - Agent implementations
- `alo/agentic_loops/core/state.py` - `LoopState` shared across all loops

### Usage
```bash
# Fix a bug
python main.py --issue "Describe the bug" --repo /path/to/repo

# Ask a question about a codebase
python main.py --prompt "Explain how authentication works"
```

### Configuration
- `config/config.yaml` - Base configuration
- `config/config_alo_*.yaml` - Variant configurations

---

## System 2: Opus Orchestrator

### Overview
Single-model system using Claude Opus 4.5 in an iterative THINK → ACT → OBSERVE loop with Docker execution. Designed for 75%+ SWE-bench resolution.

### Architecture
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

### Key Techniques
1. **One command per response** - Prevents hallucination
2. **Docker execution** - Real output from SWE-bench containers
3. **Patch validation** - Ensures source file changes (not just test files)
4. **Hallucination detection** - Catches imagined outputs

### Key Components
- `alo/agentic_loops/opus_orchestrator/agentic_loop.py` - `AgenticLoop` class
- `alo/agentic_loops/opus_orchestrator/docker_executor.py` - `DockerExecutor` class
- `benchmark/run_opus_agentic.py` - SWE-bench benchmark runner

### Usage
```bash
# Run on random instances
python benchmark/run_opus_agentic.py --num 25 --random --seed 2024 --output results.jsonl

# Run sequential
python benchmark/run_opus_agentic.py --num 10 --start 0 --output test.jsonl
```

### Model
`claude-opus-4-5-20251101` (Opus 4.5)

### Metrics
- Average cost: ~$2/instance
- Average steps: 12-21
- Patch generation rate: 64-100%

---

## System 3: Dynamic (Model Selection & Compounding)

### Overview
Adaptive system that learns optimal model selection based on task characteristics and compounds knowledge from previous runs.

### Key Components
- `alo/agentic_loops/opus_orchestrator/model_selection_learner.py` - Learns model-task mappings
- `alo/agentic_loops/opus_orchestrator/compounding_learner.py` - Knowledge compounding
- `alo/agentic_loops/opus_orchestrator/meta_orchestrator.py` - `OpusMetaOrchestrator`

### Variants
| Variant | Description | Config |
|---------|-------------|--------|
| **BestInClass** | Top model per role | `config_opus_meta_bestinclass.yaml` |
| **Optimized** | Cost/performance balanced | `config_opus_meta_optimized.yaml` |
| **Open** | Open-source models only | `config_opus_meta_open.yaml` |
| **Full** | All available models | `config_opus_meta_full.yaml` |

### Usage
Uses configuration files. Select variant by specifying the appropriate config.

---

## Comparison Table

| Feature | ALO | Opus Orchestrator | Dynamic |
|---------|-----|-------------------|---------|
| **# of Models** | 4 | 1 | Variable |
| **Execution** | Tool-based | Docker containers | Varies |
| **State** | LoopState shared | Conversation history | Learned |
| **Target** | General tasks | SWE-bench | Cost-optimized |
| **Cost per task** | ~$0.50-2.00 | ~$2-4 | Varies |

---

## Directory Structure

```
Via2/
├── alo/
│   └── agentic_loops/
│       ├── core/                  # Shared infrastructure (ALO + all systems)
│       │   ├── orchestrator.py    # ALOOrchestrator
│       │   ├── state.py          # LoopState
│       │   ├── tools.py          # ToolRegistry
│       │   └── costs.py          # CostTracker
│       ├── context_loop/         # ALO: Context agent
│       ├── repro_loop/           # ALO: Reproduction agent
│       ├── engineering_loop/     # ALO: Engineering agent
│       ├── review_loop/          # ALO: Review agent
│       └── opus_orchestrator/    # Opus Orchestrator + Dynamic
│           ├── agentic_loop.py   # AgenticLoop
│           ├── docker_executor.py
│           ├── meta_orchestrator.py
│           ├── model_selection_learner.py
│           └── compounding_learner.py
├── config/
│   ├── config.yaml              # ALO base
│   ├── config_alo_*.yaml        # ALO variants
│   └── config_opus_meta_*.yaml  # Dynamic variants
└── benchmark/
    └── run_opus_agentic.py      # Opus Orchestrator runner
```

---

## When to Use Each System

### Use ALO when:
- Task requires multiple specialized capabilities
- You want diverse model perspectives
- General software engineering tasks
- Budget allows for multi-model costs

### Use Opus Orchestrator when:
- Targeting SWE-bench or similar bug-fix benchmarks
- Maximum accuracy is the priority (cost is secondary)
- Task requires iterative exploration with real execution
- Working with Docker-containerized repositories

### Use Dynamic when:
- Cost optimization is important
- Tasks have varied complexity levels
- You want to leverage learned model preferences
- Running many similar tasks

---

*Last Updated: 2025-11-28*
