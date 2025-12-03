#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: compare_conductor_vs_opus.py
=============================================================================

Compare Opus-Conductor (multi-agent with validation) vs baseline Opus
(single-shot) on a set of coding tasks.

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import sys
import time
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional
import subprocess
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent))

from conductor import OpusConductor
from conductor.clients import ModelClientFactory, ResilientModelClient


@dataclass
class TaskResult:
    """Result for a single task."""
    task_id: str
    task: str
    method: str  # "conductor" or "opus_baseline"
    success: bool
    code: str
    execution_passed: bool
    execution_output: str
    cost: float
    time: float
    stages_completed: int = 0
    retries: int = 0
    error: Optional[str] = None


@dataclass
class ComparisonResult:
    """Overall comparison results."""
    conductor_results: List[TaskResult]
    baseline_results: List[TaskResult]
    conductor_success_rate: float
    baseline_success_rate: float
    conductor_avg_cost: float
    baseline_avg_cost: float
    conductor_avg_time: float
    baseline_avg_time: float


# Test tasks of varying complexity - expanded with harder tasks
TEST_TASKS = [
    # === SIMPLE (baseline should handle easily) ===
    {
        "id": "simple_1",
        "task": "Write a Python function `factorial(n)` that returns the factorial of n. Handle n=0 (return 1) and negative numbers (raise ValueError).",
        "test_code": """
assert factorial(0) == 1
assert factorial(1) == 1
assert factorial(5) == 120
assert factorial(10) == 3628800
try:
    factorial(-1)
    assert False, "Should raise ValueError"
except ValueError:
    pass
print("All tests passed!")
"""
    },

    # === MEDIUM (some edge cases) ===
    {
        "id": "medium_1",
        "task": "Write a Python function `merge_sorted_lists(list1, list2)` that merges two sorted lists into one sorted list. Do not use the built-in sort function.",
        "test_code": """
assert merge_sorted_lists([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6]
assert merge_sorted_lists([], [1, 2, 3]) == [1, 2, 3]
assert merge_sorted_lists([1, 2, 3], []) == [1, 2, 3]
assert merge_sorted_lists([], []) == []
assert merge_sorted_lists([1, 1, 1], [1, 1]) == [1, 1, 1, 1, 1]
assert merge_sorted_lists([1], [2]) == [1, 2]
print("All tests passed!")
"""
    },

    # === HARDER (algorithmic complexity) ===
    {
        "id": "harder_1",
        "task": "Write a Python function `longest_common_subsequence(s1, s2)` that returns the length of the longest common subsequence between two strings. A subsequence is a sequence that can be derived by deleting some characters without changing the order.",
        "test_code": """
assert longest_common_subsequence("abcde", "ace") == 3
assert longest_common_subsequence("abc", "abc") == 3
assert longest_common_subsequence("abc", "def") == 0
assert longest_common_subsequence("", "abc") == 0
assert longest_common_subsequence("abcd", "abdc") == 3
print("All tests passed!")
"""
    },

    # === TRICKY (subtle edge cases that often catch models) ===
    {
        "id": "tricky_1",
        "task": """Write a Python function `balanced_brackets(s)` that returns True if the string has balanced brackets.
The brackets to handle are: (), [], {}.
The brackets must be properly nested - e.g. "([)]" is NOT balanced but "([{}])" is balanced.
Empty string returns True. Non-bracket characters should be ignored.""",
        "test_code": """
assert balanced_brackets("()") == True
assert balanced_brackets("()[]{}") == True
assert balanced_brackets("([{}])") == True
assert balanced_brackets("([)]") == False  # Tricky: brackets don't match
assert balanced_brackets("((())") == False  # Missing close
assert balanced_brackets("") == True
assert balanced_brackets("abc") == True  # Non-brackets ignored
assert balanced_brackets("a(b[c]d)e") == True
assert balanced_brackets("[(])") == False  # Wrong nesting
assert balanced_brackets("{[()]}") == True
assert balanced_brackets("(((((((((())))))))))") == True  # Deep nesting
assert balanced_brackets("}{") == False  # Starts with close
print("All tests passed!")
"""
    },
    {
        "id": "tricky_2",
        "task": """Write a Python function `eval_rpn(tokens)` that evaluates a Reverse Polish Notation expression.
tokens is a list of strings where each string is either an integer or an operator (+, -, *, /).
Division should truncate toward zero (use int(a/b) for Python 3).
You can assume the expression is always valid.
Examples: ["2", "1", "+", "3", "*"] = ((2 + 1) * 3) = 9
         ["4", "13", "5", "/", "+"] = (4 + (13 / 5)) = 6""",
        "test_code": """
assert eval_rpn(["2", "1", "+", "3", "*"]) == 9
assert eval_rpn(["4", "13", "5", "/", "+"]) == 6
assert eval_rpn(["10", "6", "9", "3", "+", "-11", "*", "/", "*", "17", "+", "5", "+"]) == 22
assert eval_rpn(["3"]) == 3
assert eval_rpn(["-3"]) == -3
assert eval_rpn(["10", "2", "/"]) == 5
assert eval_rpn(["7", "-3", "/"]) == -2  # Truncate toward zero
assert eval_rpn(["-7", "3", "/"]) == -2  # Truncate toward zero (not floor!)
print("All tests passed!")
"""
    },
    {
        "id": "tricky_3",
        "task": """Write a Python function `min_window(s, t)` that finds the minimum window substring of s that contains all characters of t (including duplicates).
If there is no such window, return empty string "".
If there are multiple windows of the same length, return the first one.
Examples: min_window("ADOBECODEBANC", "ABC") = "BANC"
         min_window("a", "a") = "a"
         min_window("a", "aa") = "" (need 2 a's but only have 1)""",
        "test_code": """
assert min_window("ADOBECODEBANC", "ABC") == "BANC"
assert min_window("a", "a") == "a"
assert min_window("a", "aa") == ""
assert min_window("aa", "aa") == "aa"
assert min_window("", "a") == ""
assert min_window("abc", "") == ""
assert min_window("cabwefgewcwaefgcf", "cae") == "cwae"
assert min_window("ADOBECODEBANCX", "ABCX") == "BANCX"
print("All tests passed!")
"""
    },

    # === COMPLEX (multi-step logic, data structures) ===
    {
        "id": "complex_1",
        "task": """Write a Python function `serialize_deserialize_tree(root)` that returns a tuple of two functions: (serialize, deserialize).
- serialize(root) takes a binary tree node and returns a string representation
- deserialize(data) takes a string and reconstructs the binary tree
The tree node class is defined as: class TreeNode: def __init__(self, val=0, left=None, right=None): self.val = val; self.left = left; self.right = right
The serialization format is up to you, but deserialize(serialize(root)) must return an identical tree.
Handle None/empty trees.""",
        "test_code": """
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def trees_equal(t1, t2):
    if t1 is None and t2 is None:
        return True
    if t1 is None or t2 is None:
        return False
    return t1.val == t2.val and trees_equal(t1.left, t2.left) and trees_equal(t1.right, t2.right)

serialize, deserialize = serialize_deserialize_tree(None)

# Test 1: Simple tree
root1 = TreeNode(1, TreeNode(2), TreeNode(3, TreeNode(4), TreeNode(5)))
assert trees_equal(deserialize(serialize(root1)), root1)

# Test 2: Empty tree
assert deserialize(serialize(None)) is None

# Test 3: Single node
root3 = TreeNode(42)
assert trees_equal(deserialize(serialize(root3)), root3)

# Test 4: Left-skewed
root4 = TreeNode(1, TreeNode(2, TreeNode(3)))
assert trees_equal(deserialize(serialize(root4)), root4)

# Test 5: With negative values
root5 = TreeNode(-1, TreeNode(-2), TreeNode(-3))
assert trees_equal(deserialize(serialize(root5)), root5)

print("All tests passed!")
"""
    },
    {
        "id": "complex_2",
        "task": """Write a Python function `lru_cache(capacity)` that returns an LRU (Least Recently Used) cache object.
The cache object must support:
- get(key): Get the value if key exists, return -1 otherwise. Marks key as recently used.
- put(key, value): Set or update the value. If cache exceeds capacity, evict the least recently used item.
Both get and put must run in O(1) average time.
The capacity will always be > 0.""",
        "test_code": """
cache = lru_cache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1  # Returns 1, key 1 is now most recent
cache.put(3, 3)  # Evicts key 2 (least recently used)
assert cache.get(2) == -1  # Key 2 was evicted
cache.put(4, 4)  # Evicts key 1
assert cache.get(1) == -1  # Key 1 was evicted
assert cache.get(3) == 3
assert cache.get(4) == 4

# Test overwrite
cache2 = lru_cache(2)
cache2.put(1, 1)
cache2.put(2, 2)
cache2.put(1, 10)  # Update value
assert cache2.get(1) == 10

# Test capacity 1
cache3 = lru_cache(1)
cache3.put(1, 1)
cache3.put(2, 2)
assert cache3.get(1) == -1
assert cache3.get(2) == 2

print("All tests passed!")
"""
    },
]


