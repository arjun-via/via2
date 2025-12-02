"""
=============================================================================
SCRIPT NAME: compare_variants.py
=============================================================================

Comparison Benchmark: opus-optimized vs opus-baseline

INPUT FILES:
- None (uses built-in test tasks)

OUTPUT FILES:
- outputs/comparison_results_YYYY_MM_DD.xlsx: Detailed results
- outputs/comparison_summary.txt: Quick summary

VERSION: 1.0
LAST UPDATED: 2025-11-30

DESCRIPTION:
Runs the same coding tasks on both opus-optimized (meta-orchestrator with
multiple models) and opus-baseline (single Opus 4.5 call) to compare:
- Speed (total time)
- Cost (API cost in USD)
- Quality (code execution pass rate)

This is a pre-benchmark sanity check before running full SWE-bench verified.

DEPENDENCIES:
- pandas
- openpyxl

USAGE:
    python scripts/compare_variants.py --tasks 5

=============================================================================
"""

import sys
import os
import time
import json
import argparse
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

from alo.agentic_loops.opus_orchestrator import (
    MultiProviderClient,
    OpusMetaOrchestrator,
    OpusBaselineRunner,
    get_preset,
    CodeExecutor,
)


# =============================================================================
# TEST TASKS - Coding challenges with increasing difficulty
# =============================================================================

TEST_TASKS = [
    # Easy
    {
        "id": "easy_1",
        "difficulty": "easy",
        "task": "Implement a function `is_palindrome(s: str) -> bool` that checks if a string is a palindrome, ignoring case and non-alphanumeric characters.",
        "test_code": """
assert is_palindrome("A man, a plan, a canal: Panama") == True
assert is_palindrome("race a car") == False
assert is_palindrome("") == True
assert is_palindrome("a") == True
print("All tests passed!")
"""
    },
    {
        "id": "easy_2",
        "difficulty": "easy",
        "task": "Implement a function `two_sum(nums: List[int], target: int) -> List[int]` that returns indices of two numbers that add up to target. Assume exactly one solution exists.",
        "test_code": """
assert two_sum([2, 7, 11, 15], 9) == [0, 1] or two_sum([2, 7, 11, 15], 9) == [1, 0]
assert two_sum([3, 2, 4], 6) == [1, 2] or two_sum([3, 2, 4], 6) == [2, 1]
assert two_sum([3, 3], 6) == [0, 1] or two_sum([3, 3], 6) == [1, 0]
print("All tests passed!")
"""
    },
    # Medium
    {
        "id": "medium_1",
        "difficulty": "medium",
        "task": "Implement a function `merge_intervals(intervals: List[List[int]]) -> List[List[int]]` that merges all overlapping intervals. Example: [[1,3],[2,6],[8,10],[15,18]] returns [[1,6],[8,10],[15,18]]",
        "test_code": """
assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]
assert merge_intervals([[1,4],[4,5]]) == [[1,5]]
assert merge_intervals([[1,4],[0,4]]) == [[0,4]]
assert merge_intervals([]) == []
assert merge_intervals([[1,4]]) == [[1,4]]
print("All tests passed!")
"""
    },
    {
        "id": "medium_2",
        "difficulty": "medium",
        "task": "Implement a function `lru_cache(capacity: int)` that returns an LRU cache class with `get(key)` returning value or -1, and `put(key, value)` adding/updating. When capacity exceeded, evict least recently used item.",
        "test_code": """
cache = lru_cache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1
cache.put(3, 3)  # evicts key 2
assert cache.get(2) == -1
cache.put(4, 4)  # evicts key 1
assert cache.get(1) == -1
assert cache.get(3) == 3
assert cache.get(4) == 4
print("All tests passed!")
"""
    },
    {
        "id": "medium_3",
        "difficulty": "medium",
        "task": "Implement a function `find_kth_largest(nums: List[int], k: int) -> int` that finds the kth largest element in an unsorted array. You must solve it in O(n) average time using quickselect.",
        "test_code": """
assert find_kth_largest([3,2,1,5,6,4], 2) == 5
assert find_kth_largest([3,2,3,1,2,4,5,5,6], 4) == 4
assert find_kth_largest([1], 1) == 1
assert find_kth_largest([7,6,5,4,3,2,1], 5) == 3
print("All tests passed!")
"""
    },
    # Hard
    {
        "id": "hard_1",
        "difficulty": "hard",
        "task": "Implement a function `serialize(root)` and `deserialize(data)` for a binary tree. The tree node has val, left, right attributes. Serialization should produce a string, deserialization should reconstruct the exact tree. Handle None values.",
        "test_code": """
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

# Test 1: [1,2,3,null,null,4,5]
root = TreeNode(1)
root.left = TreeNode(2)
root.right = TreeNode(3)
root.right.left = TreeNode(4)
root.right.right = TreeNode(5)

data = serialize(root)
new_root = deserialize(data)
assert new_root.val == 1
assert new_root.left.val == 2
assert new_root.right.val == 3
assert new_root.right.left.val == 4
assert new_root.right.right.val == 5

# Test 2: Empty tree
assert deserialize(serialize(None)) is None

print("All tests passed!")
"""
    },
    {
        "id": "hard_2",
        "difficulty": "hard",
        "task": "Implement a function `min_window(s: str, t: str) -> str` that finds the minimum window substring of s that contains all characters in t (including duplicates). Return empty string if no such window exists. Example: s='ADOBECODEBANC', t='ABC' returns 'BANC'",
        "test_code": """
assert min_window("ADOBECODEBANC", "ABC") == "BANC"
assert min_window("a", "a") == "a"
assert min_window("a", "aa") == ""
assert min_window("aa", "aa") == "aa"
assert min_window("ab", "b") == "b"
print("All tests passed!")
"""
    },
]


