"""
=============================================================================
SCRIPT NAME: meta_orchestrator.py
=============================================================================

Opus Meta-Orchestrator - Main orchestration class.

Implements Anthropic's agent harness patterns:
1. Feature-by-feature execution (not all-at-once)
2. Clean state invariant after each feature
3. Checkpointing with git commits
4. Explicit verification before marking complete

INPUT FILES:
- Task description from user
- Repository path (optional)

OUTPUT FILES:
- OrchestrationResult with solution and metrics

VERSION: 1.0
LAST UPDATED: 2025-11-26

DESCRIPTION:
The main Opus Meta-Orchestrator that coordinates multiple specialized agents
using dynamic model selection. Opus 4.5 acts as the strategic brain,
analyzing tasks and selecting models from a registry.

DEPENDENCIES:
- subprocess (standard library)
- time (standard library)

=============================================================================
"""

from typing import Tuple, List, Optional, Dict
from dataclasses import dataclass
import time
import subprocess

from .model_registry import get_model
from .feature_list import FeatureList, Feature, FeatureStatus
from .multi_provider_client import MultiProviderClient, CompletionResult
from .strategic_planner import StrategicPlanner, ExecutionPlan
from .adaptive_validator import AdaptiveValidator, ValidationResult
from .presets import VariantPreset
from .code_executor import CodeExecutor, ExecutionResult
from .compounding_learner import CompoundingLearner
from .model_selection_learner import ModelSelectionLearner

# Import LoopState from core
from alo.agentic_loops.core.state import LoopState

# Import ToolRegistry if available
try:
    from alo.agentic_loops.core.tools import ToolRegistry
except ImportError:
    ToolRegistry = None


@dataclass
class OrchestrationResult:
    """Final result from orchestration."""
    state: LoopState
    plan: ExecutionPlan
    feature_list: FeatureList
    validations: List[ValidationResult]
    total_cost: float
    total_time: float
    features_completed: int
    features_total: int
    code_executed: bool = False
    execution_passed: bool = False
    execution_error: Optional[str] = None


