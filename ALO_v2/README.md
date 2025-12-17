# ALO v2.0 - Agentic Loop Orchestrator (Redesigned)

**Version**: 2.0.0
**Created**: 2025-12-17
**Goal**: Beat 71.8% on SWE-bench Verified (current best: Opus-Conductor)

---

## Executive Summary

ALO v2.0 is a complete redesign of the original ALO system, incorporating all lessons learned from:
- ALO v1 (4-agent pipeline): 97.6% on HumanEval, but validation gaps on SWE-bench
- Opus Orchestrator: 71.8% on SWE-bench Verified (our current best)
- Model evaluation (Dec 17, 2025): Kimi K2 outperformed all open-source models

**Key Innovation**: Smart model routing - use cheap/fast models (Kimi K2) for most tasks, escalate to expensive models (Gemini 3 Flash, Opus) only when needed.

---

## Design Choices

### 1. Model Roles

```
┌─────────────────────────────────────────────────────────────────┐
│                    OPUS = ORCHESTRATOR (BRAIN)                  │
│                                                                 │
│  Claude Opus 4.5 makes ALL decisions:                          │
│  - Analyzes issue and plans approach                           │
│  - Selects which worker model to use                           │
│  - Evaluates worker outputs                                    │
│  - Decides: proceed / retry / escalate / fail                  │
│  - Provides feedback and error context to workers              │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    WORKERS (HANDS)                              │
│                                                                 │
│  ┌─────────────┐  ┌─────────────────┐                          │
│  │  Kimi K2    │  │  Gemini 3 Flash │                          │
│  │  (default)  │  │  (large context)│                          │
│  │             │  │                 │                          │
│  │  - Fast     │  │  - 1M tokens    │                          │
│  │  - Cheap    │  │  - 78% SWE      │                          │
│  │  - 100% acc │  │  - For big files│                          │
│  └─────────────┘  └─────────────────┘                          │
│                                                                 │
│  Workers do the heavy lifting:                                  │
│  - File localization                                           │
│  - Patch generation                                            │
│  - Code analysis                                               │
│                                                                 │
│  Opus orchestrates but doesn't do these tasks directly         │
│  (unless all workers fail)                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Why Opus as Orchestrator?

| Aspect | Opus Orchestrating | Opus Doing Everything |
|--------|-------------------|----------------------|
| **Cost** | ~$0.01/issue (Opus thinks, workers do) | ~$0.10/issue |
| **Quality** | Best reasoning for decisions | Same |
| **Speed** | Fast (workers are fast) | Slow (Opus is slow) |
| **Flexibility** | Can route to best model per task | Single model |

### Model Evaluation Results (Dec 17, 2025)

| Model | Classification | Localization | Patch Gen | Latency | Role |
|-------|---------------|--------------|-----------|---------|------|
| **Opus 4.5** | Best reasoning | Best reasoning | Best reasoning | ~5,000ms | 🧠 ORCHESTRATOR |
| **Kimi K2** | 100% | 100% | 100% | 700ms | 🔧 DEFAULT WORKER |
| **Gemini 3 Flash** | 66.7% | 100% | 100% | 3,615ms | 🔧 LARGE CONTEXT WORKER |

**Rejected Models** (not used as workers):
- GLM-4.6: Poor localization (33%) and patch generation (33%)
- Kimi K2 Thinking: Same accuracy as K2 but 20x slower
- Gemini 3 Pro Deep Think: Worse patch generation (33%), very slow

### 2. Architecture: Simplified Pipeline

**Original ALO v1** (4 agents):
```
Context (Gemini) → Repro (GPT) → Engineering (GLM) → Review (Kimi)
```
Problems: Too many handoffs, context loss, expensive, slow

**ALO v2** (Opus-Orchestrated Pipeline):
```
┌─────────────────────────────────────────────────────────────────────────┐
│                      OPUS 4.5 = THE ORCHESTRATOR                        │
│                                                                         │
│  Opus is the BRAIN that:                                                │
│  - Reads the issue and understands what needs to be done                │
│  - Decides which worker to dispatch for each task                       │
│  - Evaluates worker outputs and decides next action                     │
│  - Provides feedback/context when workers need to retry                 │
│  - Makes final pass if all workers fail (last resort)                   │
│                                                                         │
│  Opus does NOT do the heavy work directly - it COORDINATES              │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    ORCHESTRATOR STATE                            │   │
│  │  - issue_id, problem_statement, repo_path                        │   │
│  │  - difficulty: EASY | MEDIUM | HARD                              │   │
│  │  - located_files: List[str]                                      │   │
│  │  - patches_tried: List[Patch]                                    │   │
│  │  - current_model: str                                            │   │
│  │  - escalation_count: int                                         │   │
│  │  - validation_results: List[TestResult]                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Stage 0: CLASSIFY                                                 │  │
│  │ ┌────────────┐                                                    │  │
│  │ │  Kimi K2   │──▶ difficulty = EASY/MEDIUM/HARD                   │  │
│  │ └────────────┘                                                    │  │
│  │        │                                                          │  │
│  │        ▼                                                          │  │
│  │ ┌─────────────────────────────────────────────────────────────┐   │  │
│  │ │ ORCHESTRATOR CHECK:                                         │   │  │
│  │ │ - Valid classification? (EASY/MEDIUM/HARD)                  │   │  │
│  │ │ - If invalid → retry with clearer prompt                    │   │  │
│  │ │ - Select model for next stage based on difficulty           │   │  │
│  │ └─────────────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                         │                                               │
│                         ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Stage 1: LOCALIZE                                                 │  │
│  │ ┌────────────┐     ┌───────────────┐                              │  │
│  │ │  Kimi K2   │ OR  │ Gemini 3 Flash│  (based on context size)     │  │
│  │ └────────────┘     └───────────────┘                              │  │
│  │        │                                                          │  │
│  │        ▼                                                          │  │
│  │ ┌─────────────────────────────────────────────────────────────┐   │  │
│  │ │ ORCHESTRATOR CHECK:                                         │   │  │
│  │ │ - Got valid file list? (parseable JSON array)               │   │  │
│  │ │ - Files exist in repo?                                      │   │  │
│  │ │ - If <3 files found → expand search, retry                  │   │  │
│  │ │ - If files don't exist → retry with corrected prompt        │   │  │
│  │ │ - Read located files, estimate tokens for next stage        │   │  │
│  │ └─────────────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                         │                                               │
│                         ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Stage 2: GENERATE PATCH                                           │  │
│  │                                                                    │  │
│  │  ┌─────────── ESCALATION LOOP ───────────┐                        │  │
│  │  │                                        │                        │  │
│  │  │  Model 1: Kimi K2 (if EASY/MEDIUM)    │                        │  │
│  │  │      │                                 │                        │  │
│  │  │      ▼                                 │                        │  │
│  │  │  ┌─────────────────────────────────┐   │                        │  │
│  │  │  │ ORCHESTRATOR CHECK:             │   │                        │  │
│  │  │  │ - Valid diff format?            │   │                        │  │
│  │  │  │ - Patch applies cleanly?        │   │                        │  │
│  │  │  │ - Modifies source (not tests)?  │   │                        │  │
│  │  │  │                                 │   │                        │  │
│  │  │  │ If FAIL → escalate to Model 2   │   │                        │  │
│  │  │  │ If PASS → proceed to validate   │   │                        │  │
│  │  │  └─────────────────────────────────┘   │                        │  │
│  │  │      │                                 │                        │  │
│  │  │      ▼ (on failure)                    │                        │  │
│  │  │  Model 2: Gemini 3 Flash              │                        │  │
│  │  │      │                                 │                        │  │
│  │  │      ▼                                 │                        │  │
│  │  │  ┌─────────────────────────────────┐   │                        │  │
│  │  │  │ ORCHESTRATOR CHECK (same)       │   │                        │  │
│  │  │  │ If FAIL → escalate to Model 3   │   │                        │  │
│  │  │  └─────────────────────────────────┘   │                        │  │
│  │  │      │                                 │                        │  │
│  │  │      ▼ (on failure)                    │                        │  │
│  │  │  Model 3: Opus 4.5 (final attempt)    │                        │  │
│  │  │                                        │                        │  │
│  │  └────────────────────────────────────────┘                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                         │                                               │
│                         ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Stage 3: VALIDATE                                                 │  │
│  │ ┌────────────────────────────────────────────────────────────┐    │  │
│  │ │ Docker Container: Run SWE-bench tests                      │    │  │
│  │ │ - Apply patch with git apply                               │    │  │
│  │ │ - Run FAIL_TO_PASS tests (must pass now)                   │    │  │
│  │ │ - Run PASS_TO_PASS tests (must still pass)                 │    │  │
│  │ └────────────────────────────────────────────────────────────┘    │  │
│  │        │                                                          │  │
│  │        ▼                                                          │  │
│  │ ┌─────────────────────────────────────────────────────────────┐   │  │
│  │ │ ORCHESTRATOR DECISION:                                      │   │  │
│  │ │                                                             │   │  │
│  │ │ Tests PASS?                                                 │   │  │
│  │ │   └─▶ SUCCESS! Return patch                                 │   │  │
│  │ │                                                             │   │  │
│  │ │ Tests FAIL?                                                 │   │  │
│  │ │   └─▶ Analyze failure:                                      │   │  │
│  │ │       - Which tests failed?                                 │   │  │
│  │ │       - What was the error?                                 │   │  │
│  │ │       └─▶ LOOP BACK to Stage 2 with error context           │   │  │
│  │ │           (provide failure info to next model)              │   │  │
│  │ │                                                             │   │  │
│  │ │ Max retries exceeded?                                       │   │  │
│  │ │   └─▶ FAIL with best attempt                                │   │  │
│  │ └─────────────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Opus Orchestrator Flow