@dataclass
class TaskResult:
    """Result for a single task on a single variant."""
    task_id: str
    difficulty: str
    variant: str
    success: bool  # Code executed without error
    tests_passed: bool  # All tests passed
    elapsed_time: float
    cost: float
    tokens_generated: int
    error_message: Optional[str] = None


def run_baseline(client: MultiProviderClient, task: dict, executor: CodeExecutor) -> TaskResult:
    """Run task on opus-baseline (single Opus call)."""
    print(f"  [baseline] Running {task['id']}...")

    runner = OpusBaselineRunner(client)

    start_time = time.time()
    try:
        result = runner.run(task=task['task'], max_tokens=4000)
        elapsed = time.time() - start_time

        # Extract and test code
        code = executor.extract_code(result.content)
        if code:
            # Combine generated code with test code
            full_code = code + "\n\n" + task.get('test_code', '')
            exec_result = executor.execute(full_code)
            tests_passed = exec_result.success
            error_message = exec_result.stderr if not exec_result.success else None
        else:
            tests_passed = False
            error_message = "No code extracted from response"

        return TaskResult(
            task_id=task['id'],
            difficulty=task['difficulty'],
            variant="opus-baseline",
            success=code is not None,
            tests_passed=tests_passed,
            elapsed_time=elapsed,
            cost=result.cost,
            tokens_generated=result.output_tokens,
            error_message=error_message
        )
    except Exception as e:
        elapsed = time.time() - start_time
        return TaskResult(
            task_id=task['id'],
            difficulty=task['difficulty'],
            variant="opus-baseline",
            success=False,
            tests_passed=False,
            elapsed_time=elapsed,
            cost=0.0,
            tokens_generated=0,
            error_message=str(e)
        )


def run_optimized(client: MultiProviderClient, task: dict, executor: CodeExecutor) -> TaskResult:
    """Run task on opus-optimized (meta-orchestrator)."""
    print(f"  [optimized] Running {task['id']}...")

    preset = get_preset('opus-optimized')
    orchestrator = OpusMetaOrchestrator(
        client=client,
        preset=preset,
        max_retries_per_feature=1,
        use_learned_prompt=False,
        use_learned_model_selection=False,
    )

    start_time = time.time()
    try:
        result = orchestrator.run(issue=task['task'])
        elapsed = time.time() - start_time

        # Extract and test code
        code = executor.extract_code(result.state.final_answer) if result.state.final_answer else None
        if code:
            # Combine generated code with test code
            full_code = code + "\n\n" + task.get('test_code', '')
            exec_result = executor.execute(full_code)
            tests_passed = exec_result.success
            error_message = exec_result.stderr if not exec_result.success else None
        else:
            tests_passed = False
            error_message = "No code extracted from response"

        return TaskResult(
            task_id=task['id'],
            difficulty=task['difficulty'],
            variant="opus-optimized",
            success=code is not None,
            tests_passed=tests_passed,
            elapsed_time=elapsed,
            cost=result.total_cost,
            tokens_generated=0,  # Meta-orchestrator doesn't track this directly
            error_message=error_message
        )
    except Exception as e:
        elapsed = time.time() - start_time
        return TaskResult(
            task_id=task['id'],
            difficulty=task['difficulty'],
            variant="opus-optimized",
            success=False,
            tests_passed=False,
            elapsed_time=elapsed,
            cost=0.0,
            tokens_generated=0,
            error_message=str(e)
        )


