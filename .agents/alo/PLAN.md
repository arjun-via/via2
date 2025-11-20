# Agentic Loops Orchestrator (ALO) Execution Plan

## Goal
Stand up the new ALO repo matching `NEW_REPO_SPEC.md`: loop-based orchestrator with specialized agents (Context, Repro, Engineering, Review), shared `LoopState`, structured logging/cost tracking, config-driven model settings, CLI entrypoint, and benchmark scaffolding. Use the existing Via Orchestrator repo as a reference for behavior and patterns, but keep the lean directory layout in the spec.

## Scope
- In-scope: Repository scaffolding; `LoopState` dataclass; `ToolRegistry`; model clients (OpenAI-compatible + Gemini); 4 agent implementations; orchestrator workflow; CLI; logging + JSONL traces; cost tracking; config loading; minimal tests to validate key flows; requirements/env samples.
- Out-of-scope (initial cut): Full SWE-bench data + large benchmark assets; cloud deployment; UI; advanced parallelization beyond the spec; migration of every legacy helper script.

## Approach
1. Mirror the roles/flow from the reference repo while simplifying to the new spec directory tree.
2. Config-first: all model IDs/params/prompts in `config/config.yaml` and `.env.example`.
3. Tooling-first: build `ToolRegistry` with guarded FS + shell calls; ensure stdout/stderr surfaced.
4. Logging/observability: structured logger to `alo.log` + JSONL trace; hook cost tracker into every model call.
5. TDD: define unit tests per module before implementations; integration-style tests only with explicit approval.

## Milestones & Tasks
1) Repository bootstrap
   - Create `alo/` package skeleton and `requirements.txt`, `.env.example`, `README.md` placeholder.
   - Add `config/config.yaml` loader utility.
2) Core primitives
   - Implement `LoopState` dataclass (shared state, history auditing).
   - Implement `ToolRegistry` with `list_files`, `read_file`, `write_file`, `run_command`, `grep_search`.
   - Implement logging setup + JSONL trace writer.
   - Implement `CostTracker` singleton.
3) Model clients
   - OpenAI-compatible client supporting OpenRouter/Cerebras extras.
   - Gemini client wrapper.
4) Agents
   - `ContextLoopAgent`, `ReproLoopAgent`, `EngineeringLoopAgent`, `ReviewLoopAgent` with loop logic per spec.
   - Ensure Engineering loop calls Review loop and respects repro results.
5) Orchestrator + CLI
   - Orchestrator coordinating plan/context/repro/engineering/review; manage `LoopState`.
   - CLI `main.py` to accept issue description + repo path.
6) Tests (unit-first)
   - Config loading, ToolRegistry behaviors, logging/trace stubs, CostTracker accounting.
   - Agent + orchestrator happy-path skeletons with mocked model/tool calls.
7) Docs & examples
   - Populate README from spec; usage instructions; quickstart.

## Risks / Mitigations
- Model/config mismatch → keep IDs/temps in config, validate at load time.
- Tooling side effects → sandbox `run_command` and limit paths; test read/write on temp dirs.
- Logging overhead → keep simple stdlib logging; optional verbosity flag.

## Testing Strategy
- Unit tests for utilities, state transitions, tool behaviors, cost tracking, orchestrator control flow with mocks.
- Integration tests will require explicit approval before adding/running.

## Open Questions
- None at present; will ask if model IDs/temperature defaults need to follow a specific variant beyond the spec.
