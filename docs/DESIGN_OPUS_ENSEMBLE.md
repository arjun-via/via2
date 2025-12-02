# Opus Ensemble: A Multi-Opus Design to Beat Single Opus

**Date:** 2025-12-01
**Goal:** Design an orchestrator that outperforms a single Opus call
**Constraint:** Time and cost are NOT important. Quality is everything.

---

## The Core Insight

A single Opus call achieves 100% on our 7-task benchmark. To beat it, we need to:
1. **Catch errors Opus might make** (even Opus makes mistakes on harder tasks)
2. **Provide more context than fits in one call** (multi-pass analysis)
3. **Verify through execution** (ground truth, not LLM judgment)
4. **Use adversarial review** (different model families catch different blind spots)

**Key Realization:** The problem isn't "Opus is too expensive" - it's "how do we make something BETTER than Opus alone?"

---

## Design: The Opus Ensemble

### Philosophy: Multiple Perspectives + Execution Verification

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        OPUS ENSEMBLE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  PHASE 1: PARALLEL GENERATION (3 Premium Models)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   Opus 4.5   │  │   GPT-5.1    │  │ Gemini 3 Pro │                  │
│  │  Solution A  │  │  Solution B  │  │  Solution C  │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                 │                 │                           │
│         └─────────────────┼─────────────────┘                           │
│                           ↓                                              │
│  PHASE 2: EXECUTION FILTER (Ground Truth)                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Execute ALL solutions against test cases                        │   │
│  │  Filter: Keep only solutions that PASS execution                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                           ↓                                              │
│  PHASE 3: ADVERSARIAL REVIEW (Cross-Model Critique)                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Each passing solution reviewed by the OTHER two models          │   │
│  │  Opus reviews GPT's solution                                     │   │
│  │  GPT reviews Gemini's solution                                   │   │
│  │  Gemini reviews Opus's solution                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                           ↓                                              │
│  PHASE 4: OPUS SYNTHESIS (Final Selection/Merge)                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Opus sees all solutions + all critiques                         │   │
│  │  Either: Select best OR Synthesize from multiple                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                           ↓                                              │
│  PHASE 5: FINAL EXECUTION VERIFICATION                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Run final solution against ALL tests                            │   │
│  │  If fails: Return to Phase 4 with error info                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Why This Can Beat Single Opus

### 1. Ensemble Diversity
Different models have different failure modes:
- **Opus** excels at: Nuanced reasoning, complex logic
- **GPT-5.1** excels at: Code patterns, common idioms
- **Gemini 3 Pro** excels at: Large context synthesis, edge cases

By generating from all three, we get **3 independent attempts**. The probability that ALL THREE fail on the same problem is much lower than one failing.

### 2. Execution as Filter
We don't trust ANY model's judgment about correctness. We actually run the code.
- If 2/3 solutions pass execution → we have options
- If 1/3 solutions pass → we use that one
- If 0/3 solutions pass → synthesis with error feedback

### 3. Adversarial Review
Each model reviews solutions from a DIFFERENT model family:
- Opus finds bugs in GPT's code (different training data)
- GPT finds bugs in Gemini's code (different architecture)
- Gemini finds bugs in Opus's code (different reasoning style)

This catches blind spots that same-model review misses.

### 4. Synthesis from Multiple Solutions
Even if all solutions pass, they might handle edge cases differently. Opus can:
- Identify the best parts of each solution
- Synthesize a solution that combines strengths
- Add edge case handling one solution has but others don't

---

## Detailed Design

### Phase 1: Parallel Generation

