"""
=============================================================================
ALO v2.0 Opus Orchestrator
=============================================================================

The brain of ALO v2 - Opus makes all decisions, workers execute tasks.

ARCHITECTURE:
- Opus (claude-opus-4-5-20251101): Orchestrator - analyzes, plans, decides
- Kimi K2: Default worker - fast, cheap, accurate
- Gemini 3 Flash: Large context worker - 1M tokens for big repos

FLOW:
1. ANALYZE: Opus reads issue, decides what information is needed
2. LOCALIZE: Worker finds relevant files (Opus supervises)
3. REPRODUCE: Worker creates reproduction (Opus validates approach)
4. FIX: Worker generates patch (Opus reviews)
5. VALIDATE: Run tests, Opus decides if done or needs retry
=============================================================================
"""

import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum

from .config import Config
from .clients import ClientFactory, ModelResponse, BaseClient
from .docker_executor import DockerExecutor, ExecutionResult


class Stage(Enum):
    """Pipeline stages"""
    ANALYZE = "analyze"
    LOCALIZE = "localize"
    REPRODUCE = "reproduce"
    FIX = "fix"
    VALIDATE = "validate"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class PipelineState:
    """State maintained throughout the pipeline"""
    instance_id: str
    problem_statement: str

    # Analysis results
    issue_type: str = ""  # bug, feature, refactor
    key_components: List[str] = field(default_factory=list)

    # Localization results
    relevant_files: List[str] = field(default_factory=list)
    file_contents: Dict[str, str] = field(default_factory=dict)

    # Reproduction results
    repro_script: str = ""
    repro_output: str = ""
    repro_confirmed: bool = False

    # Fix results
    patch: str = ""
    patch_attempts: int = 0

    # Validation results
    tests_passed: bool = False
    test_output: str = ""

    # Tracking
    current_stage: Stage = Stage.ANALYZE
    history: List[Dict[str, Any]] = field(default_factory=list)
    total_cost: float = 0.0
    total_tokens: int = 0


