"""
=============================================================================
SCRIPT NAME: handoff.py
=============================================================================

Opus-Conductor Stage Handoff Protocol

This module defines the structured handoff protocol between stages.
Each stage receives explicit requirements and must acknowledge them
before proceeding. This prevents information loss between stages.

Key Classes:
- StageHandoff: Data structure for handoffs between stages
- HandoffProtocol: Manages the handoff process
- Stage Agents: Context, Engineering, Review agents

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import time
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum

from .state import ConductorState, StageStatus, ValidationCheckpoint, AuditEvent
from .validation import ValidationResult, ValidationDecision


@dataclass
class StageHandoff:
    """
    Data structure for handoffs between stages.

    Contains all information the receiving stage needs to do its job,
    plus explicit requirements it must acknowledge.
    """
    source_stage: str
    target_stage: str
    timestamp: float = field(default_factory=time.time)

    # Requirements to acknowledge
    constraints: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    required_imports: List[str] = field(default_factory=list)
    edge_cases: List[str] = field(default_factory=list)

    # Context from previous stages
    context_summary: str = ""
    relevant_files: List[str] = field(default_factory=list)
    file_contents: Dict[str, str] = field(default_factory=dict)

    # Previous stage output (for iterations)
    previous_output: str = ""
    validation_feedback: str = ""

    # Retry information
    retry_count: int = 0
    retry_guidance: str = ""

    def build_prompt_section(self) -> str:
        """Build the requirements section for agent prompts."""
        parts = [
            "## HANDOFF FROM " + self.source_stage.upper(),
            "",
            "### Requirements to Acknowledge",
            "",
            "**Constraints:**",
        ]

        for i, constraint in enumerate(self.constraints, 1):
            parts.append(f"{i}. {constraint}")

        parts.extend([
            "",
            "**Success Criteria:**",
        ])

        for i, criterion in enumerate(self.success_criteria, 1):
            parts.append(f"{i}. {criterion}")

        if self.required_imports:
            parts.extend([
                "",
                "**Required Imports:**",
            ])
            for imp in self.required_imports:
                parts.append(f"- {imp}")

        if self.edge_cases:
            parts.extend([
                "",
                "**Edge Cases to Handle:**",
            ])
            for edge in self.edge_cases:
                parts.append(f"- {edge}")

        if self.retry_count > 0:
            parts.extend([
                "",
                f"### RETRY #{self.retry_count}",
                "",
                "**Previous Issues:**",
                self.validation_feedback,
                "",
                "**Guidance:**",
                self.retry_guidance,
            ])

        parts.extend([
            "",
            "### ACKNOWLEDGMENT REQUIRED",
            "",
            "Before proceeding, you MUST explicitly acknowledge these requirements.",
            "Start your response with:",
            "",
            '```',
            'ACKNOWLEDGMENT:',
            'I acknowledge the following requirements:',
            '- Constraints: [list them]',
            '- Success criteria: [list them]',
            '- Edge cases: [list them]',
            '```',
        ])

        return "\n".join(parts)

    @classmethod
    def from_state(
        cls,
        state: ConductorState,
        source_stage: str,
        target_stage: str,
        validation_result: Optional[ValidationResult] = None,
    ) -> "StageHandoff":
        """Create a handoff from current state."""
        handoff = cls(
            source_stage=source_stage,
            target_stage=target_stage,
            constraints=state.constraints.copy(),
            success_criteria=state.success_criteria.copy(),
            required_imports=state.required_imports.copy(),
            edge_cases=state.edge_cases.copy(),
            context_summary=state.context_summary,
            relevant_files=state.relevant_files.copy(),
            file_contents=state.file_contents.copy(),
            retry_count=state.get_stage_retry_count(target_stage),
        )

        if validation_result and not validation_result.passed:
            handoff.validation_feedback = validation_result.reasoning
            handoff.retry_guidance = validation_result.guidance
            handoff.previous_output = state.implementation_code

        return handoff


class BaseStageAgent(ABC):
    """Abstract base class for stage agents."""

    def __init__(
        self,
        model_client,  # ResilientModelClient
        logger: Optional[logging.Logger] = None,
    ):
        self.model_client = model_client
        self.logger = logger or logging.getLogger(__name__)

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Return the stage name."""
        pass

    @abstractmethod
    def run(self, state: ConductorState, handoff: StageHandoff) -> ConductorState:
        """Execute the stage and return updated state."""
        pass

    def _log(self, message: str) -> None:
        """Log a message with stage prefix."""
        self.logger.info(f"[{self.stage_name.upper()}] {message}")

    def _extract_acknowledgment(self, response: str) -> Optional[str]:
        """Extract acknowledgment section from response."""
        # Look for ACKNOWLEDGMENT section
        ack_match = re.search(
            r'ACKNOWLEDGMENT:?\s*(.*?)(?=```|$)',
            response,
            re.IGNORECASE | re.DOTALL
        )
        if ack_match:
            return ack_match.group(1).strip()
        return None

    def _verify_acknowledgment(
        self,
        acknowledgment: str,
        handoff: StageHandoff
    ) -> bool:
        """Verify that acknowledgment covers all requirements."""
        if not acknowledgment:
            return False

        ack_lower = acknowledgment.lower()

        # Check constraints mentioned
        for constraint in handoff.constraints[:3]:  # Check first 3
            keywords = [w for w in constraint.lower().split() if len(w) > 4]
            if not any(kw in ack_lower for kw in keywords[:2]):
                return False

        return True