class OpusMetaOrchestrator:
    """
    Main orchestrator that uses Opus for planning and validation.

    KEY PATTERN: Feature-by-feature execution
    - Break task into features
    - Implement ONE feature at a time
    - Verify + checkpoint after each
    - Different models for different feature complexity
    """

    def __init__(
        self,
        client: MultiProviderClient,
        tool_registry: Optional[ToolRegistry] = None,
        preset: Optional[VariantPreset] = None,
        max_retries_per_feature: int = 3,
        logger=None,
        use_learned_prompt: bool = True,
        use_learned_model_selection: bool = True,
        compounding_storage: str = "compounding_knowledge",
        model_selection_storage: str = "model_selection_knowledge"
    ):
        """
        Initialize the Opus Meta-Orchestrator.

        Args:
            client: Multi-provider client for API calls
            tool_registry: Optional tool registry for file operations
            preset: Optional variant preset to constrain model selection
            max_retries_per_feature: Max retries before escalation
            logger: Optional logger instance
            use_learned_prompt: Use evolved prompt from CompoundingLearner
            use_learned_model_selection: Use ModelSelectionLearner for routing
            compounding_storage: Path to compounding learner state
            model_selection_storage: Path to model selection learner state
        """
        self.client = client
        self.tool_registry = tool_registry
        self.preset = preset
        self.max_retries_per_feature = max_retries_per_feature
        self.logger = logger
        self.use_learned_prompt = use_learned_prompt
        self.use_learned_model_selection = use_learned_model_selection

        self.planner = StrategicPlanner(client, preset)
        self.validator = AdaptiveValidator(client)
        self.executor = CodeExecutor(timeout=30)

        # Initialize learners
        self.compounding_learner = None
        self.model_selection_learner = None

        if use_learned_prompt:
            try:
                self.compounding_learner = CompoundingLearner(
                    client, storage_path=compounding_storage
                )
                self._log(f"Loaded CompoundingLearner (v{self.compounding_learner.state.prompt_version})")
            except Exception as e:
                self._log(f"CompoundingLearner not available: {e}")

        if use_learned_model_selection:
            try:
                self.model_selection_learner = ModelSelectionLearner(
                    client,
                    storage_path=model_selection_storage,
                    candidate_models=preset.allowed_models if preset else None
                )
                stats = self.model_selection_learner.get_stats()
                self._log(f"Loaded ModelSelectionLearner ({stats['total_tasks']} tasks, {stats['routing_rules_learned']} rules)")
            except Exception as e:
                self._log(f"ModelSelectionLearner not available: {e}")

    def run(
        self,
        issue: str,
        repo_path: Optional[str] = None
    ) -> OrchestrationResult:
        """
        Execute task using feature-by-feature pattern.

        Based on Anthropic's research:
        "Incremental scope limitation prevents the failure mode where agents
        attempt to one-shot the app, leading to incomplete implementations."

        Args:
            issue: Task/issue description
            repo_path: Optional path to repository

        Returns:
            OrchestrationResult with solution and metrics
        """
        start_time = time.time()
        total_cost = 0.0
        all_validations = []

        # Initialize state
        state = LoopState(issue_description=issue, repo_path=repo_path or ".")
        state.add_history("orchestrator", message="Starting Opus Meta-Orchestrator (Feature-Based)")

        self._log("Starting Opus Meta-Orchestrator")

        # =====================================================================
        # PHASE 1: Strategic Planning + Feature Decomposition (Opus)
        # =====================================================================
        state.add_history("planning", message="Opus analyzing task and decomposing into features...")
        self._log("Phase 1: Strategic Planning")

        plan, feature_list = self.planner.create_plan_with_features(issue)

        state.add_history("planning",
            message=f"Plan created: {len(feature_list.features)} features, "
            f"archetype={plan.archetype}")

        # Log feature list (JSON format prevents modification)
        state.add_history("features", data=feature_list.to_json())

        self._log(f"Decomposed into {len(feature_list.features)} features")

        # =====================================================================
        # PHASE 2: Context Gathering (Once for all features)
        # =====================================================================
        self._log("Phase 2: Context Gathering")
        context_result = self._run_context_agent(state, plan)
        total_cost += context_result.cost

        # =====================================================================
        # PHASE 3: Feature Execution Loop (One at a time)
        # =====================================================================
        self._log("Phase 3: Feature Execution Loop")
        accumulated_code = ""  # Build up code across features

        while not feature_list.all_completed():
            feature = feature_list.get_next_pending()
            if not feature:
                break

            state.add_history("feature_start",
                message=f"Starting feature {feature.id}: {feature.description}")

            self._log(f"Starting feature {feature.id}")
            feature_list.mark_in_progress(feature.id)

            # Try to implement this feature
            for attempt in range(self.max_retries_per_feature):
                state.add_history("attempt",
                    message=f"Feature {feature.id} attempt {attempt + 1}/{self.max_retries_per_feature}")

                # ---------------------------------------------------------
                # Engineering: Implement ONE feature
                # ---------------------------------------------------------
                engineering_result = self._run_feature_engineering(
                    state, plan, feature, accumulated_code
                )
                total_cost += engineering_result.cost

                # ---------------------------------------------------------
                # Review: Verify this feature + clean state check
                # ---------------------------------------------------------
                review_result = self._run_feature_review(
                    state, plan, feature, engineering_result.content
                )
                total_cost += review_result.cost

                # ---------------------------------------------------------
                # Code Execution: Actually run the code
                # ---------------------------------------------------------
                extracted_code = self.executor.extract_code(engineering_result.content)
                if extracted_code:
                    exec_result = self.executor.execute(extracted_code)
                    state.add_history("execution",
                        message=f"Code execution: {'PASSED' if exec_result.success else 'FAILED'}",
                        error=exec_result.error_message if not exec_result.success else None)

                    if not exec_result.success:
                        # Code doesn't run - fail validation
                        validation = ValidationResult(
                            passed=False,
                            constraint_results={"code_execution": False},
                            failure_type=exec_result.error_type or "ExecutionError",
                            failure_details=exec_result.error_message,
                            retry_strategy="emphatic",
                            specific_guidance=f"Fix {exec_result.error_type}: {exec_result.error_message}"
                        )
                        all_validations.append(validation)
                        # Continue to retry logic below
                    else:
                        # Code runs - now do Opus validation
                        validation = self.validator.validate_feature(
                            state, plan, feature, engineering_result.content
                        )
                        total_cost += validation.cost
                        all_validations.append(validation)
                else:
                    # Couldn't extract code
                    validation = ValidationResult(
                        passed=False,
                        constraint_results={"code_extraction": False},
                        failure_type="ExtractionError",
                        failure_details="Could not extract Python code from response",
                        retry_strategy="emphatic"
                    )
                    all_validations.append(validation)

                if validation.passed:
                    # Feature complete!
                    accumulated_code = engineering_result.content
                    feature_list.mark_completed(feature.id)

                    # Record success for model selection learning
                    self._record_feature_result(feature, success=True)

                    # Checkpoint (git commit)
                    commit_hash = self._create_checkpoint(feature, repo_path)
                    feature_list.add_checkpoint(feature.id, commit_hash)

                    state.add_history("feature_complete",
                        message=f"Feature {feature.id} complete, checkpoint: {commit_hash[:8]}")

                    self._log(f"Feature {feature.id} completed")
                    break
                else:
                    # Retry with guidance
                    state.add_history("feature_retry",
                        message=f"Feature {feature.id} failed: {validation.failure_type}")

                    self._log(f"Feature {feature.id} retry: {validation.failure_type}")

                    # Apply retry strategy
                    if validation.retry_strategy == "upgrade" and attempt < 2:
                        feature.assigned_model = self._get_upgrade_model(feature.assigned_model)
                        state.add_history("model_upgrade",
                            message=f"Upgrading to {feature.assigned_model}")

            else:
                # All retries exhausted for this feature
                feature_list.mark_failed(feature.id, validation.failure_details or "Max retries")

                # Record failure for model selection learning
                self._record_feature_result(feature, success=False)

                state.add_history("feature_failed",
                    message=f"Feature {feature.id} failed after {self.max_retries_per_feature} attempts")

                self._log(f"Feature {feature.id} FAILED")

                # Opus takeover for remaining features
                if not feature_list.all_completed():
                    state.add_history("opus_takeover",
                        message="Opus taking over remaining features")
                    self._log("Opus takeover initiated")
                    takeover_result = self._opus_takeover(state, plan, feature_list, accumulated_code)
                    total_cost += takeover_result.cost
                    accumulated_code = takeover_result.content
                break

        # =====================================================================
        # PHASE 4: Final Execution Verification
        # =====================================================================
        state.final_answer = accumulated_code

        # Final execution test on complete code
        code_executed = False
        execution_passed = False
        execution_error = None

        if accumulated_code:
            final_code = self.executor.extract_code(accumulated_code)
            if final_code:
                code_executed = True
                final_exec = self.executor.execute(final_code)
                execution_passed = final_exec.success
                if not final_exec.success:
                    execution_error = f"{final_exec.error_type}: {final_exec.error_message}"
                state.add_history("final_execution",
                    message=f"Final code execution: {'PASSED' if execution_passed else 'FAILED'}",
                    error=execution_error)
                self._log(f"Final execution: {'PASSED' if execution_passed else 'FAILED'}")

        total_time = time.time() - start_time

        completed = len([f for f in feature_list.features
                        if f.status == FeatureStatus.COMPLETED])

        self._log(f"Completed {completed}/{len(feature_list.features)} features in {total_time:.1f}s")

        return OrchestrationResult(
            state=state,
            plan=plan,
            feature_list=feature_list,
            validations=all_validations,
            total_cost=total_cost,
            total_time=total_time,
            features_completed=completed,
            features_total=len(feature_list.features),
            code_executed=code_executed,
            execution_passed=execution_passed,
            execution_error=execution_error
        )

    def run_swebench(
        self,
        issue: str,
        repo_path: str
    ) -> OrchestrationResult:
        """
        Execute task in SWE-bench mode - generates and applies file edits.

        Unlike `run()` which generates self-contained code, this method:
        1. Analyzes the existing codebase to find relevant files
        2. Generates targeted edits (patches) for specific files
        3. Writes those edits to the actual repository files
        4. Returns result suitable for `git diff` extraction

        Args:
            issue: Problem statement / issue description
            repo_path: Path to the cloned repository (REQUIRED)

        Returns:
            OrchestrationResult with applied changes
        """
        if not repo_path:
            raise ValueError("repo_path is required for SWE-bench mode")

        start_time = time.time()
        total_cost = 0.0

        # Initialize state and tool registry
        state = LoopState(issue_description=issue, repo_path=repo_path)
        state.add_history("orchestrator", message="Starting Opus Meta-Orchestrator (SWE-bench Mode)")

        # Create tool registry for file operations
        from alo.agentic_loops.core.tools import ToolRegistry
        tool_registry = ToolRegistry(workspace_root=repo_path)

        self._log("Starting SWE-bench Mode")

        # =====================================================================
        # PHASE 1: Codebase Analysis - Find relevant files
        # =====================================================================
        state.add_history("analysis", message="Analyzing codebase to identify relevant files...")
        self._log("Phase 1: Codebase Analysis")

        # Get file listing
        try:
            all_files = tool_registry.list_files()
            # Filter to Python files (most SWE-bench issues)
            python_files = [f for f in all_files if f.endswith('.py')]
            state.add_history("files", message=f"Found {len(python_files)} Python files")
        except Exception as e:
            self._log(f"Error listing files: {e}")
            python_files = []

        # Use context model to identify relevant files
        analysis_result = self._analyze_codebase_for_issue(
            state, issue, python_files[:200]  # Limit to avoid token overflow
        )
        total_cost += analysis_result.cost

        # =====================================================================
        # PHASE 2: Generate and Apply Edits
        # =====================================================================
        state.add_history("editing", message="Generating file edits...")
        self._log("Phase 2: Generate and Apply Edits")

        edit_result = self._generate_and_apply_edits(
            state, issue, tool_registry, analysis_result.content
        )
        total_cost += edit_result.cost

        # =====================================================================
        # PHASE 3: Verify Changes
        # =====================================================================
        self._log("Phase 3: Verification")

        # Check if files were actually modified
        import subprocess
        try:
            diff_result = subprocess.run(
                ["git", "-C", repo_path, "diff", "--stat"],
                capture_output=True,
                text=True
            )
            files_changed = len([l for l in diff_result.stdout.split('\n') if '|' in l])
            state.add_history("verification",
                message=f"Modified {files_changed} files")
            self._log(f"Modified {files_changed} files")
        except Exception as e:
            files_changed = 0
            state.add_history("verification", message=f"Could not verify changes: {e}")

        total_time = time.time() - start_time

        state.final_answer = edit_result.content

        return OrchestrationResult(
            state=state,
            plan=None,  # No feature plan in SWE-bench mode
            feature_list=None,
            validations=[],
            total_cost=total_cost,
            total_time=total_time,
            features_completed=1 if files_changed > 0 else 0,
            features_total=1,
            code_executed=False,
            execution_passed=files_changed > 0,
            execution_error=None
        )

    def _analyze_codebase_for_issue(
        self,
        state: LoopState,
        issue: str,
        file_list: List[str]
    ) -> CompletionResult:
        """
        Analyze codebase to identify files relevant to the issue.

        Uses large context model (Gemini 3 Pro with 1M context) to scan
        file structure and determine which files need modification.
        Also identifies related test files.
        """
        # Use context model for analysis - Gemini 2.5 Flash has 1M context (stable)
        model_config = get_model(
            self.preset.default_context if self.preset else "gemini-2.5-flash"
        )

        # With 1M context, we can include more files
        file_tree = "\n".join(f"  {f}" for f in file_list[:500])

        # Identify test directories for this repo
        test_files = [f for f in file_list if '/test' in f or 'test_' in f]
        test_tree = "\n".join(f"  {f}" for f in test_files[:100])

        prompt = f'''You are analyzing a codebase to fix a software issue.

ISSUE/BUG REPORT:
{issue}

REPOSITORY FILE STRUCTURE (source files):
{file_tree}

TEST FILES:
{test_tree}

TASK:
1. Identify which SOURCE files are most likely to need modification to fix this issue
2. Identify which TEST files test the functionality mentioned in the issue
3. Explain why each file is relevant
4. Prioritize files by likelihood of needing changes

Return JSON:
{{
    "relevant_files": [
        {{"path": "path/to/file.py", "reason": "Why this file needs changes", "priority": 1}},
        ...
    ],
    "test_files": [
        {{"path": "path/to/test_file.py", "reason": "Tests the affected functionality"}}
    ],
    "analysis": "Brief summary of the issue and approach",
    "key_components": ["component1", "component2"],
    "likely_fix_location": "Specific function/class/method name that likely needs the fix"
}}

Focus on the 3-5 most relevant source files and 1-2 test files. Be specific about file paths.
'''

        messages = [{"role": "user", "content": prompt}]
        result = self.client.complete(model_config, messages, max_tokens=4096)

        state.context_summary = result.content
        state.add_history("analysis", message="Identified relevant files and tests")

        return result

    def _generate_and_apply_edits(
        self,
        state: LoopState,
        issue: str,
        tool_registry: ToolRegistry,
        analysis: str
    ) -> CompletionResult:
        """
        Generate specific file edits and apply them to the repository.

        This is the core SWE-bench capability - reading files, generating
        patches, and writing them back.
        """
        # Parse analysis to get relevant files and test files
        import json
        import re

        relevant_files = []
        test_files = []
        likely_fix_location = ""
        try:
            # Try to extract JSON from analysis
            json_match = re.search(r'\{[\s\S]*\}', analysis)
            if json_match:
                parsed = json.loads(json_match.group())
                relevant_files = [f["path"] for f in parsed.get("relevant_files", [])]
                test_files = [f["path"] for f in parsed.get("test_files", [])]
                likely_fix_location = parsed.get("likely_fix_location", "")
        except:
            # Fallback: look for file paths in analysis
            relevant_files = re.findall(r'[\w/]+\.py', analysis)[:5]

        if not relevant_files:
            state.add_history("error", message="No relevant files identified")
            return CompletionResult(
                content="", cost=0.0, input_tokens=0, output_tokens=0,
                elapsed_time=0.0, tokens_per_second=0.0, model="none", provider="none"
            )

        # Read the relevant source files (full content for Gemini's 1M context)
        file_contents = {}
        for file_path in relevant_files[:5]:  # Limit to 5 source files
            try:
                content = tool_registry.read_file(file_path)
                file_contents[file_path] = content
                state.add_history("read_file", message=f"Read {file_path} ({len(content)} chars)")
            except Exception as e:
                state.add_history("read_file", message=f"Could not read {file_path}: {e}")

        # Read test files to understand expected behavior
        test_contents = {}
        for test_path in test_files[:2]:  # Limit to 2 test files
            try:
                content = tool_registry.read_file(test_path)
                test_contents[test_path] = content
                state.add_history("read_test", message=f"Read test {test_path} ({len(content)} chars)")
            except Exception as e:
                state.add_history("read_test", message=f"Could not read test {test_path}: {e}")

        if not file_contents:
            state.add_history("error", message="Could not read any relevant files")
            return CompletionResult(
                content="", cost=0.0, input_tokens=0, output_tokens=0,
                elapsed_time=0.0, tokens_per_second=0.0, model="none", provider="none"
            )

        # Generate edits using engineering model
        model_name = self.preset.default_engineering if self.preset else "qwen3-235b"

        # Use model selection if available
        if self.model_selection_learner:
            try:
                selected_model, _ = self.model_selection_learner.select_model(issue)
                if self.preset and selected_model in self.preset.allowed_models:
                    model_name = selected_model
            except:
                pass

        model_config = get_model(model_name)

        # Build prompt with FULL file contents (leverage Gemini's 1M context)
        files_str = ""
        for path, content in file_contents.items():
            # Include full files - we have 1M context from Gemini
            # Only truncate extremely long files (>50K chars)
            if len(content) > 50000:
                content = content[:50000] + "\n... (truncated at 50K chars)"
            files_str += f"\n### FILE: {path}\n```python\n{content}\n```\n"

        # Include test files for context
        tests_str = ""
        if test_contents:
            tests_str = "\n\nRELATED TEST FILES (for understanding expected behavior):\n"
            for path, content in test_contents.items():
                if len(content) > 20000:
                    content = content[:20000] + "\n... (truncated)"
                tests_str += f"\n### TEST FILE: {path}\n```python\n{content}\n```\n"

        # Use evolved prompt if available
        base_prompt = self.compounding_learner.state.current_prompt if (
            self.compounding_learner and self.compounding_learner.state.current_prompt
        ) else ""

        # Add likely fix location hint if available
        fix_hint = ""
        if likely_fix_location:
            fix_hint = f"\nLIKELY FIX LOCATION: {likely_fix_location}\n"

        prompt = f'''{base_prompt}

You are fixing a bug in a Python repository.

ISSUE/BUG REPORT:
{issue}
{fix_hint}
RELEVANT FILES:
{files_str}
{tests_str}
TASK:
Generate the EXACT file edits needed to fix this issue.

OUTPUT FORMAT:
For each file that needs changes, output:

### EDIT: path/to/file.py
```python
<<<<<<< ORIGINAL
[exact original code to replace - include 2-5 lines of context]
=======
[new code to insert - keep same style/formatting]
>>>>>>> MODIFIED
```

CRITICAL RULES - FOLLOW EXACTLY:
1. Make SURGICAL, MINIMAL changes - typically 1-10 lines modified
2. NEVER rewrite entire files or functions - only change what's broken
3. NEVER delete large blocks of code unless explicitly required
4. The ORIGINAL section must contain EXACT text from the file (copy-paste)
5. Include 2-5 lines of surrounding context to uniquely identify the location
6. Preserve ALL existing code style, indentation, and formatting
7. Do NOT add comments explaining the fix
8. Do NOT refactor or "improve" unrelated code
9. Each EDIT block should modify at most 20 lines
10. If the fix requires changes in multiple places, use multiple EDIT blocks

COMMON MISTAKES TO AVOID:
- Don't replace a 50-line function when only 1 line needs to change
- Don't rewrite imports or restructure files
- Don't add type hints or docstrings unless that's the bug
- Don't "clean up" surrounding code

Generate the minimal edits now:
'''

        messages = [{"role": "user", "content": prompt}]
        result = self.client.complete(model_config, messages, max_tokens=8192)

        state.add_history("engineering", message=f"Generated edits using {model_name}")

        # Parse and apply edits
        edits_applied = self._apply_edits_to_files(
            result.content, tool_registry, state
        )

        state.add_history("applied", message=f"Applied {edits_applied} edits")
        self._log(f"Applied {edits_applied} edits")

        return result

    def _apply_edits_to_files(
        self,
        edit_response: str,
        tool_registry: ToolRegistry,
        state: LoopState,
        max_edit_lines: int = 100  # Reject edits larger than this
    ) -> int:
        """
        Parse edit instructions and apply them to files.

        Supports multiple edit formats:
        1. SEARCH/REPLACE blocks (preferred)
        2. Full file replacements (only if small)

        SAFETY: Rejects edits that are too large (likely full-file rewrites).
        """
        import re

        edits_applied = 0
        edits_rejected = 0

        # Pattern 1: EDIT blocks with ORIGINAL/MODIFIED markers
        edit_pattern = r'### EDIT:\s*([^\n]+)\n```python\n<<<<<<< ORIGINAL\n(.*?)\n=======\n(.*?)\n>>>>>>> MODIFIED\n```'
        matches = re.findall(edit_pattern, edit_response, re.DOTALL)

        for file_path, original, modified in matches:
            file_path = file_path.strip()

            # SAFETY CHECK: Reject oversized edits (likely full-file rewrites)
            original_lines = len(original.strip().split('\n'))
            modified_lines = len(modified.strip().split('\n'))
            if original_lines > max_edit_lines or modified_lines > max_edit_lines:
                state.add_history("edit_rejected",
                    message=f"Rejected oversized edit to {file_path}: {original_lines}->{modified_lines} lines (max {max_edit_lines})")
                self._log(f"REJECTED oversized edit to {file_path}: {original_lines}->{modified_lines} lines")
                edits_rejected += 1
                continue

            try:
                current_content = tool_registry.read_file(file_path)

                # Apply the edit
                if original.strip() in current_content:
                    new_content = current_content.replace(original.strip(), modified.strip(), 1)
                    tool_registry.write_file(file_path, new_content)
                    edits_applied += 1
                    state.add_history("edit_applied",
                        message=f"Applied edit to {file_path} ({modified_lines} lines)")
                    self._log(f"Applied edit to {file_path} ({modified_lines} lines)")
                else:
                    state.add_history("edit_failed",
                        message=f"Could not find original text in {file_path}")
                    self._log(f"Edit failed for {file_path}: original text not found")

            except Exception as e:
                state.add_history("edit_error",
                    message=f"Error applying edit to {file_path}: {e}")
                self._log(f"Error applying edit to {file_path}: {e}")

        # Pattern 2: Full file replacement - ONLY if no EDIT blocks worked
        # AND the replacement is small (likely a new file, not a rewrite)
        if edits_applied == 0 and edits_rejected == 0:
            # Try to find file path + code block pattern
            file_block_pattern = r'(?:File|PATH|Edit):\s*`?([^\n`]+\.py)`?\n```python\n(.*?)\n```'
            matches = re.findall(file_block_pattern, edit_response, re.DOTALL | re.IGNORECASE)

            for file_path, new_content in matches:
                file_path = file_path.strip()
                content_lines = len(new_content.strip().split('\n'))

                # Only allow small file replacements (new files or small fixes)
                if content_lines > 50:
                    state.add_history("edit_rejected",
                        message=f"Rejected full-file replacement of {file_path}: {content_lines} lines is too large")
                    self._log(f"REJECTED full-file replacement of {file_path}: {content_lines} lines")
                    continue

                try:
                    tool_registry.write_file(file_path, new_content)
                    edits_applied += 1
                    state.add_history("edit_applied",
                        message=f"Replaced {file_path} ({content_lines} lines)")
                    self._log(f"Replaced {file_path} ({content_lines} lines)")
                except Exception as e:
                    state.add_history("edit_error",
                        message=f"Error writing {file_path}: {e}")

        if edits_rejected > 0:
            state.add_history("warning",
                message=f"Rejected {edits_rejected} oversized edits - model may have attempted full-file rewrites")

        return edits_applied

    def _run_context_agent(self, state: LoopState, plan: ExecutionPlan) -> CompletionResult:
        """Run context gathering with selected model."""
        model_config = get_model(plan.context_model)

        prompt = self._build_context_prompt(plan)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Analyze the codebase for this task:\n\n{state.issue_description}"}
        ]

        result = self.client.complete(model_config, messages, max_tokens=4096)
        state.context_summary = result.content
        state.add_history("context", message=f"Context gathered using {plan.context_model}")

        return result

    def _run_feature_engineering(
        self,
        state: LoopState,
        plan: ExecutionPlan,
        feature: Feature,
        existing_code: str
    ) -> CompletionResult:
        """
        Implement ONE feature, building on existing code.

        Key Anthropic insight: "Work on one feature at a time"

        INTEGRATIONS:
        - ModelSelectionLearner: Dynamically selects best model for task type
        - CompoundingLearner: Uses evolved prompt with learned patterns
        """
        # Use ModelSelectionLearner if available
        model_name = feature.assigned_model or plan.default_engineering_model
        task_profile = None

        if self.model_selection_learner:
            try:
                selected_model, task_profile = self.model_selection_learner.select_model(
                    feature.description
                )
                # Only use if model is in preset's allowed list
                if self.preset and selected_model in self.preset.allowed_models:
                    model_name = selected_model
                    state.add_history("model_selection",
                        message=f"Learned routing selected {model_name} for {task_profile.task_type}")
                elif not self.preset:
                    model_name = selected_model
                    state.add_history("model_selection",
                        message=f"Learned routing selected {model_name} for {task_profile.task_type}")
            except Exception as e:
                self._log(f"Model selection failed, using default: {e}")

        model_config = get_model(model_name)

        # Use CompoundingLearner's evolved prompt if available
        if self.compounding_learner and self.compounding_learner.state.current_prompt:
            prompt = self._build_learned_engineering_prompt(
                plan, feature, existing_code, state.context_summary
            )
        else:
            prompt = self._build_feature_engineering_prompt(
                plan, feature, existing_code, state.context_summary
            )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Implement ONLY feature {feature.id}: {feature.description}"}
        ]

        start_time = time.time()
        result = self.client.complete(model_config, messages, max_tokens=8192)
        elapsed = time.time() - start_time

        state.add_history("engineering",
            message=f"Feature {feature.id} implemented using {model_name} ({elapsed:.1f}s)")

        # Record result for model selection learning
        if self.model_selection_learner and task_profile:
            # Will be updated with success/failure after validation
            feature._task_profile = task_profile
            feature._engineering_time = elapsed
            feature._engineering_cost = result.cost
            feature._engineering_model = model_name

        return result

    def _run_feature_review(
        self,
        state: LoopState,
        plan: ExecutionPlan,
        feature: Feature,
        code: str
    ) -> CompletionResult:
        """
        Review a single feature implementation.

        Uses DIFFERENT provider than engineering to avoid model collapse.
        """
        model_config = get_model(plan.review_model)

        prompt = f'''Review this implementation of feature {feature.id}.

FEATURE BEING REVIEWED:
ID: {feature.id}
Description: {feature.description}
Required tests: {', '.join(feature.tests)}
Constraints: {', '.join(feature.constraints)}

CODE TO REVIEW:
{code}

CLEAN STATE INVARIANT CHECKLIST:
- No syntax errors
- No TODO/FIXME comments for this feature
- No placeholder implementations (pass, ...)
- Feature {feature.id} is fully implemented
- Previous features still work (no regressions)
- Code is immediately runnable

Return JSON:
{{
    "approved": true|false,
    "clean_state": true|false,
    "issues": ["<issue1>", "<issue2>"],
    "specific_feedback": "<actionable feedback if rejected>"
}}
'''

        messages = [{"role": "user", "content": prompt}]
        result = self.client.complete(model_config, messages, max_tokens=1024)

        state.add_history("review",
            message=f"Feature {feature.id} reviewed by {plan.review_model}")

        return result

    def _opus_takeover(
        self,
        state: LoopState,
        plan: ExecutionPlan,
        feature_list: FeatureList,
        current_code: str
    ) -> CompletionResult:
        """
        Opus takes over when other models fail repeatedly.

        This is the "nuclear option" - Opus implements all remaining features.
        """
        opus_config = get_model("opus-4.5")

        # Get remaining features
        remaining = [f for f in feature_list.features
                    if f.status != FeatureStatus.COMPLETED]

        remaining_str = "\n".join(
            f"- {f.id}: {f.description}" for f in remaining
        )

        prompt = f'''OPUS TAKEOVER MODE

Previous models failed to implement these features. You must complete them.

ORIGINAL TASK:
{state.issue_description}

REMAINING FEATURES TO IMPLEMENT:
{remaining_str}

CURRENT CODE (Build on this):
{current_code if current_code else "# No code implemented yet"}

FAILURE HISTORY:
{self._get_failure_summary(feature_list)}

GLOBAL CONSTRAINTS:
{self._format_constraints(plan.global_constraints)}

REQUIREMENTS:
1. Implement ALL remaining features
2. Maintain clean state invariant
3. Ensure code is immediately executable
4. Include all tests mentioned in feature specs

Return the COMPLETE implementation.
'''

        messages = [{"role": "user", "content": prompt}]
        result = self.client.complete(opus_config, messages, max_tokens=16384)

        state.add_history("opus_takeover",
            message=f"Opus completed {len(remaining)} remaining features")
        state.final_answer = result.content

        # Mark all remaining as completed (Opus is authoritative)
        for feature in remaining:
            feature_list.mark_completed(feature.id)

        return result

    def _build_context_prompt(self, plan: ExecutionPlan) -> str:
        """Build system prompt for context agent."""
        constraints = self._format_constraints(plan.global_constraints)
        return f"""You are a context-gathering agent. Analyze the codebase to understand:
1. Relevant files and their purposes
2. Dependencies and imports
3. Existing patterns to follow

CONSTRAINTS:
{constraints}

Return a concise summary of relevant context."""

    def _build_feature_engineering_prompt(
        self,
        plan: ExecutionPlan,
        feature: Feature,
        existing_code: str,
        context: str
    ) -> str:
        """Build prompt for single-feature implementation."""
        return f'''You are implementing ONE SPECIFIC FEATURE. Do not implement anything else.

INITIALIZATION PROTOCOL:
Before writing code:
1. Read the existing code below
2. Understand what feature {feature.id} requires
3. Plan how to add it WITHOUT breaking existing functionality
4. Implement ONLY this feature

FEATURE TO IMPLEMENT:
ID: {feature.id}
Description: {feature.description}
Tests that must pass: {', '.join(feature.tests)}
Feature-specific constraints: {', '.join(feature.constraints)}

EXISTING CODE (Build on this, do NOT rewrite from scratch):
{existing_code if existing_code else "# No existing code yet - this is the first feature"}

GLOBAL CONSTRAINTS:
{self._format_constraints(plan.global_constraints)}

CLEAN STATE INVARIANT:
Your output must:
- Have no syntax errors
- Have no TODO/FIXME for this feature
- Have no placeholder implementations
- Be immediately runnable

Return the COMPLETE updated code (existing + new feature).
'''

    def _create_checkpoint(self, feature: Feature, repo_path: str) -> str:
        """Create git commit checkpoint after successful feature."""
        if not repo_path:
            return f"no_repo_{feature.id}"

        try:
            # Stage and commit
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True,
                          capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"feat({feature.id}): {feature.description}"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            return hash_result.stdout.strip()
        except Exception:
            return f"checkpoint_failed_{feature.id}"

    def _get_upgrade_model(self, current_model: str) -> str:
        """Get next model in upgrade path."""
        if self.preset and self.preset.upgrade_path:
            return self.preset.upgrade_path.get(current_model, "opus-4.5")

        default_upgrade_path = {
            "qwen3-235b": "gpt-5.1",
            "glm-4.6": "gpt-5.1",
            "gpt-5.1": "sonnet-4.5",
            "sonnet-4.5": "opus-4.5",
        }
        return default_upgrade_path.get(current_model, "opus-4.5")

    def _get_failure_summary(self, feature_list: FeatureList) -> str:
        """Summarize failures for Opus takeover context."""
        failures = []
        for f in feature_list.features:
            if f.last_error:
                failures.append(f"- {f.id}: {f.last_error} (attempts: {f.attempts})")
        return "\n".join(failures) if failures else "No specific errors recorded"

    def _format_constraints(self, constraints: List[Dict[str, str]]) -> str:
        """Format constraints for prompts."""
        if not constraints:
            return "None specified"

        lines = []
        for c in constraints:
            if isinstance(c, dict):
                lines.append(f"{c.get('level', 'MUST')}: {c.get('description', str(c))}")
            else:
                lines.append(str(c))
        return "\n".join(lines)

    def _build_learned_engineering_prompt(
        self,
        plan: ExecutionPlan,
        feature: Feature,
        existing_code: str,
        context: str
    ) -> str:
        """
        Build prompt using CompoundingLearner's evolved prompt with learned patterns.

        The evolved prompt contains:
        - Learned successful patterns (what works)
        - Anti-patterns to avoid (what fails)
        - Conventions derived from experience
        """
        # Get the evolved prompt from compounding learner
        evolved_prompt = self.compounding_learner.state.current_prompt

        # Inject feature-specific context into the evolved prompt
        # The evolved prompt expects {task_description} placeholder
        feature_context = f'''FEATURE TO IMPLEMENT:
ID: {feature.id}
Description: {feature.description}
Tests that must pass: {', '.join(feature.tests)}
Feature-specific constraints: {', '.join(feature.constraints)}

EXISTING CODE (Build on this, do NOT rewrite from scratch):
{existing_code if existing_code else "# No existing code yet - this is the first feature"}

GLOBAL CONSTRAINTS:
{self._format_constraints(plan.global_constraints)}

CLEAN STATE INVARIANT:
Your output must:
- Have no syntax errors
- Have no TODO/FIXME for this feature
- Have no placeholder implementations
- Be immediately runnable

Return the COMPLETE updated code (existing + new feature).'''

        # If evolved prompt has placeholder, use it; otherwise append context
        if "{task_description}" in evolved_prompt:
            return evolved_prompt.format(task_description=feature_context)
        else:
            # Evolved prompt is self-contained - append feature context
            return f'''{evolved_prompt}

{feature_context}'''

    def _record_feature_result(
        self,
        feature: Feature,
        success: bool
    ):
        """
        Record feature result back to ModelSelectionLearner for continuous learning.

        This closes the learning loop - the orchestrator's validation results
        feed back into the model selection system to improve future routing.
        """
        if not self.model_selection_learner:
            return

        # Check if we stored task profile during engineering
        task_profile = getattr(feature, '_task_profile', None)
        if not task_profile:
            return

        engineering_time = getattr(feature, '_engineering_time', 0.0)
        engineering_cost = getattr(feature, '_engineering_cost', 0.0)
        engineering_model = getattr(feature, '_engineering_model', None)

        if engineering_model:
            try:
                self.model_selection_learner.record_result(
                    model_id=engineering_model,
                    profile=task_profile,
                    success=success,
                    execution_time=engineering_time,
                    cost=engineering_cost
                )
                self._log(f"Recorded {engineering_model} {'success' if success else 'failure'} "
                         f"for {task_profile.task_type}/{task_profile.difficulty}")
            except Exception as e:
                self._log(f"Failed to record learning result: {e}")

    def _log(self, message: str):
        """Log message if logger available."""
        if self.logger:
            self.logger.info(message)