class ALOv2Orchestrator:
    """
    Opus-orchestrated pipeline for solving SWE-bench issues.

    Opus acts as the brain - analyzing, planning, and deciding.
    Workers (Kimi K2, Gemini 3 Flash) execute the actual tasks.
    """

    # Prompts for Opus orchestrator
    ANALYZE_PROMPT = """You are analyzing a GitHub issue to understand what needs to be fixed.

ISSUE:
{problem_statement}

Analyze this issue and provide:
1. ISSUE_TYPE: Is this a bug fix, new feature, or refactor?
2. KEY_COMPONENTS: What parts of the codebase are likely involved?
3. SEARCH_STRATEGY: What files/patterns should we search for?

Respond in JSON format:
{{
    "issue_type": "bug|feature|refactor",
    "key_components": ["component1", "component2"],
    "search_patterns": ["pattern1", "pattern2"],
    "summary": "Brief description of the issue"
}}"""

    LOCALIZE_PROMPT = """Based on the issue analysis, find the relevant source files.

ISSUE SUMMARY:
{summary}

KEY COMPONENTS: {key_components}
SEARCH PATTERNS: {search_patterns}

AVAILABLE FILES:
{file_list}

Select the most relevant files to examine. Return JSON:
{{
    "files_to_read": ["path/to/file1.py", "path/to/file2.py"],
    "reasoning": "Why these files are relevant"
}}"""

    FIX_PROMPT = """Generate a fix for this issue.

ISSUE:
{problem_statement}

RELEVANT CODE:
{file_contents}

{reproduction_context}

Generate a unified diff patch that fixes the issue. The patch should:
1. Fix the root cause, not just symptoms
2. Be minimal - only change what's necessary
3. Follow the existing code style

Return ONLY the unified diff patch, starting with --- and +++"""

    VALIDATE_PROMPT = """Review the test results and decide next steps.

ISSUE: {problem_statement}

PATCH APPLIED:
{patch}

TEST RESULTS:
Exit code: {exit_code}
Output:
{test_output}

Analyze the results and respond in JSON:
{{
    "passed": true/false,
    "analysis": "What the test results mean",
    "next_action": "complete|retry_fix|retry_localize|give_up",
    "feedback": "If retry, what should be changed"
}}"""

    def __init__(self, config: Optional[Config] = None):
        """Initialize the orchestrator with optional config"""
        self.config = config or Config()

        if not self.config.validate():
            raise ValueError("Configuration validation failed")

        # Initialize clients
        self.opus = ClientFactory.create(
            self.config.get_model("opus"),
            self.config.anthropic_api_key
        )

        self.kimi = ClientFactory.create(
            self.config.get_model("kimi-k2"),
            self.config.openrouter_api_key
        )

        self.gemini = ClientFactory.create(
            self.config.get_model("gemini-3-flash"),
            self.config.openrouter_api_key
        )

    def _select_worker(self, context_size: int) -> BaseClient:
        """Select appropriate worker based on context size"""
        if context_size > self.config.large_context_threshold:
            return self.gemini  # Use Gemini for large context
        return self.kimi  # Default to Kimi K2

    def _call_opus(self, prompt: str, state: PipelineState) -> ModelResponse:
        """Call Opus orchestrator and track costs"""
        messages = [{"role": "user", "content": prompt}]
        response = self.opus.generate(
            messages,
            system_prompt="You are an expert software engineer analyzing and fixing bugs."
        )
        state.total_cost += response.cost
        state.total_tokens += response.total_tokens
        state.history.append({
            "stage": state.current_stage.value,
            "model": "opus",
            "tokens": response.total_tokens,
            "cost": response.cost
        })
        return response

    def _call_worker(self, prompt: str, state: PipelineState, context_size: int = 0) -> ModelResponse:
        """Call appropriate worker and track costs"""
        worker = self._select_worker(context_size)
        messages = [{"role": "user", "content": prompt}]
        response = worker.generate(
            messages,
            system_prompt="You are an expert software engineer. Be precise and concise."
        )
        state.total_cost += response.cost
        state.total_tokens += response.total_tokens
        state.history.append({
            "stage": state.current_stage.value,
            "model": worker.config.model_id,
            "tokens": response.total_tokens,
            "cost": response.cost
        })
        return response

    def _analyze(self, state: PipelineState) -> PipelineState:
        """Stage 1: Opus analyzes the issue"""
        state.current_stage = Stage.ANALYZE

        prompt = self.ANALYZE_PROMPT.format(
            problem_statement=state.problem_statement
        )

        response = self._call_opus(prompt, state)

        try:
            # Parse JSON response
            result = json.loads(response.content)
            state.issue_type = result.get("issue_type", "bug")
            state.key_components = result.get("key_components", [])

            # Store search info in history for localization
            state.history.append({
                "stage": "analyze_result",
                "search_patterns": result.get("search_patterns", []),
                "summary": result.get("summary", "")
            })
        except json.JSONDecodeError:
            # Fallback: treat as bug fix
            state.issue_type = "bug"

        return state

    def _localize(self, state: PipelineState, executor: DockerExecutor) -> PipelineState:
        """Stage 2: Find relevant files"""
        state.current_stage = Stage.LOCALIZE

        # Get file list from container
        files = executor.list_files(".")

        # Get analysis results
        analysis = next(
            (h for h in state.history if h.get("stage") == "analyze_result"),
            {"search_patterns": [], "summary": state.problem_statement[:500]}
        )

        prompt = self.LOCALIZE_PROMPT.format(
            summary=analysis.get("summary", ""),
            key_components=", ".join(state.key_components),
            search_patterns=", ".join(analysis.get("search_patterns", [])),
            file_list="\n".join(files[:200])  # Limit file list
        )

        # Use worker for localization (may be large context)
        response = self._call_worker(prompt, state, context_size=len(prompt))

        try:
            result = json.loads(response.content)
            state.relevant_files = result.get("files_to_read", [])[:10]  # Limit files
        except json.JSONDecodeError:
            # Fallback: use key components to guess
            state.relevant_files = []

        # Read file contents
        for file_path in state.relevant_files:
            content = executor.read_file(f"/testbed/{file_path}")
            if content:
                state.file_contents[file_path] = content

        return state

    def _fix(self, state: PipelineState, executor: DockerExecutor) -> PipelineState:
        """Stage 4: Generate fix"""
        state.current_stage = Stage.FIX
        state.patch_attempts += 1

        # Build context from file contents
        file_context = "\n\n".join([
            f"=== {path} ===\n{content[:5000]}"  # Limit per file
            for path, content in state.file_contents.items()
        ])

        # Add reproduction context if available
        repro_context = ""
        if state.repro_confirmed:
            repro_context = f"\nREPRODUCTION CONFIRMED:\n{state.repro_output[:1000]}"

        prompt = self.FIX_PROMPT.format(
            problem_statement=state.problem_statement,
            file_contents=file_context,
            reproduction_context=repro_context
        )

        # Use worker for fix generation
        context_size = len(prompt)
        response = self._call_worker(prompt, state, context_size=context_size)

        # Extract patch from response
        state.patch = self._extract_patch(response.content)

        # Apply patch
        if state.patch:
            success, message = executor.apply_patch(state.patch)
            if not success:
                state.history.append({
                    "stage": "patch_failed",
                    "message": message
                })

        return state

    def _extract_patch(self, content: str) -> str:
        """Extract unified diff patch from model response"""
        lines = content.split("\n")
        patch_lines = []
        in_patch = False

        for line in lines:
            if line.startswith("---") or line.startswith("diff --git"):
                in_patch = True
            if in_patch:
                patch_lines.append(line)

        return "\n".join(patch_lines)

    def _validate(self, state: PipelineState, executor: DockerExecutor, test_cmd: str) -> PipelineState:
        """Stage 5: Validate the fix"""
        state.current_stage = Stage.VALIDATE

        # Run tests
        passed, output = executor.run_tests(test_cmd, timeout=300)
        state.test_output = output
        state.tests_passed = passed

        # Have Opus analyze results
        prompt = self.VALIDATE_PROMPT.format(
            problem_statement=state.problem_statement[:1000],
            patch=state.patch[:2000],
            exit_code=0 if passed else 1,
            test_output=output[:3000]
        )

        response = self._call_opus(prompt, state)

        try:
            result = json.loads(response.content)
            next_action = result.get("next_action", "give_up")

            if next_action == "complete" or passed:
                state.current_stage = Stage.COMPLETE
            elif state.patch_attempts >= self.config.max_total_attempts:
                state.current_stage = Stage.FAILED
            elif next_action == "retry_fix":
                # Will loop back to fix stage
                state.history.append({
                    "stage": "retry_feedback",
                    "feedback": result.get("feedback", "")
                })
            else:
                state.current_stage = Stage.FAILED

        except json.JSONDecodeError:
            if passed:
                state.current_stage = Stage.COMPLETE
            else:
                state.current_stage = Stage.FAILED

        return state

    def solve(
        self,
        instance_id: str,
        problem_statement: str,
        test_cmd: str = "python -m pytest"
    ) -> Dict[str, Any]:
        """
        Solve a SWE-bench instance.

        Args:
            instance_id: SWE-bench instance ID
            problem_statement: The issue description
            test_cmd: Command to run tests

        Returns:
            Dict with patch, success status, and metadata
        """
        state = PipelineState(
            instance_id=instance_id,
            problem_statement=problem_statement
        )

        start_time = time.time()

        with DockerExecutor(instance_id) as executor:
            # Stage 1: Analyze
            state = self._analyze(state)

            # Stage 2: Localize
            state = self._localize(state, executor)

            # Main loop: Fix → Validate → (retry if needed)
            while state.current_stage not in [Stage.COMPLETE, Stage.FAILED]:
                if state.patch_attempts >= self.config.max_total_attempts:
                    state.current_stage = Stage.FAILED
                    break

                # Generate fix
                state = self._fix(state, executor)

                # Validate
                state = self._validate(state, executor, test_cmd)

        elapsed = time.time() - start_time

        # Get final patch from container
        final_patch = state.patch if state.current_stage == Stage.COMPLETE else ""

        return {
            "instance_id": instance_id,
            "patch": final_patch,
            "success": state.current_stage == Stage.COMPLETE,
            "tests_passed": state.tests_passed,
            "attempts": state.patch_attempts,
            "total_cost": state.total_cost,
            "total_tokens": state.total_tokens,
            "elapsed_seconds": elapsed,
            "history": state.history
        }


def test_orchestrator():
    """Test the orchestrator with a sample instance"""
    orchestrator = ALOv2Orchestrator()

    result = orchestrator.solve(
        instance_id="django__django-11292",
        problem_statement="""
        The QuerySet.union() method doesn't work correctly when combined with
        values_list(). The resulting queryset returns incorrect results.
        """,
        test_cmd="python -m pytest tests/queries/test_qs_combinators.py -x"
    )

    print(f"Success: {result['success']}")
    print(f"Attempts: {result['attempts']}")
    print(f"Cost: ${result['total_cost']:.4f}")
    print(f"Time: {result['elapsed_seconds']:.1f}s")


if __name__ == "__main__":
    test_orchestrator()
