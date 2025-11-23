"""Complete 5-way benchmark: Run all 5 systems in parallel, then judge.

Runs: ALO, ALO-Sonnet, ALO-Open, ALO-Optimized, Sonnet+Context
Then: GPT-4o judge evaluates and ranks all 5
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.runners.alo_runner import ALORunner
from benchmark.runners.alo_sonnet_runner import ALOSonnetRunner
from benchmark.runners.alo_open_runner import ALOOpenRunner
from benchmark.runners.alo_optimized_runner import ALOOptimizedRunner
from benchmark.runners.sonnet_runner import SonnetContextRunner
from benchmark.evaluators.evaluation_schema_5way import JUDGE_PROMPT_5WAY

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import openai


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
        import traceback
        traceback.print_exc()
        return {
            "runner": runner_name,
            "prompt_id": prompt_data["id"],
            "success": False,
            "error": str(e),
            "elapsed": elapsed
        }


def call_judge(prompt_data: dict, solutions: Dict[str, str]) -> Optional[Dict]:
    """Call GPT-4o judge to evaluate and rank 5 solutions."""
    judge_prompt = JUDGE_PROMPT_5WAY.format(
        original_prompt=prompt_data["prompt"],
        context_summary="N/A (standalone prompt evaluation)",
        solution_a=solutions.get("alo", "NOT AVAILABLE"),
        solution_b=solutions.get("alo_sonnet", "NOT AVAILABLE"),
        solution_c=solutions.get("alo_open", "NOT AVAILABLE"),
        solution_d=solutions.get("alo_optimized", "NOT AVAILABLE"),
        solution_e=solutions.get("sonnet_context", "NOT AVAILABLE")
    )

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a senior software engineering evaluator."},
                {"role": "user", "content": judge_prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return result

    except Exception as e:
        print(f"  Judge error: {e}")
        return None


def main():
    print("=" * 80)
    print("COMPLETE 5-WAY BENCHMARK")
    print("=" * 80)
    print("Phase 1: Run all 5 systems in parallel on 10 prompts")
    print("Phase 2: Judge evaluates and ranks all 5")
    print("=" * 80)
    print("Systems: ALO | ALO-Sonnet | ALO-Open | ALO-Optimized | Sonnet+Context")
    print(f"Prompts: {len(HARD_PROMPTS)}")
    print(f"Total tests: {len(HARD_PROMPTS) * 5} = {len(HARD_PROMPTS)} prompts × 5 systems")
    print("=" * 80)

    # ========================================================================
    # PHASE 1: RUN ALL SYSTEMS IN PARALLEL
    # ========================================================================
    print("\n" + "=" * 80)
    print("PHASE 1: RUNNING ALL 5 SYSTEMS IN PARALLEL")
    print("=" * 80)

    # Initialize runners
    runners = {
        "alo": ALORunner(),
        "alo_sonnet": ALOSonnetRunner(),
        "alo_open": ALOOpenRunner(),
        "alo_optimized": ALOOptimizedRunner(),
        "sonnet_context": SonnetContextRunner()
    }

    # Create all test tasks (5 systems × 10 prompts = 50 tasks)
    tasks = []
    for prompt_data in HARD_PROMPTS:
        for runner_name, runner in runners.items():
            tasks.append((runner_name, runner, prompt_data))

    print(f"\nStarting {len(tasks)} tests in parallel with 8 workers...")
    print("-" * 80)

    overall_start = time.time()
    results = []

    # Run all tests in parallel
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(run_single_test, runner_name, runner, prompt_data): (runner_name, prompt_data["id"])
            for runner_name, runner, prompt_data in tasks
        }

        for future in as_completed(futures):
            runner_name, prompt_id = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"  Progress: {len(results)}/{len(tasks)} completed")
            except Exception as e:
                print(f"[{runner_name}] FATAL ERROR on {prompt_id}: {e}")
                results.append({
                    "runner": runner_name,
                    "prompt_id": prompt_id,
                    "success": False,
                    "error": f"Fatal: {e}",
                    "elapsed": 0
                })

    phase1_elapsed = time.time() - overall_start

    # Save outputs for judge
    output_dir = Path("benchmark/results/5way_complete")
    output_dir.mkdir(parents=True, exist_ok=True)

    solutions_by_prompt = {}  # prompt_id -> {system_name: output}

    for r in results:
        if r["success"]:
            prompt_id = r["prompt_id"]
            runner_name = r["runner"]

            if prompt_id not in solutions_by_prompt:
                solutions_by_prompt[prompt_id] = {}

            solutions_by_prompt[prompt_id][runner_name] = r["result"].output

            # Save individual output file
            runner_dir = output_dir / runner_name
            runner_dir.mkdir(exist_ok=True)
            output_file = runner_dir / f"{prompt_id}.txt"
            with open(output_file, "w") as f:
                f.write(r["result"].output)

    # Phase 1 summary
    print("\n" + "=" * 80)
    print("PHASE 1 RESULTS")
    print("=" * 80)

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    print(f"\nCompleted: {len(successes)}/{len(results)} tests")
    print(f"Failed: {len(failures)} tests")
    print(f"Phase 1 time: {phase1_elapsed:.1f}s")

    for runner_name in runners.keys():
        system_results = [r for r in successes if r["runner"] == runner_name]
        if system_results:
            total_cost = sum(r["result"].cost for r in system_results)
            avg_cost = total_cost / len(system_results)
            print(f"\n{runner_name.upper()}:")
            print(f"  Success: {len(system_results)}/{len(HARD_PROMPTS)}")
            print(f"  Total cost: ${total_cost:.4f}")
            print(f"  Avg cost: ${avg_cost:.4f}")

    if failures:
        print("\nFAILED TESTS:")
        for f in failures:
            print(f"  [{f['runner']}] {f['prompt_id']}: {f['error']}")

    # ========================================================================
    # PHASE 2: JUDGE EVALUATION
    # ========================================================================
    print("\n" + "=" * 80)
    print("PHASE 2: JUDGE EVALUATION")
    print("=" * 80)

    judge_start = time.time()
    all_evaluations = []
    rankings_summary = {name: [] for name in runners.keys()}

    # Map solution IDs to runner names
    solution_to_runner = {
        "solution_a": "alo",
        "solution_b": "alo_sonnet",
        "solution_c": "alo_open",
        "solution_d": "alo_optimized",
        "solution_e": "sonnet_context"
    }

    for i, prompt_data in enumerate(HARD_PROMPTS, 1):
        print(f"\n[{i}/{len(HARD_PROMPTS)}] Judging: {prompt_data['id']}")

        solutions = solutions_by_prompt.get(prompt_data["id"], {})

        if len(solutions) < 5:
            print(f"  ⚠️  Skipping - only {len(solutions)}/5 solutions available")
            continue

        print(f"  Calling GPT-4o judge...")
        evaluation = call_judge(prompt_data, solutions)

        if evaluation:
            ranking = evaluation.get("ranking", [])
            winner_solution = evaluation.get("winner", "unknown")
            winner = solution_to_runner.get(winner_solution, winner_solution)

            print(f"  ✓ Judge complete")
            print(f"    Winner: {winner}")
            print(f"    Ranking: {' > '.join(ranking)}")

            # Map solution IDs to runner names and track rankings
            for rank_idx, solution_id in enumerate(ranking):
                runner_name = solution_to_runner.get(solution_id, solution_id)
                if runner_name in rankings_summary:
                    rankings_summary[runner_name].append(rank_idx + 1)

            eval_file = output_dir / "evaluations" / f"{prompt_data['id']}_eval.json"
            eval_file.parent.mkdir(exist_ok=True)
            with open(eval_file, "w") as f:
                json.dump({
                    "prompt_id": prompt_data["id"],
                    "prompt": prompt_data["prompt"],
                    "evaluation": evaluation
                }, f, indent=2)

            all_evaluations.append({
                "prompt_id": prompt_data["id"],
                "ranking": ranking,
                "winner": winner,
                "evaluation": evaluation
            })

        time.sleep(1)  # Rate limiting

    judge_elapsed = time.time() - judge_start

    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    summary = {
        "total_evaluations": len(all_evaluations),
        "systems": list(runners.keys()),
        "rankings": {}
    }

    print(f"\nTotal evaluations: {len(all_evaluations)}")
    print(f"Phase 1 (run tests): {phase1_elapsed:.1f}s")
    print(f"Phase 2 (judge): {judge_elapsed:.1f}s")
    print(f"Total time: {phase1_elapsed + judge_elapsed:.1f}s")

    for system, ranks in rankings_summary.items():
        if not ranks:
            continue

        avg_rank = sum(ranks) / len(ranks)
        wins = ranks.count(1)
        top_3 = sum(1 for r in ranks if r <= 3)

        summary["rankings"][system] = {
            "average_rank": avg_rank,
            "wins": wins,
            "top_3_finishes": top_3,
            "total_evaluations": len(ranks),
            "rank_distribution": {
                "1st": ranks.count(1),
                "2nd": ranks.count(2),
                "3rd": ranks.count(3),
                "4th": ranks.count(4),
                "5th": ranks.count(5)
            }
        }

        print(f"\n{system.upper()}:")
        print(f"  Average rank: {avg_rank:.2f}")
        print(f"  Wins (1st): {wins}/{len(ranks)}")
        print(f"  Top 3 finishes: {top_3}/{len(ranks)}")
        print(f"  Distribution: 1st={ranks.count(1)} | 2nd={ranks.count(2)} | 3rd={ranks.count(3)} | 4th={ranks.count(4)} | 5th={ranks.count(5)}")

    # Save final summary
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    summary_file = output_dir / f"summary_{timestamp}.json"

    with open(summary_file, "w") as f:
        json.dump({
            "metadata": {
                "timestamp": timestamp,
                "judge_model": "gpt-4o",
                "total_prompts": len(HARD_PROMPTS),
                "evaluated": len(all_evaluations),
                "phase1_time": phase1_elapsed,
                "phase2_time": judge_elapsed,
                "total_time": phase1_elapsed + judge_elapsed
            },
            "summary": summary,
            "evaluations": all_evaluations
        }, f, indent=2)

    print(f"\n✓ Summary saved to: {summary_file}")

    # Overall winner
    if summary["rankings"]:
        overall_winner = min(summary["rankings"].items(), key=lambda x: x[1]["average_rank"])
        print("\n" + "=" * 80)
        print(f"🏆 OVERALL WINNER: {overall_winner[0].upper()}")
        print(f"   Average rank: {overall_winner[1]['average_rank']:.2f}")
        print(f"   Wins: {overall_winner[1]['wins']}/{len(all_evaluations)}")
        print(f"   Top 3 finishes: {overall_winner[1]['top_3_finishes']}/{len(all_evaluations)}")
        print("=" * 80)


if __name__ == "__main__":
    main()