class ContextAgent(BaseStageAgent):
    """
    Context analysis agent.

    Responsibilities:
    - Analyze the repository structure
    - Identify relevant files
    - Summarize the codebase context
    """

    @property
    def stage_name(self) -> str:
        return "context"

    def run(self, state: ConductorState, handoff: StageHandoff) -> ConductorState:
        """Analyze repository and identify relevant files."""
        self._log("Starting context analysis")
        state.context_status = StageStatus.IN_PROGRESS

        # Build prompt
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_prompt(state, handoff)

        messages = [{"role": "user", "content": user_prompt}]

        # Call model
        start_time = time.time()
        response = self.model_client.complete(messages, system=system_prompt)

        # Log the call
        state.log_model_call(
            stage=self.stage_name,
            model_id=response.model_id,
            input_text=user_prompt,
            output_text=response.content,
            cost=response.cost,
            tokens=response.total_tokens,
            duration=response.duration,
        )

        # Parse response
        self._parse_response(response.content, state)

        self._log(f"Found {len(state.relevant_files)} relevant files")
        return state

    def _get_system_prompt(self) -> str:
        return """You are a context analysis agent in the Opus-Conductor system.
Your job is to analyze the task and identify relevant files in the repository.

Output your analysis in the following format:

```
ACKNOWLEDGMENT:
I acknowledge the following requirements:
- [List key constraints and criteria]

RELEVANT_FILES:
- file1.py: Brief description of relevance
- file2.py: Brief description of relevance

CONTEXT_SUMMARY:
[2-3 paragraph summary of how these files relate to the task]

KEY_PATTERNS:
- Pattern 1: Description
- Pattern 2: Description
```

Be thorough but focused. Only include truly relevant files."""

    def _build_prompt(self, state: ConductorState, handoff: StageHandoff) -> str:
        parts = [
            "## TASK",
            state.original_task,
            "",
            handoff.build_prompt_section(),
        ]

        if state.repo_path:
            parts.extend([
                "",
                "## REPOSITORY",
                f"Path: {state.repo_path}",
            ])

        return "\n".join(parts)

    def _parse_response(self, response: str, state: ConductorState) -> None:
        """Parse context analysis response."""
        # Extract acknowledgment
        ack = self._extract_acknowledgment(response)
        if ack:
            state.engineering_acknowledgment = ack  # Reuse field for context ack

        # Extract relevant files
        files_match = re.search(
            r'RELEVANT_FILES:\s*(.*?)(?=CONTEXT_SUMMARY|KEY_PATTERNS|$)',
            response,
            re.IGNORECASE | re.DOTALL
        )
        if files_match:
            files_text = files_match.group(1)
            # Parse file lines
            for line in files_text.strip().split('\n'):
                line = line.strip()
                if line.startswith('-'):
                    file_part = line[1:].strip().split(':')[0].strip()
                    if file_part:
                        state.relevant_files.append(file_part)

        # Extract context summary
        summary_match = re.search(
            r'CONTEXT_SUMMARY:\s*(.*?)(?=KEY_PATTERNS|$)',
            response,
            re.IGNORECASE | re.DOTALL
        )
        if summary_match:
            state.context_summary = summary_match.group(1).strip()


