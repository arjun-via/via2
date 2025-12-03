# Opus Ensemble Implementation Checklist

**Goal:** Beat Opus 4.5's 80.9% on SWE-Bench Verified by using massive parallelism + execution-based filtering

**Core Insight:** "Beating Opus by using more Opus" - 20-40 parallel instances with strategy diversity, no handoffs, execution as the only arbiter.

---

## Model Configuration

The system supports multiple models for testing vs production:

| Mode | Model | Provider | Cost | Speed | Use Case |
|------|-------|----------|------|-------|----------|
| **Production** | `claude-opus-4-5-20250514` | Anthropic | $5/$25 per M | Slow | Final SWE-bench runs |
| **Testing** | `openai/gpt-oss-120b` | OpenRouter (Cerebras) | FREE | Very Fast | Development & debugging |

Toggle via environment variable or config:
```bash
# Production mode (default)
export OPUS_ENSEMBLE_MODEL=opus

# Testing mode (fast, free via Cerebras)
export OPUS_ENSEMBLE_MODEL=test
```

---

## Project Structure

```
Opus_Ensemble/
├── README.md                    # This file
├── __init__.py                  # Package exports
├── config.py                    # Configuration and constants
├── data_types.py                # Dataclasses for all entities
│
├── localization/                # Phase 1: Parallel Localization
│   ├── __init__.py
│   ├── ast_search.py            # AST-based search (AutoCodeRover style)
│   ├── dense_sparse.py          # BM25 + embedding similarity
│   ├── knowledge_graph.py       # Dependency graph builder
│   └── consensus.py             # Weighted voting across strategies
│
├── reproduction/                # Phase 2: Reproduction Test Generation
│   ├── __init__.py
│   └── test_generator.py        # Generate failing tests that prove bug exists
│
├── generation/                  # Phase 3: Parallel Patch Generation
│   ├── __init__.py
│   ├── strategies.py            # Strategy definitions (minimal, extended, etc.)
│   ├── prompt_templates.py      # Strategy-specific prompts
│   ├── parallel_generator.py    # Spawn N Opus instances concurrently
│   └── patch_parser.py          # Extract unified diff from response
│
├── verification/                # Phase 4: Execution-Based Verification
│   ├── __init__.py
│   ├── syntax_validator.py      # AST parse, linter
│   ├── patch_applier.py         # git apply, conflict handling
│   ├── test_runner.py           # Docker execution, timeout handling
│   └── result_aggregator.py     # Ranking, selection logic
│
├── correction/                  # Phase 5: Self-Correction Loop
│   ├── __init__.py
│   └── self_corrector.py        # Fresh context retry logic
│
├── orchestrator.py              # Main OpusEnsemble class
├── docker_executor.py           # Docker container management
├── api_client.py                # Parallel Opus API calls with rate limiting
│
└── scripts/
    ├── run_swebench.py          # Run on SWE-bench Verified
    ├── run_single_issue.py      # Test single issue
    └── analyze_results.py       # Performance analysis
```

---

## Implementation Checklist

### Phase 0: Infrastructure Setup
- [x] **0.1** Create `config.py` with constants
  - [x] API keys and endpoints
  - [x] Number of parallel instances (default: 40)
  - [x] Strategy distribution (8 each for 5 strategies)
  - [x] Timeout values
  - [x] Docker settings

- [x] **0.2** Create `data_types.py` with dataclasses
  - [x] `LocalizationResult` (file paths, scores, method used)
  - [x] `ReproductionTest` (test code, expected failure)
  - [x] `PatchCandidate` (code, strategy, instance_id)
  - [x] `VerificationResult` (passed stages, errors)
  - [x] `EnsembleResult` (final patch, metrics, trace)

- [x] **0.3** Create `api_client.py` for Opus API
  - [x] Rate limiting (respect API limits)
  - [x] Retry with exponential backoff
  - [x] Parallel request dispatcher
  - [x] Cost tracking per request

- [x] **0.4** Create `docker_executor.py`
  - [x] Container pool management
  - [x] Repository snapshot per container
  - [x] Safe command execution
  - [x] Timeout handling
  - [x] Cleanup on completion

---

### Phase 1: Parallel Localization
- [x] **1.1** Implement `localization/ast_search.py`
  - [x] Parse Python files with `ast` module
  - [x] Build class/method index
  - [x] `search_class(name)` - find class definitions
  - [x] `search_method_in_class(class_name, method_name)`
  - [x] `search_code(pattern)` - regex search in functions
  - [x] Return ranked file list

- [x] **1.2** Implement `localization/dense_sparse.py`
  - [x] BM25 indexer for repository
  - [x] Embedding index (placeholder for ada-002 or voyage)
  - [x] Hybrid retrieval (combine scores)
  - [x] Return ranked file list

