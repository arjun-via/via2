"""
=============================================================================
SCRIPT NAME: test_fail_is_fail.py
=============================================================================

Tests demonstrating the "FAIL IS FAIL" policy improvements.

These tests show the difference between:
- BEFORE: Silent fallbacks that masked errors and returned fake responses
- AFTER: Explicit exceptions with clear, actionable error messages

Run with: pytest tests/test_fail_is_fail.py -v

VERSION: 1.0
LAST UPDATED: 2025-01-24
=============================================================================
"""

import pytest
from unittest.mock import MagicMock, patch

from alo.agentic_loops.core.exceptions import (
    ALOError,
    ClientInitializationError,
    AgentExecutionError,
    ToolRegistryRequiredError,
    FileReadError,
)
from alo.agentic_loops.core.state import LoopState
from alo.agentic_loops.core.orchestrator import ALOOrchestrator
from alo.agentic_loops.engineering_loop.agent import EngineeringLoopAgent
from alo.agentic_loops.review_loop.agent import ReviewLoopAgent


# =============================================================================
# TEST 1: Client Initialization - No More Silent StubClient
# =============================================================================

class TestClientInitializationFailure:
    """
    BEFORE (bad behavior):
    - _safe_client() caught exceptions and returned StubClient
    - StubClient.chat() returned fake "stub response from {name}"
    - Pipeline appeared to work but produced garbage output
    - No indication anything was wrong

    AFTER (correct behavior):
    - _safe_client() raises ClientInitializationError
    - Error message includes client name and original error
    - Pipeline fails fast with actionable diagnostic
    """

    def test_client_init_failure_raises_exception(self):
        """Verify that client initialization failure raises explicit error."""
        from main import _safe_client

        def failing_factory():
            raise ValueError("Missing API key: OPENAI_API_KEY not set")

        with pytest.raises(ClientInitializationError) as exc_info:
            _safe_client(failing_factory, name="repro")

        # Verify error message is actionable
        error = exc_info.value
        assert error.client_name == "repro"
        assert "Missing API key" in str(error.original_error)
        assert "repro" in str(error)
        assert "Check your API keys" in str(error)

    def test_client_init_failure_preserves_original_error(self):
        """Verify original exception is preserved in the chain."""
        from main import _safe_client

        original = ConnectionError("Network unreachable")

        def failing_factory():
            raise original

        with pytest.raises(ClientInitializationError) as exc_info:
            _safe_client(failing_factory, name="context")

        # The original error should be accessible
        assert exc_info.value.original_error is original
        assert exc_info.value.__cause__ is original

    def test_successful_client_init_returns_client(self):
        """Verify successful initialization still works."""
        from main import _safe_client

        mock_client = MagicMock()

        def success_factory():
            return mock_client

        result = _safe_client(success_factory, name="test")
        assert result is mock_client


# =============================================================================
# TEST 2: Agent Execution - No More TypeError Masking
# =============================================================================

