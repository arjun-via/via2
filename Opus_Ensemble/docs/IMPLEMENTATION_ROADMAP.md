# Opus Conductor Implementation Roadmap

## System Overview: What We're Building

### The Big Picture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OPUS CONDUCTOR SYSTEM                              │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        CLI / API INTERFACE                           │    │
│  │                     orchestrator-run --task ...                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         OPUS CONDUCTOR                               │    │
│  │                    (Central Brain / Orchestrator)                    │    │
│  │                                                                      │    │
│  │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │    │
│  │   │ Planning │─▶│ Context  │─▶│Engineering│─▶│  Review  │           │    │
│  │   │  Stage   │  │  Stage   │  │  Stage   │  │  Stage   │           │    │
│  │   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘           │    │
│  │        │             │             │             │                  │    │
│  │        ▼             ▼             ▼             ▼                  │    │
│  │   ┌──────────────────────────────────────────────────────┐         │    │
│  │   │              VALIDATION CHECKPOINTS                   │         │    │
│  │   │         (Opus validates after EVERY stage)            │         │    │
│  │   └──────────────────────────────────────────────────────┘         │    │
│  │                              │                                      │    │
│  │                              ▼                                      │    │
│  │   ┌──────────────────────────────────────────────────────┐         │    │
│  │   │                  EXECUTION STAGE                      │         │    │
│  │   │              (Run tests, verify solution)             │         │    │
│  │   └──────────────────────────────────────────────────────┘         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│          ┌─────────────────────────┼─────────────────────────┐              │
│          ▼                         ▼                         ▼              │
│  ┌───────────────┐    ┌───────────────────────┐    ┌─────────────────┐     │
│  │   SHARED      │    │   RESILIENT MODEL     │    │   VALIDATION    │     │
│  │   STATE       │    │      CLIENT           │    │   FRAMEWORK     │     │
│  │               │    │                       │    │                 │     │
│  │ - task_id     │    │ Opus 4.5 (conductor)  │    │ - StaticAnalyzer│     │
│  │ - imports     │    │ Gemini (context)      │    │ - ExecutionValid│     │
│  │ - edge_cases  │    │ Sonnet (engineering)  │    │ - FailureClassif│     │
│  │ - code        │    │ GPT-5 (review)        │    │ - CircuitBreaker│     │
│  │ - checkpoints │    │                       │    │                 │     │
│  │ - audit_log   │    │ Auto-failover chain   │    │ Multi-layer     │     │
│  └───────────────┘    └───────────────────────┘    └─────────────────┘     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      OPTIONAL ADVANCED PATTERNS                      │    │
│  │                                                                      │    │
│  │   ┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐   │    │
│  │   │   DEBATE    │    │    ENSEMBLE     │    │    LEARNING      │   │    │
│  │   │ COORDINATOR │    │   GENERATOR     │    │    SYSTEMS       │   │    │
│  │   │             │    │                 │    │                  │   │    │
│  │   │ Multiple    │    │ N candidates    │    │ PatternLearner   │   │    │
│  │   │ reviewers   │    │ test all        │    │ AntiPatternLearn │   │    │
│  │   │ + adjudicatn│    │ pick best       │    │ PromptEvolver    │   │    │
│  │   └─────────────┘    └─────────────────┘    └──────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow: How a Task Moves Through the System