class EngineeringAgent(BaseStageAgent):
    """
    Engineering agent for code implementation.

    Responsibilities:
    - Generate code that satisfies all requirements
    - Handle all identified edge cases
    - Include all required imports
    """

    @property
    def stage_name(self) -> str:
        return "engineering"

    def run(self, state: ConductorState, handoff: StageHandoff) -> ConductorState:
        """Generate implementation code."""
        self._log("Starting code generation")
        state.engineering_status = StageStatus.IN_PROGRESS

        # Build prompt
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_prompt(state, handoff)

        messages = [{"role": "user", "content": user_prompt}]

        # Call model
        response = self.model_client.complete(messages, system=system_prompt)

        # Log the call
        state.log_model_call(
            stage=self.stage_name,
            model_id=response.model_id,
            input_text=user_prompt,
            output_text=response.content,
            cost=response.cost,
            tokens=response.total_tokens,
            duration=response.duration,
        )

        # Parse response
        self._parse_response(response.content, state, handoff)

        self._log(f"Generated {len(state.implementation_code)} chars of code")
        return state

    def _get_system_prompt(self) -> str:
        return """You are an expert software engineering agent in the Opus-Conductor system.
Your job is to generate a PATCH that satisfies ALL specified requirements.

CRITICAL RULES:
1. You MUST output a unified diff patch (not raw code)
2. You MUST handle ALL identified edge cases
3. The patch must apply cleanly to the codebase
4. Include minimal changes - only what's needed to fix the issue

Output format:

```
ACKNOWLEDGMENT:
I acknowledge the following requirements:
- Constraints: [list all]
- Success criteria: [list all]
- Edge cases I will handle: [list all]
```

```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -line,count +line,count @@
 context line
-removed line
+added line
 context line
```

CRITICAL PATCH FORMATTING:
- Start with: --- a/path/to/file.py
- Then: +++ b/path/to/file.py
- Hunk header: @@ -START,COUNT +START,COUNT @@ optional context
  - COUNT = total lines in that section (context + removed OR context + added)
  - Example: @@ -10,7 +10,9 @@ means old has 7 lines, new has 9 lines
- Context lines: start with SINGLE SPACE, then the unchanged line content
- Removed lines: start with - then the line content
- Added lines: start with + then the line content
- COUNT THE LINES CAREFULLY - wrong counts cause "corrupt patch" errors
- The patch must apply with: git apply --check patch.diff"""

    def _build_prompt(self, state: ConductorState, handoff: StageHandoff) -> str:
        parts = [
            "## TASK",
            state.original_task,
            "",
            handoff.build_prompt_section(),
            "",
            "## CONTEXT",
            state.context_summary or "No context provided",
        ]

        # Add relevant file contents if available
        if handoff.file_contents:
            parts.append("\n## RELEVANT CODE")
            for filename, content in list(handoff.file_contents.items())[:3]:
                parts.extend([
                    f"\n### {filename}",
                    "```python",
                    content[:5000],  # Limit content
                    "```",
                ])

        # Add previous attempt if retry
        if handoff.retry_count > 0 and handoff.previous_output:
            parts.extend([
                "",
                "## PREVIOUS ATTEMPT (FIX THE ISSUES)",
                "```python",
                handoff.previous_output[:3000],
                "```",
            ])

        return "\n".join(parts)

    def _parse_response(
        self,
        response: str,
        state: ConductorState,
        handoff: StageHandoff
    ) -> None:
        """Parse engineering response."""
        # Extract acknowledgment
        ack = self._extract_acknowledgment(response)
        if ack:
            state.engineering_acknowledgment = ack

        # Extract diff patch (preferred for SWE-bench)
        diff_match = re.search(r'```diff\s*(.*?)```', response, re.DOTALL)
        if diff_match:
            state.implementation_code = diff_match.group(1).strip()
        else:
            # Try to find patch starting with ---
            patch_match = re.search(r'(---\s+a/.*?)(?=```|$)', response, re.DOTALL)
            if patch_match:
                state.implementation_code = patch_match.group(1).strip()
            else:
                # Fallback: extract any code block
                code_match = re.search(r'```(?:python)?\s*(.*?)```', response, re.DOTALL)
                if code_match:
                    state.implementation_code = code_match.group(1).strip()

        # Extract edge case handling
        edge_match = re.search(
            r'EDGE_CASE_HANDLING:\s*(.*?)(?=```|$)',
            response,
            re.IGNORECASE | re.DOTALL
        )
        if edge_match:
            edge_text = edge_match.group(1)
            for edge_case in handoff.edge_cases:
                if edge_case.lower() in edge_text.lower():
                    state.edge_cases_handled[edge_case] = True


