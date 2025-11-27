# Opus Meta-Orchestrator Design - Ultrathink Analysis

## Problem Statement

**Current State:**
- ALO-Opus scores highest on LLM judge (8.50/10) but has poor execution (2/10)
- Opus excels at correctness (9.0) and completeness (9.0) when evaluated subjectively
- But over-engineers solutions with multi-file architectures and external dependencies
- When Opus CAN execute, it's BRILLIANT (10/10 on graph_cycle_detection, 8/10 on regex_engine)

**Key Insight:** Opus should do what it's BEST at - high-level reasoning, architecture, planning, and validation - NOT direct code generation.

---

## Design: Hierarchical Meta-Orchestrator Architecture

### Core Concept
Opus acts as a "senior architect" that plans, delegates, validates, and adapts strategy - while specialized models do the actual implementation.

```
┌─────────────────────────────────────────────────────────────┐
│                   OPUS META-ORCHESTRATOR                    │
│  (Strategic planning, model selection, validation, retry)  │
└─────────────────────────────────────────────────────────────┘
                           │
                ┌──────────┼──────────┐
                ▼          ▼          ▼
       ┌─────────────┬─────────────┬─────────────┐
       │   Context   │   Engine    │   Review    │
       │   Agent     │   Agent     │   Agent     │
       │  (Selected  │ (Selected   │ (Selected   │
       │  by Opus)   │  by Opus)   │  by Opus)   │
       └─────────────┴─────────────┴─────────────┘
```

---

## Phase Breakdown

### Phase 0: Strategic Analysis (OPUS ONLY)

**Opus's Role:**
1. **Problem Classification**
   - Complexity assessment (simple/medium/complex/expert)
   - Domain identification (algorithms, systems, data structures, etc.)
   - Constraint detection (performance-critical? thread-safety required?)

2. **Strategy Selection**
   - Choose optimal approach: ReAct, Chain-of-Thought, Tree-of-Thoughts
   - Decide on single-file vs multi-file (based on execution requirements)
   - Identify critical validation criteria

3. **Resource Allocation**
   - Select best model for each agent based on:
     - Context needs: Gemini 3 (large context) vs GLM-4.6 (cost-effective)
     - Engineering: Qwen3-Coder (fast) vs Sonnet (balanced) vs Opus (complex)
     - Review: Kimi-K2 (thorough) vs GPT-5.1 (fast) vs Opus (critical)

4. **Constraint Specification**
   - Generate explicit constraints for engineering agent:
     ```
     CONSTRAINTS FROM OPUS:
     - MUST use Python stdlib only (no external deps)
     - MUST be single self-contained file
     - MUST handle edge case: empty input, None values
     - MUST be thread-safe (use threading.Lock)
     - SHOULD prefer O(1) operations where possible
     ```

**Output:** Detailed execution plan with model assignments and constraints

---

### Phase 1-3: Delegated Execution (SPECIALIZED MODELS)

Models selected by Opus execute their roles, but with:
- **Enhanced context** from Opus's analysis
- **Explicit constraints** to prevent over-engineering
- **Success criteria** defined by Opus

Example engineering agent prompt:
```
You are implementing a solution based on this strategic plan:

OPUS ANALYSIS:
Problem Type: Data structure implementation (medium complexity)
Critical Requirements: O(1) operations, thread safety, TTL support
Predicted Gotchas: Race conditions in TTL cleanup, OrderedDict vs manual LinkedList

CONSTRAINTS (MUST FOLLOW):
- Single Python file, stdlib only
- Use threading.Lock for thread safety
- No external dependencies (no redis, no redis-py)

OPUS STRATEGY:
1. Use dict for O(1) key lookup
2. Use doubly-linked list for LRU ordering
3. Use monotonic clock for TTL
4. Include background cleanup thread

NOW IMPLEMENT THIS SOLUTION.
```

---

### Phase 4: Adaptive Validation (OPUS AS CRITIC)

**Opus reviews output with specific lens:**

1. **Constraint Compliance Check**
   - Did it follow single-file requirement? ✓/✗
   - Uses only stdlib? ✓/✗
   - Handles specified edge cases? ✓/✗

