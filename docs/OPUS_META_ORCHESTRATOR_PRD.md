# Product Requirements Document: Opus Meta-Orchestrator

## Document Information
- **Version:** 1.0
- **Created:** 2025-11-26
- **Status:** Draft
- **Owner:** ALO Development Team

---

## Executive Summary

### Problem Statement
The current ALO-Opus configuration achieves the highest LLM judge scores (8.50/10) but suffers from poor code execution rates (2/10) due to over-engineering. Opus creates multi-file architectures and uses external dependencies that fail in sandboxed execution environments.

### Proposed Solution
Transform Opus from a direct code generator into a **Meta-Orchestrator** that:
1. Plans execution strategy
2. Selects optimal models for each agent
3. Specifies explicit constraints to prevent over-engineering
4. Validates outputs against strategic plans
5. Adapts retry strategy based on failure analysis

### Expected Outcomes

**Primary Baseline: Opus-Only (No Orchestration)**
The Meta-Orchestrator must beat pure Opus with just its context window to justify complexity.

| Metric | Opus-Only Baseline | ALO-Opus (Current) | Target Meta-Orchestrator |
|--------|-------------------|-------------------|--------------------------|
| LLM Judge Score | TBD | 8.50/10 | 8.5-9.0/10 |
| Code Eval Score | TBD | 6.00/10 | 8.0-8.5/10 |
| Execution Rate | TBD | 2/10 | 8-9/10 |
| Avg Cost/Task | ~$0.10-0.15 | $1.43 | $0.30-0.50 |

**Success Criteria:** Meta-Orchestrator must achieve higher Combined Score than Opus-Only baseline while maintaining cost within 3-4x of baseline.

---

## Background & Context

### Current Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    ALO ORCHESTRATOR                         │
│                 (Linear Pipeline)                           │
└─────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐      ┌─────────────┐     ┌─────────┐
   │ Context │  →   │ Engineering │  →  │ Review  │
   │ Agent   │      │   Agent     │     │ Agent   │
   │(Gemini) │      │  (Qwen/GLM) │     │(Kimi-K2)│
   └─────────┘      └─────────────┘     └─────────┘
```

**Problems with Current Approach:**
1. **No strategic planning** - Each agent operates independently
2. **No constraint enforcement** - Models free to over-engineer
3. **Fixed model assignment** - Same model regardless of problem complexity
4. **Reactive review** - Review happens after the fact, not guided by plan

### Benchmark Evidence

**5-Way Benchmark Results (Nov 2025):**

| System | LLM Judge | Code Eval | Execution | Delta |
|--------|-----------|-----------|-----------|-------|
| ALO-Opus | 8.50 | 6.00 | 2/10 | -2.50 |
| ALO-BestInClass | 7.93 | 5.60 | 0/10 | -2.33 |
| ALO-Sonnet | 7.90 | 4.40 | 0/10 | -3.50 |
| ALO-Open | 7.60 | 6.00 | 3/10 | -1.60 |
| ALO-Optimized | 7.37 | 6.60 | 6/10 | -0.77 |

**Key Insight:** ALO-Optimized has lowest LLM score but BEST execution rate (6/10).

---

## Requirements

### Functional Requirements

#### FR-1: Strategic Analysis Phase (Opus)
**Priority:** P0 (Critical)

The system SHALL analyze incoming tasks and produce a structured execution plan including:

1. **Problem Classification**
   - Complexity level: simple | medium | complex | expert
   - Domain: algorithms | systems | data-structures | distributed | ml
   - Required capabilities: thread-safety | async | io | networking

2. **Constraint Generation**
   - File structure: single-file | multi-module (with justification)
   - Dependencies: stdlib-only | specific-allowed (list)
   - Performance: O(1)-required | O(n)-acceptable | no-constraint
   - Edge cases: explicit list of cases that MUST be handled

3. **Model Selection**
   - Context agent: Gemini-3 | GLM-4.6 | Sonnet-4.5 (with rationale)
   - Engineering agent: Qwen3 | GLM-4.6 | Sonnet-4.5 | Opus-4.5 (with rationale)
   - Review agent: Kimi-K2 | GPT-5.1 | Opus-4.5 (with rationale)

4. **Success Criteria**
   - Explicit checklist for validation phase
   - Predicted failure modes with mitigation strategies

#### FR-2: Constraint-Aware Execution
**Priority:** P0 (Critical)

The system SHALL inject Opus-generated constraints into agent prompts:

```
OPUS STRATEGIC CONSTRAINTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━
MUST: Use Python standard library only
MUST: Implement as single self-contained file
MUST: Use threading.Lock for thread safety
MUST: Handle edge cases: empty input, None values, concurrent access
SHOULD: Prefer O(1) operations where possible
SHOULD NOT: Use OrderedDict (use manual linked list for learning value)
━━━━━━━━━━━━━━━━━━━━━━━━━━