```
                         ┌───────────────────────────────────┐
                         │         OPUS 4.5 (BRAIN)          │
                         │                                   │
                         │  "I need to fix this Django bug.  │
                         │   Let me dispatch workers..."     │
                         └───────────────┬───────────────────┘
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            │                            │                            │
            ▼                            ▼                            ▼
   ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
   │   DISPATCH:     │         │   DISPATCH:     │         │   DISPATCH:     │
   │   "Kimi, find   │         │   "Kimi, write  │         │   "Gemini, this │
   │   relevant      │         │   a patch for   │         │   file is huge, │
   │   files"        │         │   this bug"     │         │   you handle it"│
   └────────┬────────┘         └────────┬────────┘         └────────┬────────┘
            │                            │                            │
            ▼                            ▼                            ▼
   ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
   │    KIMI K2      │         │    KIMI K2      │         │  GEMINI 3 FLASH │
   │    (worker)     │         │    (worker)     │         │    (worker)     │
   └────────┬────────┘         └────────┬────────┘         └────────┬────────┘
            │                            │                            │
            ▼                            ▼                            ▼
   ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
   │   RESULT:       │         │   RESULT:       │         │   RESULT:       │
   │   [file1, file2]│         │   <patch diff>  │         │   <patch diff>  │
   └────────┬────────┘         └────────┬────────┘         └────────┬────────┘
            │                            │                            │
            └────────────────────────────┼────────────────────────────┘
                                         │
                                         ▼
                         ┌───────────────────────────────────┐
                         │         OPUS 4.5 (BRAIN)          │
                         │                                   │
                         │  "Let me evaluate this output..." │
                         │                                   │
                         │  - Is it valid?                   │
                         │  - Should I proceed?              │
                         │  - Should I retry with feedback?  │
                         │  - Should I try a different       │
                         │    worker?                        │
                         │  - Should I do it myself?         │
                         └───────────────────────────────────┘
```