2. **Architectural Review**
   - "The implementation uses OrderedDict instead of manual LinkedList - acceptable trade-off for maintainability"
   - "Thread safety is adequate but could deadlock if get() is called within put() - needs fix"

3. **Failure Diagnosis**
   - If execution fails: "ImportError: aioredis - VIOLATED CONSTRAINT. Retry with explicit stdlib-only reminder."
   - If logic error: "Edge case not handled: empty queue during pop() - needs defensive check"

4. **Adaptive Strategy**
   - **Success** → Proceed
   - **Minor issues** → Provide specific fix guidance, retry with same model
   - **Major issues** → Switch to more capable model (e.g., Qwen → Sonnet → Opus)
   - **Constraint violations** → Regenerate with EMPHATIC constraint reminder
   - **Repeated failures** → Simplify requirements or change approach

---

## Detailed Implementation: MetaOrchestratorLoop

### New Core Component: `OpusMetaOrchestrator`

```python
class OpusMetaOrchestrator:
    """Opus-powered meta-orchestrator that plans, delegates, and validates."""

    def __init__(self):
        self.opus_client = AnthropicClient(model="claude-opus-4-5")
        self.model_registry = {
            "context": [GeminiClient(), GLM4Client(), SonnetClient()],
            "engineering": [Qwen3Client(), GLM4Client(), SonnetClient(), OpusClient()],
            "review": [KimiK2Client(), GPT51Client(), OpusClient()]
        }

    def analyze_and_plan(self, issue: str) -> ExecutionPlan:
        """Phase 0: Opus creates strategic plan."""
        analysis_prompt = f"""
        As a senior software architect, analyze this task and create an execution plan:

        TASK: {issue}

        Provide:
        1. Problem classification (complexity, domain, constraints)
        2. Implementation strategy (approach, file structure, key decisions)
        3. Model selection (which models for context/engineering/review and WHY)
        4. Critical constraints (what MUST the implementation follow?)
        5. Success criteria (how to validate the solution?)
        6. Predicted failure modes (what could go wrong?)

        Return as structured JSON.
        """

        response = self.opus_client.chat(analysis_prompt)
        return ExecutionPlan.from_json(response)

    def execute_with_plan(self, plan: ExecutionPlan) -> LoopState:
        """Execute using Opus's strategic plan."""

        # Phase 1: Context (using Opus-selected model)
        context_agent = self._select_agent("context", plan.model_selections["context"])
        state = context_agent.run(state, constraints=plan.constraints)

        # Phase 2: Engineering (using Opus-selected model + constraints)
        engineering_agent = self._select_agent("engineering", plan.model_selections["engineering"])
        state.history.append({
            "role": "opus_constraints",
            "content": plan.constraints_as_prompt()
        })
        state = engineering_agent.run(state, constraints=plan.constraints)

        # Phase 3: Opus Validation
        validation = self.validate_with_opus(state, plan)

        if validation.passed:
            return state
        else:
            return self.adaptive_retry(state, plan, validation)

    def validate_with_opus(self, state: LoopState, plan: ExecutionPlan) -> ValidationResult:
        """Opus reviews solution against strategic plan."""
        validation_prompt = f"""
        Review this implementation against the strategic plan:

        ORIGINAL PLAN:
        {plan.to_markdown()}

        IMPLEMENTATION:
        {state.proposed_fix}

        Check:
        1. Constraint compliance (did it violate any MUST requirements?)
        2. Architectural soundness (is the approach correct?)
        3. Edge case handling (are predicted gotchas addressed?)
        4. Execution prediction (will this likely run successfully?)

        If issues found, provide SPECIFIC diagnostic feedback.
        """

        response = self.opus_client.chat(validation_prompt)
        return ValidationResult.from_json(response)

    def adaptive_retry(self, state: LoopState, plan: ExecutionPlan, validation: ValidationResult) -> LoopState:
        """Opus decides retry strategy based on failure type."""

        if validation.failure_type == "constraint_violation":
            # Emphatic retry with same model
            plan.constraints.emphasis_level += 1
            return self.execute_with_plan(plan)

        elif validation.failure_type == "architectural_error":
            # Switch to more capable model
            plan.model_selections["engineering"] = self._upgrade_model(
                current=plan.model_selections["engineering"]
            )
            return self.execute_with_plan(plan)

        elif validation.failure_type == "edge_case_missing":
            # Provide specific guidance and retry
            state.history.append({
                "role": "opus_guidance",
                "content": validation.specific_fix_guidance
            })
            engineering_agent = self._select_agent("engineering", plan.model_selections["engineering"])
            return engineering_agent.run(state, constraints=plan.constraints)

        else:
            # Unknown failure - Opus takes over directly
            opus_engineering = OpusEngineeringAgent()
            return opus_engineering.run(state, constraints=plan.constraints)
```

