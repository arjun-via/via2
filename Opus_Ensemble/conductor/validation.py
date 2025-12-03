"""
=============================================================================
SCRIPT NAME: validation.py
=============================================================================

Opus-Conductor Validation Framework

Multi-layer validation system that catches issues at different levels:
1. Static Analysis - syntax, imports, basic structure
2. Semantic Validation - Opus reviews for requirement compliance
3. Execution Validation - actual code execution in sandbox

Key Classes:
- ValidationResult: Standard result format for all validators
- StaticAnalyzer: Syntax and import checking
- SemanticValidator: Opus-powered semantic review
- ExecutionValidator: Sandbox code execution

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import ast
import re
import time
import logging
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from pathlib import Path

from .state import ConductorState, ValidationCheckpoint, StageStatus


class ValidationDecision(Enum):
    """Validation decision types."""
    APPROVED = "APPROVED"
    RETRY = "RETRY"
    ESCALATE = "ESCALATE"


class IssueType(Enum):
    """Types of issues that can be found during validation."""
    SYNTAX_ERROR = "syntax_error"
    MISSING_IMPORT = "missing_import"
    MISSING_EDGE_CASE = "missing_edge_case"
    CONSTRAINT_VIOLATION = "constraint_violation"
    SUCCESS_CRITERIA_UNMET = "success_criteria_unmet"
    TEST_FAILURE = "test_failure"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"
    QUALITY_ISSUE = "quality_issue"


@dataclass
class ValidationIssue:
    """A single validation issue found."""
    issue_type: IssueType
    message: str
    severity: str = "error"  # "error", "warning", "info"
    line_number: Optional[int] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.issue_type.value,
            "message": self.message,
            "severity": self.severity,
            "line_number": self.line_number,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    """Result of a validation check."""
    passed: bool
    decision: ValidationDecision
    issues: List[ValidationIssue] = field(default_factory=list)
    reasoning: str = ""
    guidance: str = ""
    execution_output: str = ""
    duration: float = 0.0

    def to_checkpoint(self, stage: str, retry_count: int = 0) -> ValidationCheckpoint:
        """Convert to a ValidationCheckpoint for state tracking."""
        return ValidationCheckpoint(
            stage=stage,
            timestamp=time.time(),
            decision=self.decision.value,
            reasoning=self.reasoning,
            issues=[issue.message for issue in self.issues],
            guidance=self.guidance if not self.passed else None,
            retry_count=retry_count,
        )

    @property
    def error_messages(self) -> List[str]:
        """Get all error messages."""
        return [i.message for i in self.issues if i.severity == "error"]

    @property
    def warning_messages(self) -> List[str]:
        """Get all warning messages."""
        return [i.message for i in self.issues if i.severity == "warning"]


class BaseValidator(ABC):
    """Abstract base class for validators."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    @abstractmethod
    def validate(self, state: ConductorState) -> ValidationResult:
        """Perform validation and return result."""
        pass