### Opus Decision Points

| After | Opus Evaluates | Opus Decides |
|-------|----------------|--------------|
| **Localization** | Valid files? Exist in repo? | Proceed / Retry with hint / Try Gemini |
| **Patch Gen** | Valid diff? Applies cleanly? | Proceed to test / Retry with error / Escalate |
| **Validation** | Tests pass? | SUCCESS / Loop back with failure context |

### Opus Prompts (Examples)

**Initial Analysis:**
```
You are the orchestrator. Analyze this issue and plan your approach.

ISSUE: {problem_statement}
REPO: {repo}

Decide:
1. Difficulty estimate (EASY/MEDIUM/HARD)
2. Which worker to use first (kimi-k2 or gemini-3-flash)
3. What to ask the worker to do

Respond with JSON:
{"difficulty": "...", "worker": "...", "task": "localize|generate", "prompt": "..."}
```

**Evaluating Worker Output:**
```
You dispatched {worker} to {task}. Here's the result:

{worker_output}

Evaluate:
1. Is this output valid and useful?
2. Should we proceed to the next step?
3. Should we retry with feedback?
4. Should we try a different worker?

Respond with JSON:
{"valid": true/false, "action": "proceed|retry|escalate|fail", "feedback": "..."}
```

### Orchestrator State Machine

