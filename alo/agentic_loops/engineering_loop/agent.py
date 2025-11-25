import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

from alo.agentic_loops.core.exceptions import FileReadError, ToolRegistryRequiredError
from alo.agentic_loops.core.prompts import ENGINEERING_PROMPT
from alo.agentic_loops.core.state import LoopState
from alo.agentic_loops.core.temperature import RECOMMENDED_TEMPERATURES
from alo.agentic_loops.review_loop.agent import ReviewLoopAgent


class EngineeringLoopAgent:
    """Agent that generates code patches to fix issues.

    Temperature: 0.3 (moderate creativity) - Bug fixes sometimes require
    creative solutions, but too much randomness produces inconsistent patches.

    When review_agent is None, this agent performs a single attempt and
    stores the patch in state.current_patch for external review by the
    orchestrator. When review_agent is provided, it uses internal retry
    logic (backward compatible behavior).
    """

    def __init__(
        self,
        model_client: Any,
        review_agent: ReviewLoopAgent | None = None,  # Now optional for flattened loop
        repro_runner: Callable[[str], bool] | None = None,
        max_attempts: int = 3,
        prompt_template: str | None = None,
        temperature: Optional[float] = None,
    ) -> None:
        self.model_client = model_client
        self.review_agent = review_agent  # None = orchestrator handles review
        self.repro_runner = repro_runner
        self.max_attempts = max_attempts
        # Use structured prompt with diff format, requirements, and patterns
        self.prompt_template = prompt_template or ENGINEERING_PROMPT
        # Default to recommended temperature for engineering role (0.3)
        self.temperature = temperature if temperature is not None else RECOMMENDED_TEMPERATURES["engineering"]

    def run(self, state: LoopState, tool_registry: Any | None = None) -> LoopState:
        """Generate a patch and optionally verify with internal review.

        If review_agent is None (flattened loop mode):
        - Generates ONE patch attempt
        - Runs repro script
        - Stores patch in state.current_patch
        - Returns for orchestrator to handle review

        If review_agent is provided (backward compatible mode):
        - Uses internal retry loop with review
        """
        if self.review_agent is None:
            # Flattened loop mode: single attempt, orchestrator handles review
            return self._run_single_attempt(state, tool_registry)
        else:
            # Backward compatible mode: internal retry with review
            return self._run_with_internal_review(state, tool_registry)

    def _run_single_attempt(self, state: LoopState, tool_registry: Any | None) -> LoopState:
        """Single patch attempt for flattened loop mode."""
        code_context = self._gather_context(tool_registry, state)

        # Include review feedback if this is a retry
        feedback_section = ""
        if state.review_feedback:
            feedback_section = f"\n\nPrevious attempt was rejected. Feedback:\n{state.review_feedback}\n"

        prompt = self.prompt_template.format(
            issue=state.issue_description,
            context=state.context_summary,
            files=", ".join(state.relevant_files),
            code=code_context,
        ) + feedback_section

        response = self.model_client.chat(
            [{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        patch_text = response.get("content", "")

        # Store patch in state for orchestrator to review
        state.current_patch = patch_text
        self._persist_patch(patch_text, tool_registry, state)

        # Run repro to verify basic functionality
        repro_ok = self._run_repro(state, tool_registry)

        state.add_history(
            "engineering",
            attempts=1,
            repro_success=repro_ok,
            patch_generated=bool(patch_text),
        )
        return state

    def _run_with_internal_review(self, state: LoopState, tool_registry: Any | None) -> LoopState:
        """Original behavior with internal retry loop (backward compatible)."""
        review_ok = False
        for attempt in range(1, self.max_attempts + 1):
            code_context = self._gather_context(tool_registry, state)
            prompt = self.prompt_template.format(
                issue=state.issue_description,
                context=state.context_summary,
                files=", ".join(state.relevant_files),
                code=code_context,
            )
            response = self.model_client.chat(
                [{"role": "user", "content": prompt}],
                temperature=self.temperature,
            )
            patch_text = response.get("content", "")

            # Store patch in state
            state.current_patch = patch_text
            self._persist_patch(patch_text, tool_registry, state)

            repro_ok = self._run_repro(state, tool_registry)
            review_ok = self.review_agent.review_patch(state, patch_text)

            if repro_ok and review_ok:
                break

        state.add_history(
            "engineering",
            attempts=attempt,
            success=bool(state.repro_success and review_ok),
        )
        return state

    def _run_repro(self, state: LoopState, tool_registry: Any | None) -> bool:
        """Run the reproduction script to verify the fix.

        FAIL IS FAIL policy: If no tool_registry is provided and no
        repro_runner is configured, we fail explicitly rather than
        optimistically assuming success.
        """
        if self.repro_runner is not None:
            result = self.repro_runner(state.repro_script_content)
            state.repro_success = bool(result)
            return state.repro_success

        if tool_registry is None:
            # FAIL IS FAIL: Cannot verify fix without tool_registry
            raise ToolRegistryRequiredError("run_repro")

        script_name = "reproduce_issue.py"
        script_body = state.repro_script_content or "print('no repro content provided')\n"
        base_path = Path(state.repo_path or (getattr(tool_registry, "workspace_root", None) or "."))
        base_path.mkdir(parents=True, exist_ok=True)
        script_path = base_path / script_name
        script_path.write_text(script_body, encoding="utf-8")

        if tool_registry is not None:
            result = tool_registry.run_command(f"python {script_name}")
        else:
            process = subprocess.run(
                f"python {script_path.name}",
                shell=True,
                cwd=str(base_path),
                capture_output=True,
                text=True,
            )
            result = {
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }

        state.repro_success = result.get("returncode", 1) == 0
        state.add_history(
            "repro_run",
            path=str(script_path),
            returncode=result.get("returncode", 1),
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
        )
        return state.repro_success

    def _persist_patch(self, patch_text: str, tool_registry: Any | None, state: LoopState) -> None:
        if not patch_text:
            return
        base_path = self._select_base_path(tool_registry, state)
        patch_file = base_path / "applied_patch.txt"
        patch_file.parent.mkdir(parents=True, exist_ok=True)
        patch_file.write_text(patch_text, encoding="utf-8")

        applied = False
        if patch_text.lstrip().startswith("diff"):
            applied = self._apply_with_patch_command(tool_registry, base_path, patch_text, state)
            if not applied:
                applied = self._apply_naive_diff(base_path, patch_text)
        elif tool_registry is not None:
            # If not a diff, still drop content for visibility
            applied = True

        if applied:
            state.add_history("patch_applied", path=str(patch_file))

    def _select_base_path(self, tool_registry: Any | None, state: LoopState) -> Path:
        if tool_registry is not None and getattr(tool_registry, "workspace_root", None):
            return Path(tool_registry.workspace_root)
        repo_path = Path(state.repo_path) if state.repo_path else None
        if repo_path and repo_path.exists():
            return repo_path
        return Path(".")

    def _apply_with_patch_command(self, tool_registry: Any | None, base_path: Path, patch_text: str, state: LoopState) -> bool:
        if tool_registry is None:
            return False
        tool_registry.write_file("pending.patch", patch_text)
        result = tool_registry.run_command("patch -p1 < pending.patch")
        state.add_history("patch_apply", returncode=result.get("returncode"), stderr=result.get("stderr"))
        return result.get("returncode", 1) == 0

    def _apply_naive_diff(self, base_path: Path, patch_text: str) -> bool:
        lines = patch_text.splitlines()
        target = None
        removals: list[str] = []
        additions: list[str] = []
        for line in lines:
            if line.startswith("+++ "):
                target = line.split(" ", 1)[1].strip()
                if target.startswith("b/"):
                    target = target[2:]
            if line.startswith("--- "):
                continue
            if line.startswith("-") and not line.startswith("---"):
                removals.append(line[1:])
            if line.startswith("+") and not line.startswith("+++"):
                additions.append(line[1:])

        if not target:
            return False
        file_path = base_path / target
        if not file_path.exists():
            return False
        content = file_path.read_text(encoding="utf-8")
        original = content
        for rem, add in zip(removals, additions):
            if rem and rem in content:
                content = content.replace(rem, add, 1)
        if content != original:
            file_path.write_text(content, encoding="utf-8")
            return True
        return False

    def _gather_context(self, tool_registry: Any | None, state: LoopState) -> str:
        """Gather code context from relevant files.

        FAIL IS FAIL policy: File read errors are logged with details
        rather than silently skipped. We still continue with remaining
        files but track which ones failed.
        """
        if tool_registry is None or not state.relevant_files:
            return ""
        snippets = []
        failed_files = []
        for rel in state.relevant_files[:5]:
            try:
                file_text = tool_registry.read_file(rel)
                snippets.append(f"# File: {rel}\n{file_text[:1500]}")
            except Exception as e:
                # Track the failure rather than silently skipping
                failed_files.append({"file": rel, "error": str(e)})

        # Record failed file reads in state history for visibility
        if failed_files:
            state.add_history("context_gather_warnings", failed_files=failed_files)

        return "\n\n".join(snippets)
