#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: deepeval_comparison.py
=============================================================================

Compare Opus-Conductor vs baseline Opus using DeepEval metrics for
more rigorous, multi-dimensional evaluation.

Metrics used:
- GEval (custom code correctness criteria)
- TaskCompletionMetric (did it solve the task?)
- Code Execution (actual test execution)

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import sys
import time
import json
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

# DeepEval imports
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import GEval, TaskCompletionMetric, AnswerRelevancyMetric

from conductor import OpusConductor
from conductor.clients import ResilientModelClient


@dataclass
class EvalResult:
    """Result for a single evaluation."""
    task_id: str
    task: str
    method: str
    code: str

    # Execution-based
    execution_passed: bool
    execution_output: str

    # DeepEval scores
    code_correctness_score: float = 0.0
    task_completion_score: float = 0.0
    answer_relevancy_score: float = 0.0

    # Meta
    cost: float = 0.0
    time: float = 0.0
    error: Optional[str] = None

    def avg_deepeval_score(self) -> float:
        scores = [self.code_correctness_score, self.task_completion_score, self.answer_relevancy_score]
        return sum(scores) / len(scores) if scores else 0.0


# Test tasks - focused on harder problems where differences might emerge
TEST_TASKS = [
    {
        "id": "algo_1",
        "task": """Write a Python function `find_median_sorted_arrays(nums1, nums2)` that finds the median of two sorted arrays.
The overall run time complexity should be O(log (m+n)) where m and n are the sizes of the two arrays.
Examples:
- find_median_sorted_arrays([1,3], [2]) = 2.0
- find_median_sorted_arrays([1,2], [3,4]) = 2.5""",
        "test_code": """
assert find_median_sorted_arrays([1,3], [2]) == 2.0
assert find_median_sorted_arrays([1,2], [3,4]) == 2.5
assert find_median_sorted_arrays([0,0], [0,0]) == 0.0
assert find_median_sorted_arrays([], [1]) == 1.0
assert find_median_sorted_arrays([2], []) == 2.0
assert find_median_sorted_arrays([1,2,3,4,5], [6,7,8,9,10]) == 5.5
print("All tests passed!")
""",
        "expected_behavior": "Binary search approach to find median in O(log(min(m,n))) time"
    },
    {
        "id": "algo_2",
        "task": """Write a Python function `trap(height)` that computes how much water can be trapped after raining.
height is a list of non-negative integers representing an elevation map where the width of each bar is 1.
Example: trap([0,1,0,2,1,0,1,3,2,1,2,1]) = 6""",
        "test_code": """
assert trap([0,1,0,2,1,0,1,3,2,1,2,1]) == 6
assert trap([4,2,0,3,2,5]) == 9
assert trap([]) == 0
assert trap([1]) == 0
assert trap([1,2,3,4,5]) == 0  # Ascending - no water
assert trap([5,4,3,2,1]) == 0  # Descending - no water
assert trap([5,2,5]) == 3
print("All tests passed!")
""",
        "expected_behavior": "Two-pointer or DP approach to calculate trapped water"
    },
    {
        "id": "algo_3",
        "task": """Write a Python function `max_profit_k_transactions(prices, k)` that finds the maximum profit you can achieve with at most k transactions.
A transaction consists of buying and selling one share.
You cannot engage in multiple transactions simultaneously (you must sell before you buy again).
Example: max_profit_k_transactions([2,4,1], 2) = 2 (buy at 2, sell at 4)
         max_profit_k_transactions([3,2,6,5,0,3], 2) = 7 (buy at 2, sell at 6, buy at 0, sell at 3)""",
        "test_code": """
assert max_profit_k_transactions([2,4,1], 2) == 2
assert max_profit_k_transactions([3,2,6,5,0,3], 2) == 7
assert max_profit_k_transactions([3,3,5,0,0,3,1,4], 2) == 6
assert max_profit_k_transactions([1,2,3,4,5], 2) == 4
assert max_profit_k_transactions([5,4,3,2,1], 1) == 0  # Decreasing, no profit
assert max_profit_k_transactions([], 2) == 0
assert max_profit_k_transactions([1], 2) == 0
print("All tests passed!")
""",
        "expected_behavior": "DP approach with states for transactions and holding"
    },
    {
        "id": "data_struct_1",
        "task": """Write a Python function `max_sliding_window(nums, k)` that returns the max element in each sliding window of size k.
Example: max_sliding_window([1,3,-1,-3,5,3,6,7], 3) = [3,3,5,5,6,7]
The window slides from left to right, and you return the maximum for each window position.""",
        "test_code": """
assert max_sliding_window([1,3,-1,-3,5,3,6,7], 3) == [3,3,5,5,6,7]
assert max_sliding_window([1], 1) == [1]
assert max_sliding_window([1,-1], 1) == [1,-1]
assert max_sliding_window([9,11], 2) == [11]
assert max_sliding_window([4,3,2,1,0], 3) == [4,3,2]
print("All tests passed!")
""",
        "expected_behavior": "Monotonic deque for O(n) time complexity"
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


def run_deepeval_metrics(task: dict, code: str, execution_passed: bool) -> Dict[str, float]:
    """Run DeepEval metrics on the generated code."""
    scores = {
        "code_correctness": 0.0,
        "task_completion": 0.0,
        "answer_relevancy": 0.0,
    }

    # Create test case
    test_case = LLMTestCase(
        input=task["task"],
        actual_output=code,
        expected_output=task.get("expected_behavior", "Correct implementation"),
    )

    try:
        # GEval for code correctness
        code_metric = GEval(
            name="Code Correctness",
            criteria="""Evaluate the code for:
1. Correctness: Does the code solve the problem correctly?
2. Completeness: Does it handle edge cases?
3. Efficiency: Is the algorithm reasonably efficient?
4. Style: Is the code clean and well-structured?
Score from 0 to 1 where 1 is perfect.""",
            evaluation_params=["actual_output"],
            model="gpt-4o",
            threshold=0.5,
        )
        code_metric.measure(test_case)
        scores["code_correctness"] = code_metric.score or 0.0
    except Exception as e:
        print(f"    GEval error: {e}")

    try:
        # Task completion metric
        task_metric = TaskCompletionMetric(
            threshold=0.5,
            model="gpt-4o",
        )
        task_metric.measure(test_case)
        scores["task_completion"] = task_metric.score or 0.0
    except Exception as e:
        print(f"    TaskCompletion error: {e}")

    try:
        # Answer relevancy
        relevancy_metric = AnswerRelevancyMetric(
            threshold=0.5,
            model="gpt-4o",
        )
        relevancy_metric.measure(test_case)
        scores["answer_relevancy"] = relevancy_metric.score or 0.0
    except Exception as e:
        print(f"    AnswerRelevancy error: {e}")

    return scores


def run_conductor(task: dict, conductor: OpusConductor) -> EvalResult:
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

        # Run DeepEval metrics
        print(f"    Running DeepEval metrics...")
        deepeval_scores = run_deepeval_metrics(task, code, passed)

        return EvalResult(
            task_id=task['id'],
            task=task['task'],
            method="conductor",
            code=code,
            execution_passed=passed,
            execution_output=output[:500],
            code_correctness_score=deepeval_scores["code_correctness"],
            task_completion_score=deepeval_scores["task_completion"],
            answer_relevancy_score=deepeval_scores["answer_relevancy"],
            cost=result.total_cost,
            time=elapsed,
        )
    except Exception as e:
        return EvalResult(
            task_id=task['id'],
            task=task['task'],
            method="conductor",
            code="",
            execution_passed=False,
            execution_output="",
            cost=0,
            time=time.time() - start_time,
            error=str(e),
        )


def run_opus_baseline(task: dict, client: ResilientModelClient) -> EvalResult:
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

        # Run DeepEval metrics
        print(f"    Running DeepEval metrics...")
        deepeval_scores = run_deepeval_metrics(task, code, passed)

        return EvalResult(
            task_id=task['id'],
            task=task['task'],
            method="opus_baseline",
            code=code,
            execution_passed=passed,
            execution_output=output[:500],
            code_correctness_score=deepeval_scores["code_correctness"],
            task_completion_score=deepeval_scores["task_completion"],
            answer_relevancy_score=deepeval_scores["answer_relevancy"],
            cost=response.cost,
            time=elapsed,
        )
    except Exception as e:
        return EvalResult(
            task_id=task['id'],
            task=task['task'],
            method="opus_baseline",
            code="",
            execution_passed=False,
            execution_output="",
            cost=0,
            time=time.time() - start_time,
            error=str(e),
        )


def main():
    print("=" * 70)
    print("DEEPEVAL COMPARISON: OPUS-CONDUCTOR vs OPUS BASELINE")
    print("=" * 70)
    print()
    print("Metrics: Execution + GEval (Code Correctness) + Task Completion + Relevancy")
    print()

    # Initialize
    conductor = OpusConductor.from_config("config/conductor_config.yaml")
    opus_client = conductor.supervisor_client

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
              f"deepeval_avg={c_result.avg_deepeval_score():.2f}, "
              f"cost=${c_result.cost:.4f}")

        # Run baseline
        b_result = run_opus_baseline(task, opus_client)
        baseline_results.append(b_result)
        print(f"  [OPUS]      exec={'PASS' if b_result.execution_passed else 'FAIL'}, "
              f"deepeval_avg={b_result.avg_deepeval_score():.2f}, "
              f"cost=${b_result.cost:.4f}")

    # Calculate stats
    c_exec_passes = sum(1 for r in conductor_results if r.execution_passed)
    b_exec_passes = sum(1 for r in baseline_results if r.execution_passed)

    c_avg_correctness = sum(r.code_correctness_score for r in conductor_results) / len(conductor_results)
    b_avg_correctness = sum(r.code_correctness_score for r in baseline_results) / len(baseline_results)

    c_avg_task = sum(r.task_completion_score for r in conductor_results) / len(conductor_results)
    b_avg_task = sum(r.task_completion_score for r in baseline_results) / len(baseline_results)

    c_avg_relevancy = sum(r.answer_relevancy_score for r in conductor_results) / len(conductor_results)
    b_avg_relevancy = sum(r.answer_relevancy_score for r in baseline_results) / len(baseline_results)

    c_avg_deepeval = sum(r.avg_deepeval_score() for r in conductor_results) / len(conductor_results)
    b_avg_deepeval = sum(r.avg_deepeval_score() for r in baseline_results) / len(baseline_results)

    c_avg_cost = sum(r.cost for r in conductor_results) / len(conductor_results)
    b_avg_cost = sum(r.cost for r in baseline_results) / len(baseline_results)

    # Print results
    print()
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print()
    print(f"{'Metric':<25} {'Conductor':<20} {'Opus Baseline':<20}")
    print("-" * 70)
    print(f"{'Execution Pass Rate':<25} {c_exec_passes}/{len(conductor_results):<20} {b_exec_passes}/{len(baseline_results):<20}")
    print(f"{'Avg Code Correctness':<25} {c_avg_correctness:.2f}{'':<18} {b_avg_correctness:.2f}")
    print(f"{'Avg Task Completion':<25} {c_avg_task:.2f}{'':<18} {b_avg_task:.2f}")
    print(f"{'Avg Answer Relevancy':<25} {c_avg_relevancy:.2f}{'':<18} {b_avg_relevancy:.2f}")
    print(f"{'Avg DeepEval Overall':<25} {c_avg_deepeval:.2f}{'':<18} {b_avg_deepeval:.2f}")
    print(f"{'Avg Cost':<25} ${c_avg_cost:.4f}{'':<15} ${b_avg_cost:.4f}")
    print(f"{'Total Cost':<25} ${sum(r.cost for r in conductor_results):.4f}{'':<15} ${sum(r.cost for r in baseline_results):.4f}")
    print()

    # Per-task breakdown
    print("=" * 70)
    print("PER-TASK DEEPEVAL SCORES")
    print("=" * 70)
    print()
    print(f"{'Task':<12} {'Exec':<8} {'Correct':<10} {'TaskComp':<10} {'Relevancy':<10} {'Method':<12}")
    print("-" * 70)

    for c, b in zip(conductor_results, baseline_results):
        # Conductor
        c_exec = "PASS" if c.execution_passed else "FAIL"
        print(f"{c.task_id:<12} {c_exec:<8} {c.code_correctness_score:.2f}{'':<7} "
              f"{c.task_completion_score:.2f}{'':<7} {c.answer_relevancy_score:.2f}{'':<7} CONDUCTOR")

        # Baseline
        b_exec = "PASS" if b.execution_passed else "FAIL"
        print(f"{'':<12} {b_exec:<8} {b.code_correctness_score:.2f}{'':<7} "
              f"{b.task_completion_score:.2f}{'':<7} {b.answer_relevancy_score:.2f}{'':<7} OPUS")
        print()

    # Save results
    output_path = Path("results/deepeval_comparison.json")
    output_path.parent.mkdir(exist_ok=True)

    results_data = {
        "conductor_results": [asdict(r) for r in conductor_results],
        "baseline_results": [asdict(r) for r in baseline_results],
        "summary": {
            "conductor_exec_rate": c_exec_passes / len(conductor_results),
            "baseline_exec_rate": b_exec_passes / len(baseline_results),
            "conductor_avg_deepeval": c_avg_deepeval,
            "baseline_avg_deepeval": b_avg_deepeval,
            "conductor_avg_cost": c_avg_cost,
            "baseline_avg_cost": b_avg_cost,
        }
    }

    output_path.write_text(json.dumps(results_data, indent=2))
    print(f"Detailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
