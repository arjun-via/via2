"""
=============================================================================
SCRIPT NAME: adaptive_validator.py
=============================================================================

Adaptive Validator - Opus validates outputs against plan.

INPUT FILES:
- Proposed solution from engineering agent
- Execution plan from strategic planner

OUTPUT FILES:
- ValidationResult with pass/fail and guidance

VERSION: 1.0
LAST UPDATED: 2025-11-26

DESCRIPTION:
Uses Claude Opus 4.5 to validate solutions against the execution plan,
checking constraint compliance and providing retry guidance on failure.

DEPENDENCIES:
- json (standard library)
- re (standard library)

=============================================================================
"""

import json
import re
from typing import Optional, List, Dict
from dataclasses import dataclass

from .model_registry import get_model
from .multi_provider_client import MultiProviderClient
from .strategic_planner import ExecutionPlan
from .feature_list import Feature

# Import LoopState from core
from alo.agentic_loops.core.state import LoopState


@dataclass
class ValidationResult:
    """Result from validation phase."""
    passed: bool
    constraint_results: Dict[str, bool]  # constraint -> pass/fail
    failure_type: Optional[str] = None  # constraint_violation, architectural_error, etc.
    failure_details: Optional[str] = None
    retry_strategy: Optional[str] = None  # emphatic, upgrade, opus_takeover
    specific_guidance: Optional[str] = None
    cost: float = 0.0


VALIDATION_PROMPT = '''Review this implementation against the strategic plan.

ORIGINAL PLAN:
- Complexity: {complexity}
- Domain: {domain}
- Constraints:
{constraints}
- Success Criteria:
{success_criteria}

IMPLEMENTATION:
{solution}

Evaluate and return JSON:
{{
    "passed": true|false,
    "constraint_results": {{
        "<constraint>": true|false
    }},
    "failure_type": "constraint_violation|architectural_error|edge_case_missing|null",
    "failure_details": "<specific issue or null>",
    "retry_strategy": "emphatic|upgrade|opus_takeover|null",
    "specific_guidance": "<actionable fix guidance or null>"
}}

VALIDATION RULES:
- Any MUST constraint violation = automatic FAIL
- Check for ImportError risks (external dependencies)
- Check for edge cases (empty input, None, type errors)
- Predict if code will execute successfully
'''


FEATURE_VALIDATION_PROMPT = '''Validate this implementation of feature {feature_id}.

===============================================================================
FEATURE REQUIREMENTS
===============================================================================
ID: {feature_id}
Description: {feature_description}
Tests that must pass: {tests}
Constraints: {constraints}

===============================================================================
IMPLEMENTATION
===============================================================================
{code}

===============================================================================
CLEAN STATE INVARIANT
===============================================================================
The code must:
- Have no syntax errors
- Have no TODO/FIXME for this feature
- Have no placeholder implementations (pass, ...)
- Be immediately runnable
- Not break previous features

===============================================================================
OUTPUT (JSON)
===============================================================================
{{
    "passed": true|false,
    "constraint_results": {{"<constraint>": true|false}},
    "failure_type": "constraint_violation|incomplete|regression|syntax_error|null",
    "failure_details": "<specific issue or null>",
    "retry_strategy": "emphatic|upgrade|opus_takeover|null",
    "specific_guidance": "<actionable fix or null>"
}}
'''


class AdaptiveValidator:
    """Uses Opus to validate outputs against execution plan."""

    def __init__(self, client: MultiProviderClient):
        """
        Initialize the adaptive validator.

        Args:
            client: Multi-provider client for API calls
        """
        self.client = client
        self.opus_config = get_model("opus-4.5")

    def validate(self, state: LoopState, plan: ExecutionPlan) -> ValidationResult:
        """
        Validate solution against plan.

        Args:
            state: Current loop state with proposed solution
            plan: Original execution plan

        Returns:
            ValidationResult with pass/fail and guidance
        """
        constraints_str = "\n".join(
            f"  - [{c['level']}] {c['description']}"
            for c in plan.global_constraints
        )
        criteria_str = "\n".join(f"  - {c}" for c in plan.success_criteria)

        # Get solution from state
        solution = getattr(state, 'final_answer', None) or ""

        messages = [
            {"role": "user", "content": VALIDATION_PROMPT.format(
                complexity=plan.complexity,
                domain=plan.domain,
                constraints=constraints_str,
                success_criteria=criteria_str,
                solution=solution[:8000]  # Truncate if needed
            )}
        ]

        result = self.client.complete(
            model_config=self.opus_config,
            messages=messages,
            max_tokens=1000,
            temperature=0
        )

        validation = self._parse_validation(result.content)
        validation.cost = result.cost
        return validation

    def validate_feature(
        self,
        state: LoopState,
        plan: ExecutionPlan,
        feature: Feature,
        code: str
    ) -> ValidationResult:
        """
        Validate a single feature implementation.

        Checks:
        1. Feature requirements met
        2. Clean state invariant maintained
        3. No regressions in previous features

        Args:
            state: Current loop state
            plan: Execution plan
            feature: Feature being validated
            code: Implementation code

        Returns:
            ValidationResult with pass/fail and guidance
        """
        messages = [
            {"role": "user", "content": FEATURE_VALIDATION_PROMPT.format(
                feature_id=feature.id,
                feature_description=feature.description,
                tests=', '.join(feature.tests),
                constraints=', '.join(feature.constraints),
                code=code[:8000]
            )}
        ]

        result = self.client.complete(
            model_config=self.opus_config,
            messages=messages,
            max_tokens=1000,
            temperature=0
        )

        validation = self._parse_validation(result.content)
        validation.cost = result.cost
        return validation

    def quick_validate(self, code: str, constraints: List[str]) -> ValidationResult:
        """
        Quick validation without full plan context.

        Useful for rapid iteration where full Opus validation is expensive.

        Args:
            code: Code to validate
            constraints: List of constraints to check

        Returns:
            ValidationResult
        """
        # Simple heuristic checks (no API call)
        issues = []

        # Check for common issues
        if "import requests" in code or "import redis" in code:
            issues.append("External dependency detected")

        if "TODO" in code or "FIXME" in code:
            issues.append("Incomplete implementation (TODO/FIXME found)")

        if "pass" in code and code.count("pass") > 2:
            issues.append("Multiple placeholder implementations")

        if "raise NotImplementedError" in code:
            issues.append("NotImplementedError present")

        if issues:
            return ValidationResult(
                passed=False,
                constraint_results={issue: False for issue in issues},
                failure_type="constraint_violation",
                failure_details="; ".join(issues),
                retry_strategy="emphatic",
                specific_guidance=f"Fix: {issues[0]}"
            )

        return ValidationResult(
            passed=True,
            constraint_results={c: True for c in constraints}
        )

    def _parse_validation(self, content: str) -> ValidationResult:
        """Parse validation result from Opus response."""
        try:
            # Try direct parse
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return self._default_failed_result("Could not parse validation JSON")
            else:
                return self._default_failed_result("No JSON found in response")

        return ValidationResult(
            passed=data.get("passed", False),
            constraint_results=data.get("constraint_results", {}),
            failure_type=data.get("failure_type"),
            failure_details=data.get("failure_details"),
            retry_strategy=data.get("retry_strategy"),
            specific_guidance=data.get("specific_guidance")
        )

    def _default_failed_result(self, reason: str) -> ValidationResult:
        """Create a default failed validation result."""
        return ValidationResult(
            passed=False,
            constraint_results={},
            failure_type="parse_error",
            failure_details=reason,
            retry_strategy="emphatic"
        )
