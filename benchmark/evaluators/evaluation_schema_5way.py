"""Evaluation scoring schema for 5-way comparisons."""
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
class ComparativeEvaluation5Way:
    """Comparison of 5 solutions."""
    solution_a: SolutionEvaluation  # ALO (original)
    solution_b: SolutionEvaluation  # ALO-Sonnet
    solution_c: SolutionEvaluation  # ALO-Open
    solution_d: SolutionEvaluation  # ALO-Optimized
    solution_e: SolutionEvaluation  # Sonnet+Context
    comparative_analysis: str
    ranking: List[str]  # Ordered list: ["solution_b", "solution_a", ...]
    winner: str  # Best solution ID
    winner_reasoning: str


EVALUATION_DIMENSIONS = [
    "correctness",
    "completeness",
    "code_quality",
    "security",
    "clarity"
]


JUDGE_PROMPT_5WAY = """You are a STRICT, SENIOR-LEVEL software engineering evaluator conducting a code review for production deployment.

You have 20+ years of experience and have seen countless bugs in production. You are SKEPTICAL and look for problems.

**IMPORTANT SCORING CALIBRATION:**
- **1-2/10**: Fundamentally broken, missing core requirements, would crash immediately
- **3-4/10**: Has major flaws that would cause serious production issues (data corruption, security holes, crashes under load)
- **5-6/10**: Decent attempt, works for basic cases, but missing critical edge cases or has maintainability issues
- **7-8/10**: Good solution, handles most real-world cases correctly, minor issues only
- **9-10/10**: Exceptional, production-ready code with comprehensive error handling, security, and edge cases

**DEFAULT ASSUMPTION: Most solutions are 5-6/10. Only exceptional work with production-grade quality earns 9-10.**

---

## Task

Compare **5 solutions** to the following programming challenge:

**Original Prompt:**
{original_prompt}

**Context Summary:**
{context_summary}

---

## Solution A: ALO (Original Mixed Models)
Uses: Gemini context + GLM-4.6 engineering + Kimi-K2 review
{solution_a}

## Solution B: ALO-Sonnet (All Claude Sonnet 4.5)
Uses: Sonnet for all phases with multi-agent orchestration
{solution_b}

## Solution C: ALO-Open (All Open-Source)
Uses: Kimi-K2-Thinking context + Qwen3-Coder engineering + Kimi-K2 review
{solution_c}

## Solution D: ALO-Optimized
Uses: Gemini context + Qwen3-Coder engineering + Kimi-K2-Thinking review
{solution_d}

## Solution E: Sonnet+Context (Baseline)
Uses: Single-call Sonnet with context
{solution_e}

---

## Your Task

Evaluate each solution on 5 dimensions (1-10 scale). Then provide:
1. **Comparative analysis** - How do they differ? Which architectural choices worked?
2. **Ranking** - Order them from best to worst
3. **Winner** - Which solution would you deploy to production?

Return ONLY valid JSON in this exact format:

```json
{{
  "solution_a": {{
    "correctness": {{"score": X, "reasoning": "..."}},
    "completeness": {{"score": X, "reasoning": "..."}},
    "code_quality": {{"score": X, "reasoning": "..."}},
    "security": {{"score": X, "reasoning": "..."}},
    "clarity": {{"score": X, "reasoning": "..."}},
    "overall": X.X,
    "strengths": ["...", "...", "..."],
    "weaknesses": ["...", "..."]
  }},
  "solution_b": {{ ... same structure ... }},
  "solution_c": {{ ... same structure ... }},
  "solution_d": {{ ... same structure ... }},
  "solution_e": {{ ... same structure ... }},
  "comparative_analysis": "Detailed comparison of architectural approaches and quality...",
  "ranking": ["solution_X", "solution_Y", "solution_Z", "solution_W", "solution_V"],
  "winner": "solution_X",
  "winner_reasoning": "Why this solution is best for production..."
}}
```

**Be harsh. Be thorough. Think about edge cases, production failure modes, and maintainability.**
"""