Violation of MUST constraints will result in automatic rejection.
```

#### FR-3: Adaptive Validation Phase (Opus)
**Priority:** P0 (Critical)

The system SHALL validate outputs against the strategic plan:

1. **Constraint Compliance Check**
   - Binary pass/fail for each MUST constraint
   - Automatic rejection if any MUST violated

2. **Architectural Review**
   - Compare implementation approach to planned approach
   - Flag deviations with severity levels

3. **Execution Prediction**
   - Opus predicts whether code will execute successfully
   - Identifies likely failure modes (ImportError, SyntaxError, etc.)

4. **Diagnostic Output**
   - Specific, actionable feedback for failures
   - Clear indication of which constraint was violated

#### FR-4: Adaptive Retry Strategy
**Priority:** P1 (High)

The system SHALL implement intelligent retry logic:

| Failure Type | Strategy | Example |
|--------------|----------|---------|
| Constraint Violation | Emphatic retry (same model) | "You used redis - STRICTLY FORBIDDEN" |
| Architectural Error | Model upgrade | Qwen → Sonnet → Opus |
| Edge Case Missing | Guided fix | "Add check for empty input on line 47" |
| Repeated Failure (3x) | Opus takeover | Opus generates directly with constraints |

#### FR-5: Execution Plan Persistence
**Priority:** P1 (High)

The system SHALL persist execution plans for:
- Audit trail and debugging
- Learning from successful/failed strategies
- Cost tracking per phase

### Non-Functional Requirements

#### NFR-1: Performance
- Planning phase: < 30 seconds
- Total task completion: < 5 minutes (95th percentile)
- API call overhead: < 20% vs direct model calls

#### NFR-2: Cost Efficiency
- Target: 50-70% cost reduction vs full Opus pipeline
- Opus usage: Planning + Validation only (not implementation)
- Model selection should optimize cost/quality tradeoff

#### NFR-3: Observability
- Structured logging of all phases
- Cost tracking per agent and per task
- Success/failure metrics by problem type

#### NFR-4: Reliability
- Graceful degradation if Opus unavailable
- Fallback to ALO-Optimized configuration
- No silent failures (FAIL IS FAIL policy)

---

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       OPUS META-ORCHESTRATOR                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐           │
│  │   Strategic   │    │   Execution   │    │   Adaptive    │           │
│  │   Planner     │───▶│   Engine      │───▶│   Validator   │           │
│  │   (Opus)      │    │  (Multi-Model)│    │   (Opus)      │           │
│  └───────────────┘    └───────────────┘    └───────────────┘           │
│         │                    │                    │                     │
│         ▼                    ▼                    ▼                     │
│  ┌───────────────────────────────────────────────────────────┐         │
│  │                    STATE MANAGER                          │         │
│  │  - ExecutionPlan    - LoopState    - ValidationResult    │         │
│  └───────────────────────────────────────────────────────────┘         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             ┌──────────┐    ┌──────────┐    ┌──────────┐
             │  Gemini  │    │  Qwen3   │    │  Kimi-K2 │
             │  Client  │    │  Client  │    │  Client  │
             └──────────┘    └──────────┘    └──────────┘
```