```
                    ┌──────────────┐
                    │    START     │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
              ┌────▶│   CLASSIFY   │◀────┐
              │     └──────┬───────┘     │
              │            │             │
         retry│      check:valid?    retry
              │            │             │
              │     ┌──────▼───────┐     │
              └─NO──│  valid?      │──NO─┘
                    └──────┬───────┘
                           │YES
                           ▼
                    ┌──────────────┐
              ┌────▶│   LOCALIZE   │◀────┐
              │     └──────┬───────┘     │
              │            │             │
         retry│     check:files?    retry
              │            │             │
              │     ┌──────▼───────┐     │
              └─NO──│  files ok?   │──NO─┘
                    └──────┬───────┘
                           │YES
                           ▼
                    ┌──────────────┐
         ┌─────────▶│   GENERATE   │◀──────────┐
         │          └──────┬───────┘           │
         │                 │                   │
    escalate        check:patch?          loop back
         │                 │              (with error)
         │          ┌──────▼───────┐           │
         └───FAIL───│  patch ok?   │           │
                    └──────┬───────┘           │
                           │YES                │
                           ▼                   │
                    ┌──────────────┐           │
                    │   VALIDATE   │           │
                    └──────┬───────┘           │
                           │                   │
                    ┌──────▼───────┐           │
                    │  tests pass? │───FAIL────┘
                    └──────┬───────┘
                           │YES
                           ▼
                    ┌──────────────┐
                    │   SUCCESS    │
                    └──────────────┘
```

### 3. Context Window Strategy

**Problem**: Different models have different context limits
- Kimi K2: 128K tokens (sufficient for most tasks)
- Gemini 3 Flash: 1M tokens (for full repo analysis)

**Decision**: Automatic routing based on context size

```python
def select_model(context_tokens: int, difficulty: str, task: str) -> str:
    # Large context always needs Gemini 3 Flash
    if context_tokens > 128_000:
        return "gemini-3-flash-preview"

    # Hard patches benefit from Gemini 3's 78% SWE-bench score
    if difficulty == "HARD" and task == "patch_generation":
        return "gemini-3-flash-preview"

    # Default: Kimi K2 (fast, cheap, accurate)
    return "moonshotai/kimi-k2"
```

### 4. Escalation Pattern

**Problem**: Cheap models fail on some tasks. Expensive models are slow/costly.

**Decision**: Try cheap first, escalate on failure

```
Kimi K2 (attempt 1)
    │
    ├── SUCCESS ──▶ Done (cost: ~$0.0001)
    │
    └── FAIL ──▶ Gemini 3 Flash (attempt 2)
                      │
                      ├── SUCCESS ──▶ Done (cost: ~$0.003)
                      │
                      └── FAIL ──▶ Opus 4.5 (attempt 3, final)
                                        │
                                        └── Done (cost: ~$0.05)
```