```python
class ParallelGenerator:
    """Generate solutions from 3 premium models in parallel."""

    def __init__(self, client: MultiProviderClient):
        self.client = client
        self.models = [
            "opus-4.5",      # Anthropic's best
            "gpt-5.1",       # OpenAI's best
            "gemini-3-pro",  # Google's best
        ]

    async def generate_all(self, task: str, context: str) -> List[Solution]:
        """Generate solutions from all models in parallel."""

        prompt = f"""
You are an expert software engineer. Solve this task completely.

TASK:
{task}

CONTEXT:
{context}

REQUIREMENTS:
1. Include ALL necessary imports at the top
2. Handle edge cases (empty input, None, boundary conditions)
3. Write complete, runnable code
4. No placeholders or TODOs

Output ONLY the complete Python code.
"""

        # Run all 3 in parallel
        tasks = [
            self._generate(model, prompt)
            for model in self.models
        ]

        solutions = await asyncio.gather(*tasks)

        return [
            Solution(model=self.models[i], code=sol, passed_execution=None)
            for i, sol in enumerate(solutions)
        ]
```

### Phase 2: Execution Filter

```python
class ExecutionFilter:
    """Filter solutions by actual execution."""

    def __init__(self, executor: CodeExecutor):
        self.executor = executor

    def filter(
        self,
        solutions: List[Solution],
        test_cases: List[TestCase]
    ) -> Tuple[List[Solution], List[Solution]]:
        """
        Run all solutions, return (passing, failing).
        """

        passing = []
        failing = []

        for solution in solutions:
            # Build full test code
            test_code = solution.code + "\n\n"
            for test in test_cases:
                test_code += f"assert {test.call} == {test.expected}, "
                test_code += f"f'Expected {test.expected}, got {{{test.call}}}'\n"
            test_code += "print('ALL TESTS PASSED')"

            # Execute
            result = self.executor.execute(test_code, timeout=30)

            if result.success and "ALL TESTS PASSED" in result.stdout:
                solution.passed_execution = True
                solution.execution_output = result.stdout
                passing.append(solution)
            else:
                solution.passed_execution = False
                solution.execution_error = result.stderr or result.stdout
                failing.append(solution)

        return passing, failing
```

### Phase 3: Adversarial Review

```python
class AdversarialReviewer:
    """Cross-model review - each model reviews another's code."""

    def __init__(self, client: MultiProviderClient):
        self.client = client

        # Each model reviews a DIFFERENT model's solution
        self.review_pairs = {
            "opus-4.5": "gpt-5.1",      # Opus reviews GPT
            "gpt-5.1": "gemini-3-pro",  # GPT reviews Gemini
            "gemini-3-pro": "opus-4.5", # Gemini reviews Opus
        }

    async def review_all(
        self,
        solutions: List[Solution],
        task: str
    ) -> List[SolutionWithReview]:
        """Have each solution reviewed by a different model."""

        results = []

        for solution in solutions:
            # Find which model should review this solution
            reviewer = self.review_pairs[solution.model]

            review = await self._review(
                reviewer_model=reviewer,
                code=solution.code,
                author_model=solution.model,
                task=task
            )

            results.append(SolutionWithReview(
                solution=solution,
                reviewer=reviewer,
                review=review
            ))

        return results

    async def _review(
        self,
        reviewer_model: str,
        code: str,
        author_model: str,
        task: str
    ) -> Review:
        """Get adversarial review from one model of another's code."""

        prompt = f"""
You are reviewing code written by {author_model}. Your job is to find bugs and issues.

TASK THAT WAS GIVEN:
{task}

CODE TO REVIEW (written by {author_model}):
```python
{code}
```

Be CRITICAL. Look for:
1. Logic errors (off-by-one, wrong comparisons, incorrect algorithm)
2. Edge cases not handled (empty input, None, boundary conditions)
3. Missing imports
4. Incorrect output format
5. Subtle bugs that tests might not catch

If you find issues, explain exactly what's wrong and how to fix it.
If the code is correct, say "APPROVED" and explain why it's correct.

Be thorough - trace through the algorithm with test cases.
"""

        response = await self.client.complete(
            get_model(reviewer_model),
            [{"role": "user", "content": prompt}]
        )

        return Review(
            reviewer=reviewer_model,
            content=response.content,
            approved="APPROVED" in response.content.upper(),
            issues=self._extract_issues(response.content)
        )
```

