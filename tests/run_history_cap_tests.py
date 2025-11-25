#!/usr/bin/env python
"""
Direct test runner for History Cap tests.

Demonstrates:
- BEFORE: Unbounded history growth, potential memory exhaustion
- AFTER: History capped at max_history, oldest entries pruned
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_test(name, passed, details=""):
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {name}")
    if details and not passed:
        print(f"         {details}")


def run_tests():
    print("\n" + "=" * 70)
    print("HISTORY CAP - Test Results")
    print("=" * 70)

    passed = 0
    failed = 0

    from alo.agentic_loops.core.state import LoopState, DEFAULT_MAX_HISTORY

    # =========================================================================
    # TEST GROUP 1: Default Behavior
    # =========================================================================
    print("\n--- Group 1: Default Behavior ---")

    # Test 1.1: Default max_history is 100
    try:
        state = LoopState(issue_description="test", repo_path="/tmp")
        if state.max_history == DEFAULT_MAX_HISTORY == 100:
            print_test("Default max_history is 100", True)
            passed += 1
        else:
            print_test("Default max_history is 100", False, f"Got {state.max_history}")
            failed += 1
    except Exception as e:
        print_test("Default max_history is 100", False, str(e))
        failed += 1

    # Test 1.2: History starts empty
    try:
        state = LoopState(issue_description="test", repo_path="/tmp")
        if len(state.history) == 0 and state._history_truncated_count == 0:
            print_test("History starts empty with no truncation", True)
            passed += 1
        else:
            print_test("History starts empty with no truncation", False)
            failed += 1
    except Exception as e:
        print_test("History starts empty with no truncation", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 2: History Capping
    # =========================================================================
    print("\n--- Group 2: History Capping ---")

    # Test 2.1: History stays within limit
    try:
        state = LoopState(issue_description="test", repo_path="/tmp", max_history=10)

        # Add 15 entries
        for i in range(15):
            state.add_history(f"step_{i}", value=i)

        # Should be capped at 10
        if len(state.history) == 10:
            print_test("History capped at max_history", True)
            passed += 1
        else:
            print_test("History capped at max_history", False, f"Got {len(state.history)}")
            failed += 1
    except Exception as e:
        print_test("History capped at max_history", False, str(e))
        failed += 1

    # Test 2.2: Oldest entries are removed (FIFO)
    try:
        state = LoopState(issue_description="test", repo_path="/tmp", max_history=5)

        # Add 10 entries (0-9)
        for i in range(10):
            state.add_history(f"step_{i}", value=i)

        # Should have entries 5-9 (most recent), plus truncation marker
        # First entry should be truncation marker
        has_marker = state.history[0].get("step") == "_history_truncated"

        # Last entry should be step_9
        last_is_9 = state.history[-1].get("step") == "step_9"

        if has_marker and last_is_9:
            print_test("Oldest entries removed (FIFO), newest kept", True)
            passed += 1
        else:
            print_test("Oldest entries removed (FIFO), newest kept", False,
                       f"marker={has_marker}, last={state.history[-1].get('step')}")
            failed += 1
    except Exception as e:
        print_test("Oldest entries removed (FIFO), newest kept", False, str(e))
        failed += 1

    # Test 2.3: Truncation marker tracks count
    try:
        state = LoopState(issue_description="test", repo_path="/tmp", max_history=5)

        # Add 20 entries
        for i in range(20):
            state.add_history(f"step_{i}", value=i)

        marker = state.history[0]
        # Should have truncated 15 entries (20 - 5 = 15, but marker takes 1 slot)
        # Actually: 20 entries added, cap is 5, so 15 truncated
        expected_truncated = 15

        if marker.get("step") == "_history_truncated" and marker.get("truncated_count") >= expected_truncated:
            print_test("Truncation marker tracks total truncated count", True)
            passed += 1
        else:
            print_test("Truncation marker tracks total truncated count", False,
                       f"truncated_count={marker.get('truncated_count')}, expected>={expected_truncated}")
            failed += 1
    except Exception as e:
        print_test("Truncation marker tracks total truncated count", False, str(e))
        failed += 1

    # Test 2.4: _history_truncated_count accumulates
    try:
        state = LoopState(issue_description="test", repo_path="/tmp", max_history=5)

        # Add 10 entries
        for i in range(10):
            state.add_history(f"step_{i}")

        first_count = state._history_truncated_count

        # Add 10 more
        for i in range(10, 20):
            state.add_history(f"step_{i}")

        second_count = state._history_truncated_count

        if second_count > first_count:
            print_test("Truncation count accumulates over time", True)
            passed += 1
        else:
            print_test("Truncation count accumulates over time", False,
                       f"first={first_count}, second={second_count}")
            failed += 1
    except Exception as e:
        print_test("Truncation count accumulates over time", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 3: Unlimited History
    # =========================================================================
    print("\n--- Group 3: Unlimited History ---")

    # Test 3.1: max_history=0 means unlimited
    try:
        state = LoopState(issue_description="test", repo_path="/tmp", max_history=0)

        # Add 200 entries
        for i in range(200):
            state.add_history(f"step_{i}")

        if len(state.history) == 200 and state._history_truncated_count == 0:
            print_test("max_history=0 allows unlimited history", True)
            passed += 1
        else:
            print_test("max_history=0 allows unlimited history", False,
                       f"size={len(state.history)}, truncated={state._history_truncated_count}")
            failed += 1
    except Exception as e:
        print_test("max_history=0 allows unlimited history", False, str(e))
        failed += 1

    # Test 3.2: Negative max_history treated as unlimited
    try:
        state = LoopState(issue_description="test", repo_path="/tmp", max_history=-1)

        for i in range(50):
            state.add_history(f"step_{i}")

        if len(state.history) == 50:
            print_test("Negative max_history treated as unlimited", True)
            passed += 1
        else:
            print_test("Negative max_history treated as unlimited", False)
            failed += 1
    except Exception as e:
        print_test("Negative max_history treated as unlimited", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 4: History Stats
    # =========================================================================
    print("\n--- Group 4: History Stats ---")

    # Test 4.1: get_history_stats() returns correct info
    try:
        state = LoopState(issue_description="test", repo_path="/tmp", max_history=10)

        for i in range(15):
            state.add_history(f"step_{i}")

        stats = state.get_history_stats()

        checks = [
            stats["current_size"] == 10,
            stats["max_size"] == 10,
            stats["truncated_count"] > 0,
            stats["is_truncated"] is True,
        ]

        if all(checks):
            print_test("get_history_stats() returns correct info", True)
            passed += 1
        else:
            print_test("get_history_stats() returns correct info", False, f"stats={stats}")
            failed += 1
    except Exception as e:
        print_test("get_history_stats() returns correct info", False, str(e))
        failed += 1

    # Test 4.2: Stats show not truncated when within limit
    try:
        state = LoopState(issue_description="test", repo_path="/tmp", max_history=10)

        for i in range(5):
            state.add_history(f"step_{i}")

        stats = state.get_history_stats()

        if stats["is_truncated"] is False and stats["truncated_count"] == 0:
            print_test("Stats correctly show no truncation when within limit", True)
            passed += 1
        else:
            print_test("Stats correctly show no truncation when within limit", False)
            failed += 1
    except Exception as e:
        print_test("Stats correctly show no truncation when within limit", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 5: Clear History
    # =========================================================================
    print("\n--- Group 5: Clear History ---")

    # Test 5.1: clear_history() resets everything
    try:
        state = LoopState(issue_description="test", repo_path="/tmp", max_history=5)

        for i in range(20):
            state.add_history(f"step_{i}")

        state.clear_history()

        if len(state.history) == 0 and state._history_truncated_count == 0:
            print_test("clear_history() resets history and truncation count", True)
            passed += 1
        else:
            print_test("clear_history() resets history and truncation count", False)
            failed += 1
    except Exception as e:
        print_test("clear_history() resets history and truncation count", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 6: Memory Efficiency
    # =========================================================================
    print("\n--- Group 6: Memory Efficiency ---")

    # Test 6.1: Large number of entries doesn't grow memory
    try:
        state = LoopState(issue_description="test", repo_path="/tmp", max_history=50)

        # Add 10,000 entries
        for i in range(10000):
            state.add_history(f"step_{i}", data="x" * 100)

        # Should still only have 50 entries
        size_ok = len(state.history) == 50
        truncated_ok = state._history_truncated_count > 9900

        if size_ok and truncated_ok:
            print_test("10,000 entries stays at 50 (memory bounded)", True)
            passed += 1
        else:
            print_test("10,000 entries stays at 50 (memory bounded)", False,
                       f"size={len(state.history)}, truncated={state._history_truncated_count}")
            failed += 1
    except Exception as e:
        print_test("10,000 entries stays at 50 (memory bounded)", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 7: Backward Compatibility
    # =========================================================================
    print("\n--- Group 7: Backward Compatibility ---")

    # Test 7.1: Normal usage still works
    try:
        state = LoopState(issue_description="test", repo_path="/tmp")

        state.add_history("context", files=["a.py", "b.py"])
        state.add_history("repro", script="print('test')")
        state.add_history("engineering", patch="diff...")

        found_steps = [h.get("step") for h in state.history]
        expected = ["context", "repro", "engineering"]

        if found_steps == expected:
            print_test("Normal add_history usage still works", True)
            passed += 1
        else:
            print_test("Normal add_history usage still works", False, f"Got {found_steps}")
            failed += 1
    except Exception as e:
        print_test("Normal add_history usage still works", False, str(e))
        failed += 1

    # Test 7.2: History details preserved
    try:
        state = LoopState(issue_description="test", repo_path="/tmp")

        state.add_history("test_step", value=42, name="test", nested={"key": "value"})

        entry = state.history[0]
        checks = [
            entry.get("step") == "test_step",
            entry.get("value") == 42,
            entry.get("name") == "test",
            entry.get("nested", {}).get("key") == "value",
        ]

        if all(checks):
            print_test("History entry details preserved correctly", True)
            passed += 1
        else:
            print_test("History entry details preserved correctly", False)
            failed += 1
    except Exception as e:
        print_test("History entry details preserved correctly", False, str(e))
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
        print(f"\n✅ All {passed} tests PASSED - History Cap working!")
        return 0


if __name__ == "__main__":
    sys.exit(run_tests())