**Failure Criteria**:
- Patch doesn't apply cleanly
- Tests still fail after patch
- Model refuses or returns empty
- Timeout (>60 seconds)

### 5. Validation Strategy (Critical)

**Lesson Learned**: Our biggest issue was validation gap (80% internal vs 30% official)

**Root Cause**: Module-level vs function-level test parsing

**Decision**: Exact SWE-bench methodology

```python
# WRONG (what we did before)
def validate_module_level(test_output):
    return "PASSED" in test_output  # Too coarse!

# RIGHT (what SWE-bench does)
def validate_function_level(container, test_spec):
    # 1. Parse FAIL_TO_PASS tests from test_spec
    fail_to_pass = test_spec["FAIL_TO_PASS"]

    # 2. Run each test function individually
    for test_func in fail_to_pass:
        exit_code = container.exec(f"pytest {test_func} -x")
        if exit_code != 0:
            return False  # This specific test must pass

    # 3. Also check PASS_TO_PASS didn't regress
    pass_to_pass = test_spec["PASS_TO_PASS"]
    for test_func in pass_to_pass:
        exit_code = container.exec(f"pytest {test_func} -x")
        if exit_code != 0:
            return False  # Regression!

    return True
```

### 6. Docker Execution (from Opus Orchestrator)

**Lesson Learned**: One command per response prevents hallucination

**Decision**: Adopt Opus Orchestrator's execution pattern

```python
class DockerExecutor:
    def __init__(self, container_id: str):
        self.container_id = container_id

    def exec(self, command: str, timeout: int = 120) -> tuple[int, str]:
        """
        Execute ONE command and return real output.

        CRITICAL: Never let the model "imagine" command output.
        Always execute and return actual results.
        """
        result = subprocess.run(
            ["docker", "exec", self.container_id, "bash", "-c", command],
            capture_output=True,
            timeout=timeout
        )
        return result.returncode, result.stdout.decode()
```

### 7. Patch Format

**Decision**: Unified diff format (standard)

```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,7 +10,7 @@
 def some_function():
-    return wrong_value
+    return correct_value
```

**Validation**:
1. Must have `---` and `+++` markers
2. Must have `@@` hunk headers
3. Must apply cleanly with `git apply`
4. Must not modify test files (source files only)

### 8. Task Classification

**Decision**: Use Kimi K2 to classify before processing

```python
CLASSIFICATION_PROMPT = """
Classify this GitHub issue by difficulty:

ISSUE:
{issue_text}

REPOSITORY: {repo}

Respond with ONE word: EASY, MEDIUM, or HARD

EASY = Single file, <10 lines, obvious fix
MEDIUM = 2-3 files, 10-50 lines, component interaction
HARD = Multiple files, 50+ lines, architectural understanding

Classification:
"""
```

**Why Classify?**
- Route EASY tasks directly to Kimi K2 (no escalation needed)
- Route HARD tasks to Gemini 3 Flash first (skip cheap model)
- Save costs by not over-engineering simple fixes

### 9. Cost Optimization

**Target**: <$0.01 per issue (average)

| Task | Model | Est. Cost |
|------|-------|-----------|
| Classification | Kimi K2 | $0.0001 |
| Localization | Kimi K2 | $0.0002 |
| Patch (easy) | Kimi K2 | $0.0005 |
| Patch (hard) | Gemini 3 Flash | $0.003 |
| Escalation | Opus 4.5 | $0.05 |

**Expected distribution** (based on SWE-bench):
- 40% EASY → Kimi K2 only → $0.0008
- 40% MEDIUM → Kimi K2 + maybe escalate → $0.002
- 20% HARD → Gemini 3 Flash + maybe Opus → $0.02

**Weighted average**: ~$0.005 per issue

### 10. Error Handling

**Decision**: Fail loudly, no silent fallbacks (per CLAUDE.md rules)

```python
class ALOv2Error(Exception):
    """Base exception for ALO v2"""
    pass

class ModelError(ALOv2Error):
    """Model API call failed"""
    pass

class ValidationError(ALOv2Error):
    """Patch validation failed"""
    pass

class EscalationExhausted(ALOv2Error):
    """All models failed, no more fallbacks"""
    pass
```