class StaticAnalyzer(BaseValidator):
    """
    Static analysis validator for Python code.

    Checks:
    - Syntax validity (AST parsing)
    - Import completeness
    - Basic structure requirements
    """

    def __init__(
        self,
        check_syntax: bool = True,
        check_imports: bool = True,
        check_edge_cases: bool = True,
        max_line_length: int = 120,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(logger)
        self.check_syntax = check_syntax
        self.check_imports = check_imports
        self.check_edge_cases = check_edge_cases
        self.max_line_length = max_line_length

    def validate(self, state: ConductorState) -> ValidationResult:
        """Run static analysis on the implementation code."""
        start_time = time.time()
        issues = []
        code = state.implementation_code

        if not code.strip():
            return ValidationResult(
                passed=False,
                decision=ValidationDecision.RETRY,
                issues=[ValidationIssue(
                    issue_type=IssueType.SYNTAX_ERROR,
                    message="No implementation code provided",
                    severity="error"
                )],
                reasoning="No code to validate",
                guidance="Provide an implementation",
                duration=time.time() - start_time,
            )

        # Check syntax
        if self.check_syntax:
            syntax_issues = self._check_syntax(code)
            issues.extend(syntax_issues)

        # Check imports
        if self.check_imports and state.required_imports:
            import_issues = self._check_imports(code, state.required_imports)
            issues.extend(import_issues)

            # Update state with found imports
            state.imports_included = self._extract_imports(code)

        # Check edge case mentions (heuristic)
        if self.check_edge_cases and state.edge_cases:
            edge_case_issues = self._check_edge_case_handling(code, state.edge_cases, state)
            issues.extend(edge_case_issues)

        # Check line length
        line_issues = self._check_line_lengths(code)
        issues.extend(line_issues)

        # Determine decision
        errors = [i for i in issues if i.severity == "error"]
        passed = len(errors) == 0

        if passed:
            decision = ValidationDecision.APPROVED
            reasoning = "Static analysis passed: syntax valid, all imports present"
            guidance = ""
        else:
            decision = ValidationDecision.RETRY
            reasoning = f"Static analysis found {len(errors)} error(s)"
            guidance = self._generate_guidance(errors)

        return ValidationResult(
            passed=passed,
            decision=decision,
            issues=issues,
            reasoning=reasoning,
            guidance=guidance,
            duration=time.time() - start_time,
        )

    def _check_syntax(self, code: str) -> List[ValidationIssue]:
        """Check Python syntax validity."""
        issues = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(ValidationIssue(
                issue_type=IssueType.SYNTAX_ERROR,
                message=f"Syntax error: {e.msg}",
                severity="error",
                line_number=e.lineno,
                suggestion=f"Fix syntax at line {e.lineno}: {e.text.strip() if e.text else 'unknown'}"
            ))
        return issues

    def _check_imports(self, code: str, required_imports: List[str]) -> List[ValidationIssue]:
        """Check if all required imports are present."""
        issues = []
        code_lower = code.lower()

        for req_import in required_imports:
            # Skip optional imports (marked with "optional" or in parentheses suggesting optional)
            if "optional" in req_import.lower() or "(optional" in req_import.lower():
                continue

            # Extract just the module name (handle cases like "module (for something)")
            module_name = req_import.split()[0].split('(')[0].strip()
            module_lower = module_name.lower()

            # Check various import patterns
            patterns = [
                f"import {module_lower}",
                f"from {module_lower}",
                f"import {module_lower} as",
            ]
            found = any(p in code_lower for p in patterns)

            if not found:
                # Make this a warning, not an error - let semantic validation decide
                issues.append(ValidationIssue(
                    issue_type=IssueType.MISSING_IMPORT,
                    message=f"Potentially missing import: {module_name}",
                    severity="warning",  # Changed from error to warning
                    suggestion=f"Consider adding 'import {module_name}' if needed"
                ))

        return issues

    def _extract_imports(self, code: str) -> List[str]:
        """Extract all import statements from code."""
        imports = []
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(f"import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    imports.append(f"from {module} import ...")
        except SyntaxError:
            # Fall back to regex if AST fails
            import_pattern = r'^(?:from\s+\S+\s+)?import\s+.+$'
            imports = re.findall(import_pattern, code, re.MULTILINE)
        return imports

    def _check_edge_case_handling(
        self,
        code: str,
        edge_cases: List[str],
        state: ConductorState
    ) -> List[ValidationIssue]:
        """Heuristically check if edge cases are handled."""
        issues = []
        code_lower = code.lower()

        for edge_case in edge_cases:
            # Check if already marked as handled
            if state.edge_cases_handled.get(edge_case, False):
                continue

            # Simple heuristic: check if edge case keywords appear
            keywords = edge_case.lower().split()
            found = any(kw in code_lower for kw in keywords if len(kw) > 3)

            if found:
                state.edge_cases_handled[edge_case] = True
            else:
                issues.append(ValidationIssue(
                    issue_type=IssueType.MISSING_EDGE_CASE,
                    message=f"Edge case may not be handled: {edge_case}",
                    severity="warning",  # Warning, not error - heuristic
                    suggestion=f"Ensure code handles: {edge_case}"
                ))

        return issues

    def _check_line_lengths(self, code: str) -> List[ValidationIssue]:
        """Check for overly long lines."""
        issues = []
        for i, line in enumerate(code.split('\n'), 1):
            if len(line) > self.max_line_length:
                issues.append(ValidationIssue(
                    issue_type=IssueType.QUALITY_ISSUE,
                    message=f"Line {i} exceeds {self.max_line_length} characters ({len(line)})",
                    severity="warning",
                    line_number=i,
                ))
        return issues

    def _generate_guidance(self, errors: List[ValidationIssue]) -> str:
        """Generate guidance text from errors."""
        guidance_parts = []
        for error in errors:
            if error.suggestion:
                guidance_parts.append(error.suggestion)
            else:
                guidance_parts.append(f"Fix: {error.message}")
        return "\n".join(guidance_parts)


class SemanticValidator(BaseValidator):
    """
    Semantic validator using Opus to review code against requirements.

    This is the key differentiator - Opus stays in the loop and validates
    that the implementation actually meets the stated requirements.
    """

    def __init__(
        self,
        model_client,  # ResilientModelClient
        require_acknowledgment: bool = True,
        verify_constraints: bool = True,
        verify_success_criteria: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(logger)
        self.model_client = model_client
        self.require_acknowledgment = require_acknowledgment
        self.verify_constraints = verify_constraints
        self.verify_success_criteria = verify_success_criteria

    def validate(self, state: ConductorState) -> ValidationResult:
        """Use Opus to semantically validate the implementation."""
        start_time = time.time()

        # Build the validation prompt
        prompt = self._build_validation_prompt(state)

        # Call Opus for validation
        messages = [{"role": "user", "content": prompt}]
        system = self._get_system_prompt()

        try:
            response = self.model_client.complete(messages, system=system)
            result = self._parse_validation_response(response.content, state)
            result.duration = time.time() - start_time

            # Log the model call in state
            state.log_model_call(
                stage="semantic_validation",
                model_id=response.model_id,
                input_text=prompt,
                output_text=response.content,
                cost=response.cost,
                tokens=response.total_tokens,
                duration=response.duration,
            )

            return result

        except Exception as e:
            self.logger.error(f"Semantic validation failed: {e}")
            return ValidationResult(
                passed=False,
                decision=ValidationDecision.RETRY,
                issues=[ValidationIssue(
                    issue_type=IssueType.RUNTIME_ERROR,
                    message=f"Semantic validation error: {str(e)}",
                    severity="error"
                )],
                reasoning=f"Validation call failed: {e}",
                duration=time.time() - start_time,
            )

    def _get_system_prompt(self) -> str:
        """Get system prompt for Opus validation."""
        return """You are Opus, the supervisor agent in a multi-agent code generation system.
Your role is to validate that code implementations meet all specified requirements.

You must output your decision in the following JSON format:
{
    "decision": "APPROVED" | "RETRY" | "ESCALATE",
    "reasoning": "Detailed explanation of your decision",
    "issues": [
        {"type": "constraint_violation", "message": "Description of issue"},
        ...
    ],
    "guidance": "Specific instructions for fixing issues (if RETRY)"
}

Decision guidelines:
- APPROVED: All requirements met, code is correct
- RETRY: Issues found but fixable by the same agent
- ESCALATE: Fundamental problems requiring re-planning

Be thorough but fair. Only flag real issues."""

    def _build_validation_prompt(self, state: ConductorState) -> str:
        """Build the validation prompt from state."""
        parts = [
            "## VALIDATION REQUEST",
            "",
            "### Original Task",
            state.original_task,
            "",
            "### Constraints",
        ]

        for i, constraint in enumerate(state.constraints, 1):
            parts.append(f"{i}. {constraint}")

        parts.extend([
            "",
            "### Success Criteria",
        ])

        for i, criterion in enumerate(state.success_criteria, 1):
            parts.append(f"{i}. {criterion}")

        parts.extend([
            "",
            "### Edge Cases to Handle",
        ])

        for edge_case in state.edge_cases:
            handled = state.edge_cases_handled.get(edge_case, False)
            status = "[HANDLED]" if handled else "[NOT HANDLED]"
            parts.append(f"- {status} {edge_case}")

        parts.extend([
            "",
            "### Implementation Code",
            "```python",
            state.implementation_code,
            "```",
            "",
            "### Agent's Acknowledgment",
            state.engineering_acknowledgment or "(No acknowledgment provided)",
            "",
            "Please validate this implementation against all requirements.",
        ])

        return "\n".join(parts)

    def _parse_validation_response(self, response: str, state: ConductorState) -> ValidationResult:
        """Parse Opus's validation response."""
        import json

        # Try to extract JSON from response
        try:
            # Look for JSON block
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")

            decision_str = data.get("decision", "RETRY").upper()
            decision = ValidationDecision[decision_str]

            issues = []
            for issue_data in data.get("issues", []):
                issue_type_str = issue_data.get("type", "quality_issue")
                try:
                    issue_type = IssueType(issue_type_str)
                except ValueError:
                    issue_type = IssueType.QUALITY_ISSUE

                issues.append(ValidationIssue(
                    issue_type=issue_type,
                    message=issue_data.get("message", "Unknown issue"),
                    severity="error" if decision != ValidationDecision.APPROVED else "warning"
                ))

            return ValidationResult(
                passed=decision == ValidationDecision.APPROVED,
                decision=decision,
                issues=issues,
                reasoning=data.get("reasoning", ""),
                guidance=data.get("guidance", ""),
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            self.logger.warning(f"Failed to parse validation response: {e}")

            # Fall back to heuristic parsing
            response_upper = response.upper()
            if "APPROVED" in response_upper:
                return ValidationResult(
                    passed=True,
                    decision=ValidationDecision.APPROVED,
                    reasoning=response[:500],
                )
            elif "ESCALATE" in response_upper:
                return ValidationResult(
                    passed=False,
                    decision=ValidationDecision.ESCALATE,
                    reasoning=response[:500],
                    issues=[ValidationIssue(
                        issue_type=IssueType.QUALITY_ISSUE,
                        message="Escalation requested by Opus",
                        severity="error"
                    )],
                )
            else:
                return ValidationResult(
                    passed=False,
                    decision=ValidationDecision.RETRY,
                    reasoning=response[:500],
                    issues=[ValidationIssue(
                        issue_type=IssueType.QUALITY_ISSUE,
                        message="Validation issues found",
                        severity="error"
                    )],
                    guidance=response[:500],
                )


class ExecutionValidator(BaseValidator):
    """
    Execution validator that runs code in a sandbox.

    Supports:
    - Local subprocess execution
    - Docker container execution (for SWE-bench)
    """

    def __init__(
        self,
        timeout: int = 60,
        sandbox_enabled: bool = True,
        docker_image: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(logger)
        self.timeout = timeout
        self.sandbox_enabled = sandbox_enabled
        self.docker_image = docker_image

    def validate(self, state: ConductorState) -> ValidationResult:
        """Execute the code and check for errors."""
        start_time = time.time()

        if not state.implementation_code.strip():
            return ValidationResult(
                passed=False,
                decision=ValidationDecision.RETRY,
                issues=[ValidationIssue(
                    issue_type=IssueType.SYNTAX_ERROR,
                    message="No code to execute",
                    severity="error"
                )],
                duration=time.time() - start_time,
            )

        try:
            if self.docker_image:
                output, success = self._execute_in_docker(state)
            else:
                output, success = self._execute_local(state)

            state.execution_output = output

            if success:
                return ValidationResult(
                    passed=True,
                    decision=ValidationDecision.APPROVED,
                    reasoning="Code executed successfully",
                    execution_output=output,
                    duration=time.time() - start_time,
                )
            else:
                # Parse errors from output
                issues = self._parse_execution_errors(output)
                return ValidationResult(
                    passed=False,
                    decision=ValidationDecision.RETRY,
                    issues=issues,
                    reasoning="Code execution failed",
                    guidance=f"Fix execution errors:\n{output[:1000]}",
                    execution_output=output,
                    duration=time.time() - start_time,
                )

        except subprocess.TimeoutExpired:
            return ValidationResult(
                passed=False,
                decision=ValidationDecision.RETRY,
                issues=[ValidationIssue(
                    issue_type=IssueType.TIMEOUT,
                    message=f"Execution timed out after {self.timeout}s",
                    severity="error"
                )],
                reasoning=f"Code execution timed out after {self.timeout} seconds",
                guidance="Optimize code to complete faster or check for infinite loops",
                duration=time.time() - start_time,
            )

        except Exception as e:
            return ValidationResult(
                passed=False,
                decision=ValidationDecision.RETRY,
                issues=[ValidationIssue(
                    issue_type=IssueType.RUNTIME_ERROR,
                    message=str(e),
                    severity="error"
                )],
                reasoning=f"Execution error: {e}",
                duration=time.time() - start_time,
            )

    def _execute_local(self, state: ConductorState) -> Tuple[str, bool]:
        """Execute code locally in a subprocess."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(state.implementation_code)
            temp_path = f.name

        try:
            result = subprocess.run(
                ['python', temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=state.repo_path if state.repo_path else None,
            )

            output = result.stdout + result.stderr
            success = result.returncode == 0
            return output, success

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def _execute_in_docker(self, state: ConductorState) -> Tuple[str, bool]:
        """Execute code in a Docker container."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(state.implementation_code)
            temp_path = f.name

        try:
            cmd = [
                'docker', 'run', '--rm',
                '-v', f'{temp_path}:/code/script.py:ro',
                '--network', 'none',  # No network access
                '--memory', '512m',   # Memory limit
                '--cpus', '1',        # CPU limit
                self.docker_image,
                'python', '/code/script.py'
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            output = result.stdout + result.stderr
            success = result.returncode == 0
            return output, success

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def _parse_execution_errors(self, output: str) -> List[ValidationIssue]:
        """Parse execution output for specific errors."""
        issues = []

        # Check for common error patterns
        if "SyntaxError" in output:
            issues.append(ValidationIssue(
                issue_type=IssueType.SYNTAX_ERROR,
                message="Syntax error during execution",
                severity="error"
            ))

        if "ImportError" in output or "ModuleNotFoundError" in output:
            issues.append(ValidationIssue(
                issue_type=IssueType.MISSING_IMPORT,
                message="Import error during execution",
                severity="error"
            ))

        if "AssertionError" in output:
            issues.append(ValidationIssue(
                issue_type=IssueType.TEST_FAILURE,
                message="Assertion failed during execution",
                severity="error"
            ))

        if "FAILED" in output or "ERRORS" in output:
            issues.append(ValidationIssue(
                issue_type=IssueType.TEST_FAILURE,
                message="Tests failed during execution",
                severity="error"
            ))

        # Generic error if nothing specific found
        if not issues and ("Error" in output or "Exception" in output):
            issues.append(ValidationIssue(
                issue_type=IssueType.RUNTIME_ERROR,
                message="Runtime error during execution",
                severity="error"
            ))

        return issues


class CompositeValidator(BaseValidator):
    """
    Composite validator that runs multiple validators in sequence.

    Stops on first failure if stop_on_failure is True.
    """

    def __init__(
        self,
        validators: List[BaseValidator],
        stop_on_failure: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(logger)
        self.validators = validators
        self.stop_on_failure = stop_on_failure

    def validate(self, state: ConductorState) -> ValidationResult:
        """Run all validators in sequence."""
        start_time = time.time()
        all_issues = []
        all_passed = True

        for validator in self.validators:
            result = validator.validate(state)
            all_issues.extend(result.issues)

            if not result.passed:
                all_passed = False
                if self.stop_on_failure:
                    return ValidationResult(
                        passed=False,
                        decision=result.decision,
                        issues=all_issues,
                        reasoning=result.reasoning,
                        guidance=result.guidance,
                        execution_output=result.execution_output,
                        duration=time.time() - start_time,
                    )

        # All passed (or collected all issues)
        decision = ValidationDecision.APPROVED if all_passed else ValidationDecision.RETRY
        return ValidationResult(
            passed=all_passed,
            decision=decision,
            issues=all_issues,
            reasoning="All validations passed" if all_passed else "Some validations failed",
            duration=time.time() - start_time,
        )
