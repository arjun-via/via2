"""Run judge evaluation only on existing 5-way results."""
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.evaluators.evaluation_schema_5way import JUDGE_PROMPT_5WAY

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import openai


HARD_PROMPTS = [
    {"id": "rate_limiter", "prompt": "Implement a rate limiter using the token bucket algorithm in Python. Include thread safety and support for multiple users."},
    {"id": "lru_cache", "prompt": "Design and implement a thread-safe LRU cache in Python with O(1) get/put operations. Support TTL expiration."},
    {"id": "byzantine_consensus", "prompt": "Implement the Byzantine Generals Problem solution using a simplified consensus algorithm. Handle up to f faulty nodes in a network of 3f+1 nodes."},
    {"id": "compiler_parser", "prompt": "Write a recursive descent parser for a simple programming language with variables, arithmetic operations, and if/else statements. Include error recovery."},
    {"id": "database_btree", "prompt": "Implement a B-tree data structure for a database index. Support insertion, deletion, and range queries. Handle node splitting and merging."},
    {"id": "distributed_lock", "prompt": "Design a distributed lock manager using Redis. Handle lock acquisition, renewal, and graceful release. Include deadlock detection."},
    {"id": "async_task_queue", "prompt": "Build an async task queue system with priority scheduling, retry logic with exponential backoff, and dead letter queue. Support task dependencies."},
    {"id": "timeseries_anomaly", "prompt": "Implement a time series anomaly detection system using statistical methods (Z-score, moving average). Handle seasonality and detect point/contextual anomalies."},
    {"id": "graph_cycle_detection", "prompt": "Write algorithms to detect cycles in directed and undirected graphs. Include Tarjan's algorithm for strongly connected components."},
    {"id": "regex_engine", "prompt": "Build a simple regex engine supporting . * + ? [] operators. Use Thompson's construction and NFA simulation."}
]

SOLUTION_TO_RUNNER = {
    "solution_a": "alo",
    "solution_b": "alo_sonnet",
    "solution_c": "alo_open",
    "solution_d": "alo_optimized",
    "solution_e": "sonnet_context"
}


def load_solution(base_path: Path, system: str, prompt_id: str) -> Optional[str]:
    """Load a solution output from disk."""
    path = base_path / system / f"{prompt_id}.txt"
    if path.exists():
        return path.read_text()
    return None


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
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"  Judge error: {e}")
        return None


def main():
    print("=" * 80)
    print("5-WAY JUDGE EVALUATION (Existing Results)")
    print("=" * 80)

    results_dir = Path("benchmark/results/5way_complete")
    output_dir = results_dir

    all_evaluations = []
    rankings_summary = {
        "alo": [],
        "alo_sonnet": [],
        "alo_open": [],
        "alo_optimized": [],
        "sonnet_context": []
    }

    for i, prompt_data in enumerate(HARD_PROMPTS, 1):
        print(f"\n[{i}/{len(HARD_PROMPTS)}] Judging: {prompt_data['id']}")

        # Load all 5 solutions
        solutions = {
            "alo": load_solution(results_dir, "alo", prompt_data["id"]),
            "alo_sonnet": load_solution(results_dir, "alo_sonnet", prompt_data["id"]),
            "alo_open": load_solution(results_dir, "alo_open", prompt_data["id"]),
            "alo_optimized": load_solution(results_dir, "alo_optimized", prompt_data["id"]),
            "sonnet_context": load_solution(results_dir, "sonnet_context", prompt_data["id"])
        }

        available = [k for k, v in solutions.items() if v is not None]
        if len(available) < 5:
            print(f"  ⚠️  Skipping - only {len(available)}/5 solutions")
            continue

        print(f"  Calling GPT-4o judge...")
        evaluation = call_judge(prompt_data, solutions)

        if evaluation:
            ranking = evaluation.get("ranking", [])
            winner_solution = evaluation.get("winner", "unknown")
            winner = SOLUTION_TO_RUNNER.get(winner_solution, winner_solution)

            print(f"  ✓ Winner: {winner}")
            print(f"    Ranking: {' > '.join([SOLUTION_TO_RUNNER.get(s, s) for s in ranking])}")

            # Track rankings
            for rank_idx, solution_id in enumerate(ranking):
                runner_name = SOLUTION_TO_RUNNER.get(solution_id, solution_id)
                if runner_name in rankings_summary:
                    rankings_summary[runner_name].append(rank_idx + 1)

            # Save evaluation
            eval_file = output_dir / "evaluations" / f"{prompt_data['id']}_eval.json"
            eval_file.parent.mkdir(exist_ok=True, parents=True)
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

        time.sleep(1)

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print(f"\nTotal evaluations: {len(all_evaluations)}")

    for system, ranks in rankings_summary.items():
        if not ranks:
            continue

        avg_rank = sum(ranks) / len(ranks)
        wins = ranks.count(1)
        top_3 = sum(1 for r in ranks if r <= 3)

        print(f"\n{system.upper()}:")
        print(f"  Average rank: {avg_rank:.2f}")
        print(f"  Wins (1st): {wins}/{len(ranks)}")
        print(f"  Top 3: {top_3}/{len(ranks)}")
        print(f"  Distribution: 1st={ranks.count(1)} | 2nd={ranks.count(2)} | 3rd={ranks.count(3)} | 4th={ranks.count(4)} | 5th={ranks.count(5)}")

    # Save summary
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    summary_file = output_dir / f"summary_{timestamp}.json"

    with open(summary_file, "w") as f:
        json.dump({
            "metadata": {"timestamp": timestamp, "judge_model": "gpt-4o", "evaluated": len(all_evaluations)},
            "rankings": {system: {"average_rank": sum(ranks)/len(ranks), "wins": ranks.count(1), "rank_distribution": {f"{i}st" if i==1 else f"{i}nd" if i==2 else f"{i}rd" if i==3 else f"{i}th": ranks.count(i) for i in range(1, 6)}} for system, ranks in rankings_summary.items() if ranks},
            "evaluations": all_evaluations
        }, f, indent=2)

    print(f"\n✓ Summary saved: {summary_file}")

    # Overall winner
    if any(rankings_summary.values()):
        best = min(((s, sum(r)/len(r)) for s, r in rankings_summary.items() if r), key=lambda x: x[1])
        print("\n" + "=" * 80)
        print(f"🏆 OVERALL WINNER: {best[0].upper()}")
        print(f"   Average rank: {best[1]:.2f}")
        print("=" * 80)


if __name__ == "__main__":
    main()