### Phase 4: Opus Synthesis

```python
class OpusSynthesizer:
    """Opus makes final decision, potentially synthesizing from multiple."""

    def __init__(self, client: MultiProviderClient):
        self.client = client

    async def synthesize(
        self,
        task: str,
        solutions_with_reviews: List[SolutionWithReview],
        failing_solutions: List[Solution]
    ) -> FinalSolution:
        """
        Opus sees everything and produces final solution.
        """

        # Build comprehensive context
        context = self._build_synthesis_context(
            task, solutions_with_reviews, failing_solutions
        )

        prompt = f"""
You are the final decision maker. You've seen solutions from multiple models
and reviews from other models. Your job is to produce the BEST possible solution.

{context}

OPTIONS:
1. SELECT: If one solution is clearly best, select it
2. SYNTHESIZE: If you can combine the best parts of multiple solutions
3. REWRITE: If all solutions have issues, write a better one

For your chosen approach, explain your reasoning, then output the final code.

CRITICAL: The code must be complete and runnable. Include all imports.
Do NOT output placeholder code.

Format:
DECISION: [SELECT/SYNTHESIZE/REWRITE]
REASONING: [Your analysis]
FINAL_CODE:
```python
[Complete code here]
```
"""

        response = await self.client.complete(
            get_model("opus-4.5"),
            [{"role": "user", "content": prompt}],
            max_tokens=8000
        )

        return self._parse_final_solution(response.content)

    def _build_synthesis_context(
        self,
        task: str,
        solutions_with_reviews: List[SolutionWithReview],
        failing_solutions: List[Solution]
    ) -> str:
        """Build context showing all solutions and reviews."""

        sections = [f"TASK:\n{task}\n"]

        sections.append("=" * 60)
        sections.append("SOLUTIONS THAT PASSED EXECUTION:")
        sections.append("=" * 60)

        for swr in solutions_with_reviews:
            sections.append(f"\n### Solution from {swr.solution.model}:")
            sections.append(f"```python\n{swr.solution.code}\n```")
            sections.append(f"\n### Review by {swr.reviewer}:")
            sections.append(swr.review.content)
            sections.append("-" * 40)

        if failing_solutions:
            sections.append("\n" + "=" * 60)
            sections.append("SOLUTIONS THAT FAILED EXECUTION (for reference):")
            sections.append("=" * 60)

            for sol in failing_solutions:
                sections.append(f"\n### Failed solution from {sol.model}:")
                sections.append(f"```python\n{sol.code}\n```")
                sections.append(f"Error: {sol.execution_error}")

        return "\n".join(sections)
```

### Phase 5: Final Verification

```python
class FinalVerifier:
    """Verify final solution passes all tests."""

    def __init__(self, executor: CodeExecutor):
        self.executor = executor

    def verify(
        self,
        solution: FinalSolution,
        test_cases: List[TestCase]
    ) -> VerificationResult:
        """
        Run final solution against ALL tests.
        This is the ground truth.
        """

        # Build comprehensive test code
        test_code = solution.code + "\n\n"

        for i, test in enumerate(test_cases):
            test_code += f"# Test {i+1}\n"
            test_code += f"result_{i} = {test.call}\n"
            test_code += f"expected_{i} = {test.expected}\n"
            test_code += f"assert result_{i} == expected_{i}, "
            test_code += f"f'Test {i+1} failed: expected {{expected_{i}}}, got {{result_{i}}}'\n"
            test_code += f"print(f'Test {i+1}: PASS')\n\n"

        test_code += "print('\\n=== ALL TESTS PASSED ===')"

        # Execute
        result = self.executor.execute(test_code, timeout=60)

        if result.success and "ALL TESTS PASSED" in result.stdout:
            return VerificationResult(
                passed=True,
                output=result.stdout,
                solution=solution
            )
        else:
            return VerificationResult(
                passed=False,
                output=result.stdout,
                error=result.stderr,
                solution=solution
            )
```