def print_summary(results: List[TaskResult]):
    """Print a summary of results."""
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)

    # Group by variant
    baseline_results = [r for r in results if r.variant == "opus-baseline"]
    optimized_results = [r for r in results if r.variant == "opus-optimized"]

    for variant, variant_results in [("opus-baseline", baseline_results), ("opus-optimized", optimized_results)]:
        if not variant_results:
            continue

        passed = sum(1 for r in variant_results if r.tests_passed)
        total = len(variant_results)
        total_time = sum(r.elapsed_time for r in variant_results)
        total_cost = sum(r.cost for r in variant_results)
        avg_time = total_time / total if total > 0 else 0
        avg_cost = total_cost / total if total > 0 else 0

        print(f"\n{variant}:")
        print(f"  Pass Rate: {passed}/{total} ({100*passed/total:.1f}%)")
        print(f"  Total Time: {total_time:.1f}s")
        print(f"  Avg Time/Task: {avg_time:.1f}s")
        print(f"  Total Cost: ${total_cost:.4f}")
        print(f"  Avg Cost/Task: ${avg_cost:.4f}")

        # By difficulty
        for diff in ["easy", "medium", "hard"]:
            diff_results = [r for r in variant_results if r.difficulty == diff]
            if diff_results:
                diff_passed = sum(1 for r in diff_results if r.tests_passed)
                print(f"  {diff.capitalize()}: {diff_passed}/{len(diff_results)}")

    print("\n" + "=" * 70)

    # Head-to-head comparison
    print("\nHEAD-TO-HEAD (by task):")
    print("-" * 70)
    print(f"{'Task ID':<15} {'Difficulty':<10} {'Baseline':<12} {'Optimized':<12} {'Winner':<12}")
    print("-" * 70)

    task_ids = set(r.task_id for r in results)
    for task_id in sorted(task_ids):
        baseline = next((r for r in baseline_results if r.task_id == task_id), None)
        optimized = next((r for r in optimized_results if r.task_id == task_id), None)

        if baseline and optimized:
            baseline_status = "PASS" if baseline.tests_passed else "FAIL"
            optimized_status = "PASS" if optimized.tests_passed else "FAIL"

            if baseline.tests_passed and not optimized.tests_passed:
                winner = "Baseline"
            elif optimized.tests_passed and not baseline.tests_passed:
                winner = "Optimized"
            elif baseline.tests_passed and optimized.tests_passed:
                # Both passed - compare cost
                if baseline.cost < optimized.cost:
                    winner = "Baseline ($)"
                else:
                    winner = "Optimized ($)"
            else:
                winner = "Neither"

            print(f"{task_id:<15} {baseline.difficulty:<10} {baseline_status:<12} {optimized_status:<12} {winner:<12}")


def save_results(results: List[TaskResult], output_dir: str = "outputs"):
    """Save results to Excel and JSON."""
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")

    # Save to JSON
    json_path = os.path.join(output_dir, f"comparison_results_{timestamp}.json")
    with open(json_path, 'w') as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    print(f"\nResults saved to: {json_path}")

    # Save to Excel
    try:
        import pandas as pd
        df = pd.DataFrame([asdict(r) for r in results])
        xlsx_path = os.path.join(output_dir, f"comparison_results_{timestamp}.xlsx")
        df.to_excel(xlsx_path, index=False)
        print(f"Results saved to: {xlsx_path}")
    except ImportError:
        print("Note: pandas not available, skipping Excel export")


def main():
    parser = argparse.ArgumentParser(description="Compare opus-optimized vs opus-baseline")
    parser.add_argument("--tasks", type=int, default=3, help="Number of tasks to run (default: 3)")
    parser.add_argument("--difficulty", type=str, choices=["easy", "medium", "hard", "all"],
                       default="all", help="Filter tasks by difficulty")
    parser.add_argument("--only", type=str, choices=["baseline", "optimized"],
                       help="Run only one variant")
    args = parser.parse_args()

    print("=" * 70)
    print("OPUS VARIANT COMPARISON BENCHMARK")
    print("=" * 70)
    print(f"Running up to {args.tasks} tasks")
    print(f"Difficulty filter: {args.difficulty}")
    print()

    # Filter tasks
    tasks = TEST_TASKS
    if args.difficulty != "all":
        tasks = [t for t in tasks if t['difficulty'] == args.difficulty]
    tasks = tasks[:args.tasks]

    print(f"Selected {len(tasks)} tasks:")
    for t in tasks:
        print(f"  - {t['id']} ({t['difficulty']})")
    print()

    # Initialize
    client = MultiProviderClient()
    executor = CodeExecutor(timeout=30)
    results: List[TaskResult] = []

    # Run each task on both variants
    for i, task in enumerate(tasks):
        print(f"\n[{i+1}/{len(tasks)}] Task: {task['id']} ({task['difficulty']})")
        print(f"  {task['task'][:80]}...")

        if args.only != "optimized":
            result = run_baseline(client, task, executor)
            results.append(result)
            status = "PASS" if result.tests_passed else "FAIL"
            print(f"    Baseline: {status} ({result.elapsed_time:.1f}s, ${result.cost:.4f})")
            if result.error_message and not result.tests_passed:
                print(f"      Error: {result.error_message[:100]}")

        if args.only != "baseline":
            result = run_optimized(client, task, executor)
            results.append(result)
            status = "PASS" if result.tests_passed else "FAIL"
            print(f"    Optimized: {status} ({result.elapsed_time:.1f}s, ${result.cost:.4f})")
            if result.error_message and not result.tests_passed:
                print(f"      Error: {result.error_message[:100]}")

    # Print summary
    print_summary(results)

    # Save results
    save_results(results)


if __name__ == "__main__":
    main()
