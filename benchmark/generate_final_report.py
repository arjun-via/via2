"""Generate comprehensive final report combining LLM judge + code evaluation."""
import json
from pathlib import Path
from typing import Dict


def load_llm_judge_scores(summary_file: Path) -> Dict:
    """Load existing LLM judge scores from summary JSON."""
    with open(summary_file) as f:
        data = json.load(f)

    # Extract scores from "all_scores" section
    return data.get("all_scores", {})


def load_code_evaluation(code_eval_file: Path) -> Dict:
    """Load code evaluation results."""
    with open(code_eval_file) as f:
        return json.load(f)


def calculate_code_score(result: Dict) -> float:
    """Calculate 0-10 score from code evaluation."""
    score = 0.0
    if result.get("syntax_valid"):
        score += 4.0
    if result.get("executes"):
        score += 4.0
    if result.get("has_required_patterns"):
        score += 2.0
    return score


def main():
    """Generate final comprehensive report."""
    results_dir = Path("benchmark/results/final_5way")

    # Load both evaluation types
    llm_scores = load_llm_judge_scores(results_dir / "summary_20251125_092338.json")
    code_eval = load_code_evaluation(results_dir / "code_evaluation_results.json")

    print("=" * 100)
    print("COMPREHENSIVE EVALUATION REPORT - LLM Judge + Code Evaluation")
    print("=" * 100)

    # Define systems
    systems = ["alo_optimized", "alo_open", "alo_bestinclass", "alo_sonnet", "alo_opus"]
    prompts = [
        "rate_limiter", "lru_cache", "byzantine_consensus", "compiler_parser",
        "database_btree", "distributed_lock", "async_task_queue",
        "timeseries_anomaly", "graph_cycle_detection", "regex_engine"
    ]

    # Calculate combined scores
    combined_results = {}

    for system in systems:
        print(f"\n{system.upper()}")
        print("-" * 100)
        print(f"{'Prompt':<25} {'Code':<10} {'LLM-Cor':<10} {'LLM-Com':<10} {'LLM-Qual':<10} {'LLM-Avg':<10} {'Combined':<10}")
        print("-" * 100)

        system_scores = {
            "code_scores": [],
            "llm_scores": [],
            "combined_scores": []
        }

        for prompt in prompts:
            # Code eval score
            code_result = code_eval.get(system, {}).get(prompt, {})
            code_score = calculate_code_score(code_result)

            # LLM judge scores
            llm_result = llm_scores.get(system, {}).get(prompt, {})
            correctness = llm_result.get("correctness", {}).get("score", 0) if llm_result else 0
            completeness = llm_result.get("completeness", {}).get("score", 0) if llm_result else 0
            quality = llm_result.get("code_quality", {}).get("score", 0) if llm_result else 0

            # Calculate LLM average (use correctness, completeness, quality)
            llm_avg = (correctness + completeness + quality) / 3.0 if llm_result else 0.0

            # Combined score (equal weight)
            combined = (code_score + llm_avg) / 2.0

            # Store for aggregate calculation
            system_scores["code_scores"].append(code_score)
            system_scores["llm_scores"].append(llm_avg)
            system_scores["combined_scores"].append(combined)

            # Print row
            print(f"{prompt:<25} {code_score:<10.1f} {correctness:<10.1f} {completeness:<10.1f} {quality:<10.1f} {llm_avg:<10.2f} {combined:<10.2f}")

        # Print system averages
        avg_code = sum(system_scores["code_scores"]) / len(system_scores["code_scores"])
        avg_llm = sum(system_scores["llm_scores"]) / len(system_scores["llm_scores"])
        avg_combined = sum(system_scores["combined_scores"]) / len(system_scores["combined_scores"])

        print("-" * 100)
        print(f"{'AVERAGE':<25} {avg_code:<10.2f} {'':10} {'':10} {'':10} {avg_llm:<10.2f} {avg_combined:<10.2f}")

        combined_results[system] = {
            "avg_code": avg_code,
            "avg_llm": avg_llm,
            "avg_combined": avg_combined
        }

    # Final rankings
    print("\n" + "=" * 100)
    print("FINAL RANKINGS")
    print("=" * 100)

    # Sort by combined score
    rankings = sorted(combined_results.items(), key=lambda x: x[1]["avg_combined"], reverse=True)

    print(f"\n{'Rank':<6} {'System':<20} {'Combined':<12} {'Code Eval':<12} {'LLM Judge':<12} {'Delta':<10}")
    print("-" * 75)

    for rank, (system, scores) in enumerate(rankings, 1):
        delta = scores["avg_code"] - scores["avg_llm"]
        delta_str = f"{delta:+.2f}"
        print(f"{rank:<6} {system:<20} {scores['avg_combined']:<12.2f} {scores['avg_code']:<12.2f} {scores['avg_llm']:<12.2f} {delta_str:<10}")

    # Analysis
    print("\n" + "=" * 100)
    print("KEY INSIGHTS")
    print("=" * 100)

    print("\n1. CODE EVALUATION VS LLM JUDGE CORRELATION:")
    for system, scores in rankings:
        diff = scores["avg_code"] - scores["avg_llm"]
        if abs(diff) < 0.5:
            status = "ALIGNED"
        elif diff > 0:
            status = "CODE BETTER"
        else:
            status = "LLM BETTER"
        print(f"   {system:<20} Δ={diff:+5.2f} → {status}")

    print("\n2. WINNER BY EVALUATION METHOD:")
    code_winner = max(combined_results.items(), key=lambda x: x[1]["avg_code"])
    llm_winner = max(combined_results.items(), key=lambda x: x[1]["avg_llm"])
    combined_winner = rankings[0]

    print(f"   Code Evaluation:  {code_winner[0]} ({code_winner[1]['avg_code']:.2f}/10)")
    print(f"   LLM Judge:        {llm_winner[0]} ({llm_winner[1]['avg_llm']:.2f}/10)")
    print(f"   Combined (50/50): {combined_winner[0]} ({combined_winner[1]['avg_combined']:.2f}/10)")

    if code_winner[0] != llm_winner[0]:
        print(f"\n   ⚠️  WARNING: Code eval and LLM judge disagree on winner!")
        print(f"      This validates Hamel/Shreya's warning about LLM judge limitations.")

    print("\n3. CONSISTENCY ANALYSIS:")
    for system, scores in combined_results.items():
        variance = abs(scores["avg_code"] - scores["avg_llm"])
        if variance < 1.0:
            consistency = "HIGH"
        elif variance < 2.0:
            consistency = "MEDIUM"
        else:
            consistency = "LOW"
        print(f"   {system:<20} Variance: {variance:5.2f} → {consistency} consistency")

    # Save report
    report_data = {
        "rankings": [{"rank": i+1, "system": s, **sc} for i, (s, sc) in enumerate(rankings)],
        "detailed_scores": combined_results,
        "insights": {
            "code_winner": code_winner[0],
            "llm_winner": llm_winner[0],
            "combined_winner": combined_winner[0],
            "evaluation_disagreement": code_winner[0] != llm_winner[0]
        }
    }

    report_file = results_dir / "comprehensive_report.json"
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)

    print(f"\n✓ Report saved to: {report_file}")
    print("=" * 100)


if __name__ == "__main__":
    main()