---

## The Complete Orchestrator

```python
class OpusEnsemble:
    """
    The complete Opus Ensemble orchestrator.
    Goal: Beat single Opus through ensemble + adversarial review + execution.
    """

    def __init__(self, client: MultiProviderClient):
        self.client = client
        self.generator = ParallelGenerator(client)
        self.executor = CodeExecutor(timeout=30)
        self.filter = ExecutionFilter(self.executor)
        self.reviewer = AdversarialReviewer(client)
        self.synthesizer = OpusSynthesizer(client)
        self.verifier = FinalVerifier(self.executor)

        # Retry limits
        self.max_synthesis_attempts = 3

    async def run(self, task: str, test_cases: List[TestCase]) -> EnsembleResult:
        """
        Run the full ensemble pipeline.
        """

        # Phase 1: Generate from 3 premium models in parallel
        print("Phase 1: Generating solutions from Opus, GPT-5.1, Gemini 3 Pro...")
        solutions = await self.generator.generate_all(task, "")
        print(f"  Generated {len(solutions)} solutions")

        # Phase 2: Filter by execution
        print("Phase 2: Filtering by execution...")
        passing, failing = self.filter.filter(solutions, test_cases)
        print(f"  Passing: {len(passing)}, Failing: {len(failing)}")

        # Handle edge case: no solutions pass
        if not passing:
            print("  No solutions passed! Attempting synthesis from failures...")
            return await self._handle_all_failed(task, test_cases, failing)

        # Phase 3: Adversarial review
        print("Phase 3: Adversarial cross-model review...")
        solutions_with_reviews = await self.reviewer.review_all(passing, task)
        for swr in solutions_with_reviews:
            status = "APPROVED" if swr.review.approved else "ISSUES FOUND"
            print(f"  {swr.reviewer} reviewed {swr.solution.model}: {status}")

        # Phase 4: Opus synthesis
        print("Phase 4: Opus synthesis...")
        for attempt in range(self.max_synthesis_attempts):
            final_solution = await self.synthesizer.synthesize(
                task, solutions_with_reviews, failing
            )
            print(f"  Attempt {attempt + 1}: {final_solution.decision}")

            # Phase 5: Final verification
            print("Phase 5: Final verification...")
            verification = self.verifier.verify(final_solution, test_cases)

            if verification.passed:
                print("  VERIFIED: All tests passed!")
                return EnsembleResult(
                    success=True,
                    final_solution=final_solution,
                    all_solutions=solutions,
                    passing_solutions=passing,
                    reviews=solutions_with_reviews,
                    verification=verification
                )
            else:
                print(f"  FAILED: {verification.error}")
                # Add error to context for next attempt
                failing.append(Solution(
                    model="opus-synthesis",
                    code=final_solution.code,
                    passed_execution=False,
                    execution_error=verification.error
                ))

        # All attempts failed
        return EnsembleResult(
            success=False,
            error="All synthesis attempts failed",
            all_solutions=solutions
        )

    async def _handle_all_failed(
        self,
        task: str,
        test_cases: List[TestCase],
        failed_solutions: List[Solution]
    ) -> EnsembleResult:
        """
        Handle case where all initial solutions failed.
        Opus analyzes failures and synthesizes correct solution.
        """

        prompt = f"""
All three models (Opus 4.5, GPT-5.1, Gemini 3 Pro) failed to produce working code.
Analyze their failures and write a CORRECT solution.

TASK:
{task}

FAILED ATTEMPTS:

"""
        for sol in failed_solutions:
            prompt += f"### {sol.model} (FAILED):\n"
            prompt += f"```python\n{sol.code}\n```\n"
            prompt += f"Error: {sol.execution_error}\n\n"

        prompt += """
Analyze WHY each solution failed. Then write a correct solution that:
1. Avoids ALL the mistakes above
2. Includes ALL necessary imports
3. Handles ALL edge cases
4. Passes the test cases

FINAL_CODE:
```python
[Your corrected code]
```
"""

        response = await self.client.complete(
            get_model("opus-4.5"),
            [{"role": "user", "content": prompt}],
            max_tokens=8000
        )

        final_solution = self._parse_code(response.content)
        verification = self.verifier.verify(final_solution, test_cases)

        return EnsembleResult(
            success=verification.passed,
            final_solution=final_solution,
            verification=verification,
            strategy="failure_analysis"
        )
```