- [x] **1.3** Implement `localization/knowledge_graph.py`
  - [x] Build import graph
  - [x] Build call graph
  - [x] Trace dependencies from issue keywords
  - [x] Return ranked file list

- [x] **1.4** Implement `localization/consensus.py`
  - [x] Weighted voting across 3 strategies
  - [x] Union of top-5 from each
  - [x] Final ranked list with confidence scores
  - [x] Context expansion (include imports, dependencies)

---

### Phase 2: Reproduction Test Generation
- [x] **2.1** Implement `reproduction/test_generator.py`
  - [x] Prompt template for reproduction test generation
  - [x] Opus call with issue + localized code
  - [x] Extract test code from response
  - [x] Execute test against base commit
  - [x] Verify test FAILS (proves bug exists)
  - [x] Retry if test passes (didn't capture bug)

---

### Phase 3: Parallel Patch Generation
- [x] **3.1** Implement `generation/strategies.py`
  - [x] `MinimalPatchStrategy` - smallest change
  - [x] `ExtendedThinkingStrategy` - max thinking tokens
  - [x] `TestDrivenStrategy` - write tests first
  - [x] `RefactorSafeStrategy` - preserve patterns
  - [x] `HighTemperatureStrategy` - temp=0.8 exploration

- [x] **3.2** Implement `generation/prompt_templates.py`
  - [x] Base template (issue, localized code, reproduction test)
  - [x] Strategy-specific system prompts
  - [x] Output format instructions (unified diff)

- [x] **3.3** Implement `generation/parallel_generator.py`
  - [x] Distribute instances across strategies (8 each)
  - [x] Build context for each instance
  - [x] Spawn all Opus calls concurrently (asyncio.gather)
  - [x] Collect all responses
  - [x] Track which strategy produced each patch

- [x] **3.4** Implement `generation/patch_parser.py`
  - [x] Extract unified diff from response
  - [x] Handle multiple formats (```diff, raw, etc.)
  - [x] Validate diff syntax
  - [x] Return `PatchCandidate` objects

---

### Phase 4: Execution-Based Verification
- [x] **4.1** Implement `verification/syntax_validator.py`
  - [x] Parse patched code with `ast.parse()`
  - [x] Run flake8/ruff for lint errors
  - [x] Check for common issues (undefined vars, syntax)
  - [x] Return pass/fail with error details

- [x] **4.2** Implement `verification/patch_applier.py`
  - [x] `git apply --check` to verify clean apply
  - [x] Handle merge conflicts
  - [x] Apply patch to repository copy
  - [x] Return success/failure with details

- [x] **4.3** Implement `verification/test_runner.py`
  - [x] Execute reproduction test in Docker
  - [x] Must PASS now (bug fixed)
  - [x] Execute full test suite
  - [x] Track pass/fail counts
  - [x] Timeout handling (60s per test file)

- [x] **4.4** Implement `verification/result_aggregator.py`
  - [x] Filter: syntax valid → apply clean → repro passes → regression passes
  - [x] Rank surviving patches by:
    1. Test pass rate (primary)
    2. Patch size (smaller = better)
    3. Semantic voting (identical changes = confidence)
    4. Strategy agreement
  - [x] Return ranked list of surviving patches

---

### Phase 5: Self-Correction Loop
- [x] **5.1** Implement `correction/self_correction.py`
  - [x] Triggered when no patch passes all tests
  - [x] Select best failing patches (top 3)
  - [x] Build fresh context with:
    - Original issue
    - Localized code
    - Failed test + execution trace
    - The failing patch (to avoid repeating)
  - [x] Spawn new Opus calls with failure analysis prompt
  - [x] Max 3 iterations
  - [x] Track which iteration succeeded

---

### Phase 6: Main Orchestrator
- [x] **6.1** Implement `orchestrator.py` - `OpusEnsemble` class
  - [x] `__init__()` - initialize all components
  - [x] `run(issue, repo_path)` - main entry point
  - [x] Phase 1: Call parallel localization
  - [x] Phase 2: Generate reproduction test
  - [x] Phase 3: Parallel patch generation
  - [x] Phase 4: Verification pipeline
  - [x] Phase 5: Self-correction if needed
  - [x] Return final patch + metrics

- [x] **6.2** Implement `swebench_orchestrator.py` - Full SWE-bench pipeline
  - [x] Integrates localization, reproduction, generation, verification, correction
  - [x] Docker container management
  - [x] Batch processing for multiple tasks
  - [x] Results output in SWE-bench format

- [x] **6.3** Add logging and tracing
  - [x] Log every decision point
  - [x] Record which strategies produced passing patches
  - [x] Track timing per phase
  - [x] Track cost per phase
  - [ ] Save full trace to JSONL

---

### Phase 7: Scripts and Testing
- [x] **7.1** Create `scripts/test_modules.py`
  - [x] Verify all modules can be imported
  - [x] Quick test of localization on sample repo
  - [x] Test Docker image name mapping

- [x] **7.2** Create `scripts/run_swebench.py`
  - [x] Load SWE-bench Verified dataset from HuggingFace
  - [x] Run on all issues (or subset with --num)
  - [x] Random selection with --random
  - [x] Test/production mode toggle
  - [x] Save predictions in required JSONL format
  - [x] Track overall success rate

- [ ] **7.3** Create `scripts/analyze_results.py`
  - [ ] Which strategies succeeded most?
  - [ ] How often did self-correction help?
  - [ ] Cost breakdown by phase
  - [ ] Time breakdown by phase

---

### Phase 8: Optimization and Tuning
- [ ] **8.1** Tune number of parallel instances
  - [ ] Test 20, 30, 40 instances
  - [ ] Find diminishing returns point

- [ ] **8.2** Tune strategy distribution
  - [ ] Track which strategies succeed most
  - [ ] Adjust allocation based on results

- [ ] **8.3** Optimize localization
  - [ ] Track localization accuracy
  - [ ] Weight strategies by historical performance

- [ ] **8.4** Add caching
  - [ ] Cache repository embeddings
  - [ ] Cache AST parses
  - [ ] Cache common test results

---

## Success Criteria

| Metric | Target | Baseline (Opus 4.5) |
|--------|--------|---------------------|
| SWE-bench Verified | 85%+ | 80.9% |
| Cost per issue | <$5 | ~$0.50 |
| Time per issue | <10 min | ~1 min |

**Key tradeoff:** We're trading cost and time for accuracy. That's the explicit goal.

---

## Implementation Order

**Week 1: Foundation**
1. `config.py`, `data_types.py`
2. `api_client.py` (Opus parallel calls)
3. `docker_executor.py`

**Week 2: Core Pipeline**
4. Phase 1: Localization (start with AST-based only)
5. Phase 3: Parallel generation (minimal strategies first)
6. Phase 4: Verification pipeline

**Week 3: Enhancement**
7. Phase 2: Reproduction tests
8. Phase 5: Self-correction
9. Full localization (all 3 strategies)

**Week 4: Testing & Tuning**
10. Run on SWE-bench subset (50 issues)
11. Analyze results, tune parameters
12. Run full SWE-bench Verified

---

## Notes

- **No handoffs between models** - every Opus instance has complete context
- **Execution is the only arbiter** - no LLM reviewing LLM output
- **Fresh context per correction** - no accumulated history degradation
- **Strategy diversity, not model diversity** - same Opus, different prompts

---

*Last Updated: 2025-12-02*

---

# Opus-Conductor: Multi-Agent Orchestration with Continuous Validation

**NEW APPROACH (2025-12-03):** After the parallel ensemble approach yielded 0% solve rate on initial tests, we pivoted to a new architecture where Opus stays in the loop at every stage.

## Key Differentiator

The original ensemble tried "Opus in parallel, no handoffs, execution only" - but this led to disconnected solutions with no feedback loop. Opus-Conductor takes the opposite approach:

**Opus validates after EVERY stage** (not just plans then disappears)

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     OPUS-CONDUCTOR PIPELINE                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  PHASE 1: OPUS PLANNING                                  │    │
│   │  • Analyze task, extract requirements                    │    │
│   │  • Define constraints, success criteria, edge cases      │    │
│   │  • Create "contract" for downstream agents               │    │
│   └─────────────────────────────────────────────────────────┘    │
│                              ↓                                    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  PHASE 2: CONTEXT ANALYSIS (Gemini)                      │    │
│   │  • Analyze repository structure                          │    │
│   │  • Identify relevant files                               │    │
│   │  • Summarize codebase context                            │    │
│   │  • ✓ OPUS VALIDATES BEFORE PROCEEDING                    │    │
│   └─────────────────────────────────────────────────────────┘    │
│                              ↓                                    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  PHASE 3: ENGINEERING (Sonnet)                           │    │
│   │  • Generate code with explicit acknowledgment            │    │
│   │  • Handle all edge cases from contract                   │    │
│   │  • Include all required imports                          │    │
│   │  • ✓ OPUS VALIDATES (static + semantic)                  │    │
│   │  • Retry with guidance if needed                         │    │
│   └─────────────────────────────────────────────────────────┘    │
│                              ↓                                    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  PHASE 4: REVIEW (GPT-4o)                                │    │
│   │  • Independent code review against requirements          │    │
│   │  • Check correctness, completeness, edge cases           │    │
│   │  • Can send back to engineering if issues found          │    │
│   └─────────────────────────────────────────────────────────┘    │
│                              ↓                                    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  PHASE 5: EXECUTION VALIDATION                           │    │
│   │  • Run code in sandbox                                   │    │
│   │  • Verify syntax and runtime correctness                 │    │
│   │  • Final gate before output                              │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Project Structure (Opus-Conductor)

```
Opus_Ensemble/
├── conductor/                     # Opus-Conductor core
│   ├── __init__.py               # Package exports
│   ├── state.py                  # ConductorState, checkpoints
│   ├── clients.py                # ResilientModelClient, providers
│   ├── validation.py             # Static, Semantic, Execution validators
│   ├── handoff.py                # StageHandoff protocol
│   ├── conductor.py              # OpusConductor main class
│   │
│   └── advanced/                 # Advanced patterns
│       ├── __init__.py
│       ├── debate.py             # Multi-agent debate for complex problems
│       ├── ensemble.py           # Parallel generation with voting
│       └── learning.py           # Prompt evolution, model selection
│
├── cli/                          # Command line interface
│   ├── __init__.py
│   └── main.py                   # CLI entry point
│
├── config/
│   └── conductor_config.yaml     # Model and orchestration config
│
└── tests/
    └── test_state.py             # State tests (31 tests passing)
```

## Usage

### Basic Usage

```bash
# Run with CLI
python -m cli.main --task "Implement a binary search function" --config config/conductor_config.yaml

# With repository context
python -m cli.main --task "Fix the cache bug" --repo /path/to/repo

# Dry run (validate config only)
python -m cli.main --task "..." --dry-run
```

### Programmatic Usage

```python
from conductor import OpusConductor

conductor = OpusConductor.from_config("config/conductor_config.yaml")
result = conductor.run(
    task="Write a function to merge two sorted lists",
    repo_path="/optional/path",
)

if result.success:
    print(f"Generated code:\n{result.final_code}")
    print(f"Cost: ${result.total_cost:.4f}")
```

### Advanced Patterns

```python
# Multi-Agent Debate
from conductor.advanced import DebateOrchestrator

debate = DebateOrchestrator(
    agents={"sonnet": sonnet_client, "gpt4": gpt4_client},
    judge=opus_client,
    max_rounds=2,
)
result = debate.run(state)

# Parallel Ensemble with Voting
from conductor.advanced import EnsembleOrchestrator, EnsembleStrategy

ensemble = EnsembleOrchestrator(
    generators={"sonnet": sonnet_client, "gpt4": gpt4_client},
    judge=opus_client,
    strategy=EnsembleStrategy.EXECUTION,
)
result = ensemble.run(state)

# Learning Module (evolves prompts over time)
from conductor.advanced import LearningModule

learner = LearningModule(
    models=["opus", "sonnet", "gpt4"],
    base_prompts={"engineering": "...", "review": "..."},
    storage_dir=Path("data/learning"),
)
best_model = learner.get_model(state)
learner.record_success(state, stage="engineering", model_id=best_model)
```

## Model Roster

| Role | Primary | Fallback | Purpose |
|------|---------|----------|---------|
| **Supervisor** | Opus 4.5 | Sonnet 4.5 | Planning, validation at every stage |
| **Context** | Gemini 2.0 Flash | Gemini 2.0 Flash | Large context repo analysis |
| **Engineering** | Sonnet 4.5 | GPT-4o | Code generation |
| **Review** | GPT-4o | Sonnet 4.5 | Independent code review |
| **Fast** | Gemini 2.0 Flash | GPT-4o-mini | Quick iterations |

## Key Components

### ConductorState
Single source of truth that tracks:
- Original task and requirements
- Constraints, success criteria, edge cases (the "contract")
- Stage statuses (pending → in_progress → validated)
- Validation checkpoints at each stage
- Audit trail of all model calls

### Structured Handoffs
Each stage transition includes:
- Explicit requirements to acknowledge
- Context from previous stages
- Validation feedback if retry

### Multi-Layer Validation
1. **Static Analysis** - syntax, imports, structure
2. **Semantic Validation** - Opus verifies against requirements
3. **Execution Validation** - runs code in sandbox

### Circuit Breaker
Prevents infinite retry loops by tracking consecutive failures.

## Test Results

```
============================================================
OPUS-CONDUCTOR VERIFICATION TEST
============================================================
Task: Write a function is_palindrome(s)...

Success: True
Stages completed: 4/4
Retries used: 0
Total cost: $0.15
Total time: 46.8s

Stage statuses:
  Context: validated ✅
  Engineering: validated ✅
  Review: validated ✅
  Execution: validated ✅
```

---

*Opus-Conductor Last Updated: 2025-12-03*
