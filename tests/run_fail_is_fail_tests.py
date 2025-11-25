#!/usr/bin/env python
"""
Direct test runner for FAIL IS FAIL tests.
Avoids pytest path conflicts from SWE-bench workspace.
"""
import sys
import os
import traceback

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock


def print_test(name, passed, details=""):
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {name}")
    if details and not passed:
        print(f"         {details}")


def run_tests():
    print("\n" + "=" * 70)
    print("FAIL IS FAIL POLICY - Test Results")
    print("=" * 70)

    passed = 0
    failed = 0

    # Import after path setup
    from alo.agentic_loops.core.exceptions import (
        ALOError,
        ClientInitializationError,
        AgentExecutionError,
        ToolRegistryRequiredError,
    )
    from alo.agentic_loops.core.state import LoopState
    from alo.agentic_loops.core.orchestrator import ALOOrchestrator
    from alo.agentic_loops.engineering_loop.agent import EngineeringLoopAgent
    from alo.agentic_loops.review_loop.agent import ReviewLoopAgent
    from main import _safe_client

    # =========================================================================
    # TEST GROUP 1: Client Initialization - No More Silent StubClient
    # =========================================================================
    print("\n--- Group 1: Client Initialization Failures ---")

    # Test 1.1: Client init failure raises exception
    try:
        def failing_factory():
            raise ValueError("Missing API key: OPENAI_API_KEY not set")

        try:
            _safe_client(failing_factory, name="repro")
            print_test("Client init failure raises exception", False, "No exception raised!")
            failed += 1
        except ClientInitializationError as e:
            if "repro" in str(e) and "Missing API key" in str(e.original_error):
                print_test("Client init failure raises exception", True)
                passed += 1
            else:
                print_test("Client init failure raises exception", False, f"Wrong message: {e}")
                failed += 1
    except Exception as e:
        print_test("Client init failure raises exception", False, f"Unexpected: {e}")
        failed += 1

    # Test 1.2: Original error is preserved
    try:
        original = ConnectionError("Network unreachable")

        def failing_factory():
            raise original

        try:
            _safe_client(failing_factory, name="context")
            print_test("Original error is preserved", False, "No exception raised!")
            failed += 1
        except ClientInitializationError as e:
            if e.original_error is original and e.__cause__ is original:
                print_test("Original error is preserved", True)
                passed += 1
            else:
                print_test("Original error is preserved", False, "Error not preserved properly")
                failed += 1
    except Exception as e:
        print_test("Original error is preserved", False, f"Unexpected: {e}")
        failed += 1

    # Test 1.3: Successful init still works
    try:
        mock_client = MagicMock()
        result = _safe_client(lambda: mock_client, name="test")
        if result is mock_client:
            print_test("Successful init returns client", True)
            passed += 1
        else:
            print_test("Successful init returns client", False, "Wrong client returned")
            failed += 1
    except Exception as e:
        print_test("Successful init returns client", False, f"Unexpected: {e}")
        failed += 1

    # =========================================================================
    # TEST GROUP 2: Agent Execution - No More TypeError Masking
    # =========================================================================
    print("\n--- Group 2: Agent Execution Errors ---")

    # Test 2.1: Agent without run method raises error
    try:
        class BadAgent:
            pass

        orchestrator = ALOOrchestrator(
            context_agent=BadAgent(),
            repro_agent=MagicMock(),
            engineering_agent=MagicMock(),
            review_agent=MagicMock(),
        )
        state = LoopState(issue_description="test", repo_path="/tmp")

        try:
            orchestrator._call_agent(BadAgent(), state, "bad_agent")
            print_test("Agent without run() raises error", False, "No exception raised!")
            failed += 1
        except AgentExecutionError as e:
            if "bad_agent" in str(e) and "run" in str(e).lower():
                print_test("Agent without run() raises error", True)
                passed += 1
            else:
                print_test("Agent without run() raises error", False, f"Wrong message: {e}")
                failed += 1
    except Exception as e:
        print_test("Agent without run() raises error", False, f"Unexpected: {e}")
        traceback.print_exc()
        failed += 1

    # Test 2.2: Bug in agent code raises error
    try:
        class BuggyAgent:
            def run(self, state, tool_registry=None):
                return state.nonexistent_attribute  # AttributeError!

        orchestrator = ALOOrchestrator(
            context_agent=BuggyAgent(),
            repro_agent=MagicMock(),
            engineering_agent=MagicMock(),
            review_agent=MagicMock(),
        )
        state = LoopState(issue_description="test", repo_path="/tmp")

        try:
            orchestrator._call_agent(BuggyAgent(), state, "buggy_agent")
            print_test("Bug in agent raises error", False, "No exception raised!")
            failed += 1
        except AgentExecutionError as e:
            if "buggy_agent" in str(e) and isinstance(e.original_error, AttributeError):
                print_test("Bug in agent raises error", True)
                passed += 1
            else:
                print_test("Bug in agent raises error", False, f"Wrong error type: {e}")
                failed += 1
    except Exception as e:
        print_test("Bug in agent raises error", False, f"Unexpected: {e}")
        traceback.print_exc()
        failed += 1

    # Test 2.3: Signature detection works correctly
    try:
        received_args = {}

        class AgentWithToolRegistry:
            def run(self, state, tool_registry=None):
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

        if received_args.get('tool_registry') is mock_tool_registry:
            print_test("Signature detection passes tool_registry", True)
            passed += 1
        else:
            print_test("Signature detection passes tool_registry", False, "tool_registry not passed")
            failed += 1
    except Exception as e:
        print_test("Signature detection passes tool_registry", False, f"Unexpected: {e}")
        traceback.print_exc()
        failed += 1

    # =========================================================================
    # TEST GROUP 3: Repro Script - No More Optimistic Success
    # =========================================================================
    print("\n--- Group 3: Repro Script Execution ---")

    # Test 3.1: Missing tool_registry raises error
    try:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "patch content"}

        mock_review = MagicMock(spec=ReviewLoopAgent)
        mock_review.review_patch.return_value = True

        agent = EngineeringLoopAgent(
            model_client=mock_client,
            review_agent=mock_review,
            repro_runner=None,
            max_attempts=1,
        )

        state = LoopState(issue_description="test", repo_path="/tmp")
        state.relevant_files = []
        state.context_summary = "test context"
        state.repro_script_content = "print('test')"

        try:
            agent.run(state, tool_registry=None)
            print_test("Missing tool_registry raises error", False, "No exception raised!")
            failed += 1
        except ToolRegistryRequiredError as e:
            if "run_repro" in str(e):
                print_test("Missing tool_registry raises error", True)
                passed += 1
            else:
                print_test("Missing tool_registry raises error", False, f"Wrong message: {e}")
                failed += 1
    except Exception as e:
        print_test("Missing tool_registry raises error", False, f"Unexpected: {e}")
        traceback.print_exc()
        failed += 1

    # Test 3.2: Custom repro_runner still works
    try:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "patch content"}

        mock_review = MagicMock(spec=ReviewLoopAgent)
        mock_review.review_patch.return_value = True

        runner_called = []

        def custom_runner(script_content):
            runner_called.append(script_content)
            return True

        agent = EngineeringLoopAgent(
            model_client=mock_client,
            review_agent=mock_review,
            repro_runner=custom_runner,
            max_attempts=1,
        )

        state = LoopState(issue_description="test", repo_path="/tmp")
        state.relevant_files = []
        state.context_summary = "test context"
        state.repro_script_content = "print('test')"

        result = agent.run(state, tool_registry=None)

        if len(runner_called) == 1 and result.repro_success is True:
            print_test("Custom repro_runner still works", True)
            passed += 1
        else:
            print_test("Custom repro_runner still works", False, f"Runner calls: {len(runner_called)}, success: {result.repro_success}")
            failed += 1
    except Exception as e:
        print_test("Custom repro_runner still works", False, f"Unexpected: {e}")
        traceback.print_exc()
        failed += 1

    # =========================================================================
    # TEST GROUP 4: File Read Errors - No More Silent Skipping
    # =========================================================================
    print("\n--- Group 4: File Read Error Tracking ---")

    try:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "patch"}

        mock_review = MagicMock(spec=ReviewLoopAgent)
        mock_review.review_patch.return_value = True

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
            repro_runner=lambda x: True,
            max_attempts=1,
        )

        state = LoopState(issue_description="test", repo_path="/tmp")
        state.relevant_files = ["good.py", "missing.py", "another_good.py"]
        state.context_summary = "test"
        state.repro_script_content = "print('test')"

        context = agent._gather_context(mock_tool_registry, state)

        # Good files should be in context
        has_good_files = "good.py" in context and "another_good.py" in context

        # Failed file should be tracked in history (uses "step" key, not "event")
        history_entry = next(
            (h for h in state.history if h.get("step") == "context_gather_warnings"),
            None
        )
        has_warning = (
            history_entry is not None
            and len(history_entry.get("failed_files", [])) == 1
            and history_entry["failed_files"][0]["file"] == "missing.py"
        )

        if has_good_files and has_warning:
            print_test("File read errors tracked in history", True)
            passed += 1
        else:
            print_test("File read errors tracked in history", False,
                       f"has_good_files={has_good_files}, has_warning={has_warning}")
            failed += 1
    except Exception as e:
        print_test("File read errors tracked in history", False, f"Unexpected: {e}")
        traceback.print_exc()
        failed += 1

    # =========================================================================
    # TEST GROUP 5: Exception Hierarchy
    # =========================================================================
    print("\n--- Group 5: Exception Hierarchy ---")

    try:
        exceptions = [
            ClientInitializationError("test", ValueError("test")),
            AgentExecutionError("test", ValueError("test")),
            ToolRegistryRequiredError("test"),
        ]

        all_inherit = all(isinstance(e, ALOError) for e in exceptions)

        if all_inherit:
            print_test("All exceptions inherit from ALOError", True)
            passed += 1
        else:
            print_test("All exceptions inherit from ALOError", False, "Some don't inherit")
            failed += 1
    except Exception as e:
        print_test("All exceptions inherit from ALOError", False, f"Unexpected: {e}")
        failed += 1

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    total = passed + failed
    print(f"SUMMARY: {passed}/{total} tests passed")

    if failed > 0:
        print(f"\n❌ {failed} test(s) FAILED")
        return 1
    else:
        print(f"\n✅ All {passed} tests PASSED - FAIL IS FAIL policy working!")
        return 0


if __name__ == "__main__":
    sys.exit(run_tests())