class ReviewAgent(BaseStageAgent):
    """
    Code review agent.

    Responsibilities:
    - Review code against requirements
    - Check for bugs and issues
    - Verify edge case handling
    """

    @property
    def stage_name(self) -> str:
        return "review"

    def run(self, state: ConductorState, handoff: StageHandoff) -> ConductorState:
        """Review the implementation."""
        self._log("Starting code review")
        state.review_status = StageStatus.IN_PROGRESS

        # Build prompt
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_prompt(state, handoff)

        messages = [{"role": "user", "content": user_prompt}]

        # Call model
        response = self.model_client.complete(messages, system=system_prompt)

        # Log the call
        state.log_model_call(
            stage=self.stage_name,
            model_id=response.model_id,
            input_text=user_prompt,
            output_text=response.content,
            cost=response.cost,
            tokens=response.total_tokens,
            duration=response.duration,
        )

        # Parse response
        self._parse_response(response.content, state)

        self._log(f"Review result: {'PASSED' if state.review_passed else 'FAILED'}")
        return state

    def _get_system_prompt(self) -> str:
        return """You are a code review agent in the Opus-Conductor system.
Your job is to review code implementations against requirements.

Review the code for:
1. Correctness - Does it solve the problem?
2. Completeness - Are all requirements addressed?
3. Edge cases - Are all edge cases handled?
4. Quality - Is the code clean and maintainable?

Output format:

```json
{
    "verdict": "PASS" | "FAIL",
    "issues": [
        {"severity": "error|warning", "message": "Description", "suggestion": "How to fix"}
    ],
    "summary": "Overall assessment"
}
```

Be thorough but fair. Only flag real issues."""

    def _build_prompt(self, state: ConductorState, handoff: StageHandoff) -> str:
        parts = [
            "## TASK",
            state.original_task,
            "",
            "## REQUIREMENTS",
            "",
            "**Constraints:**",
        ]
        for c in state.constraints:
            parts.append(f"- {c}")

        parts.extend(["", "**Success Criteria:**"])
        for c in state.success_criteria:
            parts.append(f"- {c}")

        parts.extend(["", "**Edge Cases:**"])
        for e in state.edge_cases:
            handled = state.edge_cases_handled.get(e, False)
            status = "[CLAIMED HANDLED]" if handled else "[NOT HANDLED]"
            parts.append(f"- {status} {e}")

        parts.extend([
            "",
            "## CODE TO REVIEW",
            "```python",
            state.implementation_code,
            "```",
            "",
            "## AGENT'S ACKNOWLEDGMENT",
            state.engineering_acknowledgment or "(None provided)",
        ])

        return "\n".join(parts)

    def _parse_response(self, response: str, state: ConductorState) -> None:
        """Parse review response."""
        import json

        # Try to extract JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                verdict = data.get("verdict", "").upper()
                state.review_passed = verdict == "PASS"
                state.review_issues = [
                    issue.get("message", "Unknown issue")
                    for issue in data.get("issues", [])
                ]
                state.review_feedback = data.get("summary", "")
                return
            except json.JSONDecodeError:
                pass

        # Fallback to keyword detection
        response_upper = response.upper()
        state.review_passed = "PASS" in response_upper and "FAIL" not in response_upper
        state.review_feedback = response[:1000]


class HandoffProtocol:
    """
    Manages the handoff process between stages.

    Ensures structured transitions with explicit acknowledgments.
    """

    def __init__(
        self,
        require_acknowledgment: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        self.require_acknowledgment = require_acknowledgment
        self.logger = logger or logging.getLogger(__name__)

    def create_handoff(
        self,
        state: ConductorState,
        source_stage: str,
        target_stage: str,
        validation_result: Optional[ValidationResult] = None,
    ) -> StageHandoff:
        """Create a handoff from source to target stage."""
        handoff = StageHandoff.from_state(
            state=state,
            source_stage=source_stage,
            target_stage=target_stage,
            validation_result=validation_result,
        )

        self.logger.info(f"Created handoff: {source_stage} -> {target_stage}")
        return handoff

    def verify_handoff_receipt(
        self,
        state: ConductorState,
        handoff: StageHandoff,
    ) -> bool:
        """Verify that the receiving agent acknowledged the handoff."""
        if not self.require_acknowledgment:
            return True

        ack = state.engineering_acknowledgment
        if not ack:
            self.logger.warning(f"No acknowledgment found for {handoff.target_stage}")
            return False

        # Check that key requirements are mentioned
        ack_lower = ack.lower()
        for constraint in handoff.constraints[:2]:
            keywords = [w.lower() for w in constraint.split() if len(w) > 4]
            if not any(kw in ack_lower for kw in keywords[:3]):
                self.logger.warning(f"Constraint not acknowledged: {constraint}")
                return False

        return True

    def log_handoff(
        self,
        state: ConductorState,
        handoff: StageHandoff,
        success: bool,
    ) -> None:
        """Log the handoff in the audit trail."""
        state.add_audit_event(AuditEvent(
            timestamp=time.time(),
            event_type="handoff",
            stage=f"{handoff.source_stage}->{handoff.target_stage}",
            metadata={
                "constraints_count": len(handoff.constraints),
                "edge_cases_count": len(handoff.edge_cases),
                "retry_count": handoff.retry_count,
                "success": success,
            }
        ))
