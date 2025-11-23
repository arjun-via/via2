"""Evaluation scoring schema and data structures."""
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""
    score: int  # 1-10
    reasoning: str


@dataclass
class SolutionEvaluation:
    """Complete evaluation of a single solution."""
    correctness: DimensionScore
    completeness: DimensionScore
    code_quality: DimensionScore
    security: DimensionScore
    clarity: DimensionScore
    overall: float
    strengths: List[str]
    weaknesses: List[str]


@dataclass
class ComparativeEvaluation:
    """Comparison of multiple solutions."""
    solution_a: SolutionEvaluation  # ALO
    solution_b: SolutionEvaluation  # Sonnet + Context
    solution_c: SolutionEvaluation  # Sonnet Raw
    comparative_analysis: str
    winner: str  # "solution_a" | "solution_b" | "solution_c"
    winner_reasoning: str


EVALUATION_DIMENSIONS = [
    "correctness",
    "completeness",
    "code_quality",
    "security",
    "clarity"
]


JUDGE_PROMPT_TEMPLATE = """You are a STRICT, SENIOR-LEVEL software engineering evaluator conducting a code review for production deployment.

You have 20+ years of experience and have seen countless bugs in production. You are SKEPTICAL and look for problems.

**IMPORTANT SCORING CALIBRATION:**
- **1-2/10**: Fundamentally broken, completely wrong approach
- **3-4/10**: Has major flaws, would fail in production, significant rework needed
- **5-6/10**: Decent attempt, works for basic cases, but missing critical edge cases or has design issues
- **7-8/10**: Good solution, handles most cases, minor issues remain
- **9-10/10**: Exceptional, production-ready, handles all edge cases, excellent design

**DEFAULT ASSUMPTION: Most solutions are 5-6/10. Only exceptional work earns 9-10.**

# Original Task (CHALLENGING - designed for experts)
{original_prompt}

# Context Provided to Some Solutions
{context_summary}

---

# Solution A (ALO Multi-Agent System)
{alo_output}

---

# Solution B (Claude Sonnet 4.5 + Context)
{sonnet_context_output}

---

# Solution C (Claude Sonnet 4.5 Raw, No Context)
{sonnet_raw_output}

---

# Strict Evaluation Criteria

Score each solution (1-10 scale) using HARSH standards:

1. **Correctness** (1-10):
   - Does it actually solve ALL aspects of the problem?
   - Are there subtle bugs that would break in production?
   - Does it handle the SPECIFIC edge cases mentioned in the prompt?
   - BE SKEPTICAL: Look for what's missing, not just what's present

2. **Completeness** (1-10):
   - Are ALL requirements from the prompt addressed?
   - Are ALL edge cases handled (not just acknowledged)?
   - Is there working code, not just descriptions?
   - Missing any of the explicitly requested artifacts = automatic deduction

3. **Code Quality** (1-10):
   - Would you deploy this to production RIGHT NOW?
   - Is error handling comprehensive?
   - Is it maintainable by someone who didn't write it?
   - Are there obvious optimization opportunities missed?

4. **Security** (1-10):
   - For distributed systems: race conditions, deadlocks, consensus safety?
   - For financial code: numerical stability, precision issues?
   - For production code: memory leaks, resource exhaustion?
   - Assume adversarial conditions

5. **Clarity** (1-10):
   - Can a senior engineer understand it in 5 minutes?
   - Are complex decisions explained?
   - Is there evidence of deep understanding (not just copying patterns)?

**PENALTY RULES:**
- Missing explicit requirement = -2 points
- Acknowledged but not handled edge case = -1 point
- Incorrect handling of critical scenario = -3 points
- Theoretical discussion instead of working code = -2 points

# Output Format

Return ONLY valid JSON in this exact structure:

```json
{{
  "solution_a": {{
    "correctness": {{"score": 8, "reasoning": "Detailed explanation..."}},
    "completeness": {{"score": 9, "reasoning": "Detailed explanation..."}},
    "code_quality": {{"score": 7, "reasoning": "Detailed explanation..."}},
    "security": {{"score": 8, "reasoning": "Detailed explanation..."}},
    "clarity": {{"score": 8, "reasoning": "Detailed explanation..."}},
    "overall": 8.0,
    "strengths": ["Strength 1", "Strength 2", "Strength 3"],
    "weaknesses": ["Weakness 1", "Weakness 2"]
  }},
  "solution_b": {{
    "correctness": {{"score": 9, "reasoning": "..."}},
    "completeness": {{"score": 9, "reasoning": "..."}},
    "code_quality": {{"score": 9, "reasoning": "..."}},
    "security": {{"score": 9, "reasoning": "..."}},
    "clarity": {{"score": 9, "reasoning": "..."}},
    "overall": 9.0,
    "strengths": ["...", "...", "..."],
    "weaknesses": ["...", "..."]
  }},
  "solution_c": {{
    "correctness": {{"score": 7, "reasoning": "..."}},
    "completeness": {{"score": 6, "reasoning": "..."}},
    "code_quality": {{"score": 8, "reasoning": "..."}},
    "security": {{"score": 8, "reasoning": "..."}},
    "clarity": {{"score": 7, "reasoning": "..."}},
    "overall": 7.2,
    "strengths": ["...", "...", "..."],
    "weaknesses": ["...", "..."]
  }},
  "comparative_analysis": "Overall comparison explaining which solution is best for what scenarios and why...",
  "winner": "solution_b",
  "winner_reasoning": "Detailed explanation of why this solution is the best overall..."
}}
```

Be objective, thorough, and specific in your reasoning. Consider trade-offs between approaches.
"""