---

## Why This Beats Single Opus

### Mathematical Intuition

Let's say single Opus has a 97% success rate (from HumanEval data).

With 3 independent models each at ~95-97%:
- P(at least one succeeds) = 1 - P(all fail)
- P(all fail) = 0.03 × 0.05 × 0.03 = 0.000045 (assuming independence)
- P(at least one succeeds) = 99.995%

Even if they're correlated (similar training data), the ensemble effect still helps.

### Additional Advantages

1. **Adversarial Review Catches Blind Spots**
   - Different model families have different biases
   - GPT might miss something Opus catches, and vice versa

2. **Execution is Ground Truth**
   - We don't trust any model's "LGTM"
   - Code either runs or it doesn't

3. **Synthesis Combines Strengths**
   - Solution A handles edge case X well
   - Solution B handles edge case Y well
   - Final solution handles both

4. **Failure Analysis is Powerful**
   - When models fail, they fail differently
   - Opus can learn from 3 different failure modes

---

## Model Selection Rationale

Since cost is NOT a constraint, we use the **three best models available**:

| Model | Why |
|-------|-----|
| **Opus 4.5** | Best overall reasoning, our conductor |
| **GPT-5.1** | Excellent code generation, different architecture |
| **Gemini 3 Pro** | 1M context, different training data, good at edge cases |

We DON'T use:
- Qwen, Kimi, GLM (lower quality, save them for cost-constrained scenarios)
- Sonnet (good but Opus is better and cost doesn't matter)

---

## Expected Performance

| Metric | Single Opus | Opus Ensemble | Why Better |
|--------|-------------|---------------|------------|
| Pass@1 | 97% | 99%+ | 3 attempts + synthesis |
| Edge Case Coverage | Good | Excellent | 3 models find different cases |
| Import Errors | Occasional | Near Zero | Execution catches all |
| Logic Bugs | Rare | Very Rare | Adversarial review |

---

## Implementation Priority

1. **Phase 1-2** (Parallel Generation + Execution Filter)
   - Core ensemble functionality
   - Already provides major improvement

2. **Phase 3** (Adversarial Review)
   - Adds bug-catching capability
   - Cross-model critique

3. **Phase 4-5** (Synthesis + Verification)
   - Final polish
   - Combines best of all solutions

---

## Testing Plan

1. **Run on 7-task benchmark**
   - Must achieve 100% (baseline Opus achieves 100%)
   - Track which solutions came from which model

2. **Run on HumanEval (164 problems)**
   - Target: >98% (beat single Opus at 97.6%)

3. **Run on harder benchmarks**
   - EvalPlus (80x more tests)
   - SWE-bench Verified

4. **Analyze ensemble dynamics**
   - How often do models agree vs. disagree?
   - Which model's solution gets selected most often?
   - Does synthesis produce better solutions than selection?

---

## Summary

The **Opus Ensemble** design beats single Opus by:

1. **Generating 3 solutions in parallel** from Opus, GPT-5.1, and Gemini 3 Pro
2. **Filtering by actual execution** (ground truth, not LLM judgment)
3. **Adversarial cross-model review** (Opus reviews GPT, GPT reviews Gemini, Gemini reviews Opus)
4. **Opus synthesis** from multiple passing solutions with full context
5. **Final execution verification** before accepting

This is not about saving money - it's about **being more correct than any single model**.

The key insight: **Multiple premium models catching each other's mistakes > One premium model working alone**.
