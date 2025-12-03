# Opus Conductor Build Specification

## Summary

This spec targets an advanced AI coding model to build the Opus-Conductor system. It defines:
- The modules, data contracts, and workflows to implement
- "How to think" instructions: when to use high reasoning effort, when to re-read files, how to self-test

No code in this document, only a precise map of what to build.

---

## 1. Context: Capabilities to Exploit

This spec targets a high-capability coding model with:
- Configurable reasoning vs non-reasoning effort
- Large context windows (~128k tokens) for code + logs
- Tools for file read/write/list/diff and shell command execution
- Ability to complete multi-step coding tasks including multi-file refactors, test-driven iteration, and autonomous debugging

### Assumptions

1. **Model interface**: Responses API with tools for:
   - File read/write/list/diff
   - Shell command execution (for tests, lint, etc.)
   - HTTP or local process tools (if provided by the host environment)

2. **Context**: ≥128k tokens effective context for code + logs

3. **Reasoning controls**: A `reasoning` or `effort` parameter that can be set high/low per call

### Usage Guidelines

- **High-effort reasoning** for: planning, orchestration logic, validation code, tricky algorithms
- **Lower-effort** for: boilerplate, wiring, docstrings, small refactors once patterns are clear
- **Always use tools and tests** instead of hallucinating

---

## 2. High-Level Goals & Non-Goals

### 2.1 Goals

Build a Python library + CLI that:

1. **Implements the Opus Conductor multi-agent orchestration architecture**:
   - Central orchestrator (`OpusConductor`) that controls flow and validations
   - Specialized agents: context, implementation, review, execution
   - Structured shared state and explicit stage handoff contracts
   - Multi-layer validation (static, semantic, review, execution)
   - Failover and retry logic across multiple model providers
   - Optional ensemble/debate patterns

2. **Ready to plug into SWE-Bench Verified-style workflows**:
   - Accepts a task description and repository path
   - Finds/loads relevant code and tests
   - Applies a patch that makes tests pass
   - Returns final diff and logs

3. **Robust**:
   - No silent failures; clear error types and logs
   - Handles provider errors with automatic retry/failover
   - Persists state periodically so long-running tasks can be resumed

### 2.2 Non-Goals

- Build a GUI or web frontend
- Train or fine-tune models; only orchestrate existing APIs
- Implement SWE-Bench dataset loading itself (just expose an API the caller can plug into)

---

## 3. Tech Stack & Project Layout

### 3.1 Tech Stack

- **Language**: Python 3.11+
- **Core dependencies**:
  - HTTP client for LLMs (e.g., `openai` or generic client abstraction)
  - `pydantic` or `dataclasses` for typed state models
  - `pytest` for tests
  - `toml`/`yaml` for config loading
- **Execution environment**:
  - Shell command tool (for pytest, git, etc.)
  - Execution sandbox (separate process) for running arbitrary repo code

### 3.2 Repository Structure

```
orchestrator/
├── __init__.py
├── state.py          # OrchestratorState, StageStatus, ValidationCheckpoint, AuditEvent
├── conductor.py      # OpusConductor main loop
├── clients.py        # ResilientModelClient, provider config
├── validation.py     # StaticAnalyzer, ExecutionValidator, FailureClassifier, CircuitBreaker
├── handoff.py        # StageHandoff structures and validation logic
├── patterns.py       # PatternLearner, AntiPatternLearner, PromptEvolver (can be stubbed first)
├── debate.py         # DebateCoordinator, EnsembleGenerator, HierarchicalReviewer
├── config.py         # model roster, timeouts, thresholds

cli/
├── __init__.py
├── main.py           # CLI entrypoints, argument parsing

tests/
├── Unit tests for each module
├── Integration tests simulating a simple bug-fix repo

pyproject.toml or setup.cfg for packaging
README.md
```

Keep module responsibilities tight and avoid circular imports.

---

## 4. Data Model Spec

