"""Run 5-way judge evaluation comparing all ALO variants.

Evaluates and ranks: ALO, ALO-Sonnet, ALO-Open, ALO-Optimized, Sonnet+Context
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.evaluators.evaluation_schema_5way import (
    JUDGE_PROMPT_5WAY,
    ComparativeEvaluation5Way,
    DimensionScore,
    SolutionEvaluation
)

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


def load_solution(base_path: Path, system: str, prompt_id: str) -> Optional[str]:
    """Load a solution output from disk."""
    # Try multiple possible locations
    possible_paths = [
        base_path / "parallel_2systems" / system / f"{prompt_id}.txt",
        base_path / "run_20251121_090012" / system / f"{prompt_id}.txt",  # 3-system run
        base_path / system / f"{prompt_id}.txt",
    ]

    for path in possible_paths:
        if path.exists():
            return path.read_text()

    return None


def call_judge(prompt_data: dict, solutions: Dict[str, str]) -> Optional[Dict]:
    """Call GPT-4o judge to evaluate and rank 5 solutions."""

    # Build judge prompt
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
    print("5-WAY JUDGE EVALUATION")
    print("=" * 80)
    print("Systems: ALO | ALO-Sonnet | ALO-Open | ALO-Optimized | Sonnet+Context")
    print(f"Prompts: {len(HARD_PROMPTS)}")
    print("Judge: GPT-4o with strict scoring")
    print("=" * 80)

    results_dir = Path("benchmark/results")

    # Prepare output directory
    output_dir = results_dir / "5way_judge"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_evaluations = []
    rankings_summary = {
        "alo": [],
        "alo_sonnet": [],
        "alo_open": [],
        "alo_optimized": [],
        "sonnet_context": []
    }

    for i, prompt_data in enumerate(HARD_PROMPTS, 1):
        print(f"\n[{i}/{len(HARD_PROMPTS)}] {prompt_data['id']}")
        print("-" * 80)

        # Load all 5 solutions
        solutions = {
            "alo": load_solution(results_dir, "alo", prompt_data["id"]),
            "alo_sonnet": load_solution(results_dir, "alo_sonnet", prompt_data["id"]),
            "alo_open": load_solution(results_dir, "alo_open", prompt_data["id"]),
            "alo_optimized": load_solution(results_dir, "alo_optimized", prompt_data["id"]),
            "sonnet_context": load_solution(results_dir, "sonnet_context", prompt_data["id"])
        }

        # Check which solutions are available
        available = [k for k, v in solutions.items() if v is not None]
        missing = [k for k, v in solutions.items() if v is None]

        print(f"  Available: {', '.join(available)}")
        if missing:
            print(f"  Missing: {', '.join(missing)}")

        if len(available) < 5:
            print(f"  ⚠️  Skipping - need all 5 solutions")
            continue

        # Call judge
        print("  Calling judge...")
        evaluation = call_judge(prompt_data, solutions)

        if evaluation:
            # Extract ranking
            ranking = evaluation.get("ranking", [])
            winner = evaluation.get("winner", "unknown")

            print(f"  ✓ Judge complete")
            print(f"    Winner: {winner}")
            print(f"    Ranking: {' > '.join(ranking)}")

            # Track rankings for each system
            for rank_idx, system_id in enumerate(ranking):
                rankings_summary[system_id].append(rank_idx + 1)  # 1st place, 2nd place, etc.

            # Save individual evaluation
            eval_file = output_dir / f"{prompt_data['id']}_eval.json"
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
        else:
            print(f"  ✗ Judge failed")

        time.sleep(1)  # Rate limiting

    # Generate summary report
    print("\n" + "=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)

    summary = {
        "total_evaluations": len(all_evaluations),
        "systems": list(rankings_summary.keys()),
        "rankings": {}
    }

    print(f"\nTotal evaluations: {len(all_evaluations)}")

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
        print(f"  Wins (1st): {wins}")
        print(f"  Top 3 finishes: {top_3}/{len(ranks)}")
        print(f"  Rank distribution: 1st={ranks.count(1)} | 2nd={ranks.count(2)} | 3rd={ranks.count(3)} | 4th={ranks.count(4)} | 5th={ranks.count(5)}")

    # Save summary
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    summary_file = output_dir / f"summary_{timestamp}.json"

    with open(summary_file, "w") as f:
        json.dump({
            "metadata": {
                "timestamp": timestamp,
                "judge_model": "gpt-4o",
                "total_prompts": len(HARD_PROMPTS),
                "evaluated": len(all_evaluations)
            },
            "summary": summary,
            "evaluations": all_evaluations
        }, f, indent=2)

    print(f"\n✓ Summary saved to: {summary_file}")

    # Determine overall winner
    if summary["rankings"]:
        overall_winner = min(summary["rankings"].items(), key=lambda x: x[1]["average_rank"])
        print("\n" + "=" * 80)
        print(f"🏆 OVERALL WINNER: {overall_winner[0].upper()}")
        print(f"   Average rank: {overall_winner[1]['average_rank']:.2f}")
        print(f"   Wins: {overall_winner[1]['wins']}")
        print("=" * 80)

    return summary


if __name__ == "__main__":
    main()