### Data Models

#### ExecutionPlan
```python
@dataclass
class ExecutionPlan:
    task_id: str
    timestamp: datetime

    # Problem Analysis
    complexity: Literal["simple", "medium", "complex", "expert"]
    domain: str
    capabilities_required: List[str]

    # Constraints
    constraints: List[Constraint]

    # Model Selection
    model_selections: Dict[str, ModelConfig]
    selection_rationale: Dict[str, str]

    # Success Criteria
    success_criteria: List[str]
    predicted_failure_modes: List[str]

    # Execution Strategy
    approach: str
    key_decisions: List[str]

@dataclass
class Constraint:
    level: Literal["MUST", "SHOULD", "SHOULD_NOT", "MUST_NOT"]
    description: str
    validation_check: str  # How to verify compliance
```

#### ValidationResult
```python
@dataclass
class ValidationResult:
    passed: bool

    # Constraint Compliance
    constraint_results: Dict[str, bool]
    violated_constraints: List[str]

    # Failure Analysis
    failure_type: Optional[str]  # constraint_violation | architectural_error | edge_case_missing
    failure_details: Optional[str]

    # Recommended Action
    retry_strategy: Optional[str]
    specific_guidance: Optional[str]
    model_recommendation: Optional[str]
```

### API Contracts

#### OpusMetaOrchestrator.run()
```python
def run(
    self,
    issue: str,
    repo_path: Optional[str] = None,
    max_retries: int = 3
) -> Tuple[LoopState, ExecutionPlan, List[ValidationResult]]:
    """
    Execute task using meta-orchestrator pattern.

    Args:
        issue: Task description
        repo_path: Path to target repository (optional)
        max_retries: Maximum retry attempts per phase

    Returns:
        Tuple of:
        - Final LoopState with solution
        - ExecutionPlan used
        - List of ValidationResults from each attempt
    """
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (3-4 days)
- [ ] Create `ExecutionPlan` and `ValidationResult` dataclasses
- [ ] Implement `StrategicPlanner` class with Opus integration
- [ ] Create constraint injection system for agent prompts
- [ ] Add execution plan persistence to trace.jsonl

### Phase 2: Validation System (2-3 days)
- [ ] Implement `AdaptiveValidator` class with Opus
- [ ] Create constraint compliance checker
- [ ] Build failure type classifier
- [ ] Implement retry strategy selector

### Phase 3: Integration (2-3 days)
- [ ] Create `OpusMetaOrchestrator` main class
- [ ] Integrate with existing agent infrastructure
- [ ] Add model selection routing
- [ ] Implement fallback to ALO-Optimized

### Phase 4: Evaluation (2 days)
- [ ] Run full benchmark suite (10 prompts)
- [ ] Compare against existing 5 systems
- [ ] Analyze cost vs quality tradeoffs
- [ ] Document learnings and tune parameters

---

## Success Metrics

### Primary KPIs
| Metric | Target | Measurement |
|--------|--------|-------------|
| Combined Score | ≥ 8.0/10 | (LLM Judge + Code Eval) / 2 |
| Execution Rate | ≥ 80% | Code executes without error |
| Cost Efficiency | ≤ $0.50/task | Total API costs |

### Secondary KPIs
| Metric | Target | Measurement |
|--------|--------|-------------|
| Planning Accuracy | ≥ 90% | Predictions match outcomes |
| Constraint Compliance | ≥ 95% | Implementations follow constraints |
| Retry Rate | ≤ 20% | Tasks requiring retry |

---

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Opus planning adds latency | Medium | Medium | Cache common patterns, parallel planning |
| Constraints too restrictive | High | Medium | Iterative tuning, allow constraint relaxation |
| Model selection suboptimal | Medium | Low | A/B testing, learning from outcomes |
| Opus unavailable | High | Low | Fallback to ALO-Optimized config |

---

## Appendix

### A. Prompt Templates

#### Strategic Planning Prompt
```
You are a senior software architect creating an execution plan for an AI coding system.

