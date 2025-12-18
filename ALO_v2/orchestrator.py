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

Generate the fix using SEARCH/REPLACE blocks. For each change needed:
1. Copy the EXACT text from the file that needs to change (including whitespace)
2. Show what it should be replaced with

Format your response as one or more SEARCH/REPLACE blocks:

<<<<<<< SEARCH
[exact text to find - copy from the file above exactly]
=======
[replacement text]
>>>>>>> REPLACE

IMPORTANT:
- The SEARCH text must match EXACTLY what's in the file (copy-paste it)
- Include enough context to make the match unique (usually 3-10 lines)
- You can have multiple SEARCH/REPLACE blocks for multiple changes
- Each block fixes one location in the code"""

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
        """Stage 4: Generate fix using SEARCH/REPLACE blocks"""
        state.current_stage = Stage.FIX
        state.patch_attempts += 1

        # Build context from file contents with line numbers for reference
        file_context_parts = []
        for path, content in state.file_contents.items():
            lines = content.split('\n')[:200]  # Limit lines
            numbered = '\n'.join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
            file_context_parts.append(f"=== {path} ===\n{numbered}")
        file_context = "\n\n".join(file_context_parts)

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

        # Parse SEARCH/REPLACE blocks
        changes = self._parse_search_replace(response.content)

        if not changes:
            # Fallback: try to extract unified diff patch
            state.patch = self._extract_patch(response.content)
            if state.patch:
                success, message = executor.apply_patch(state.patch)
                if not success:
                    state.history.append({
                        "stage": "patch_failed",
                        "message": message
                    })
            return state

        # Apply SEARCH/REPLACE changes
        all_success = True
        applied_changes = []

        for search, replace in changes:
            # Find which file contains this text
            found_in = None
            for path, content in state.file_contents.items():
                if search in content:
                    found_in = path
                    break

            if not found_in:
                state.history.append({
                    "stage": "patch_failed",
                    "message": f"SEARCH text not found in any file: {search[:100]}..."
                })
                all_success = False
                continue

            # Apply the change
            success, message = self._apply_search_replace(executor, found_in, search, replace)
            if success:
                applied_changes.append((found_in, search[:50], replace[:50]))
            else:
                state.history.append({
                    "stage": "patch_failed",
                    "message": f"Failed to apply change to {found_in}: {message}"
                })
                all_success = False

        # Generate patch from applied changes for the result
        if applied_changes:
            state.patch = executor.get_diff()

        return state

    def _parse_search_replace(self, content: str) -> list:
        """Parse SEARCH/REPLACE blocks from model response"""
        changes = []

        # Pattern: <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE
        import re
        pattern = r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE'
        matches = re.findall(pattern, content, re.DOTALL)

        for search, replace in matches:
            # Clean up the text
            search = search.strip()
            replace = replace.strip()
            if search:  # Only add if search is not empty
                changes.append((search, replace))

        return changes

    def _apply_search_replace(self, executor: DockerExecutor, file_path: str, search: str, replace: str) -> tuple:
        """Apply a single SEARCH/REPLACE change to a file"""
        # Read current file content
        full_path = f"/testbed/{file_path}"
        content = executor.read_file(full_path)

        if content is None:
            return False, f"Could not read {file_path}"

        if search not in content:
            return False, f"SEARCH text not found in {file_path}"

        # Count occurrences
        count = content.count(search)
        if count > 1:
            return False, f"SEARCH text found {count} times (must be unique)"

        # Apply replacement
        new_content = content.replace(search, replace)

        # Write back
        success = executor.write_file(full_path, new_content)

        if success:
            return True, "Applied successfully"
        else:
            return False, "Failed to write file"

    def _extract_patch(self, content: str) -> str:
        """Extract unified diff patch from model response and normalize format"""
        lines = content.split("\n")
        patch_lines = []
        in_patch = False

        for line in lines:
            if line.startswith("---") or line.startswith("diff --git"):
                in_patch = True
            if in_patch:
                patch_lines.append(line)

        patch = "\n".join(patch_lines)

        # Normalize patch format - add a/ and b/ prefixes if missing
        normalized_lines = []
        for line in patch.split("\n"):
            if line.startswith("--- ") and not line.startswith("--- a/"):
                # Convert "--- path" to "--- a/path"
                path = line[4:].strip()
                # Remove leading ./ if present
                if path.startswith("./"):
                    path = path[2:]
                normalized_lines.append(f"--- a/{path}")
            elif line.startswith("+++ ") and not line.startswith("+++ b/"):
                # Convert "+++ path" to "+++ b/path"
                path = line[4:].strip()
                # Remove leading ./ if present
                if path.startswith("./"):
                    path = path[2:]
                normalized_lines.append(f"+++ b/{path}")
            else:
                normalized_lines.append(line)

        return "\n".join(normalized_lines)

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
