"""Analyze detailed scores from 5-way judge evaluation."""
import json
from pathlib import Path
from collections import defaultdict

# Map solution IDs to system names
SOLUTION_TO_SYSTEM = {
    "solution_a": "ALO",
    "solution_b": "ALO-Sonnet",
    "solution_c": "ALO-Open",
    "solution_d": "ALO-Optimized",
    "solution_e": "Sonnet+Context"
}

DIMENSIONS = ["correctness", "completeness", "code_quality", "security", "clarity"]

def main():
    eval_dir = Path("benchmark/results/5way_complete/evaluations")

    # Collect all scores
    scores_by_system = defaultdict(lambda: defaultdict(list))
    overall_by_system = defaultdict(list)

    eval_files = sorted(eval_dir.glob("*_eval.json"))

    print("=" * 80)
    print("DETAILED SCORE ANALYSIS")
    print("=" * 80)
    print(f"\nAnalyzing {len(eval_files)} evaluations...")
    print()

    for eval_file in eval_files:
        with open(eval_file) as f:
            data = json.load(f)

        evaluation = data["evaluation"]

        for solution_id, system_name in SOLUTION_TO_SYSTEM.items():
            if solution_id in evaluation:
                sol_data = evaluation[solution_id]

                # Collect dimension scores
                for dim in DIMENSIONS:
                    if dim in sol_data:
                        score = sol_data[dim]["score"]
                        scores_by_system[system_name][dim].append(score)

                # Collect overall score
                if "overall" in sol_data:
                    overall_by_system[system_name].append(sol_data["overall"])

    # Calculate averages
    print("=" * 80)
    print("AVERAGE SCORES BY SYSTEM (1-10 scale)")
    print("=" * 80)
    print()

    results = []
    for system in ["ALO-Optimized", "Sonnet+Context", "ALO", "ALO-Sonnet", "ALO-Open"]:
        if system not in scores_by_system:
            continue

        print(f"{'=' * 80}")
        print(f"{system}")
        print(f"{'=' * 80}")

        dim_scores = scores_by_system[system]
        overall = overall_by_system[system]

        avg_overall = sum(overall) / len(overall) if overall else 0

        print(f"  Overall:         {avg_overall:.2f}")
        print()

        dim_avgs = {}
        for dim in DIMENSIONS:
            if dim in dim_scores:
                avg = sum(dim_scores[dim]) / len(dim_scores[dim])
                dim_avgs[dim] = avg
                print(f"  {dim.replace('_', ' ').title():<18} {avg:.2f}")

        print()

        results.append({
            "system": system,
            "overall": avg_overall,
            "dimensions": dim_avgs
        })

    # Summary table
    print("\n" + "=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)
    print()
    print(f"{'System':<20} {'Overall':<10} {'Correct':<10} {'Complete':<10} {'Quality':<10} {'Security':<10} {'Clarity':<10}")
    print("-" * 100)

    for r in results:
        dims = r["dimensions"]
        print(f"{r['system']:<20} {r['overall']:<10.2f} "
              f"{dims.get('correctness', 0):<10.2f} "
              f"{dims.get('completeness', 0):<10.2f} "
              f"{dims.get('code_quality', 0):<10.2f} "
              f"{dims.get('security', 0):<10.2f} "
              f"{dims.get('clarity', 0):<10.2f}")

    # Find strengths
    print("\n" + "=" * 80)
    print("SYSTEM STRENGTHS")
    print("=" * 80)

    for dim in DIMENSIONS:
        best_system = max(results, key=lambda r: r["dimensions"].get(dim, 0))
        best_score = best_system["dimensions"].get(dim, 0)
        print(f"\n{dim.replace('_', ' ').title()}:")
        print(f"  🏆 {best_system['system']}: {best_score:.2f}")

    # Overall winner
    print("\n" + "=" * 80)
    best_overall = max(results, key=lambda r: r["overall"])
    print(f"🏆 HIGHEST OVERALL SCORE: {best_overall['system']} ({best_overall['overall']:.2f}/10)")
    print("=" * 80)


if __name__ == "__main__":
    main()