### 4.1 Core Enums and Data Classes

Define in `orchestrator/state.py`:

#### StageStatus

```python
class StageStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATED = "validated"
    FAILED = "failed"
    SKIPPED = "skipped"
```

Used for: `context_status`, `engineering_status`, `review_status`, `execution_status`

#### ValidationCheckpoint

```python
@dataclass
class ValidationCheckpoint:
    stage: str              # e.g., "context", "engineering"
    timestamp: float        # UNIX epoch seconds
    decision: str           # "APPROVED" | "RETRY" | "ESCALATE"
    reasoning: str          # Opus's textual explanation
    issues: List[str]       # specific issues found
    guidance: Optional[str] # how to fix on retry
```

#### AuditEvent

```python
@dataclass
class AuditEvent:
    timestamp: float
    event_type: str         # "stage_start" | "stage_end" | "model_call" | "validation" | "retry" | "error"
    stage: str
    model_id: str
    input_preview: str      # truncated
    output_preview: str     # truncated
    cost: float
    tokens: int
    validation_result: Optional[str]
```

#### OrchestratorState

Required fields:

```python
@dataclass
class OrchestratorState:
    # Task identity & metadata
    task_id: str
    original_task: str                      # user prompt / SWE-Bench description
    task_archetype: str                     # e.g., "bug_fix", "feature", "refactor"
    complexity: str                         # e.g., "simple", "medium", "complex", "expert"

    # Global requirements (initialized by Opus planning)
    constraints: List[str]
    success_criteria: List[str]
    required_imports: List[str]
    edge_cases: List[str]
    plan: str                               # structured high-level plan text

    # Context stage
    context_status: StageStatus
    relevant_files: List[str]
    context_summary: str
    context_validation: Optional[ValidationCheckpoint]

    # Engineering stage
    engineering_status: StageStatus
    implementation_code: str
    imports_included: List[str]             # from static analysis
    edge_cases_handled: Dict[str, bool]     # mapping each edge case to True/False
    engineering_validation: Optional[ValidationCheckpoint]

    # Review stage
    review_status: StageStatus
    review_passed: bool
    review_issues: List[str]
    review_validation: Optional[ValidationCheckpoint]

    # Execution stage
    execution_status: StageStatus
    execution_passed: bool
    execution_output: str
    execution_errors: List[str]

    # Meta
    total_cost: float
    total_tokens: int
    total_time: float
    retry_count: int
    checkpoints: List[ValidationCheckpoint]
    audit_events: List[AuditEvent]

    # Helper methods
    def verify_imports_complete(self) -> bool:
        """Ensures all required_imports appear in imports_included."""
        ...

    def verify_edge_cases_handled(self) -> bool:
        """Ensures every edge_cases key is True in edge_cases_handled."""
        ...
```

### 4.2 Handoff Protocol

In `orchestrator/handoff.py`:

```python
@dataclass
class StageHandoff:
    from_stage: str
    to_stage: str
    timestamp: float
    payload: Dict[str, Any]                 # imports, edge cases, file list, summaries
    required_acknowledgments: List[str]
    opus_validated: bool
    opus_notes: str
```

**Helper methods**:

- `build_context_to_engineering_handoff(state: OrchestratorState) -> StageHandoff`
  - Payload must include: `required_imports`, `edge_cases`, `context_summary`, `relevant_files`
  - Required acknowledgments must include statements like:
    - "I acknowledge required imports: <list>"
    - "I acknowledge edge cases to handle: <list>"
    - "I will include all required imports at the top of my code."
    - "I will handle all listed edge cases."

- `validate_acknowledgment(handoff: StageHandoff, agent_response: str) -> bool`
  - Use simple semantic checks: ensure for each `required_acknowledgments` phrase, there is evidence in `agent_response`
  - If returns False, orchestrator should not accept the handoff as complete and must re-prompt/clarify

This formalizes the "no information lost at handoffs" guarantee.

---