def execute_code(code: str, test_code: str) -> tuple:
    """Execute code with tests and return (output, passed)."""
    full_code = code + "\n\n" + test_code

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(full_code)
        temp_path = f.name

    try:
        result = subprocess.run(
            ['python', temp_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        passed = result.returncode == 0 and "All tests passed" in output
        return output, passed
    except subprocess.TimeoutExpired:
        return "Timeout", False
    except Exception as e:
        return str(e), False
    finally:
        Path(temp_path).unlink(missing_ok=True)


def run_conductor(task: dict, conductor: OpusConductor) -> TaskResult:
    """Run task through Opus-Conductor."""
    print(f"  [CONDUCTOR] Running: {task['id']}")
    start_time = time.time()

    try:
        result = conductor.run(task=task['task'])
        elapsed = time.time() - start_time

        code = result.final_code or ""

        # Execute tests
        if code:
            output, passed = execute_code(code, task['test_code'])
        else:
            output, passed = "No code generated", False

        return TaskResult(
            task_id=task['id'],
            task=task['task'],
            method="conductor",
            success=result.success,
            code=code,
            execution_passed=passed,
            execution_output=output[:500],
            cost=result.total_cost,
            time=elapsed,
            stages_completed=result.stages_completed,
            retries=result.retries_used,
        )
    except Exception as e:
        return TaskResult(
            task_id=task['id'],
            task=task['task'],
            method="conductor",
            success=False,
            code="",
            execution_passed=False,
            execution_output="",
            cost=0,
            time=time.time() - start_time,
            error=str(e),
        )


def run_opus_baseline(task: dict, client: ResilientModelClient) -> TaskResult:
    """Run task with single Opus call (baseline)."""
    print(f"  [OPUS] Running: {task['id']}")
    start_time = time.time()

    prompt = f"""Write Python code to solve this task:

{task['task']}

Output ONLY the Python code, no explanations. The code should be complete and runnable."""

    system = """You are an expert Python programmer. Write clean, correct, complete code.
Always handle edge cases. Output only the code in a single code block."""

    try:
        response = client.complete(
            messages=[{"role": "user", "content": prompt}],
            system=system,
        )
        elapsed = time.time() - start_time

        # Extract code
        import re
        code_match = re.search(r'```python\s*(.*?)```', response.content, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
        else:
            code_match = re.search(r'```\s*(.*?)```', response.content, re.DOTALL)
            code = code_match.group(1).strip() if code_match else response.content

        # Execute tests
        output, passed = execute_code(code, task['test_code'])

        return TaskResult(
            task_id=task['id'],
            task=task['task'],
            method="opus_baseline",
            success=passed,
            code=code,
            execution_passed=passed,
            execution_output=output[:500],
            cost=response.cost,
            time=elapsed,
        )
    except Exception as e:
        return TaskResult(
            task_id=task['id'],
            task=task['task'],
            method="opus_baseline",
            success=False,
            code="",
            execution_passed=False,
            execution_output="",
            cost=0,
            time=time.time() - start_time,
            error=str(e),
        )


def main():
    print("=" * 70)
    print("OPUS-CONDUCTOR vs OPUS BASELINE COMPARISON")
    print("=" * 70)
    print()

    # Initialize
    conductor = OpusConductor.from_config("config/conductor_config.yaml")
    opus_client = conductor.supervisor_client  # Reuse the Opus client

    conductor_results = []
    baseline_results = []

    print(f"Running {len(TEST_TASKS)} tasks...")
    print("-" * 70)

    for task in TEST_TASKS:
        print(f"\nTask: {task['id']}")
        print(f"  {task['task'][:60]}...")

        # Run conductor
        c_result = run_conductor(task, conductor)
        conductor_results.append(c_result)
        print(f"  [CONDUCTOR] exec={'PASS' if c_result.execution_passed else 'FAIL'}, "
              f"cost=${c_result.cost:.4f}, time={c_result.time:.1f}s")

        # Run baseline
        b_result = run_opus_baseline(task, opus_client)
        baseline_results.append(b_result)
        print(f"  [OPUS]      exec={'PASS' if b_result.execution_passed else 'FAIL'}, "
              f"cost=${b_result.cost:.4f}, time={b_result.time:.1f}s")

    # Calculate stats
    c_passes = sum(1 for r in conductor_results if r.execution_passed)
    b_passes = sum(1 for r in baseline_results if r.execution_passed)

    c_success_rate = c_passes / len(conductor_results) * 100
    b_success_rate = b_passes / len(baseline_results) * 100

    c_avg_cost = sum(r.cost for r in conductor_results) / len(conductor_results)
    b_avg_cost = sum(r.cost for r in baseline_results) / len(baseline_results)

    c_avg_time = sum(r.time for r in conductor_results) / len(conductor_results)
    b_avg_time = sum(r.time for r in baseline_results) / len(baseline_results)

    # Print results
    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print()
    print(f"{'Metric':<25} {'Conductor':<20} {'Opus Baseline':<20}")
    print("-" * 70)
    print(f"{'Tasks Passed':<25} {c_passes}/{len(conductor_results):<20} {b_passes}/{len(baseline_results):<20}")
    print(f"{'Success Rate':<25} {c_success_rate:.1f}%{'':<17} {b_success_rate:.1f}%")
    print(f"{'Avg Cost':<25} ${c_avg_cost:.4f}{'':<15} ${b_avg_cost:.4f}")
    print(f"{'Avg Time':<25} {c_avg_time:.1f}s{'':<17} {b_avg_time:.1f}s")
    print(f"{'Total Cost':<25} ${sum(r.cost for r in conductor_results):.4f}{'':<15} ${sum(r.cost for r in baseline_results):.4f}")
    print()

    # Per-task breakdown
    print("=" * 70)
    print("PER-TASK BREAKDOWN")
    print("=" * 70)
    print()
    print(f"{'Task':<15} {'Conductor':<15} {'Opus Baseline':<15} {'Winner':<15}")
    print("-" * 70)

    conductor_wins = 0
    baseline_wins = 0
    ties = 0

    for c, b in zip(conductor_results, baseline_results):
        c_status = "PASS" if c.execution_passed else "FAIL"
        b_status = "PASS" if b.execution_passed else "FAIL"

        if c.execution_passed and not b.execution_passed:
            winner = "CONDUCTOR"
            conductor_wins += 1
        elif b.execution_passed and not c.execution_passed:
            winner = "OPUS"
            baseline_wins += 1
        else:
            winner = "TIE"
            ties += 1

        print(f"{c.task_id:<15} {c_status:<15} {b_status:<15} {winner:<15}")

    print()
    print("-" * 70)
    print(f"Conductor Wins: {conductor_wins}")
    print(f"Opus Wins: {baseline_wins}")
    print(f"Ties: {ties}")
    print()

    # Save detailed results
    output_path = Path("results/conductor_vs_opus_comparison.json")
    output_path.parent.mkdir(exist_ok=True)

    results_data = {
        "conductor_results": [asdict(r) for r in conductor_results],
        "baseline_results": [asdict(r) for r in baseline_results],
        "summary": {
            "conductor_success_rate": c_success_rate,
            "baseline_success_rate": b_success_rate,
            "conductor_avg_cost": c_avg_cost,
            "baseline_avg_cost": b_avg_cost,
            "conductor_avg_time": c_avg_time,
            "baseline_avg_time": b_avg_time,
            "conductor_wins": conductor_wins,
            "baseline_wins": baseline_wins,
            "ties": ties,
        }
    }

    output_path.write_text(json.dumps(results_data, indent=2))
    print(f"Detailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
