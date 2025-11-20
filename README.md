# Agentic Loops Orchestrator (ALO)

Lightweight implementation of the loop-based orchestrator described in `NEW_REPO_SPEC.md`. This repo wires four specialized agents (Context, Repro, Engineering, Review) under a single orchestrator, with shared `LoopState`, tool access, logging/tracing, and cost tracking hooks.

## Quick start
1. Create a virtualenv and install deps:
   ```bash
   pip install -r requirements.txt
   ```
2. Add your API keys to `.env` (see `.env.example`).
3. Run the CLI:
   ```bash
   python main.py --issue "Describe the bug" --repo /path/to/repo
   ```

## Layout
- `alo/config/loader.py` — config + env overrides.
- `alo/agentic_loops/core/` — `LoopState`, tools, logging/tracing, cost tracker, orchestrator.
- `alo/agentic_loops/{context,repro,engineering,review}_loop/agent.py` — loop agents.
- `alo/backend/clients/` — OpenAI-compatible + Gemini clients.
- `tests/` — unit tests for config, tools, logging, clients, agents, orchestrator, CLI.

## Testing
Run all unit tests:
```bash
pytest
```

## Model smoke test
To verify API wiring for configured models, set your keys in `.env` and run:
```bash
PYTHONPATH=. python scripts/model_smoketest.py
```
This sends a small “ping” to each configured model and reports success/failure.