## 5. Model Client & Provider Failover

In `orchestrator/clients.py`:

### 5.1 ModelConfig

```python
@dataclass
class ModelConfig:
    provider: str           # e.g., "openai", "openrouter", "cerebras"
    model_id: str           # e.g., "gpt-5.1-thinking", "claude-sonnet-4.5"
    max_tokens: int
    temperature: float
    reasoning_effort: str   # "low" | "medium" | "high" (if available)
```

### 5.2 ResilientModelClient

**Public methods**:
- `complete_with_failover(role: str, messages: List[dict], **kwargs) -> CompletionResult`

**Internal behavior**:

1. Maintain `fallback_chains` per role:
   - `"conductor"`: `["opus-4.5"]` (or `"gpt-5.1-thinking"` in all-OpenAI deployment)
   - `"context"`: `["gemini-3-pro", "gemini-2.5-flash", "sonnet-4.5"]`
   - `"engineering"`: `["sonnet-4.5", "gpt-5.1-codex-max", "qwen3-235b"]`
   - `"review"`: `["gpt-5.1-codex-max", "kimi-k2-thinking", "sonnet-4.5"]`

2. When called:
   - Iterate through chain `[primary, fallback1, fallback2, ...]`
   - For each model, send the request:
     - Use high reasoning effort for conductor/validation tasks
     - Use medium for engineering/review by default, escalating to high if previous attempts failed
   - On API error: catch provider exceptions (timeout, 5xx, rate limit), log an `AuditEvent`, move to next model
   - If all fail: raise `AllProvidersFailedError`

3. Track:
   - Per-call token usage and cost (if available through metadata)
   - Log any use of fallback (for later analysis)

Use this client as the **only path to call LLMs**, never directly call providers from the orchestrator.

---

## 6. Validation & Execution Framework

### 6.1 StaticAnalyzer

In `orchestrator/validation.py`:

```python
class StaticAnalyzer:
    def analyze(self, code: str, required_imports: List[str]) -> StaticAnalysisResult:
        ...

@dataclass
class StaticAnalysisResult:
    passed: bool
    issues: List[str]
    found_imports: List[str]
    functions_defined: List[str]
```

**Checks**:

1. **Syntax**: Try to parse AST; if fails, append SyntaxError with line number and message

2. **Imports**:
   - Extract imports from AST; record as `found_imports`
   - For each `required_import` not in `found_imports`, add "MISSING IMPORT: <name>"

3. **Dangerous patterns** (string-match / regex):
   - `os.system(`, `subprocess.*shell=True`, `eval(`, `exec(`, `__import__(`
   - For each, append "DANGEROUS: <pattern description>"

4. Optionally: simple unused import detection and basic style warnings (non-fatal)

### 6.2 ExecutionValidator

```python
class ExecutionValidator:
    def validate(self, code: str, test_cases: Optional[List[dict]], test_command: Optional[str]) -> ExecutionResult:
        ...

@dataclass
class ExecutionResult:
    all_passed: bool
    results: List[dict]     # per test
    summary: str            # human-readable summary
    raw_stdout: str
    raw_stderr: str
```

**Two modes**:

1. **Test-command mode** (for SWE-Bench):
   - Write code into the target repo (patch application handled elsewhere)
   - Run `test_command` (e.g., "pytest") via shell tool with timeout
   - Capture stdout, stderr, and return code

2. **Inline test mode** (for simple function tasks):
   - Compose a temporary file with code plus assert-based tests from `test_cases`
   - Execute via Python subprocess with timeout

**Rules**:
- If test command exits 0, mark `all_passed = True`
- If timeout, mark `all_passed = False` and note "TIMEOUT" in summary

### 6.3 FailureClassifier & Recovery