TASK:
{issue}

Analyze this task and provide a structured execution plan:

1. PROBLEM CLASSIFICATION
   - Complexity: [simple|medium|complex|expert]
   - Domain: [algorithms|systems|data-structures|distributed|ml]
   - Required capabilities: [list]

2. CONSTRAINTS (critical for success)
   For each constraint, specify:
   - Level: MUST | SHOULD | SHOULD_NOT | MUST_NOT
   - Description: What the constraint requires
   - Validation: How to verify compliance

   Common constraints to consider:
   - File structure (single file vs multi-module)
   - Dependencies (stdlib only vs specific packages)
   - Performance requirements
   - Thread safety requirements
   - Edge cases that MUST be handled

3. MODEL SELECTION
   For each agent (context, engineering, review), recommend:
   - Model: [Gemini-3|GLM-4.6|Qwen3|Sonnet-4.5|Opus-4.5|Kimi-K2|GPT-5.1]
   - Rationale: Why this model for this task

4. SUCCESS CRITERIA
   - List specific, verifiable criteria
   - Include edge cases to test

5. PREDICTED FAILURE MODES
   - What could go wrong?
   - How to detect each failure?

Return as structured JSON.
```

#### Validation Prompt
```
Review this implementation against the strategic plan:

ORIGINAL PLAN:
{execution_plan}

IMPLEMENTATION:
{proposed_solution}

Evaluate:

1. CONSTRAINT COMPLIANCE
   For each constraint in the plan, check:
   - Compliant: YES | NO
   - Evidence: Quote from code or explain violation

2. ARCHITECTURAL REVIEW
   - Does the approach match the plan?
   - Any concerning deviations?

3. EXECUTION PREDICTION
   - Will this code execute successfully?
   - Predicted failure mode (if any): [ImportError|SyntaxError|RuntimeError|None]
   - Specific issue (if predicted to fail)

4. RECOMMENDATION
   If issues found:
   - Failure type: [constraint_violation|architectural_error|edge_case_missing]
   - Specific fix guidance
   - Should we retry with same model or upgrade?

Return as structured JSON.
```

### B. Example Execution Plan

```json
{
  "task_id": "rate_limiter_001",
  "complexity": "medium",
  "domain": "systems",
  "capabilities_required": ["thread-safety", "time-management"],

  "constraints": [
    {
      "level": "MUST",
      "description": "Use Python standard library only",
      "validation_check": "No imports outside of stdlib"
    },
    {
      "level": "MUST",
      "description": "Implement as single self-contained file",
      "validation_check": "No relative imports, no multi-file structure"
    },
    {
      "level": "MUST",
      "description": "Use threading.Lock for thread safety",
      "validation_check": "Lock acquisition around shared state"
    },
    {
      "level": "SHOULD",
      "description": "Use time.monotonic() instead of time.time()",
      "validation_check": "monotonic preferred for intervals"
    }
  ],

  "model_selections": {
    "context": {
      "model": "GLM-4.6",
      "rationale": "Simple context needs, cost-effective"
    },
    "engineering": {
      "model": "Qwen3-Coder",
      "rationale": "Standard implementation, fast and reliable"
    },
    "review": {
      "model": "Kimi-K2",
      "rationale": "Thorough validation without over-engineering"
    }
  },

  "success_criteria": [
    "Implements token bucket algorithm correctly",
    "Thread-safe under concurrent access",
    "Supports multiple users with separate buckets",
    "Handles edge case: refill during consumption"
  ],

  "predicted_failure_modes": [
    "ImportError if using redis/aioredis",
    "Race condition if Lock not used properly",
    "Incorrect refill timing if using time.time()"
  ]
}
```
