# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Agentic Loops Orchestrator (ALO)** is an autonomous software engineering agent system that uses multiple specialized LLMs working in coordinated loops to solve complex coding tasks. The system replaces linear LLM pipelines with a dynamic, iterative loop architecture where agents autonomously iterate until they satisfy their success criteria.

## Core Architecture

ALO uses a **stateful orchestrator** pattern that coordinates four specialized agent loops:

1. **Context Loop (Gemini 3)**: Analyzes the full repository with massive context window to identify relevant files and dependencies
2. **Reproduction Loop (GPT-5.1)**: Creates standalone reproduction scripts using ReAct pattern (Think -> Act -> Observe)
3. **Engineering Loop (GLM-4.6)**: Writes code fixes and iterates based on reproduction script results
4. **Review Loop (Kimi K2)**: Reviews proposed fixes for security and correctness, can reject and force re-iteration

All agents share a `LoopState` object that flows through the pipeline, accumulating context and results. The orchestrator manages handoffs and ensures the overall goal is met.

## Key Components

### State Management
- `alo/agentic_loops/core/state.py`: `LoopState` dataclass persists across all loops
- Contains: issue description, repo path, relevant files, context summary, repro script, history audit log
- `add_history()` method tracks all steps for observability

### Client Architecture
- `alo/backend/clients/openai_client.py`: `OpenAICompatibleClient` for GPT, GLM, Kimi (supports `extra_body` for OpenRouter/Cerebras)
- `alo/backend/clients/gemini_client.py`: `GeminiClient` using native Google SDK
- All clients integrated with `CostTracker` for token counting and cost estimation

### Tool System
- `alo/agentic_loops/core/tools.py`: `ToolRegistry` provides sandboxed filesystem and shell access
- Tools: `list_files`, `read_file`, `write_file`, `run_command`, `grep_search`
- All tools are workspace-scoped to prevent escaping target repository

### Observability
- `alo/agentic_loops/core/logging_utils.py`: Structured logging to `alo.log` and JSONL tracing to `trace.jsonl`
- `alo/agentic_loops/core/costs.py`: `CostTracker` singleton intercepts all API calls, tracks tokens/costs by model

## Running the System

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your keys: OPENAI_API_KEY, GEMINI_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY
```

### Code Fix Mode (Full Pipeline)
```bash
python main.py --issue "Fix race condition in cache.py" --repo /path/to/target/repo
```

### Prompt Mode (Context + Prompt Agent Only)
```bash
python main.py --prompt "Explain how authentication works in this codebase"
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_orchestrator_cli.py

# Run with verbose output
pytest -v

# Run single test
pytest tests/test_state_agents.py::test_context_agent_integration -v
```

### Model Smoke Test
```bash
# Verify API connectivity for all configured models
PYTHONPATH=. python scripts/model_smoketest.py
```

## Configuration

### config/config.yaml Structure
- `models`: Each agent's model ID, base_url, temperature, and pricing (prompt/completion cost per 1k tokens)
- `logging`: Log level configuration
- `prompts`: System prompt templates for each agent (supports variable interpolation)

### Model Configuration Pattern
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

### Adding a New Agent Loop
1. Create `alo/agentic_loops/new_loop/agent.py` with a class implementing `run(state: LoopState, tool_registry: ToolRegistry) -> LoopState`
2. Add client initialization in `main.py::build_orchestrator()`
3. Wire into orchestrator call chain in `ALOOrchestrator.run()`
4. Add corresponding prompt template to `config/config.yaml`

### Client Fallback Pattern
`main.py` uses `_safe_client()` wrapper that returns a `StubClient` if API initialization fails. This allows testing pipeline logic without live API credentials.

### Tool Call Pattern
Agents receive `tool_registry` and call tools synchronously:
```python
result = tool_registry.call_tool("read_file", {"path": "src/main.py"})
```

### Cost Tracking Integration
All clients must accept `cost_tracker`, `prompt_cost_per_1k`, and `completion_cost_per_1k` parameters and call `cost_tracker.track_usage()` after each API call.

## Important Implementation Details

### Engineering-Review Loop Interaction
`EngineeringLoopAgent` calls `ReviewLoopAgent` internally before declaring success. If review fails, engineering loops back to revise the fix. This creates a nested loop pattern.

### Prompt Orchestrator vs ALO Orchestrator
- `ALOOrchestrator`: Full pipeline (Context -> Repro -> Engineering w/ Review)
- `PromptOrchestrator`: Simplified pipeline (Context -> Prompt Agent) for question-answering tasks

### Trace Format
`trace.jsonl` records one JSON object per line:
```json
{"timestamp": "ISO-8601", "event": "start|complete|agent_name", "source": "class_name", "data": {...}}
```

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

Use `conftest.py` fixtures for common setup (temp directories, stub clients, etc.).