```python
class FailureType(Enum):
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    RUNTIME_ERROR = "runtime_error"
    WRONG_OUTPUT = "wrong_output"
    ALGORITHM_ERROR = "algorithm_error"
    EDGE_CASE_MISS = "edge_case_miss"
    CONSTRAINT_VIOLATION = "constraint_violation"
    CONTEXT_LOSS = "context_loss"
    REQUIREMENT_DRIFT = "requirement_drift"
    SCOPE_CREEP = "scope_creep"

class FailureClassifier:
    def classify(self, error: str, code: str, state: OrchestratorState) -> FailureType:
        # Use regex/keywords to detect syntax/import/runtime errors
        # For ambiguous cases, prompt Opus with error, code snippet, and context
        ...

class CircuitBreaker:
    def __init__(self, max_retries_per_stage: int, max_total_retries: int, max_cost: float):
        ...

    def can_retry(self, stage: str, current_cost: float) -> Tuple[bool, str]:
        ...

    def record_retry(self, stage: str, cost: float):
        ...
```

The orchestrator must consult `CircuitBreaker` before any retry.

---

## 7. OpusConductor: Control Flow

In `orchestrator/conductor.py`:

```python
class OpusConductor:
    def run(self, task: str, repo_path: str, config: OrchestratorConfig) -> OrchestrationResult:
        ...
```

### 7.1 Orchestration Steps

Implement the following phases in order, with Opus validation in between:

#### 1. Planning (Opus)

Call conductor model with:
- Task description
- Repo path (or limited file listing)

Ask it to:
- Identify task archetype and complexity
- List explicit `required_imports` and `edge_cases`
- Outline high-level plan steps
- Identify constraints & success criteria

Populate `OrchestratorState` accordingly. Log a `ValidationCheckpoint` for planning.

#### 2. Context Gathering (Context Agent)

Use context model to:
- Scan repo for relevant files
- Summarize relevant code sections
- Refine `required_imports` and `edge_cases`

Update state fields: `relevant_files`, `context_summary`, possibly adjust lists.

#### 3. Opus Validation — Context

Prompt conductor model with:
- Task
- `required_imports`, `edge_cases`, `context_summary`, `relevant_files`

Checklist:
- Are required imports complete and plausible?
- Are edge cases realistic and sufficient?
- Is context summary accurate and specific?

Decision:
- **"APPROVED"** → `context_status = VALIDATED`
- **"RETRY"** → adjust prompt to context agent and re-run; increment retries
- **"ESCALATE"** → escalate to more capable context strategy

#### 4. Handoff to Engineering Agent

Build `StageHandoff` using `build_context_to_engineering_handoff`.

Compose prompt including:
- Task description
- Context summary and file paths
- Required imports and edge cases
- Constraints / success criteria
- Handoff's `required_acknowledgments`

Expect first part of response to explicitly acknowledge each requirement.

#### 5. Engineering Agent — Implementation

Engineering agent generates new or modified code:
- Output full file content(s) for changed files, not partial diff
- Ensure imports are at the top and edge cases are handled

#### 6. Opus Validation — Implementation

- Run `StaticAnalyzer` on new code; update `imports_included`
- If static fails → immediate RETRY with explicit guidance
- If static passes:
  - Prompt conductor model with task, required imports, edge cases, implementation code
  - Ask it to confirm all required imports present, edge cases handled, algorithm correct
  - Decision: "APPROVED", "RETRY" (with guidance), "ESCALATE"

#### 7. Review Agent — Independent Review

If implementation is APPROVED by Opus, call review model to:
- Review for correctness, missed edge cases, constraints, style/performance

Optionally:
- Call multiple reviewers and gather separate critiques for debate/ensemble logic

#### 8. Opus Validation — Review

- Aggregate critiques
- Prompt Opus to synthesize issues and decide if critical
- If critical → send guidance back to engineering agent and re-iterate
- If minor → proceed

#### 9. Execution

Use `ExecutionValidator` to:
- Apply patch (via file writes)
- Run tests within repo at `repo_path`
- Update `execution_passed` and error details

#### 10. Opus Diagnosis — Execution Failure