```
USER TASK
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│ 1. PLANNING (Opus)                                                 │
│    Input:  Task description                                        │
│    Output: required_imports, edge_cases, plan, constraints         │
│    → State updated with requirements                               │
└───────────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│ 2. CONTEXT GATHERING (Gemini)                                      │
│    Input:  Task + repo path                                        │
│    Output: relevant_files, context_summary, refined imports/edges  │
│    → State updated with context                                    │
└───────────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│ 3. OPUS VALIDATION #1                                              │
│    Checklist: imports complete? edges realistic? summary accurate? │
│    Decision: APPROVED → continue | RETRY → back to step 2         │
└───────────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│ 4. HANDOFF to ENGINEERING                                          │
│    Build StageHandoff with:                                        │
│    - required_imports (MUST include)                               │
│    - edge_cases (MUST handle)                                      │
│    - required_acknowledgments (agent MUST confirm)                 │
└───────────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│ 5. CODE GENERATION (Sonnet/GPT-5)                                  │
│    Input:  Handoff payload + task                                  │
│    Output: Full implementation code                                │
│    Agent must acknowledge: "I will include X, handle Y..."         │
└───────────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│ 6. OPUS VALIDATION #2 (Static + Semantic)                          │
│    Static:   Parse AST, check imports present, no dangerous code   │
│    Semantic: Opus reviews algorithm, edge case handling            │
│    Decision: APPROVED | RETRY with guidance | ESCALATE model       │
└───────────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│ 7. INDEPENDENT REVIEW (GPT-5/Kimi)                                 │
│    Different model reviews for fresh perspective                   │
│    Optional: Multiple reviewers + debate                           │
└───────────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│ 8. OPUS VALIDATION #3                                              │
│    Aggregate review feedback                                       │
│    Critical issues? → back to engineering                          │
│    Minor/none? → proceed to execution                              │
└───────────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│ 9. EXECUTION                                                       │
│    Apply patch to repo                                             │
│    Run test command (pytest, etc.)                                 │
│    Capture stdout/stderr/exit code                                 │
└───────────────────────────────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────────────┐
│ 10. RESULT                                                         │
│     Tests PASS → Return solution + audit trail                     │
│     Tests FAIL → Opus diagnoses → back to engineering (loop)       │
│     Circuit breaker prevents infinite loops                        │
└───────────────────────────────────────────────────────────────────┘
```

---

## Final Project Structure

```
Opus_Ensemble/
├── orchestrator/
│   ├── __init__.py              # Package exports
│   ├── state.py                 # OrchestratorState, StageStatus, ValidationCheckpoint, AuditEvent
│   ├── conductor.py             # OpusConductor main class (the brain)
│   ├── clients.py               # ResilientModelClient, ModelConfig, provider failover
│   ├── validation.py            # StaticAnalyzer, ExecutionValidator, FailureClassifier, CircuitBreaker
│   ├── handoff.py               # StageHandoff, acknowledgment validation
│   ├── patterns.py              # PatternLearner, AntiPatternLearner, PromptEvolver (stub initially)
│   └── debate.py                # DebateCoordinator, EnsembleGenerator (optional advanced)
│
├── cli/
│   ├── __init__.py
│   └── main.py                  # CLI entrypoint: orchestrator-run
│
├── config/
│   └── conductor_config.yaml    # Model roster, fallback chains, timeouts, thresholds
│
├── tests/
│   ├── __init__.py
│   ├── test_state.py            # Unit tests for state management
│   ├── test_validation.py       # Unit tests for static analyzer, execution validator
│   ├── test_clients.py          # Unit tests for resilient client (mock providers)
│   ├── test_handoff.py          # Unit tests for handoff protocol
│   ├── test_conductor.py        # Integration tests for full flow
│   └── fixtures/
│       └── simple_bug_repo/     # Sample repo with known bug for testing
│
├── docs/
│   ├── opus_conductor_architecture.md
│   ├── opus_conductor_build_spec.md
│   └── IMPLEMENTATION_ROADMAP.md  (this file)
│
├── pyproject.toml               # Package config
└── README.md                    # User-facing documentation
```

---

## Implementation Phases

