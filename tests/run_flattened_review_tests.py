#!/usr/bin/env python
"""
Direct test runner for Flattened Review Loop tests.

Demonstrates:
- BEFORE: Review nested inside Engineering (control flow hidden)
- AFTER: Review at orchestrator level (explicit, visible control flow)
"""
import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock


def print_test(name, passed, details=""):
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {name}")
    if details and not passed:
        print(f"         {details}")


def run_tests():
    print("\n" + "=" * 70)
    print("FLATTENED REVIEW LOOP - Test Results")
    print("=" * 70)

    passed = 0
    failed = 0

    from alo.agentic_loops.core.state import LoopState
    from alo.agentic_loops.core.orchestrator import ALOOrchestrator
    from alo.agentic_loops.engineering_loop.agent import EngineeringLoopAgent
    from alo.agentic_loops.review_loop.agent import ReviewLoopAgent

    # =========================================================================
    # TEST GROUP 1: State Has New Fields
    # =========================================================================
    print("\n--- Group 1: State Tracking Fields ---")

    try:
        state = LoopState(issue_description="test", repo_path="/tmp")
        has_fields = (
            hasattr(state, 'current_patch') and
            hasattr(state, 'review_passed') and
            hasattr(state, 'review_feedback')
        )
        if has_fields:
            print_test("State has current_patch, review_passed, review_feedback", True)
            passed += 1
        else:
            print_test("State has current_patch, review_passed, review_feedback", False)
            failed += 1
    except Exception as e:
        print_test("State has current_patch, review_passed, review_feedback", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 2: Engineering Agent Modes
    # =========================================================================
    print("\n--- Group 2: Engineering Agent Modes ---")

    # Test 2.1: Engineering with review_agent=None (flattened mode)
    try:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "def fix(): pass"}

        agent = EngineeringLoopAgent(
            model_client=mock_client,
            review_agent=None,  # Flattened mode
            repro_runner=lambda x: True,
            max_attempts=3,
        )

        state = LoopState(issue_description="test", repo_path="/tmp")
        state.relevant_files = []
        state.context_summary = "test"
        state.repro_script_content = "print('test')"

        result = agent.run(state, tool_registry=None)

        # In flattened mode, should store patch in state.current_patch
        if result.current_patch == "def fix(): pass":
            print_test("Flattened mode stores patch in state.current_patch", True)
            passed += 1
        else:
            print_test("Flattened mode stores patch in state.current_patch", False,
                       f"Got: {result.current_patch[:50]}...")
            failed += 1
    except Exception as e:
        print_test("Flattened mode stores patch in state.current_patch", False, str(e))
        traceback.print_exc()
        failed += 1

    # Test 2.2: Engineering with review_agent (nested mode, backward compatible)
    try:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "def fix(): pass"}

        mock_review = MagicMock(spec=ReviewLoopAgent)
        mock_review.review_patch.return_value = True

        agent = EngineeringLoopAgent(
            model_client=mock_client,
            review_agent=mock_review,  # Nested mode
            repro_runner=lambda x: True,
            max_attempts=3,
        )

        state = LoopState(issue_description="test", repo_path="/tmp")
        state.relevant_files = []
        state.context_summary = "test"
        state.repro_script_content = "print('test')"

        result = agent.run(state, tool_registry=None)

        # In nested mode, review should be called
        if mock_review.review_patch.called:
            print_test("Nested mode calls review_agent.review_patch()", True)
            passed += 1
        else:
            print_test("Nested mode calls review_agent.review_patch()", False)
            failed += 1
    except Exception as e:
        print_test("Nested mode calls review_agent.review_patch()", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 3: Review Agent Standard Interface
    # =========================================================================
    print("\n--- Group 3: Review Agent Standard Interface ---")

    # Test 3.1: ReviewLoopAgent.run() sets state fields
    try:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "PASS - looks good!"}

        agent = ReviewLoopAgent(model_client=mock_client)

        state = LoopState(issue_description="test", repo_path="/tmp")
        state.current_patch = "def fix(): pass"

        result = agent.run(state)

        if result.review_passed is True and result.review_feedback == "":
            print_test("Review PASS sets review_passed=True, clears feedback", True)
            passed += 1
        else:
            print_test("Review PASS sets review_passed=True, clears feedback", False,
                       f"passed={result.review_passed}, feedback='{result.review_feedback}'")
            failed += 1
    except Exception as e:
        print_test("Review PASS sets review_passed=True, clears feedback", False, str(e))
        traceback.print_exc()
        failed += 1

    # Test 3.2: Review FAIL sets feedback for retry
    try:
        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "FAIL - missing error handling for edge case"}

        agent = ReviewLoopAgent(model_client=mock_client)

        state = LoopState(issue_description="test", repo_path="/tmp")
        state.current_patch = "def fix(): pass"

        result = agent.run(state)

        if result.review_passed is False and "missing error handling" in result.review_feedback:
            print_test("Review FAIL sets review_passed=False with feedback", True)
            passed += 1
        else:
            print_test("Review FAIL sets review_passed=False with feedback", False,
                       f"passed={result.review_passed}, feedback='{result.review_feedback[:50]}'")
            failed += 1
    except Exception as e:
        print_test("Review FAIL sets review_passed=False with feedback", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 4: Orchestrator Modes
    # =========================================================================
    print("\n--- Group 4: Orchestrator Modes ---")

    # Test 4.1: Nested mode (default, backward compatible)
    try:
        # All mock agents
        mock_context = MagicMock()
        mock_context.run.return_value = LoopState(issue_description="test", repo_path="/tmp")

        mock_repro = MagicMock()
        def repro_run(state, tool_registry=None):
            state.repro_script_content = "print('test')"
            return state
        mock_repro.run.side_effect = repro_run

        mock_engineering = MagicMock()
        def eng_run(state, tool_registry=None):
            state.current_patch = "fix"
            return state
        mock_engineering.run.side_effect = eng_run

        mock_review = MagicMock()
        mock_review.run.return_value = MagicMock()

        orchestrator = ALOOrchestrator(
            context_agent=mock_context,
            repro_agent=mock_repro,
            engineering_agent=mock_engineering,
            review_agent=mock_review,
            use_flattened_review=False,  # Nested mode
        )

        result = orchestrator.run("test issue", "/tmp")

        # In nested mode, review.run() should NOT be called by orchestrator
        if not mock_review.run.called:
            print_test("Nested mode: orchestrator doesn't call review.run()", True)
            passed += 1
        else:
            print_test("Nested mode: orchestrator doesn't call review.run()", False)
            failed += 1
    except Exception as e:
        print_test("Nested mode: orchestrator doesn't call review.run()", False, str(e))
        traceback.print_exc()
        failed += 1

    # Test 4.2: Flattened mode calls both engineering and review
    try:
        call_order = []

        mock_context = MagicMock()
        def context_run(state, tool_registry=None):
            call_order.append("context")
            return state
        mock_context.run.side_effect = context_run

        mock_repro = MagicMock()
        def repro_run(state, tool_registry=None):
            call_order.append("repro")
            state.repro_script_content = "print('test')"
            return state
        mock_repro.run.side_effect = repro_run

        mock_engineering = MagicMock()
        def eng_run(state, tool_registry=None):
            call_order.append("engineering")
            state.current_patch = "fix"
            state.repro_success = True
            return state
        mock_engineering.run.side_effect = eng_run

        mock_review = MagicMock()
        def review_run(state, tool_registry=None):
            call_order.append("review")
            state.review_passed = True
            return state
        mock_review.run.side_effect = review_run

        orchestrator = ALOOrchestrator(
            context_agent=mock_context,
            repro_agent=mock_repro,
            engineering_agent=mock_engineering,
            review_agent=mock_review,
            use_flattened_review=True,  # Flattened mode
        )

        result = orchestrator.run("test issue", "/tmp")

        expected = ["context", "repro", "engineering", "review"]
        if call_order == expected:
            print_test("Flattened mode: calls context→repro→engineering→review", True)
            passed += 1
        else:
            print_test("Flattened mode: calls context→repro→engineering→review", False,
                       f"Got: {call_order}")
            failed += 1
    except Exception as e:
        print_test("Flattened mode: calls context→repro→engineering→review", False, str(e))
        traceback.print_exc()
        failed += 1

    # Test 4.3: Flattened mode retries on review failure
    try:
        attempt_count = [0]

        mock_context = MagicMock()
        mock_context.run.return_value = LoopState(issue_description="test", repo_path="/tmp")

        mock_repro = MagicMock()
        def repro_run(state, tool_registry=None):
            return state
        mock_repro.run.side_effect = repro_run

        mock_engineering = MagicMock()
        def eng_run(state, tool_registry=None):
            attempt_count[0] += 1
            state.current_patch = f"fix attempt {attempt_count[0]}"
            state.repro_success = True
            return state
        mock_engineering.run.side_effect = eng_run

        mock_review = MagicMock()
        def review_run(state, tool_registry=None):
            # Fail first 2 attempts, pass on 3rd
            if attempt_count[0] < 3:
                state.review_passed = False
                state.review_feedback = "needs more work"
            else:
                state.review_passed = True
            return state
        mock_review.run.side_effect = review_run

        orchestrator = ALOOrchestrator(
            context_agent=mock_context,
            repro_agent=mock_repro,
            engineering_agent=mock_engineering,
            review_agent=mock_review,
            use_flattened_review=True,
            max_review_attempts=5,
        )

        result = orchestrator.run("test issue", "/tmp")

        if attempt_count[0] == 3 and result.review_passed:
            print_test("Flattened mode: retries until review passes", True)
            passed += 1
        else:
            print_test("Flattened mode: retries until review passes", False,
                       f"attempts={attempt_count[0]}, passed={result.review_passed}")
            failed += 1
    except Exception as e:
        print_test("Flattened mode: retries until review passes", False, str(e))
        traceback.print_exc()
        failed += 1

    # =========================================================================
    # TEST GROUP 5: Feedback Propagation
    # =========================================================================
    print("\n--- Group 5: Feedback Propagation ---")

    # Test: Engineering receives feedback on retry
    try:
        prompts_received = []

        mock_client = MagicMock()
        def chat_side_effect(messages, **kwargs):
            prompts_received.append(messages[0]["content"])
            return {"content": "def fix(): pass"}
        mock_client.chat.side_effect = chat_side_effect

        agent = EngineeringLoopAgent(
            model_client=mock_client,
            review_agent=None,  # Flattened mode
            repro_runner=lambda x: True,
        )

        state = LoopState(issue_description="fix bug", repo_path="/tmp")
        state.relevant_files = []
        state.context_summary = "test"
        state.repro_script_content = "print('test')"
        state.review_feedback = "Previous fix had security vulnerability"

        agent.run(state)

        if len(prompts_received) == 1 and "security vulnerability" in prompts_received[0]:
            print_test("Engineering receives review feedback on retry", True)
            passed += 1
        else:
            print_test("Engineering receives review feedback on retry", False,
                       f"Feedback not in prompt: {prompts_received[0][:100] if prompts_received else 'no prompt'}")
            failed += 1
    except Exception as e:
        print_test("Engineering receives review feedback on retry", False, str(e))
        traceback.print_exc()
        failed += 1

    # =========================================================================
    # TEST GROUP 6: History Tracking
    # =========================================================================
    print("\n--- Group 6: History Tracking ---")

    try:
        mock_context = MagicMock()
        mock_context.run.return_value = LoopState(issue_description="test", repo_path="/tmp")

        mock_repro = MagicMock()
        mock_repro.run.side_effect = lambda s, t=None: s

        mock_engineering = MagicMock()
        def eng_run(state, tool_registry=None):
            state.current_patch = "fix"
            state.repro_success = True
            return state
        mock_engineering.run.side_effect = eng_run

        mock_review = MagicMock()
        def review_run(state, tool_registry=None):
            state.review_passed = True
            return state
        mock_review.run.side_effect = review_run

        orchestrator = ALOOrchestrator(
            context_agent=mock_context,
            repro_agent=mock_repro,
            engineering_agent=mock_engineering,
            review_agent=mock_review,
            use_flattened_review=True,
        )

        result = orchestrator.run("test issue", "/tmp")

        # Check for engineering_review_loop in history
        loop_entry = next(
            (h for h in result.history if h.get("step") == "engineering_review_loop"),
            None
        )

        if loop_entry and "attempts" in loop_entry:
            print_test("Flattened mode records engineering_review_loop in history", True)
            passed += 1
        else:
            print_test("Flattened mode records engineering_review_loop in history", False,
                       f"History: {[h.get('step') for h in result.history]}")
            failed += 1
    except Exception as e:
        print_test("Flattened mode records engineering_review_loop in history", False, str(e))
        traceback.print_exc()
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
        print(f"\n✅ All {passed} tests PASSED - Flattened Review Loop working!")
        return 0


if __name__ == "__main__":
    sys.exit(run_tests())