If tests fail, prompt Opus with:
- Failing test output
- Relevant code excerpt

Ask it to:
- Classify failure type
- Pinpoint likely cause(s)
- Propose concrete changes

Feed guidance back into engineering agent and loop, respecting `CircuitBreaker`.

#### 11. Finalization

When tests pass, compile `OrchestrationResult` with:
- Final code / diff
- Success = True
- Stats: time, cost, number of retries
- Audit trail summary

Implement this control flow **explicitly**, not implicitly via prompts. Each step is a Python method, and each LLM call is a distinct, logged operation.

---

## 8. Multi-Agent Coordination Patterns

In `orchestrator/debate.py`:

### 8.1 DebateCoordinator

Given code, task, and state:

1. Ask N reviewers independently for critiques
2. Optionally run one or two "reply" rounds where each reviewer sees others' critiques
3. Ask Opus to adjudicate based on all critiques

**Output**:
```python
@dataclass
class DebateResult:
    critiques: List[dict]
    verdict: str            # "APPROVED" | "NEEDS_REVISION"
    approved: bool
```

### 8.2 EnsembleGenerator

Given task, state, and test harness:

1. Generate M candidate solutions via different models (or same model with different seeds/plans)
2. Run `ExecutionValidator` on each
3. Choose:
   - First candidate with all tests passed; or
   - Candidate with maximum tests passed
4. If none pass:
   - Prompt Opus to synthesize a new solution using failed attempts and their errors

**Output**:
```python
@dataclass
class EnsembleResult:
    selected: dict              # chosen solution metadata
    all_solutions: List[dict]
    strategy: str               # "execution_verified" or "opus_synthesis"
```

**Usage policy**: For very hard tasks (flagged by complexity "expert" or after first attempt fails), switch into ensemble mode.

---

## 9. Learning & Adaptation

In `orchestrator/patterns.py`:

### 9.1 PatternLearner

Given a successful run (task + final code + execution result):
- Extract and store patterns:
  - `name`, `category`, `description`, `code_template`, `keywords`, `success_count`
- Use Opus to analyze code and generate pattern JSON
- Persist patterns (e.g., `patterns.json` or pluggable storage)
- Provide `get_relevant_patterns(task: str) -> List[Pattern]`

### 9.2 AntiPatternLearner

Given a failed attempt (task + code + error + stage):
- Extract an anti-pattern with:
  - `name`, `category`, `trigger_keywords`, `bad_example`, `fix_guidance`
- Provide `get_warnings_for_task(task: str) -> List[str]`

### 9.3 PromptEvolver

Given task and role ("engineering", "review", etc.):
- Retrieve relevant patterns and anti-patterns
- Insert a short "Hints & Warnings" section into the prompt:
  - Up to 3 patterns (most relevant)
  - Up to 2 warnings (most critical)

**Design constraints**:
- Don't overload prompts (keep hints concise)
- This system can start with stubs that just log patterns; more sophistication comes later

---

## 10. CLI / API Interface

In `cli/main.py`:

Provide `orchestrator-run` CLI with arguments:
- `--task-file` or `--task-text`
- `--repo-path`
- `--config` (for model keys, etc.)
- `--max-retries`, `--max-cost` overrides

**Behavior**:
- Load config and initialize `OpusConductor`
- Run `OpusConductor.run(...)`
- Print:
  - Final decision (success/failure)
  - Short summary
  - Optionally a diff (using git diff or pure text diff)
- Exit status:
  - 0 if success (`execution_passed=True`)
  - Non-zero otherwise

This allows orchestration to be used as a subprocess in SWE-Bench harnesses.

---

## 11. Test Plan

### 11.1 Unit Tests

**`test_state.py`**:
- `OrchestratorState` initialization
- `verify_imports_complete` and `verify_edge_cases_handled`

**`test_validation.py`**:
- `StaticAnalyzer`: syntax error detection, missing import, dangerous patterns
- `ExecutionValidator`: handles success/failure/timeouts (using dummy scripts)