class TestAgentExecutionErrors:
    """
    BEFORE (bad behavior):
    - _call_agent() caught TypeError and tried alternate signature
    - This masked real TypeErrors in agent code
    - Bugs in agents could go undetected

    AFTER (correct behavior):
    - Uses introspection to determine correct signature upfront
    - Real exceptions from agent code are wrapped in AgentExecutionError
    - Actual bugs are surfaced immediately
    """

    def test_agent_without_run_method_raises_error(self):
        """Agents must have a run() method."""
        class BadAgent:
            pass  # No run method!

        orchestrator = ALOOrchestrator(
            context_agent=BadAgent(),
            repro_agent=MagicMock(),
            engineering_agent=MagicMock(),
            review_agent=MagicMock(),
        )

        state = LoopState(issue_description="test", repo_path="/tmp")

        with pytest.raises(AgentExecutionError) as exc_info:
            orchestrator._call_agent(BadAgent(), state, "bad_agent")

        assert "bad_agent" in str(exc_info.value)
        assert "no 'run' method" in str(exc_info.value)

    def test_agent_with_bug_raises_error(self):
        """Real bugs in agent code should be surfaced."""
        class BuggyAgent:
            def run(self, state, tool_registry=None):
                # This is a real bug - accessing nonexistent attribute
                return state.nonexistent_attribute  # AttributeError!

        orchestrator = ALOOrchestrator(
            context_agent=BuggyAgent(),
            repro_agent=MagicMock(),
            engineering_agent=MagicMock(),
            review_agent=MagicMock(),
        )

        state = LoopState(issue_description="test", repo_path="/tmp")

        with pytest.raises(AgentExecutionError) as exc_info:
            orchestrator._call_agent(BuggyAgent(), state, "buggy_agent")

        assert "buggy_agent" in str(exc_info.value)
        assert isinstance(exc_info.value.original_error, AttributeError)

    def test_agent_signature_detection_with_tool_registry(self):
        """Agent accepting tool_registry should receive it."""
        received_args = {}

        class AgentWithToolRegistry:
            def run(self, state, tool_registry=None):
                received_args['state'] = state
                received_args['tool_registry'] = tool_registry
                return state

        mock_tool_registry = MagicMock()
        orchestrator = ALOOrchestrator(
            context_agent=AgentWithToolRegistry(),
            repro_agent=MagicMock(),
            engineering_agent=MagicMock(),
            review_agent=MagicMock(),
            tool_registry=mock_tool_registry,
        )

        state = LoopState(issue_description="test", repo_path="/tmp")
        orchestrator._call_agent(AgentWithToolRegistry(), state, "test_agent")

        assert received_args['tool_registry'] is mock_tool_registry

    def test_agent_signature_detection_without_tool_registry(self):
        """Agent not accepting tool_registry should work without it."""
        received_args = {}

        class AgentWithoutToolRegistry:
            def run(self, state):  # No tool_registry param
                received_args['state'] = state
                return state

        orchestrator = ALOOrchestrator(
            context_agent=AgentWithoutToolRegistry(),
            repro_agent=MagicMock(),
            engineering_agent=MagicMock(),
            review_agent=MagicMock(),
            tool_registry=MagicMock(),
        )

        state = LoopState(issue_description="test", repo_path="/tmp")
        # Should not raise - introspection detects signature
        orchestrator._call_agent(AgentWithoutToolRegistry(), state, "test_agent")

        assert received_args['state'] is state


# =============================================================================
# TEST 3: Repro Script Execution - No More Optimistic Success
# =============================================================================

class TestReproScriptExecution:
    """
    BEFORE (bad behavior):
    - If tool_registry was None, _run_repro() set repro_success = True
    - This meant untested code was marked as "passing"
    - False confidence in fixes that were never verified

    AFTER (correct behavior):
    - If tool_registry is None and no repro_runner, raises ToolRegistryRequiredError
    - Cannot claim success without actually testing
    - Forces proper configuration before running
    """

    def test_missing_tool_registry_raises_error(self):
        """Cannot run repro without tool_registry or repro_runner."""
        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "patch content"}

        mock_review = MagicMock(spec=ReviewLoopAgent)
        mock_review.review_patch.return_value = True

        agent = EngineeringLoopAgent(
            model_client=mock_client,
            review_agent=mock_review,
            repro_runner=None,  # No custom runner
            max_attempts=1,
        )

        state = LoopState(issue_description="test", repo_path="/tmp")
        state.relevant_files = []
        state.context_summary = "test context"
        state.repro_script_content = "print('test')"

        with pytest.raises(ToolRegistryRequiredError) as exc_info:
            agent.run(state, tool_registry=None)  # No tool_registry!

        assert "run_repro" in str(exc_info.value)
        assert "tool_registry" in str(exc_info.value).lower()

    def test_custom_repro_runner_still_works(self):
        """Custom repro_runner should still work as before."""
        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "patch content"}

        mock_review = MagicMock(spec=ReviewLoopAgent)
        mock_review.review_patch.return_value = True

        # Custom runner that actually tests
        runner_called = []
        def custom_runner(script_content):
            runner_called.append(script_content)
            return True  # Test passed

        agent = EngineeringLoopAgent(
            model_client=mock_client,
            review_agent=mock_review,
            repro_runner=custom_runner,  # Provided custom runner
            max_attempts=1,
        )

        state = LoopState(issue_description="test", repo_path="/tmp")
        state.relevant_files = []
        state.context_summary = "test context"
        state.repro_script_content = "print('test')"

        # Should work fine with custom runner, even without tool_registry
        result = agent.run(state, tool_registry=None)

        assert len(runner_called) == 1
        assert result.repro_success is True


# =============================================================================
# TEST 4: File Read Errors - No More Silent Skipping
# =============================================================================

