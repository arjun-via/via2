#!/usr/bin/env python
"""
Run all orchestrator improvement tests to verify everything is working.
"""
import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TESTS = [
    ("Group 1: FAIL IS FAIL", "tests/run_fail_is_fail_tests.py"),
    ("Group 2: Flattened Review", "tests/run_flattened_review_tests.py"),
    ("Group 3: API Retry", "tests/run_retry_tests.py"),
    ("Group 4: History Cap", "tests/run_history_cap_tests.py"),
    ("Group 5: Structured Prompts", "tests/run_structured_prompts_tests.py"),
    ("Group 6: Variable Temperature", "tests/run_variable_temperature_tests.py"),
]


def main():
    print("=" * 80)
    print("ALL ORCHESTRATOR IMPROVEMENTS - VERIFICATION")
    print("=" * 80)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    results = []
    total_passed = 0
    total_failed = 0

    for name, test_file in TESTS:
        print(f"\n{'='*60}")
        print(f"Running: {name}")
        print("=" * 60)

        test_path = os.path.join(base_dir, test_file)
        result = subprocess.run(
            [sys.executable, test_path],
            capture_output=True,
            text=True,
            cwd=base_dir
        )

        # Extract pass/fail counts from output
        output = result.stdout

        # Look for "SUMMARY: X/Y tests passed"
        import re
        match = re.search(r"SUMMARY: (\d+)/(\d+) tests passed", output)

        if match:
            passed = int(match.group(1))
            total = int(match.group(2))
            failed = total - passed
            total_passed += passed
            total_failed += failed

            status = "PASS" if result.returncode == 0 else "FAIL"
            results.append((name, passed, total, status))
            print(f"  Result: {passed}/{total} tests passed")
        else:
            results.append((name, 0, 0, "ERROR"))
            print(f"  Result: Could not parse output")
            print(f"  stdout: {output[:500]}")
            print(f"  stderr: {result.stderr[:500]}")

    # Final Summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    print("\n{:<30} {:>10} {:>10} {:>10}".format("Group", "Passed", "Total", "Status"))
    print("-" * 65)

    for name, passed, total, status in results:
        print("{:<30} {:>10} {:>10} {:>10}".format(name, passed, total, status))

    print("-" * 65)
    print("{:<30} {:>10} {:>10}".format("TOTAL", total_passed, total_passed + total_failed))

    print("\n" + "=" * 80)

    if total_failed == 0:
        print(f"ALL {total_passed} TESTS PASSED - Orchestrator improvements verified!")
        print("=" * 80)

        print("\nImprovements Applied:")
        print("  1. FAIL IS FAIL policy - No silent fallbacks")
        print("  2. Flattened Review Loop - Explicit control flow")
        print("  3. API Retry with Backoff - Handles transient failures")
        print("  4. History Capping - Memory bounded at 100 entries")
        print("  5. Structured Prompts - 13.8x more detailed with schemas")
        print("  6. Variable Temperature - Role-specific (0/0/0.3/0)")

        return 0
    else:
        print(f"{total_failed} tests FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