---

## Key Advantages

### 1. **Leverages Opus's Strengths**
- Strategic thinking and planning (where it scores 9.0)
- Constraint identification (prevents over-engineering)
- Validation and critique (uses superior reasoning)

### 2. **Avoids Opus's Weaknesses**
- Doesn't use Opus for direct code generation (where it over-engineers)
- Constraints prevent multi-file architectures
- Other models handle "just get it working" coding

### 3. **Cost-Efficient**
- Opus only used for high-value planning and validation
- Cheaper models (Qwen, GLM) do bulk of execution
- Opus only codes directly as last resort

### 4. **Adaptive Intelligence**
- System learns from failures and adjusts strategy
- Can escalate to Opus for difficult problems
- Can de-escalate to faster models for simple tasks

### 5. **Explainable**
- Opus's plan provides clear rationale for decisions
- Validation reports explain why solutions pass/fail
- Retry logic is transparent and justified

---

## Benchmark Prediction

Based on current data:

**Expected Performance:**
- **Code Evaluation:** 8.0-9.0/10 (up from 6.0)
  - Constraints prevent ImportErrors
  - Opus ensures correctness before acceptance

- **LLM Judge:** 8.5-9.0/10 (maintain current 8.5)
  - Opus's planning shows in solution quality

- **Execution Rate:** 8-9/10 (up from 2/10)
  - Explicit constraints prevent over-engineering

- **Cost:** ~$0.30-0.50 per task (vs $1.43 for full Opus)
  - Opus only for planning + validation
  - Cheap models do implementation

**Why This Beats Current Approaches:**
1. **vs ALO-Opus:** Same reasoning quality, 4x better execution
2. **vs ALO-Optimized:** Higher correctness/completeness, similar execution
3. **vs ALO-BestInClass:** Better execution, lower cost

---

## Implementation Priority

### Phase 1: Proof of Concept (2-3 days)
- [ ] Implement `OpusMetaOrchestrator` class
- [ ] Create `ExecutionPlan` dataclass with model selection
- [ ] Test on 3 benchmark prompts (rate_limiter, lru_cache, compiler_parser)

### Phase 2: Full Integration (3-4 days)
- [ ] Integrate with existing `ALOOrchestrator`
- [ ] Add adaptive retry logic
- [ ] Implement constraint generation and validation

### Phase 3: Evaluation (1-2 days)
- [ ] Run full 10-prompt benchmark
- [ ] Compare against existing 5 systems
- [ ] Analyze cost vs quality tradeoffs

---

## Alternative: "Opus + Qwen Dream Team"

Simpler variant focusing on the two extremes:

- **Opus:** Planning, constraints, validation (high-level reasoning)
- **Qwen3-Coder:** Fast, practical implementation (code generation)
- **No context/review loops:** Opus's upfront planning replaces them

This could be 2x faster and even cheaper while maintaining quality.

---

## Recommendation

**Implement the Meta-Orchestrator approach** because:

1. ✅ Uses Opus where it's actually superior (reasoning > coding)
2. ✅ Fixes the over-engineering problem with explicit constraints
3. ✅ Preserves cost-efficiency (Opus only for planning/validation)
4. ✅ Likely to achieve 8-9/10 on BOTH code eval and LLM judge
5. ✅ Creates explainable, adaptive system

The current ALO-Opus scored 8.50 LLM / 6.0 code because it over-engineers.
This design should achieve **8.5 LLM / 8.5 code** by using Opus as an architect, not a coder.
