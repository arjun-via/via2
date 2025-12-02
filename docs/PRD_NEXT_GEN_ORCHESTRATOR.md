# Product Requirements Document: Next-Generation Multi-Agent Orchestration System

**Version:** 1.0
**Date:** 2025-12-01
**Author:** Claude Opus 4.5 (synthesized from Via2 codebase analysis)
**Audience:** Deep Research, Architecture Review

---

## Executive Summary

This PRD proposes a complete redesign of the Via2 multi-agent orchestration system based on empirical evidence from 7,277+ lines of production code and extensive benchmarking. The core finding is that **the current "opus-optimized" multi-model architecture fails at 43% while a single Opus call achieves 100%** on the same tasks.

**Root Cause:** Opus plans but doesn't coordinate. Cheap models execute without supervision, losing context at each handoff.

**Proposed Solution:** A new architecture where Opus acts as a true "conductor" - maintaining state, validating every transition, and having veto power at each stage.

**Key Constraint:** Time and cost are NOT constraints. The goal is maximum quality.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Lessons Learned from Current System](#2-lessons-learned-from-current-system)
3. [Proposed Architecture: Opus Conductor](#3-proposed-architecture-opus-conductor)
4. [Detailed Component Design](#4-detailed-component-design)
5. [Information Flow & State Management](#5-information-flow--state-management)
6. [Validation Framework](#6-validation-framework)
7. [Multi-Agent Coordination Patterns](#7-multi-agent-coordination-patterns)
8. [Learning & Adaptation](#8-learning--adaptation)
9. [Failure Handling & Recovery](#9-failure-handling--recovery)
10. [Evaluation Criteria](#10-evaluation-criteria)
11. [Research Questions](#11-research-questions)
12. [Appendix: Evidence Base](#appendix-evidence-base)

---

## 1. Problem Statement

### 1.1 The Core Paradox

We built a sophisticated multi-model orchestrator with:
- Strategic planning (Opus 4.5)
- Context gathering (Gemini 2.5 Flash - 1M context)
- Code generation (Qwen3 235B - 735 tok/s)
- Code review (Kimi K2 - different provider)
- Adaptive validation
- Learning systems (model selection, prompt evolution)

**Expected Result:** Better than single-model through specialization.

**Actual Result:**
| Variant | Pass Rate | Avg Time | Avg Cost |
|---------|-----------|----------|----------|
| opus-baseline (single call) | **100%** (7/7) | 21.6s | $0.032 |
| opus-optimized (multi-model) | **43%** (3/7) | 81.3s | $0.041 |

The sophisticated system is **slower, more expensive, and dramatically worse**.

### 1.2 Why This Happens

Analysis of the 4 failures in opus-optimized:

| Task | Error | What Went Wrong |
|------|-------|-----------------|
| easy_2 | `NameError: List not defined` | Qwen forgot `from typing import List` |
| medium_1 | AssertionError on merge_intervals | Algorithm bug - wrong merge logic |
| medium_2 | AssertionError on LRU cache | Logic bug in eviction |
| hard_2 | Cerebras 503 | Provider failure (no retry) |

**Pattern:** These are not "hard problems" - they're **coordination failures**:
1. Missing imports (context lost between models)
2. Algorithm bugs (no verification before output)
3. Logic bugs (review model missed them)
4. Provider failures (no fallback)

### 1.3 The Architectural Flaw

```
CURRENT ARCHITECTURE (opus-optimized):
┌──────────┐
│  OPUS    │ ─── Plans once, then disappears
└────┬─────┘
     ↓
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Gemini   │ ──→ │  Qwen    │ ──→ │  Kimi    │ ──→ OUTPUT
│ (context)│     │ (code)   │     │ (review) │
└──────────┘     └──────────┘     └──────────┘
                      ↑
                      └── No one checks if imports are included
                      └── No one validates algorithm correctness
                      └── No one catches provider failures
```

**The fundamental problem:** Opus is the "brain" but it's only used at the start. The cheap models operate unsupervised, and errors compound.

### 1.4 Design Requirements for Solution

1. **Opus must validate every transition** - Not just plan, but verify
2. **No information loss at handoffs** - State must be complete at each stage
3. **Actual code execution** - Don't trust any model's "this works" claim
4. **Provider-agnostic reliability** - Failures must be caught and retried
5. **Learn from both success and failure** - Compound knowledge over time

---

## 2. Lessons Learned from Current System

### 2.1 Patterns That Work (Keep These)

#### 2.1.1 One Command Per Response
```python
# PROVEN EFFECTIVE: Forces model to wait for real output
bash_blocks = re.findall(r'```bash\n.*?```', response)
if len(bash_blocks) > 1:
    return True  # REJECT - too many commands
```
**Why it works:** Prevents hallucination of command output. Model must wait for reality.

#### 2.1.2 Patch Validation
```python
# PROVEN EFFECTIVE: Ensures actual source changes
test_patterns = [r'^test_', r'/tests?/', r'_test\.py$']
source_files = [f for f in files if not any(re.search(p, f) for p in test_patterns)]
if len(source_files) == 0:
    return False  # REJECT - no actual fix
```
**Why it works:** Models try to write test files that "pass" instead of fixing bugs.

#### 2.1.3 Feature-Based Execution
```python
# PROVEN EFFECTIVE: Incremental progress with checkpoints
for feature in features:
    result = implement(feature)
    if passes_validation(result):
        git_commit(feature)  # Checkpoint
    else:
        retry_or_escalate()
```
**Why it works:** Prevents scope creep, enables recovery from partial failures.

#### 2.1.4 Hallucination Detection
```python
# PROVEN EFFECTIVE: Catches imagined output
patterns = [
    r'```bash\n.*?```\s*\n\s*(Output|Result)',  # Output after command
    r'```bash\n.*?```\s*\n\s*```',  # Multiple blocks
]
```
**Why it works:** Models often write what they expect to see instead of waiting.

#### 2.1.5 Provider Diversification
```yaml
# PROVEN EFFECTIVE: Different providers catch different mistakes
engineering: cerebras/qwen   # Fast
review: openrouter/kimi      # Different perspective
```
**Why it works:** Same-provider models have correlated biases.

### 2.2 Patterns That Failed (Fix These)

#### 2.2.1 Plan-Then-Disappear Orchestration
```
CURRENT (BROKEN):
Opus plans → Cheap models execute → No supervision → Errors compound
```
**Fix:** Opus must validate EVERY stage transition, not just plan.

#### 2.2.2 Implicit Context Passing
```
CURRENT (BROKEN):
Context model outputs summary → Engineering model receives summary → Import context lost
```
**Fix:** Explicit structured state with required fields that must be validated.

#### 2.2.3 Trust-Based Review
```
CURRENT (BROKEN):
Code generated → Review model says "LGTM" → No actual execution → Bug ships
```
**Fix:** Code execution is mandatory. "LGTM" from any model is not sufficient.

#### 2.2.4 Single-Provider Dependency
```
CURRENT (BROKEN):
Cerebras returns 503 → Entire pipeline fails → No recovery
```
**Fix:** Every model call must have automatic failover to alternate provider.

### 2.3 Empirical Performance Data

From HumanEval (164 problems) benchmarks:

| Configuration | Pass Rate | Key Insight |
|---------------|-----------|-------------|
| Claude Sonnet 4.5 (single) | 97.6% | Premium model, single call |
| ALO-Optimized (multi-model) | 97.0% | Multi-model with coordination |
| ALO-Open (all OSS) | 95.1% | Open source only |

From Compare Variants (7 problems, harder):

| Configuration | Pass Rate | Key Insight |
|---------------|-----------|-------------|
| opus-baseline | 100% | Single Opus call |
| opus-optimized | 43% | Multi-model without Opus coordination |

**Critical Insight:** Multi-model CAN work (ALO-Optimized at 97%) but requires proper coordination. Current opus-optimized lacks that coordination.

---

## 3. Proposed Architecture: Opus Conductor

### 3.1 Core Concept: Opus as Conductor, Not Planner

```
NEW ARCHITECTURE (Opus Conductor):
                    ┌─────────────────────────────────────────┐
                    │              OPUS CONDUCTOR              │
                    │  (Maintains state, validates transitions)│
                    └────────────────────┬────────────────────┘
                                         │
          ┌──────────────────────────────┼──────────────────────────────┐
          │                              │                              │
          ↓                              ↓                              ↓
    ┌──────────┐                  ┌──────────┐                  ┌──────────┐
    │ Gemini   │──── VALIDATE ────│  Qwen    │──── VALIDATE ────│  Kimi    │
    │ (context)│     BY OPUS      │ (code)   │     BY OPUS      │ (review) │
    └──────────┘                  └──────────┘                  └──────────┘
          │                              │                              │
          └──────────────────────────────┼──────────────────────────────┘
                                         │
                                         ↓
                                  ┌──────────┐
                                  │ EXECUTE  │
                                  │ (Python) │
                                  └──────────┘
```

### 3.2 Key Principles

#### Principle 1: Opus Validates Every Transition
After each specialist model completes, Opus reviews:
- Is the output complete?
- Does it satisfy the requirements?
- Are there obvious errors (missing imports, syntax issues)?
- Should we proceed, retry, or escalate?

#### Principle 2: Structured State (Not Free-Form Text)
```python
@dataclass
class OrchestratorState:
    """Structured state with REQUIRED fields."""

    # Immutable (set once)
    task_id: str
    original_task: str
    constraints: List[str]
    success_criteria: List[str]

    # Updated by Context Agent (validated by Opus)
    relevant_files: List[str]
    context_summary: str
    required_imports: List[str]  # EXPLICIT!
    edge_cases: List[str]        # EXPLICIT!

    # Updated by Engineering Agent (validated by Opus)
    implementation_code: str
    imports_included: List[str]  # VERIFIED against required_imports
    edge_cases_handled: Dict[str, bool]  # VERIFIED against edge_cases

    # Updated by Review Agent (validated by Opus)
    review_passed: bool
    review_issues: List[str]

    # Updated by Execution (ground truth)
    execution_passed: bool
    execution_output: str
    execution_errors: List[str]
```

#### Principle 3: Execution Is Mandatory
No solution is accepted without actual code execution passing. This is the only ground truth.

#### Principle 4: Automatic Failover
Every model call is wrapped with:
```python
def call_with_failover(model_id: str, messages: List, fallback_models: List[str]):
    for model in [model_id] + fallback_models:
        try:
            return client.complete(model, messages)
        except (ProviderError, RateLimitError, TimeoutError):
            continue
    raise AllProvidersFailedError()
```

#### Principle 5: Explicit Handoff Protocol
Each stage produces a structured output that the next stage MUST acknowledge:

```
CONTEXT → ENGINEERING HANDOFF:
{
  "from": "context_agent",
  "to": "engineering_agent",
  "required_acknowledgments": [
    "I have received the required imports: [List, Dict, Optional]",
    "I have received the edge cases: [empty input, single element, duplicates]",
    "I will handle all edge cases explicitly"
  ],
  "opus_validation": "APPROVED - all fields populated"
}
```

### 3.3 Execution Flow

```
1. TASK INPUT
   └── User provides task description

2. OPUS PLANNING (Opus 4.5)
   ├── Classify task archetype
   ├── Identify complexity level
   ├── Define required_imports (explicit list)
   ├── Define edge_cases (explicit list)
   ├── Define success_criteria (testable)
   └── Select specialist models

3. CONTEXT GATHERING (Gemini 2.5 Flash)
   ├── Analyze full codebase (1M context)
   ├── Identify relevant files
   ├── Extract required imports
   └── Identify edge cases

   >>> OPUS VALIDATION CHECKPOINT <<<
   ├── Verify required_imports populated
   ├── Verify edge_cases populated
   ├── Verify context_summary complete
   └── Decision: PROCEED / RETRY / ESCALATE

4. IMPLEMENTATION (Qwen3 235B or GPT-5.1)
   ├── Acknowledge required_imports (copy them in)
   ├── Acknowledge edge_cases (plan handling)
   ├── Write implementation
   └── Self-verify imports and edge cases

   >>> OPUS VALIDATION CHECKPOINT <<<
   ├── Static analysis (syntax, imports)
   ├── Verify imports_included matches required_imports
   ├── Verify edge_cases_handled has all edge_cases
   └── Decision: PROCEED / RETRY / ESCALATE

5. CODE REVIEW (Kimi K2 or Sonnet 4.5)
   ├── Review logic correctness
   ├── Check edge case handling
   ├── Verify constraint compliance
   └── Identify issues

   >>> OPUS VALIDATION CHECKPOINT <<<
   ├── Aggregate review findings
   ├── Assess severity of issues
   └── Decision: PROCEED / RETRY / ESCALATE

6. EXECUTION (Python subprocess)
   ├── Actually run the code
   ├── Run against test cases
   └── Capture output/errors

   >>> OPUS FINAL VALIDATION <<<
   ├── Verify execution_passed == True
   ├── If failed: analyze error, retry with guidance
   └── Decision: ACCEPT / RETRY / FAIL

7. OUTPUT
   └── Return validated, executed solution
```

### 3.4 Model Roster (Time/Cost Unconstrained)

Since time and cost are not constraints, use the best model for each role:

| Role | Primary Model | Fallback 1 | Fallback 2 |
|------|---------------|------------|------------|
| **Conductor** | Opus 4.5 | - | - |
| **Context** | Gemini 3 Pro (1M) | Gemini 2.5 Flash | Claude Sonnet |
| **Engineering** | Claude Sonnet 4.5 | GPT-5.1 | Qwen3 235B |
| **Review** | GPT-5.1 | Kimi K2 Thinking | Claude Sonnet |
| **Validation** | Opus 4.5 | - | - |

**Rationale:**
- Opus as conductor ensures highest quality coordination
- Sonnet for engineering (97.6% HumanEval, proven)
- Different providers for review (avoids same-model bias)
- Multiple fallbacks for reliability

---

## 4. Detailed Component Design

### 4.1 Opus Conductor Module

```python
class OpusConductor:
    """
    The brain of the orchestration system.
    Opus validates EVERY stage transition.
    """

    def __init__(self, client: MultiProviderClient):
        self.client = client
        self.state = OrchestratorState()
        self.checkpoint_history = []

    def run(self, task: str) -> OrchestrationResult:
        """Main orchestration loop with Opus validation at each step."""

        # Phase 1: Planning (Opus)
        plan = self._opus_plan(task)
        self.state.initialize_from_plan(plan)

        # Phase 2: Context (Specialist + Opus validation)
        context_result = self._run_context_agent()
        if not self._opus_validate_context(context_result):
            context_result = self._retry_or_escalate("context")

        # Phase 3: Implementation (Specialist + Opus validation)
        impl_result = self._run_engineering_agent()
        if not self._opus_validate_implementation(impl_result):
            impl_result = self._retry_or_escalate("engineering")

        # Phase 4: Review (Specialist + Opus validation)
        review_result = self._run_review_agent()
        if not self._opus_validate_review(review_result):
            review_result = self._retry_or_escalate("review")

        # Phase 5: Execution (Ground truth)
        exec_result = self._execute_code()
        if not exec_result.success:
            return self._opus_diagnose_and_retry(exec_result)

        return OrchestrationResult(
            success=True,
            code=self.state.implementation_code,
            cost=self._calculate_total_cost(),
            stages_completed=5
        )

    def _opus_validate_context(self, result: ContextResult) -> bool:
        """Opus validates context agent output."""

        prompt = f"""
        You are validating the output of the Context Agent.

        TASK: {self.state.original_task}

        CONTEXT AGENT OUTPUT:
        - Relevant files: {result.relevant_files}
        - Required imports: {result.required_imports}
        - Edge cases: {result.edge_cases}
        - Context summary: {result.context_summary}

        VALIDATION CHECKLIST:
        1. Are required_imports complete? (all necessary modules for the task)
        2. Are edge_cases comprehensive? (empty input, boundary conditions, error cases)
        3. Is context_summary accurate and relevant?

        RESPOND WITH:
        - APPROVED: If all checks pass
        - RETRY: If minor issues (specify what's missing)
        - ESCALATE: If fundamental misunderstanding
        """

        response = self._call_opus(prompt)
        return "APPROVED" in response

    def _opus_validate_implementation(self, result: ImplResult) -> bool:
        """Opus validates engineering agent output."""

        # First: Static analysis (fast, cheap)
        static_issues = self._static_analyze(result.code)
        if static_issues:
            return False  # Don't even ask Opus, obvious problems

        # Second: Opus semantic validation
        prompt = f"""
        You are validating the output of the Engineering Agent.

        TASK: {self.state.original_task}
        REQUIRED IMPORTS: {self.state.required_imports}
        EDGE CASES TO HANDLE: {self.state.edge_cases}

        IMPLEMENTATION:
        ```python
        {result.code}
        ```

        VALIDATION CHECKLIST:
        1. Does the code include ALL required imports? Compare to list above.
        2. Does the code handle ALL edge cases? Check each one explicitly.
        3. Is the algorithm correct? Trace through with simple example.
        4. Are there any obvious bugs (off-by-one, wrong comparison, etc.)?

        RESPOND WITH:
        - APPROVED: If all checks pass
        - RETRY with guidance: [specific issues to fix]
        - ESCALATE: If algorithm is fundamentally wrong
        """

        response = self._call_opus(prompt)
        return "APPROVED" in response
```

### 4.2 Structured State Schema

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

class StageStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATED = "validated"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class ValidationCheckpoint:
    """Record of Opus validation at a stage."""
    stage: str
    timestamp: float
    opus_decision: str  # APPROVED, RETRY, ESCALATE
    reasoning: str
    issues_found: List[str]
    guidance_for_retry: Optional[str]

@dataclass
class OrchestratorState:
    """
    Complete state of orchestration.
    All fields are explicit and validated.
    """

    # === IMMUTABLE (set at planning) ===
    task_id: str
    original_task: str
    task_archetype: str  # quick_fix, feature_build, architecture, etc.
    complexity: str  # simple, medium, complex, expert

    # Explicit requirements (not free-form)
    required_imports: List[str] = field(default_factory=list)
    edge_cases: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)

    # === CONTEXT STAGE ===
    context_status: StageStatus = StageStatus.PENDING
    relevant_files: List[str] = field(default_factory=list)
    context_summary: str = ""
    context_validation: Optional[ValidationCheckpoint] = None

    # === ENGINEERING STAGE ===
    engineering_status: StageStatus = StageStatus.PENDING
    implementation_code: str = ""
    imports_included: List[str] = field(default_factory=list)
    edge_cases_handled: Dict[str, bool] = field(default_factory=dict)
    engineering_validation: Optional[ValidationCheckpoint] = None

    # === REVIEW STAGE ===
    review_status: StageStatus = StageStatus.PENDING
    review_passed: bool = False
    review_issues: List[str] = field(default_factory=list)
    review_validation: Optional[ValidationCheckpoint] = None

    # === EXECUTION STAGE (Ground Truth) ===
    execution_status: StageStatus = StageStatus.PENDING
    execution_passed: bool = False
    execution_output: str = ""
    execution_errors: List[str] = field(default_factory=list)

    # === METADATA ===
    total_cost: float = 0.0
    total_time: float = 0.0
    retry_count: int = 0
    checkpoints: List[ValidationCheckpoint] = field(default_factory=list)

    def verify_imports_complete(self) -> bool:
        """Check that all required imports are in implementation."""
        return all(imp in self.imports_included for imp in self.required_imports)

    def verify_edge_cases_handled(self) -> bool:
        """Check that all edge cases are handled."""
        return all(self.edge_cases_handled.get(ec, False) for ec in self.edge_cases)
```

### 4.3 Handoff Protocol

```python
@dataclass
class StageHandoff:
    """
    Explicit handoff between stages.
    The receiving stage MUST acknowledge all fields.
    """
    from_stage: str
    to_stage: str
    timestamp: float

    # What the sender is passing
    payload: Dict[str, Any]

    # What the receiver MUST acknowledge
    required_acknowledgments: List[str]

    # Opus validation of handoff
    opus_validated: bool
    opus_notes: str

class HandoffProtocol:
    """
    Ensures information is not lost between stages.
    """

    @staticmethod
    def context_to_engineering(state: OrchestratorState) -> StageHandoff:
        """Create handoff from context to engineering."""

        return StageHandoff(
            from_stage="context",
            to_stage="engineering",
            timestamp=time.time(),
            payload={
                "required_imports": state.required_imports,
                "edge_cases": state.edge_cases,
                "context_summary": state.context_summary,
                "relevant_files": state.relevant_files,
            },
            required_acknowledgments=[
                f"I acknowledge required imports: {state.required_imports}",
                f"I acknowledge edge cases to handle: {state.edge_cases}",
                "I will include ALL imports at the top of my code",
                "I will handle ALL edge cases with explicit logic",
            ],
            opus_validated=False,
            opus_notes=""
        )

    @staticmethod
    def validate_acknowledgment(handoff: StageHandoff, response: str) -> bool:
        """Check that engineering agent acknowledged all requirements."""

        for ack in handoff.required_acknowledgments:
            # Check for semantic match, not exact string
            if not any(phrase in response.lower() for phrase in ack.lower().split()):
                return False
        return True
```

### 4.4 Multi-Provider Failover

```python
class ResilientModelClient:
    """
    Client with automatic failover and retry.
    No single provider failure can stop execution.
    """

    def __init__(self, primary_client: MultiProviderClient):
        self.client = primary_client
        self.failure_log: List[Dict] = []

        # Define fallback chains for each role
        self.fallback_chains = {
            "conductor": ["opus-4.5"],  # No fallback - Opus is essential
            "context": ["gemini-3-pro", "gemini-2.5-flash", "sonnet-4.5"],
            "engineering": ["sonnet-4.5", "gpt-5.1", "qwen3-235b"],
            "review": ["gpt-5.1", "kimi-k2-thinking", "sonnet-4.5"],
        }

    def complete_with_failover(
        self,
        role: str,
        messages: List[Dict],
        max_tokens: int = 4096
    ) -> CompletionResult:
        """
        Try primary model, then fallbacks.
        """

        chain = self.fallback_chains.get(role, [])

        for i, model_id in enumerate(chain):
            try:
                model_config = get_model(model_id)
                result = self.client.complete(
                    model_config=model_config,
                    messages=messages,
                    max_tokens=max_tokens
                )

                if i > 0:
                    # Log that we used fallback
                    self.failure_log.append({
                        "role": role,
                        "primary_failed": chain[0],
                        "used_fallback": model_id,
                        "timestamp": time.time()
                    })

                return result

            except (ProviderError, RateLimitError, TimeoutError) as e:
                self.failure_log.append({
                    "role": role,
                    "model": model_id,
                    "error": str(e),
                    "timestamp": time.time()
                })
                continue

        raise AllProvidersFailedError(
            f"All providers failed for role {role}: {chain}"
        )
```

---

## 5. Information Flow & State Management

### 5.1 Information Loss Prevention

The current system loses information at handoffs because:
1. Context is passed as free-form text
2. No verification that receiver understood
3. No explicit acknowledgment protocol

**New approach:**

```
BEFORE (Information Loss):
┌──────────┐                    ┌──────────┐
│ Context  │ ──"summary text"──→│Engineering│
│ Agent    │                    │  Agent   │
└──────────┘                    └──────────┘
     │                               │
     └── required_imports: [List]    └── forgets to import List
```

```
AFTER (Information Preserved):
┌──────────┐                    ┌──────────┐
│ Context  │ ──structured data──→│Engineering│
│ Agent    │    + handoff obj    │  Agent   │
└──────────┘                    └──────────┘
     │           │                   │
     │     ┌─────┴─────┐            │
     │     │   OPUS    │            │
     │     │ Validates │            │
     │     │ Handoff   │            │
     │     └───────────┘            │
     │                              │
     └── required_imports: [List]   └── MUST acknowledge: "I have List"
         edge_cases: [empty, ...]       MUST acknowledge: "I handle empty"
```

### 5.2 State Persistence & Recovery

```python
class StateManager:
    """
    Persistent state with checkpointing for recovery.
    """

    def __init__(self, task_id: str, persist_dir: str = "state"):
        self.task_id = task_id
        self.persist_path = f"{persist_dir}/{task_id}.json"
        self.state = OrchestratorState(task_id=task_id)

    def checkpoint(self, stage: str, validation: ValidationCheckpoint):
        """
        Save state after each validated stage.
        Enables recovery if later stages fail.
        """
        self.state.checkpoints.append(validation)

        with open(self.persist_path, 'w') as f:
            json.dump(asdict(self.state), f, indent=2)

    def recover_from_checkpoint(self, stage: str) -> OrchestratorState:
        """
        Recover state from last valid checkpoint.
        Used when a stage fails and we need to retry from known-good state.
        """
        with open(self.persist_path, 'r') as f:
            data = json.load(f)

        state = OrchestratorState(**data)

        # Reset state after the failed stage
        stage_order = ["planning", "context", "engineering", "review", "execution"]
        stage_idx = stage_order.index(stage)

        for later_stage in stage_order[stage_idx:]:
            setattr(state, f"{later_stage}_status", StageStatus.PENDING)

        return state
```

### 5.3 Audit Trail

```python
@dataclass
class AuditEvent:
    """Single event in audit trail."""
    timestamp: float
    event_type: str  # stage_start, stage_end, validation, retry, error
    stage: str
    model_used: str
    input_summary: str  # First 500 chars
    output_summary: str  # First 500 chars
    cost: float
    tokens: int
    validation_result: Optional[str]

class AuditTrail:
    """
    Complete audit trail for debugging and learning.
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.events: List[AuditEvent] = []

    def record(self, event: AuditEvent):
        self.events.append(event)

    def get_failure_analysis(self) -> Dict:
        """
        Analyze what went wrong for learning system.
        """
        failures = [e for e in self.events if "error" in e.event_type or
                   (e.validation_result and "APPROVED" not in e.validation_result)]

        return {
            "task_id": self.task_id,
            "total_events": len(self.events),
            "failures": len(failures),
            "failure_stages": [f.stage for f in failures],
            "failure_details": [
                {
                    "stage": f.stage,
                    "model": f.model_used,
                    "validation": f.validation_result,
                    "output_preview": f.output_summary
                }
                for f in failures
            ]
        }
```

---

## 6. Validation Framework

### 6.1 Multi-Layer Validation

The current system relies too heavily on LLM review. We need multiple layers:

```
LAYER 1: Static Analysis (Instant, Free)
├── Syntax check (AST parsing)
├── Import verification (are all imports present?)
├── Type hint validation (if present)
└── Basic lint (unused variables, etc.)

LAYER 2: Opus Semantic Review (5-10s, $0.10)
├── Algorithm correctness (trace through)
├── Edge case coverage (check each one)
├── Constraint compliance (check each constraint)
└── Output format verification

LAYER 3: Specialist Review (10-20s, $0.05)
├── Code style and idioms
├── Performance considerations
├── Security review (if applicable)
└── Maintainability assessment

LAYER 4: Execution (1-30s, Free)
├── Actually run the code
├── Run against test cases
├── Capture output/errors
└── GROUND TRUTH - overrides all above
```

### 6.2 Static Analysis Module

```python
import ast
import re
from typing import List, Tuple

class StaticAnalyzer:
    """
    Fast, free validation before expensive LLM calls.
    """

    def analyze(self, code: str, required_imports: List[str]) -> StaticAnalysisResult:
        """
        Perform static analysis on generated code.
        """
        issues = []

        # 1. Syntax check
        syntax_ok, syntax_error = self._check_syntax(code)
        if not syntax_ok:
            issues.append(f"SYNTAX ERROR: {syntax_error}")

        # 2. Import verification
        found_imports = self._extract_imports(code)
        missing_imports = set(required_imports) - set(found_imports)
        if missing_imports:
            issues.append(f"MISSING IMPORTS: {missing_imports}")

        # 3. Dangerous patterns
        dangerous = self._check_dangerous_patterns(code)
        if dangerous:
            issues.append(f"DANGEROUS PATTERNS: {dangerous}")

        return StaticAnalysisResult(
            passed=len(issues) == 0,
            issues=issues,
            found_imports=found_imports,
            functions_defined=self._extract_functions(code)
        )

    def _check_syntax(self, code: str) -> Tuple[bool, str]:
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"

    def _extract_imports(self, code: str) -> List[str]:
        """Extract all imported modules/names."""
        imports = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.append(alias.name)
        except:
            pass
        return imports

    def _check_dangerous_patterns(self, code: str) -> List[str]:
        """Check for dangerous code patterns."""
        dangerous = []
        patterns = [
            (r'os\.system\s*\(', "os.system call"),
            (r'subprocess\..*shell\s*=\s*True', "shell=True"),
            (r'eval\s*\(', "eval() usage"),
            (r'exec\s*\(', "exec() usage"),
            (r'__import__\s*\(', "__import__ usage"),
        ]
        for pattern, desc in patterns:
            if re.search(pattern, code):
                dangerous.append(desc)
        return dangerous
```

### 6.3 Execution Validator

```python
class ExecutionValidator:
    """
    The ultimate validator: actually run the code.
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def validate(
        self,
        code: str,
        test_cases: List[Dict]
    ) -> ExecutionResult:
        """
        Run code against test cases.
        This is GROUND TRUTH - if execution fails, the code is wrong.
        """

        results = []

        for test in test_cases:
            test_code = f"""
{code}

# Test case
result = {test['function_call']}
assert result == {test['expected']}, f"Expected {test['expected']}, got {{result}}"
print("PASS")
"""

            try:
                result = self._execute_in_subprocess(test_code)
                results.append({
                    "test": test['function_call'],
                    "passed": "PASS" in result.stdout,
                    "output": result.stdout,
                    "error": result.stderr
                })
            except TimeoutError:
                results.append({
                    "test": test['function_call'],
                    "passed": False,
                    "output": "",
                    "error": "TIMEOUT"
                })

        return ExecutionResult(
            all_passed=all(r["passed"] for r in results),
            results=results,
            summary=f"{sum(r['passed'] for r in results)}/{len(results)} tests passed"
        )

    def _execute_in_subprocess(self, code: str) -> subprocess.CompletedProcess:
        """Execute code in isolated subprocess with timeout."""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()

            try:
                result = subprocess.run(
                    ['python', f.name],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                return result
            finally:
                os.unlink(f.name)
```

---

## 7. Multi-Agent Coordination Patterns

### 7.1 Debate Pattern

Instead of single review, have multiple models debate:

```python
class DebateCoordinator:
    """
    Multiple models debate the solution.
    Forces deeper reasoning and catches blind spots.
    """

    def __init__(self, client: ResilientModelClient):
        self.client = client
        self.debaters = ["gpt-5.1", "kimi-k2-thinking", "sonnet-4.5"]

    def debate(self, code: str, task: str, rounds: int = 2) -> DebateResult:
        """
        Multiple models critique the solution.
        """

        critiques = []

        # Round 1: Independent critiques
        for model in self.debaters:
            critique = self._get_critique(model, code, task)
            critiques.append({"model": model, "critique": critique})

        # Round 2: Respond to each other's critiques
        if rounds > 1:
            for i, model in enumerate(self.debaters):
                others_critiques = [c for j, c in enumerate(critiques) if j != i]
                response = self._respond_to_critiques(model, code, others_critiques)
                critiques[i]["response"] = response

        # Opus adjudicates
        final_verdict = self._opus_adjudicate(code, task, critiques)

        return DebateResult(
            critiques=critiques,
            verdict=final_verdict,
            approved="APPROVED" in final_verdict
        )

    def _get_critique(self, model: str, code: str, task: str) -> str:
        prompt = f"""
        You are a code reviewer. Critically analyze this solution.

        TASK: {task}

        CODE:
        ```python
        {code}
        ```

        Identify:
        1. Correctness issues (bugs, logic errors)
        2. Missing edge cases
        3. Missing imports or dependencies
        4. Performance problems

        Be thorough. Don't say "looks good" unless you've traced through the logic.
        """

        return self.client.complete_with_failover("review", [
            {"role": "user", "content": prompt}
        ]).content

    def _opus_adjudicate(self, code: str, task: str, critiques: List[Dict]) -> str:
        prompt = f"""
        You are the final adjudicator. Multiple reviewers have analyzed this code.

        TASK: {task}

        CODE:
        ```python
        {code}
        ```

        REVIEWER CRITIQUES:
        {json.dumps(critiques, indent=2)}

        Synthesize the critiques and make a final decision:
        - APPROVED: If no significant issues remain
        - NEEDS REVISION: If issues were identified (list them)

        Your decision overrides individual reviewers.
        """

        return self.client.complete_with_failover("conductor", [
            {"role": "user", "content": prompt}
        ]).content
```

### 7.2 Ensemble Generation

Generate multiple solutions and select the best:

```python
class EnsembleGenerator:
    """
    Generate multiple solutions from different models.
    Select the best through validation.
    """

    def __init__(self, client: ResilientModelClient, executor: ExecutionValidator):
        self.client = client
        self.executor = executor
        self.generators = ["sonnet-4.5", "gpt-5.1", "qwen3-235b"]

    def generate_ensemble(
        self,
        task: str,
        context: OrchestratorState,
        test_cases: List[Dict]
    ) -> EnsembleResult:
        """
        Generate solutions from multiple models.
        Validate each and select the best.
        """

        solutions = []

        # Generate from each model
        for model in self.generators:
            code = self._generate(model, task, context)
            exec_result = self.executor.validate(code, test_cases)

            solutions.append({
                "model": model,
                "code": code,
                "execution_passed": exec_result.all_passed,
                "tests_passed": sum(r["passed"] for r in exec_result.results),
                "tests_total": len(exec_result.results)
            })

        # Select best (first by execution, then by test count)
        passing = [s for s in solutions if s["execution_passed"]]

        if passing:
            best = max(passing, key=lambda s: s["tests_passed"])
            return EnsembleResult(
                selected=best,
                all_solutions=solutions,
                strategy="execution_verified"
            )
        else:
            # None passed - use Opus to synthesize
            best = self._opus_synthesize(task, solutions)
            return EnsembleResult(
                selected=best,
                all_solutions=solutions,
                strategy="opus_synthesis"
            )

    def _opus_synthesize(self, task: str, failed_solutions: List[Dict]) -> Dict:
        """
        Opus synthesizes from multiple failed attempts.
        Uses failure analysis to create correct solution.
        """

        prompt = f"""
        Multiple models attempted this task but all failed execution.
        Analyze their attempts and create a correct solution.

        TASK: {task}

        FAILED ATTEMPTS:
        {json.dumps(failed_solutions, indent=2)}

        For each failed attempt, identify why it failed.
        Then synthesize a correct solution that avoids ALL identified issues.

        Output ONLY the corrected code.
        """

        response = self.client.complete_with_failover("conductor", [
            {"role": "user", "content": prompt}
        ])

        return {
            "model": "opus-4.5-synthesized",
            "code": self._extract_code(response.content),
            "execution_passed": None,  # Will be verified after
            "tests_passed": 0,
            "tests_total": 0
        }
```

### 7.3 Hierarchical Review

```python
class HierarchicalReviewer:
    """
    Fast models do initial screening.
    Premium models only review if issues found.
    """

    def __init__(self, client: ResilientModelClient):
        self.client = client

        # Review hierarchy (fastest → premium)
        self.hierarchy = [
            {"model": "kimi-k2", "threshold": "obvious_bugs"},
            {"model": "gpt-5.1", "threshold": "logic_errors"},
            {"model": "opus-4.5", "threshold": "subtle_issues"},
        ]

    def review(self, code: str, task: str, state: OrchestratorState) -> ReviewResult:
        """
        Hierarchical review - escalate only if issues found.
        """

        all_issues = []

        for level in self.hierarchy:
            result = self._review_at_level(level["model"], code, task, state)

            if result.issues:
                all_issues.extend(result.issues)

                # If severe issues, escalate to next level
                if self._is_severe(result.issues, level["threshold"]):
                    continue  # Go to next level
                else:
                    break  # Issues found but not severe, stop here
            else:
                break  # No issues, approved

        return ReviewResult(
            approved=len(all_issues) == 0,
            issues=all_issues,
            highest_level_used=level["model"]
        )
```

---

## 8. Learning & Adaptation

### 8.1 Pattern Learning (From Successes)

```python
class PatternLearner:
    """
    Extract patterns from successful solutions.
    Build a library of "what works."
    """

    def __init__(self, storage_path: str = "patterns"):
        self.storage_path = storage_path
        self.patterns: Dict[str, Pattern] = self._load_patterns()

    def learn_from_success(self, task: str, code: str, execution_result: ExecutionResult):
        """
        Extract patterns from successful solution.
        """

        # Use Opus to identify patterns
        prompt = f"""
        Analyze this successful solution and extract reusable patterns.

        TASK: {task}

        SUCCESSFUL CODE:
        ```python
        {code}
        ```

        For each pattern, provide:
        1. Name (e.g., "two_pointer_technique", "hash_map_lookup")
        2. Category (data_structures, algorithms, error_handling, etc.)
        3. Description (when to use this pattern)
        4. Code template (minimal example)
        5. When to use (what kind of problems benefit)

        Output as JSON array.
        """

        response = self._call_opus(prompt)
        patterns = json.loads(response)

        for p in patterns:
            self._add_pattern(Pattern(**p))

    def get_relevant_patterns(self, task: str) -> List[Pattern]:
        """
        Find patterns relevant to a new task.
        """

        # Simple keyword matching (could be more sophisticated)
        task_lower = task.lower()
        relevant = []

        for pattern in self.patterns.values():
            if any(kw in task_lower for kw in pattern.keywords):
                relevant.append(pattern)

        return sorted(relevant, key=lambda p: p.success_count, reverse=True)[:5]
```

### 8.2 Anti-Pattern Learning (From Failures)

```python
class AntiPatternLearner:
    """
    Extract anti-patterns from failed solutions.
    Build a library of "what NOT to do."
    """

    def learn_from_failure(
        self,
        task: str,
        code: str,
        error: str,
        stage: str
    ):
        """
        Extract anti-pattern from failed solution.
        """

        prompt = f"""
        Analyze this failed solution and identify the anti-pattern.

        TASK: {task}

        FAILED CODE:
        ```python
        {code}
        ```

        ERROR: {error}

        STAGE WHERE FAILURE DETECTED: {stage}

        Provide:
        1. Anti-pattern name (e.g., "missing_import", "off_by_one_error")
        2. Category (syntax, logic, edge_case, import, etc.)
        3. Bad example (minimal code showing the mistake)
        4. Fix guidance (how to avoid this in future)
        5. Detection heuristic (how to catch this before execution)

        Output as JSON.
        """

        response = self._call_opus(prompt)
        anti_pattern = AntiPattern(**json.loads(response))

        self._add_anti_pattern(anti_pattern)

    def get_warnings_for_task(self, task: str) -> List[str]:
        """
        Get relevant warnings based on learned anti-patterns.
        """

        warnings = []
        task_lower = task.lower()

        for ap in self.anti_patterns.values():
            if any(kw in task_lower for kw in ap.trigger_keywords):
                warnings.append(
                    f"WARNING ({ap.category}): {ap.name}\n"
                    f"Common mistake: {ap.bad_example}\n"
                    f"Guidance: {ap.fix_guidance}"
                )

        return warnings
```

### 8.3 Prompt Evolution

```python
class PromptEvolver:
    """
    Evolve prompts based on learning.
    """

    def __init__(
        self,
        pattern_learner: PatternLearner,
        anti_pattern_learner: AntiPatternLearner
    ):
        self.patterns = pattern_learner
        self.anti_patterns = anti_pattern_learner
        self.base_prompt = self._load_base_prompt()

    def generate_evolved_prompt(self, task: str, role: str) -> str:
        """
        Generate prompt that includes relevant patterns and warnings.
        """

        # Get relevant patterns
        relevant_patterns = self.patterns.get_relevant_patterns(task)
        pattern_section = self._format_patterns(relevant_patterns)

        # Get relevant warnings
        warnings = self.anti_patterns.get_warnings_for_task(task)
        warning_section = self._format_warnings(warnings)

        # Compose evolved prompt
        return f"""
{self.base_prompt}

===== LEARNED PATTERNS (use these when applicable) =====
{pattern_section}

===== WARNINGS (avoid these mistakes) =====
{warning_section}

===== YOUR TASK =====
{task}
"""
```

---

## 9. Failure Handling & Recovery

### 9.1 Failure Taxonomy

```python
class FailureType(Enum):
    """Classification of failures for appropriate handling."""

    # Provider failures (retry with fallback)
    PROVIDER_ERROR = "provider_error"       # 503, 429, etc.
    TIMEOUT = "timeout"                      # Model took too long
    RATE_LIMIT = "rate_limit"               # API rate limited

    # Code failures (retry with guidance)
    SYNTAX_ERROR = "syntax_error"           # Code doesn't parse
    IMPORT_ERROR = "import_error"           # Missing imports
    RUNTIME_ERROR = "runtime_error"         # Exception during execution
    WRONG_OUTPUT = "wrong_output"           # Runs but wrong result

    # Logic failures (needs escalation)
    ALGORITHM_ERROR = "algorithm_error"     # Fundamental logic wrong
    EDGE_CASE_MISS = "edge_case_miss"       # Didn't handle edge case
    CONSTRAINT_VIOLATION = "constraint"     # Violated a constraint

    # Coordination failures (needs Opus intervention)
    CONTEXT_LOSS = "context_loss"           # Information lost at handoff
    REQUIREMENT_DRIFT = "requirement_drift" # Deviated from requirements
    SCOPE_CREEP = "scope_creep"            # Added unrequested features

class FailureClassifier:
    """Classify failures to determine appropriate response."""

    def classify(self, error: str, code: str, context: OrchestratorState) -> FailureType:
        """Classify the failure type."""

        # Check for provider errors
        if "503" in error or "429" in error or "timeout" in error.lower():
            return FailureType.PROVIDER_ERROR

        # Check for syntax errors
        if "SyntaxError" in error:
            return FailureType.SYNTAX_ERROR

        # Check for import errors
        if "ImportError" in error or "ModuleNotFoundError" in error:
            return FailureType.IMPORT_ERROR

        if "NameError" in error and "not defined" in error:
            # Check if it's a missing import
            undefined = re.search(r"name '(\w+)' is not defined", error)
            if undefined:
                name = undefined.group(1)
                if name in context.required_imports:
                    return FailureType.IMPORT_ERROR

        # Check for assertion errors (wrong output)
        if "AssertionError" in error:
            return FailureType.WRONG_OUTPUT

        # Use Opus to classify complex failures
        return self._opus_classify(error, code, context)
```

### 9.2 Recovery Strategies

```python
class RecoveryEngine:
    """
    Recover from failures based on failure type.
    """

    def __init__(self, client: ResilientModelClient, state_manager: StateManager):
        self.client = client
        self.state = state_manager

    def recover(
        self,
        failure_type: FailureType,
        error: str,
        stage: str
    ) -> RecoveryAction:
        """
        Determine and execute recovery action.
        """

        strategy = self._get_strategy(failure_type)

        if strategy == "retry_with_fallback":
            # Try different provider
            return RecoveryAction(
                action="retry",
                use_fallback=True,
                guidance=None
            )

        elif strategy == "retry_with_guidance":
            # Same model, but with specific guidance
            guidance = self._generate_guidance(failure_type, error)
            return RecoveryAction(
                action="retry",
                use_fallback=False,
                guidance=guidance
            )

        elif strategy == "escalate_model":
            # Try more capable model
            return RecoveryAction(
                action="escalate",
                use_fallback=False,
                guidance=self._generate_guidance(failure_type, error)
            )

        elif strategy == "opus_takeover":
            # Let Opus handle the whole thing
            return RecoveryAction(
                action="opus_takeover",
                use_fallback=False,
                guidance=self._compile_failure_context()
            )

        elif strategy == "checkpoint_recovery":
            # Roll back to last good state
            return RecoveryAction(
                action="checkpoint_recovery",
                checkpoint_stage=self._find_last_good_checkpoint(),
                guidance=error
            )

    def _get_strategy(self, failure_type: FailureType) -> str:
        """Map failure type to recovery strategy."""

        mapping = {
            FailureType.PROVIDER_ERROR: "retry_with_fallback",
            FailureType.TIMEOUT: "retry_with_fallback",
            FailureType.RATE_LIMIT: "retry_with_fallback",

            FailureType.SYNTAX_ERROR: "retry_with_guidance",
            FailureType.IMPORT_ERROR: "retry_with_guidance",
            FailureType.RUNTIME_ERROR: "retry_with_guidance",
            FailureType.WRONG_OUTPUT: "retry_with_guidance",

            FailureType.ALGORITHM_ERROR: "escalate_model",
            FailureType.EDGE_CASE_MISS: "escalate_model",
            FailureType.CONSTRAINT_VIOLATION: "escalate_model",

            FailureType.CONTEXT_LOSS: "opus_takeover",
            FailureType.REQUIREMENT_DRIFT: "opus_takeover",
            FailureType.SCOPE_CREEP: "checkpoint_recovery",
        }

        return mapping.get(failure_type, "opus_takeover")

    def _generate_guidance(self, failure_type: FailureType, error: str) -> str:
        """Generate specific guidance for retry."""

        if failure_type == FailureType.IMPORT_ERROR:
            return f"""
            CRITICAL FIX REQUIRED:
            The previous attempt failed with: {error}

            You MUST include all necessary imports at the top of your code.
            Do NOT assume any modules are pre-imported.

            Required imports based on task: {self.state.state.required_imports}
            """

        elif failure_type == FailureType.WRONG_OUTPUT:
            return f"""
            CRITICAL FIX REQUIRED:
            The previous attempt failed with: {error}

            The code executed but produced wrong output.
            Trace through your algorithm with the failing test case.
            Check for off-by-one errors, wrong comparisons, or incorrect logic.
            """

        # ... more guidance types
```

### 9.3 Circuit Breaker

```python
class CircuitBreaker:
    """
    Prevent infinite retry loops.
    """

    def __init__(
        self,
        max_retries_per_stage: int = 3,
        max_total_retries: int = 10,
        max_cost: float = 50.0
    ):
        self.max_retries_per_stage = max_retries_per_stage
        self.max_total_retries = max_total_retries
        self.max_cost = max_cost

        self.stage_retries: Dict[str, int] = {}
        self.total_retries: int = 0
        self.total_cost: float = 0.0

    def can_retry(self, stage: str) -> Tuple[bool, str]:
        """Check if retry is allowed."""

        stage_count = self.stage_retries.get(stage, 0)

        if stage_count >= self.max_retries_per_stage:
            return False, f"Max retries for stage {stage} ({self.max_retries_per_stage})"

        if self.total_retries >= self.max_total_retries:
            return False, f"Max total retries reached ({self.max_total_retries})"

        if self.total_cost >= self.max_cost:
            return False, f"Cost limit reached (${self.max_cost})"

        return True, "OK"

    def record_retry(self, stage: str, cost: float):
        """Record a retry attempt."""
        self.stage_retries[stage] = self.stage_retries.get(stage, 0) + 1
        self.total_retries += 1
        self.total_cost += cost
```

---

## 10. Evaluation Criteria

### 10.1 Primary Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Pass@1** | >95% | % of tasks passing on first orchestration attempt |
| **Pass@3** | >99% | % of tasks passing within 3 attempts |
| **Execution Success** | 100% | All "passed" solutions actually execute |

### 10.2 Secondary Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Handoff Integrity** | 100% | No information lost between stages |
| **Import Accuracy** | 100% | All required imports present |
| **Edge Case Coverage** | >95% | Identified edge cases are handled |
| **Recovery Success** | >80% | Failures recovered without Opus takeover |

### 10.3 Efficiency Metrics (Informational Only)

| Metric | Note |
|--------|------|
| **Time to Solution** | Track but don't optimize |
| **Total Cost** | Track but don't optimize |
| **Tokens Used** | Track for analysis |

### 10.4 Benchmark Suite

1. **Via2 Comparison Tasks** (7 problems, varying difficulty)
   - Must achieve 100% (currently: baseline=100%, optimized=43%)

2. **HumanEval** (164 problems)
   - Must achieve >97% (current best: 97.6%)

3. **SWE-bench Verified** (500 problems)
   - Target: >50% (current SOTA ~55%)

4. **Custom Edge Case Suite** (to be developed)
   - Focus on the failure modes we've identified

---

## 11. Research Questions

### 11.1 Coordination Patterns

1. **When should Opus validate?**
   - After every stage? (current proposal)
   - Only when fast-model confidence is low?
   - Based on task complexity?

2. **How detailed should Opus validation be?**
   - Full trace-through of algorithm?
   - Just check structured criteria?
   - Adaptive based on failure history?

3. **Can we predict when coordination is needed?**
   - Train classifier on task → needs_coordination?
   - Use simpler systems for simple tasks?

### 11.2 Multi-Agent Dynamics

4. **Does debate improve quality?**
   - Compare: single review vs. multi-model debate
   - Is the cost justified?

5. **Does ensemble generation help?**
   - Generate 3, pick best vs. generate 1, retry if wrong
   - What's the quality/cost tradeoff?

6. **Optimal provider diversification?**
   - Same family (Claude) vs. different families (Claude + GPT + Gemini)?
   - Provider-specific biases?

### 11.3 Learning & Adaptation

7. **How fast does pattern learning help?**
   - N tasks to see improvement?
   - Quality of learned patterns?

8. **Anti-pattern effectiveness?**
   - Do warnings actually prevent mistakes?
   - Over-warning problem?

9. **Prompt evolution convergence?**
   - Does evolved prompt stabilize?
   - When to reset vs. continue evolving?

### 11.4 Failure Modes

10. **What failures can't be recovered?**
    - Fundamental misunderstanding of task?
    - Ambiguous requirements?

11. **Optimal retry budget allocation?**
    - More retries early (context) vs. late (execution)?
    - Adaptive based on task?

12. **When does Opus takeover help vs. hurt?**
    - Cost of takeover vs. continued retries?
    - Does Opus actually do better?

---

## Appendix: Evidence Base

### A.1 Comparison Test Results (2025-11-30)

```json
{
  "test_date": "2025-11-30",
  "task_count": 7,
  "results": {
    "opus-baseline": {
      "pass_rate": "100%",
      "passed": 7,
      "failed": 0,
      "avg_time": "21.6s",
      "avg_cost": "$0.032"
    },
    "opus-optimized": {
      "pass_rate": "43%",
      "passed": 3,
      "failed": 4,
      "avg_time": "81.3s",
      "avg_cost": "$0.041"
    }
  },
  "failure_analysis": [
    {"task": "easy_2", "error": "NameError: List not defined", "cause": "Missing import"},
    {"task": "medium_1", "error": "AssertionError", "cause": "Algorithm bug"},
    {"task": "medium_2", "error": "AssertionError", "cause": "Logic bug"},
    {"task": "hard_2", "error": "503 from Cerebras", "cause": "Provider failure"}
  ]
}
```

### A.2 HumanEval Benchmark Results (2025-11-23)

```
ALO-BestInClass: 97.6% (160/164)
ALO-Sonnet:      97.6% (160/164)
ALO-Optimized:   97.0% (159/164)
ALO-Open:        95.1% (156/164)
```

### A.3 Codebase Statistics

| Component | Lines | Purpose |
|-----------|-------|---------|
| agentic_loop.py | 569 | Core loop |
| meta_orchestrator.py | 1,218 | Current orchestrator |
| docker_executor.py | 309 | Container management |
| model_selection_learner.py | 460 | Model routing |
| compounding_learner.py | 576 | Pattern learning |
| strategic_planner.py | 466 | Task planning |
| multi_provider_client.py | 362 | API client |
| **TOTAL** | 7,277+ | Opus Orchestrator |

### A.4 Current Model Registry

| Model | Provider | Speed | Input Cost | Output Cost | Context |
|-------|----------|-------|------------|-------------|---------|
| opus-4.5 | OpenRouter | 45 tok/s | $5.00/M | $25.00/M | 200K |
| sonnet-4.5 | OpenRouter | 77 tok/s | $3.00/M | $15.00/M | 200K |
| gpt-5.1 | OpenAI | 72 tok/s | $1.25/M | $10.00/M | 272K |
| gemini-3-pro | OpenRouter | 80 tok/s | $1.50/M | $12.00/M | 1M |
| gemini-2.5-flash | OpenRouter | 200 tok/s | $0.15/M | $0.60/M | 1M |
| qwen3-235b | Cerebras | 735 tok/s | $0.60/M | $1.20/M | 262K |
| kimi-k2 | OpenRouter | 200 tok/s | $0.14/M | $0.28/M | 131K |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-01 | Claude Opus 4.5 | Initial PRD based on Via2 codebase analysis |

---

*END OF DOCUMENT*