### Phase 1: Foundation (State + Config)
**Goal**: Build the data structures everything else depends on

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: Foundation                                              │
│                                                                  │
│ Files to create:                                                 │
│ ├── orchestrator/__init__.py                                     │
│ ├── orchestrator/state.py                                        │
│ │   ├── StageStatus (enum)                                       │
│ │   ├── ValidationCheckpoint (dataclass)                         │
│ │   ├── AuditEvent (dataclass)                                   │
│ │   └── OrchestratorState (dataclass)                            │
│ │       ├── verify_imports_complete()                            │
│ │       └── verify_edge_cases_handled()                          │
│ ├── config/conductor_config.yaml                                 │
│ └── tests/test_state.py                                          │
│                                                                  │
│ Test checkpoint: pytest tests/test_state.py passes               │
└─────────────────────────────────────────────────────────────────┘
```

**Step-by-step**:
1. Create `orchestrator/__init__.py` (empty for now)
2. Create `orchestrator/state.py` with all dataclasses
3. Create `config/conductor_config.yaml` with model roster
4. Write `tests/test_state.py` - test state initialization, helper methods
5. Run pytest, ensure all pass

---

### Phase 2: Model Client Layer
**Goal**: Build resilient API client with automatic failover

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: Model Client Layer                                      │
│                                                                  │
│ Files to create:                                                 │
│ ├── orchestrator/clients.py                                      │
│ │   ├── ModelConfig (dataclass)                                  │
│ │   ├── CompletionResult (dataclass)                             │
│ │   ├── AllProvidersFailedError (exception)                      │
│ │   └── ResilientModelClient                                     │
│ │       ├── __init__(fallback_chains, configs)                   │
│ │       ├── complete_with_failover(role, messages)               │
│ │       └── _call_single_provider(config, messages)              │
│ └── tests/test_clients.py                                        │
│                                                                  │
│ Test checkpoint: Mock provider errors, verify failover works     │
└─────────────────────────────────────────────────────────────────┘
```

**Step-by-step**:
1. Create `orchestrator/clients.py`
2. Implement `ModelConfig` with provider, model_id, etc.
3. Implement `ResilientModelClient`:
   - Load fallback chains from config
   - `complete_with_failover()` tries primary, then fallbacks
   - Log `AuditEvent` on each attempt
   - Raise `AllProvidersFailedError` if all fail
4. Write `tests/test_clients.py` with mocked API responses
5. Test: primary works, primary fails → fallback works, all fail → error

---

### Phase 3: Validation Framework
**Goal**: Build all validation layers (static, execution, classification)

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: Validation Framework                                    │
│                                                                  │
│ Files to create:                                                 │
│ ├── orchestrator/validation.py                                   │
│ │   ├── StaticAnalysisResult (dataclass)                         │
│ │   ├── StaticAnalyzer                                           │
│ │   │   └── analyze(code, required_imports)                      │
│ │   ├── ExecutionResult (dataclass)                              │
│ │   ├── ExecutionValidator                                       │
│ │   │   └── validate(code, test_cases, test_command)             │
│ │   ├── FailureType (enum)                                       │
│ │   ├── FailureClassifier                                        │
│ │   │   └── classify(error, code, state)                         │
│ │   └── CircuitBreaker                                           │
│ │       ├── can_retry(stage, cost)                               │
│ │       └── record_retry(stage, cost)                            │
│ └── tests/test_validation.py                                     │
│                                                                  │
│ Test checkpoint: Static catches syntax/import errors,            │
│                  Execution handles pass/fail/timeout              │
└─────────────────────────────────────────────────────────────────┘
```

**Step-by-step**:
1. Create `orchestrator/validation.py`
2. Implement `StaticAnalyzer`:
   - AST parse for syntax errors
   - Extract imports, compare to required list
   - Regex for dangerous patterns (eval, exec, os.system)
3. Implement `ExecutionValidator`:
   - Test-command mode: run pytest with timeout
   - Inline mode: create temp file with code + assertions
4. Implement `FailureClassifier`:
   - Regex patterns for common errors
   - Fallback to Opus LLM for ambiguous cases
5. Implement `CircuitBreaker`:
   - Track retries per stage and total
   - `can_retry()` checks limits
6. Write comprehensive tests

---

### Phase 4: Handoff Protocol
**Goal**: Build explicit handoff mechanism between stages

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 4: Handoff Protocol                                        │
│                                                                  │
│ Files to create:                                                 │
│ ├── orchestrator/handoff.py                                      │
│ │   ├── StageHandoff (dataclass)                                 │
│ │   ├── build_context_to_engineering_handoff(state)              │
│ │   └── validate_acknowledgment(handoff, response)               │
│ └── tests/test_handoff.py                                        │
│                                                                  │
│ Test checkpoint: Handoff builds correct payload,                 │
│                  Acknowledgment validation works                  │
└─────────────────────────────────────────────────────────────────┘
```