**`test_clients.py`**:
- `ResilientModelClient`: fallback order (mock provider errors)

**`test_handoff.py`**:
- `StageHandoff` payload and acknowledgment validation

### 11.2 Integration Tests

A small sample repo under `tests/fixtures/simple_bug_repo/` with:
- One file containing a bug (e.g., off-by-one)
- Simple tests that fail initially, then pass after the patch

Test:
- Running `OpusConductor` on that repo with a textual task
- For test runs, mock out LLM calls to return pre-defined outputs (deterministic)

### 11.3 Smoke Test (Manual)

Documented in README — describe how to run the system end-to-end with real models once API keys are configured.

---

## 12. "How to Work" — Model-Usage Guidance

This section provides instructions on behavior while implementing, to maximize accuracy and avoid self-inflicted bugs.

### 12.1 General Rules

1. **Always read the relevant files before editing**
   - Before modifying a module, re-open the file and scan top-to-bottom

2. **Edit whole files, not fragments**
   - When changing code, regenerate the full content of the file
   - Avoids patch misalignment and keeps formatting consistent

3. **Use high reasoning effort for critical decisions**
   - Apply high reasoning mode for:
     - Designing data models
     - Implementing `OpusConductor` flow and validation logic
     - Writing `ExecutionValidator` & `FailureClassifier`
   - Use lower effort for:
     - Boilerplate, CLI argument parsing, packaging

4. **Decompose tasks explicitly**
   - Before working on a module, briefly outline the steps, then implement

5. **Don't guess external APIs**
   - For LLM provider calls, prefer a configurable interface (`ModelConfig`, `ResilientModelClient`)
   - Confine actual provider details to config

### 12.2 Self-Checking Behavior

- **Run tests frequently**
  - After implementing major modules, call pytest on relevant tests
  - On failure, read stack traces carefully, identify root cause, and fix

- **Lint or minimally sanity-check**
  - Use `python -m compileall` or `python -m py_compile` before running tests

- **Re-read orchestrator flow end-to-end**
  - Once `OpusConductor` is implemented, re-scan the entire class to ensure:
    - All stages call correct methods
    - `CircuitBreaker` is consulted before retries
    - Audit events are logged at key points
    - No stage is skipped inadvertently

- **Validate invariants with asserts**
  - Sprinkle internal assertions where appropriate
  - E.g., `assert state.verify_imports_complete()` before marking implementation as validated

### 12.3 Prompting Strategy (Within the System)

When writing prompts for other models (Opus, context agent, reviewers):

- **Keep prompts structured**
  - Use numbered checklists and explicit "RESPOND WITH:" sections

- **Request explicit verdict flags**
  - Ask for lines like `DECISION: APPROVED` or `DECISION: RETRY` for easy parsing

- **Limit unnecessary verbosity**
  - Prompts should be concise but complete

### 12.4 Handling Long Tasks

For long-running, multi-step tasks:

- **Persist state after key milestones**:
  - After context is validated
  - After implementation is validated
  - After each successful execution run

- **Implement checkpoint loading** so interrupted runs can resume

**State persistence format**: JSON file under `./.orchestrator_state/<task_id>.json`

---

## 13. Implications & Expectations

If this spec is followed carefully:

- We get a modular, testable orchestration engine that:
  - Is explicit about state and stage transitions
  - Uses multiple models in a fail-safe, redundant way
  - Validates code like a disciplined human engineer: static checks, review, and real execution

- On SWE-Bench Verified–style tasks:
  - The system can iteratively refine patches until tests pass
  - Provider hiccups and obvious bugs should no longer tank runs
  - Over time, pattern/anti-pattern learning should reduce repeated mistakes

---

## Next Steps

When ready:
1. "Generate the initial project skeleton for this spec"
2. Let the model iteratively fill it in with tests + code

---

*Last Updated: 2025-12-02*
