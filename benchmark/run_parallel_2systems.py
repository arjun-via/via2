"""Run ALO-Open and ALO-Optimized on all 10 prompts in parallel.

This script runs both systems concurrently to maximize throughput.
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.runners.alo_open_runner import ALOOpenRunner
from benchmark.runners.alo_optimized_runner import ALOOptimizedRunner

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


HARD_PROMPTS = [
    {
        "id": "rate_limiter",
        "prompt": "Implement a rate limiter using the token bucket algorithm in Python. Include thread safety and support for multiple users.",
        "category": "concurrency"
    },
    {
        "id": "lru_cache",
        "prompt": "Design and implement a thread-safe LRU cache in Python with O(1) get/put operations. Support TTL expiration.",
        "category": "data_structures"
    },
    {
        "id": "byzantine_consensus",
        "prompt": "Implement the Byzantine Generals Problem solution using a simplified consensus algorithm. Handle up to f faulty nodes in a network of 3f+1 nodes.",
        "category": "distributed_systems"
    },
    {
        "id": "compiler_parser",
        "prompt": "Write a recursive descent parser for a simple programming language with variables, arithmetic operations, and if/else statements. Include error recovery.",
        "category": "compilers"
    },
    {
        "id": "database_btree",
        "prompt": "Implement a B-tree data structure for a database index. Support insertion, deletion, and range queries. Handle node splitting and merging.",
        "category": "databases"
    },
    {
        "id": "distributed_lock",
        "prompt": "Design a distributed lock manager using Redis. Handle lock acquisition, renewal, and graceful release. Include deadlock detection.",
        "category": "distributed_systems"
    },
    {
        "id": "async_task_queue",
        "prompt": "Build an async task queue system with priority scheduling, retry logic with exponential backoff, and dead letter queue. Support task dependencies.",
        "category": "async_systems"
    },
    {
        "id": "timeseries_anomaly",
        "prompt": "Implement a time series anomaly detection system using statistical methods (Z-score, moving average). Handle seasonality and detect point/contextual anomalies.",
        "category": "machine_learning"
    },
    {
        "id": "graph_cycle_detection",
        "prompt": "Write algorithms to detect cycles in directed and undirected graphs. Include Tarjan's algorithm for strongly connected components.",
        "category": "algorithms"
    },
    {
        "id": "regex_engine",
        "prompt": "Build a simple regex engine supporting . * + ? [] operators. Use Thompson's construction and NFA simulation.",
        "category": "compilers"
    }
]


def run_single_test(runner_name: str, runner, prompt_data: dict) -> dict:
    """Run a single test and return result."""
    print(f"[{runner_name}] Starting: {prompt_data['id']}")
    start = time.time()

    try:
        result = runner.run(prompt_data["prompt"])
        elapsed = time.time() - start

        print(f"[{runner_name}] ✓ {prompt_data['id']} - ${result.cost:.4f} - {elapsed:.1f}s")

        return {
            "runner": runner_name,
            "prompt_id": prompt_data["id"],
            "success": True,
            "result": result,
            "elapsed": elapsed
        }
    except Exception as e:
        elapsed = time.time() - start
        print(f"[{runner_name}] ✗ {prompt_data['id']} - ERROR: {e}")
        return {
            "runner": runner_name,
            "prompt_id": prompt_data["id"],
            "success": False,
            "error": str(e),
            "elapsed": elapsed
        }


def main():
    print("=" * 80)
    print("PARALLEL 2-SYSTEM BENCHMARK: ALO-Open + ALO-Optimized")
    print("=" * 80)
    print(f"Prompts: {len(HARD_PROMPTS)}")
    print(f"Systems: 2 (ALO-Open, ALO-Optimized)")
    print(f"Total tests: {len(HARD_PROMPTS) * 2}")
    print("Execution: PARALLEL (both systems run concurrently)")
    print("=" * 80)

    # Initialize runners
    alo_open = ALOOpenRunner()
    alo_optimized = ALOOptimizedRunner()

    # Create all test tasks
    tasks = []
    for prompt_data in HARD_PROMPTS:
        tasks.append(("alo_open", alo_open, prompt_data))
        tasks.append(("alo_optimized", alo_optimized, prompt_data))

    print(f"\nStarting {len(tasks)} tests in parallel...")
    print("-" * 80)

    overall_start = time.time()
    results = []

    # Run all tests in parallel with thread pool
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all tasks
        futures = {
            executor.submit(run_single_test, runner_name, runner, prompt_data): (runner_name, prompt_data["id"])
            for runner_name, runner, prompt_data in tasks
        }

        # Collect results as they complete
        for future in as_completed(futures):
            runner_name, prompt_id = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"[{runner_name}] FATAL ERROR on {prompt_id}: {e}")
                results.append({
                    "runner": runner_name,
                    "prompt_id": prompt_id,
                    "success": False,
                    "error": f"Fatal: {e}",
                    "elapsed": 0
                })

    overall_elapsed = time.time() - overall_start

    # Analyze results
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    print(f"\nCompleted: {len(successes)}/{len(results)} tests")
    print(f"Failed: {len(failures)} tests")
    print(f"Total time: {overall_elapsed:.1f}s")
    print(f"Average time per test: {overall_elapsed/len(results):.1f}s")

    # By-system breakdown
    for runner_name in ["alo_open", "alo_optimized"]:
        system_results = [r for r in successes if r["runner"] == runner_name]
        if system_results:
            total_cost = sum(r["result"].cost for r in system_results)
            avg_cost = total_cost / len(system_results)
            avg_time = sum(r["elapsed"] for r in system_results) / len(system_results)

            print(f"\n{runner_name.upper()}:")
            print(f"  Success: {len(system_results)}/{len(HARD_PROMPTS)}")
            print(f"  Total cost: ${total_cost:.4f}")
            print(f"  Avg cost: ${avg_cost:.4f}")
            print(f"  Avg time: {avg_time:.1f}s")

    # Save results
    output_dir = Path("benchmark/results/parallel_2systems")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"run_{timestamp}.json"

    output_data = {
        "metadata": {
            "timestamp": timestamp,
            "total_tests": len(results),
            "successes": len(successes),
            "failures": len(failures),
            "total_time": overall_elapsed,
            "systems": ["alo_open", "alo_optimized"]
        },
        "results": []
    }

    for r in results:
        if r["success"]:
            output_data["results"].append({
                "runner": r["runner"],
                "prompt_id": r["prompt_id"],
                "cost": r["result"].cost,
                "elapsed_time": r["elapsed"],
                "output_length": len(r["result"].output),
                "metadata": r["result"].metadata
            })
        else:
            output_data["results"].append({
                "runner": r["runner"],
                "prompt_id": r["prompt_id"],
                "error": r["error"],
                "elapsed_time": r["elapsed"]
            })

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✓ Results saved to: {output_file}")

    # Save individual outputs for judge evaluation
    for r in successes:
        runner_dir = output_dir / r["runner"]
        runner_dir.mkdir(exist_ok=True)

        output_file = runner_dir / f"{r['prompt_id']}.txt"
        with open(output_file, "w") as f:
            f.write(r["result"].output)

        print(f"  Saved: {output_file.relative_to(Path.cwd())}")

    if failures:
        print("\nFAILED TESTS:")
        for f in failures:
            print(f"  [{f['runner']}] {f['prompt_id']}: {f['error']}")

    print("\n" + "=" * 80)
    print("Ready for 5-way judge evaluation!")
    print("=" * 80)


if __name__ == "__main__":
    main()