**Step-by-step**:
1. Create `orchestrator/handoff.py`
2. Implement `StageHandoff` dataclass
3. Implement `build_context_to_engineering_handoff()`:
   - Package required_imports, edge_cases, context_summary
   - Generate required_acknowledgments list
4. Implement `validate_acknowledgment()`:
   - Check agent response contains evidence of each acknowledgment
   - Return True/False
5. Write tests for payload building and validation

---

### Phase 5: Opus Conductor Core
**Goal**: Build the main orchestrator that ties everything together

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 5: Opus Conductor Core                                     │
│                                                                  │
│ Files to create:                                                 │
│ ├── orchestrator/conductor.py                                    │
│ │   ├── OrchestrationResult (dataclass)                          │
│ │   └── OpusConductor                                            │
│ │       ├── __init__(client, config)                             │
│ │       ├── run(task, repo_path) -> OrchestrationResult          │
│ │       ├── _opus_plan(task)                                     │
│ │       ├── _call_context_agent(state)                           │
│ │       ├── _validate_context() -> bool                          │
│ │       ├── _call_engineering_agent(state)                       │
│ │       ├── _validate_implementation() -> bool                   │
│ │       ├── _call_review_agent(state)                            │
│ │       ├── _validate_review() -> bool                           │
│ │       ├── _execute_solution(code)                              │
│ │       ├── _handle_*_failure() methods                          │
│ │       └── _prepare_final_output()                              │
│ └── tests/test_conductor.py                                      │
│                                                                  │
│ Test checkpoint: Full flow with mocked LLM responses             │
└─────────────────────────────────────────────────────────────────┘
```

**Step-by-step**:
1. Create `orchestrator/conductor.py`
2. Implement `OpusConductor.__init__()`:
   - Initialize state, client, validators, circuit breaker
3. Implement each stage method:
   - `_opus_plan()`: Call Opus to generate plan, parse into state
   - `_call_context_agent()`: Call Gemini, parse structured output
   - `_validate_context()`: Opus checklist validation
   - Build handoff, call engineering, validate implementation
   - Call review, validate review feedback
   - Execute solution
4. Implement failure handlers:
   - Route to retry with guidance
   - Escalate model if needed
   - Respect circuit breaker
5. Implement `run()` that orchestrates the full flow
6. Write integration tests with fixture repo

---

### Phase 6: CLI Interface
**Goal**: Make the system usable from command line

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 6: CLI Interface                                           │
│                                                                  │
│ Files to create:                                                 │
│ ├── cli/__init__.py                                              │
│ ├── cli/main.py                                                  │
│ │   ├── parse_args()                                             │
│ │   └── main()                                                   │
│ └── pyproject.toml (with entry point)                            │
│                                                                  │
│ Test checkpoint: orchestrator-run --help works                   │
│                  Full run on fixture repo succeeds                │
└─────────────────────────────────────────────────────────────────┘
```

**Step-by-step**:
1. Create `cli/__init__.py`
2. Create `cli/main.py`:
   - Parse arguments: --task-file, --task-text, --repo-path, --config
   - Load config, initialize conductor
   - Run and print results
   - Exit 0 on success, non-zero on failure
3. Update `pyproject.toml` with CLI entry point
4. Test end-to-end

---

