# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Via2** is an autonomous software engineering agent repository containing three distinct systems for solving coding tasks:

| System | Description | Models | Entry Point |
|--------|-------------|--------|-------------|
| **ALO** | Multi-model pipeline with 4 specialized agents | Gemini, GPT, GLM, Kimi | `python main.py` |
| **Opus Orchestrator** | Single-model iterative Docker loop | Claude Opus 4.5 | `python benchmark/run_opus_agentic.py` |
| **Dynamic** | Adaptive model selection with learning | Multiple, dynamically selected | `config/config_opus_meta_*.yaml` |

---

## System 1: ALO (Agentic Loops Orchestrator)

Multi-model pipeline coordinating four specialized agent loops:

```
Context (Gemini) → Repro (GPT) → Engineering (GLM) → Review (Kimi)
```

### Architecture
- **Context Loop**: Analyzes full repository with massive context window
- **Reproduction Loop**: Creates standalone reproduction scripts (ReAct pattern)
- **Engineering Loop**: Writes code fixes, iterates based on reproduction results
- **Review Loop**: Reviews fixes for security/correctness, can reject and force re-iteration

All agents share a `LoopState` object that flows through the pipeline.

### Key Components
- `alo/agentic_loops/core/orchestrator.py`: `ALOOrchestrator` class
- `alo/agentic_loops/{context,repro,engineering,review}_loop/agent.py`: Agent implementations
- `config/config.yaml` and `config/config_alo_*.yaml`: Configurations

### Running ALO
```bash
python main.py --issue "Fix race condition in cache.py" --repo /path/to/target/repo
```

---

## System 2: Opus Orchestrator

Single-model system using Claude Opus 4.5 in an iterative THINK → ACT → OBSERVE loop.

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
- **One command per response**: Prevents hallucination of command output
- **Docker execution**: Commands run in SWE-bench containers
- **Patch validation**: Ensures source file changes (not just test files)
- **Hallucination detection**: Catches when model imagines output

### Key Components
- `alo/agentic_loops/opus_orchestrator/agentic_loop.py`: Core `AgenticLoop` class
- `alo/agentic_loops/opus_orchestrator/docker_executor.py`: `DockerExecutor` class
- `benchmark/run_opus_agentic.py`: SWE-bench runner

### Running Opus Orchestrator
```bash
python benchmark/run_opus_agentic.py --num 25 --random --output results.jsonl
```

### Model
`claude-opus-4-5-20251101` (Opus 4.5)

---

## System 3: Dynamic (Model Selection & Compounding)

Adaptive system that learns optimal model selection based on task characteristics.

### Components
- `alo/agentic_loops/opus_orchestrator/model_selection_learner.py`: Learns model-task mappings
- `alo/agentic_loops/opus_orchestrator/compounding_learner.py`: Knowledge compounding
- `alo/agentic_loops/opus_orchestrator/meta_orchestrator.py`: `OpusMetaOrchestrator` class

### Variants
- **BestInClass**: Top models per role
- **Optimized**: Cost/performance balanced
- **Open**: Open-source models only

### Configuration
`config/config_opus_meta_*.yaml`

---

## Shared Infrastructure

### State Management
- `alo/agentic_loops/core/state.py`: `LoopState` dataclass persists across all loops
- Contains: issue description, repo path, relevant files, context summary, repro script, history audit log

### Client Architecture
- `alo/backend/clients/openai_client.py`: `OpenAICompatibleClient` for GPT, GLM, Kimi
- `alo/backend/clients/gemini_client.py`: `GeminiClient` using native Google SDK
- All clients integrated with `CostTracker` for token counting and cost estimation

### Tool System
- `alo/agentic_loops/core/tools.py`: `ToolRegistry` provides sandboxed filesystem and shell access
- Tools: `list_files`, `read_file`, `write_file`, `run_command`, `grep_search`

### Observability
- `alo/agentic_loops/core/logging_utils.py`: Structured logging to `alo.log` and JSONL tracing to `trace.jsonl`
- `alo/agentic_loops/core/costs.py`: `CostTracker` singleton tracks tokens/costs by model

---

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with: ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY
```

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_orchestrator_cli.py

# Model connectivity smoke test
PYTHONPATH=. python scripts/model_smoketest.py
```

## Configuration

### config/config.yaml Structure
```yaml
models:
  agent_name:
    id: "model-identifier"
    base_url: "https://api.provider.com/v1"
    temperature: 0
    pricing:
      prompt: 0.002    # per 1k tokens
      completion: 0.006
```

## Development Patterns

### Adding a New Agent Loop (ALO)
1. Create `alo/agentic_loops/new_loop/agent.py` implementing `run(state: LoopState, tool_registry: ToolRegistry) -> LoopState`
2. Add client initialization in `main.py::build_orchestrator()`
3. Wire into orchestrator call chain in `ALOOrchestrator.run()`
4. Add corresponding prompt template to `config/config.yaml`

### Tool Call Pattern
```python
result = tool_registry.call_tool("read_file", {"path": "src/main.py"})
```

### Cost Tracking Integration
All clients must accept `cost_tracker`, `prompt_cost_per_1k`, and `completion_cost_per_1k` parameters and call `cost_tracker.track_usage()` after each API call.

## Testing Philosophy

Tests are organized by component:
- `test_config.py`: Configuration loading and validation
- `test_clients.py`: API client mocking and error handling
- `test_tools.py`: Tool registry filesystem operations
- `test_state_agents.py`: Individual agent loop behavior
- `test_orchestrator_cli.py`: End-to-end CLI argument parsing
- `test_integration_orchestrator.py`: Full pipeline with stub clients
- `test_logging_tracing.py`: Observability infrastructure
- `test_cost_tracker.py`: Token counting and cost calculation

---

*Last Updated: 2025-11-28*