class TestFileReadErrorTracking:
    """
    BEFORE (bad behavior):
    - _gather_context() silently caught all exceptions and continued
    - Failed file reads were invisible
    - Context could be incomplete without anyone knowing

    AFTER (correct behavior):
    - File read errors are tracked in state.history
    - Successful files are still processed
    - Failures are visible for debugging
    """

    def test_file_read_errors_tracked_in_history(self):
        """Failed file reads should be recorded in state history."""
        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "patch"}

        mock_review = MagicMock(spec=ReviewLoopAgent)
        mock_review.review_patch.return_value = True

        # Mock tool_registry that fails on some files
        mock_tool_registry = MagicMock()
        def read_file_side_effect(path):
            if "missing" in path:
                raise FileNotFoundError(f"File not found: {path}")
            return "file content"

        mock_tool_registry.read_file.side_effect = read_file_side_effect
        mock_tool_registry.workspace_root = "/tmp/test"

        agent = EngineeringLoopAgent(
            model_client=mock_client,
            review_agent=mock_review,
            repro_runner=lambda x: True,  # Skip actual repro
            max_attempts=1,
        )

        state = LoopState(issue_description="test", repo_path="/tmp")
        state.relevant_files = ["good.py", "missing.py", "another_good.py"]
        state.context_summary = "test"
        state.repro_script_content = "print('test')"

        # Gather context
        context = agent._gather_context(mock_tool_registry, state)

        # Good files should be in context
        assert "good.py" in context
        assert "another_good.py" in context

        # Failed file should be tracked in history (uses "step" key, not "event")
        history_entry = next(
            (h for h in state.history if h.get("step") == "context_gather_warnings"),
            None
        )
        assert history_entry is not None
        assert len(history_entry["failed_files"]) == 1
        assert history_entry["failed_files"][0]["file"] == "missing.py"
        assert "not found" in history_entry["failed_files"][0]["error"].lower()


# =============================================================================
# TEST 5: Exception Hierarchy
# =============================================================================

class TestExceptionHierarchy:
    """Verify all custom exceptions inherit from ALOError."""

    def test_all_exceptions_inherit_from_alo_error(self):
        """All custom exceptions should be catchable as ALOError."""
        exceptions = [
            ClientInitializationError("test", ValueError("test")),
            AgentExecutionError("test", ValueError("test")),
            ToolRegistryRequiredError("test"),
            FileReadError("test.py", ValueError("test")),
        ]

        for exc in exceptions:
            assert isinstance(exc, ALOError), f"{type(exc).__name__} should inherit from ALOError"

    def test_can_catch_all_alo_errors(self):
        """Should be able to catch all ALO errors with single except clause."""
        def raise_client_error():
            raise ClientInitializationError("test", ValueError("test"))

        def raise_agent_error():
            raise AgentExecutionError("test", ValueError("test"))

        def raise_tool_error():
            raise ToolRegistryRequiredError("test")

        for raiser in [raise_client_error, raise_agent_error, raise_tool_error]:
            try:
                raiser()
            except ALOError:
                pass  # Expected - all should be catchable as ALOError
            else:
                pytest.fail(f"{raiser.__name__} did not raise ALOError")


# =============================================================================
# DEMONSTRATION: Before vs After Comparison
# =============================================================================

class TestBeforeAfterComparison:
    """
    These tests demonstrate the behavioral difference between
    the old (silent fallback) and new (fail-fast) approaches.
    """

    def test_old_behavior_documentation(self):
        """
        DOCUMENTATION: This is how the OLD code behaved (now fixed):

        ```python
        # OLD _safe_client (REMOVED):
        def _safe_client(factory, name: str):
            try:
                return factory()
            except Exception:
                class StubClient:
                    def chat(self, messages, **kwargs):
                        return {"content": f"stub response from {name}"}
                return StubClient()

        # Problem: This code would SILENTLY succeed:
        client = _safe_client(lambda: raise_error(), "test")
        response = client.chat([])  # Returns "stub response from test"
        # No indication anything is wrong!
        ```

        The new code raises ClientInitializationError immediately.
        """
        pass  # This test is documentation only

    def test_new_behavior_fails_fast(self):
        """Verify new behavior fails immediately with clear error."""
        from main import _safe_client

        # This SHOULD fail immediately
        with pytest.raises(ClientInitializationError) as exc_info:
            _safe_client(
                lambda: (_ for _ in ()).throw(ValueError("API key missing")),
                name="test_client"
            )

        # Error message should be helpful
        error_msg = str(exc_info.value)
        assert "test_client" in error_msg
        assert "API key" in error_msg or "Check your" in error_msg