---

## File Structure

```
ALO_v2/
├── README.md                 # This file
├── __init__.py
├── config.py                 # Model configs, API keys
├── models/
│   ├── __init__.py
│   ├── base.py              # BaseModel abstract class
│   ├── kimi_k2.py           # Kimi K2 client
│   ├── gemini.py            # Gemini 3 Flash client
│   └── opus.py              # Claude Opus 4.5 client
├── stages/
│   ├── __init__.py
│   ├── classifier.py        # Stage 0: Task classification
│   ├── localizer.py         # Stage 1: File localization
│   ├── generator.py         # Stage 2: Patch generation
│   └── validator.py         # Stage 3: Docker validation
├── orchestrator.py          # Main orchestration logic
├── docker_executor.py       # Docker command execution
├── utils/
│   ├── __init__.py
│   ├── diff_utils.py        # Patch parsing/application
│   ├── token_counter.py     # Token estimation
│   └── cost_tracker.py      # Cost tracking
└── tests/
    ├── test_classifier.py
    ├── test_localizer.py
    ├── test_generator.py
    └── test_integration.py
```

---

## API Keys Required

```bash
# .env file - ONLY 2 KEYS NEEDED
ANTHROPIC_API_KEY=...     # For Opus 4.5 orchestrator
OPENROUTER_API_KEY=...    # For workers: Kimi K2, Gemini 3 Flash
```

**Note**: Gemini 3 Flash is now available via OpenRouter (`google/gemini-3-flash-preview`), simplifying the setup to just 2 API keys.

---

## Usage

```python
from ALO_v2 import ALOv2Orchestrator

# Initialize
orchestrator = ALOv2Orchestrator()

# Process a single issue
result = orchestrator.solve(
    instance_id="django__django-12345",
    problem_statement="...",
    repo_path="/path/to/repo"
)

# Result contains
print(result.patch)          # The generated patch
print(result.model_used)     # Which model generated it
print(result.attempts)       # Number of escalations
print(result.cost)           # Total cost
print(result.validated)      # Whether tests pass
```

---

## Metrics to Track

1. **Accuracy**: % of issues where generated patch passes SWE-bench tests
2. **Cost per issue**: Average $ spent per issue
3. **Latency**: Time from issue to patch
4. **Escalation rate**: % of issues requiring escalation
5. **Model distribution**: Which model solved which difficulty

---

## Success Criteria

| Metric | Target | Stretch |
|--------|--------|---------|
| SWE-bench Verified | >71.8% | >78% |
| Cost per issue | <$0.01 | <$0.005 |
| Avg latency | <30s | <15s |
| Escalation rate | <30% | <20% |

---

## Implementation Order

1. **Phase 1**: Core infrastructure
   - [ ] Model clients (Kimi K2, Gemini 3, Opus)
   - [ ] Docker executor
   - [ ] Config management

2. **Phase 2**: Pipeline stages
   - [ ] Classifier (Stage 0)
   - [ ] Localizer (Stage 1)
   - [ ] Generator (Stage 2)
   - [ ] Validator (Stage 3)

3. **Phase 3**: Orchestration
   - [ ] Escalation logic
   - [ ] Cost tracking
   - [ ] Error handling

4. **Phase 4**: Testing
   - [ ] Unit tests
   - [ ] Integration tests
   - [ ] SWE-bench pilot (25 issues)

5. **Phase 5**: Full evaluation
   - [ ] SWE-bench Verified (500 issues)
   - [ ] Compare to baseline (71.8%)

---

## Changelog

- **2025-12-17**: Initial design based on model evaluation results
  - Kimi K2 selected as primary model (100% accuracy, 700ms latency)
  - Gemini 3 Flash for large context (1M tokens, 78% SWE-bench)
  - Rejected GLM-4.6 (poor performance) and Gemini 3 Pro Deep Think (slow, worse patches)

---

*Last Updated: 2025-12-17*