### Phase 7: Advanced Patterns (Optional)
**Goal**: Add debate, ensemble, and learning capabilities

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 7: Advanced Patterns (Optional)                            │
│                                                                  │
│ Files to create:                                                 │
│ ├── orchestrator/debate.py                                       │
│ │   ├── DebateResult (dataclass)                                 │
│ │   ├── DebateCoordinator                                        │
│ │   ├── EnsembleResult (dataclass)                               │
│ │   └── EnsembleGenerator                                        │
│ └── orchestrator/patterns.py                                     │
│     ├── Pattern (dataclass)                                      │
│     ├── PatternLearner                                           │
│     ├── AntiPattern (dataclass)                                  │
│     ├── AntiPatternLearner                                       │
│     └── PromptEvolver                                            │
│                                                                  │
│ These can start as stubs and be fleshed out later                │
└─────────────────────────────────────────────────────────────────┘
```

**Step-by-step**:
1. Create `orchestrator/debate.py`:
   - `DebateCoordinator`: Multiple reviewers + adjudication
   - `EnsembleGenerator`: N candidates, test all, pick best
2. Create `orchestrator/patterns.py`:
   - Start with stubs that just log
   - Implement actual learning later
3. Integrate into conductor (optional paths based on config)

---

## Module Dependency Graph

```
                    ┌─────────────┐
                    │   cli/main  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  conductor  │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
  ┌───────────┐     ┌───────────┐     ┌───────────┐
  │  clients  │     │ validation │    │  handoff  │
  └─────┬─────┘     └─────┬─────┘     └─────┬─────┘
        │                 │                 │
        └────────────────►│◄────────────────┘
                          │
                          ▼
                    ┌───────────┐
                    │   state   │ ◄── Foundation (no deps)
                    └───────────┘

Optional:
  ┌───────────┐     ┌───────────┐
  │  debate   │     │  patterns │
  └───────────┘     └───────────┘
        │                 │
        └────────┬────────┘
                 ▼
           ┌───────────┐
           │ conductor │
           └───────────┘
```

**Build Order**: state → clients → validation → handoff → conductor → cli → (debate, patterns)

---

## Testing Checkpoints

### After Each Phase

| Phase | Test Command | Expected Result |
|-------|-------------|-----------------|
| 1 | `pytest tests/test_state.py` | All state tests pass |
| 2 | `pytest tests/test_clients.py` | Failover logic works |
| 3 | `pytest tests/test_validation.py` | Static + execution validators work |
| 4 | `pytest tests/test_handoff.py` | Handoff protocol works |
| 5 | `pytest tests/test_conductor.py` | Full flow with mocks works |
| 6 | `orchestrator-run --help` | CLI works |
| 6 | `pytest tests/` | All tests pass |

### Integration Test: Simple Bug Fix

Create `tests/fixtures/simple_bug_repo/`:
```
simple_bug_repo/
├── calculator.py     # Has an off-by-one bug
└── test_calculator.py  # Tests that fail initially
```

Task: "Fix the off-by-one error in calculator.py"

Expected: System finds bug, fixes it, tests pass.

---

## Key Design Decisions to Remember

1. **Opus Never Disappears**: Validates after every stage, not just at planning
2. **Structured State**: No implicit context passing - everything in `OrchestratorState`
3. **Explicit Acknowledgments**: Engineering agent must confirm it received requirements
4. **Multi-Layer Validation**: Static → Semantic → Review → Execution
5. **Failover Chains**: Every role has fallback models
6. **Circuit Breaker**: Prevents infinite retry loops
7. **Audit Trail**: Every action logged as `AuditEvent`

---

## Getting Started

```bash
# 1. Create project skeleton
cd Opus_Ensemble
mkdir -p orchestrator cli tests/fixtures config

# 2. Start with Phase 1
touch orchestrator/__init__.py
# Create state.py with all dataclasses

# 3. Write tests first (TDD)
# Create test_state.py before implementing

# 4. Iterate through phases
# Each phase: implement → test → commit
```

---

*Last Updated: 2025-12-02*
