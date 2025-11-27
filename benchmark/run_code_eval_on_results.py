"""Run code evaluations on existing benchmark results."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.evaluators import CodeEvaluator


PROMPT_IDS = [
    "rate_limiter",
    "lru_cache",
    "byzantine_consensus",
    "compiler_parser",
    "database_btree",
    "distributed_lock",
    "async_task_queue",
    "timeseries_anomaly",
    "graph_cycle_detection",
    "regex_engine"
]

SYSTEMS = [
    "alo_optimized",
    "alo_open",
    "alo_bestinclass",
    "alo_sonnet",
    "alo_opus"
]


def main():
    """Run code evaluation on all benchmark outputs."""
    results_dir = Path("benchmark/results/final_5way")

    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return

    evaluator = CodeEvaluator(timeout=10)

    # Store all results
    all_results = {}

    print("=" * 80)
    print("CODE EVALUATION - 5-Way Benchmark Results")
    print("=" * 80)

    for system in SYSTEMS:
        system_dir = results_dir / system
        if not system_dir.exists():
            print(f"\nSkipping {system} - directory not found")
            continue

        print(f"\n{system.upper()}:")
        print("-" * 60)

        system_results = {}

        for prompt_id in PROMPT_IDS:
            output_file = system_dir / f"{prompt_id}.txt"

            if not output_file.exists():
                print(f"  {prompt_id}: MISSING")
                continue

            # Read output
            output = output_file.read_text()

            # Evaluate
            result = evaluator.evaluate(output, prompt_id)

            # Store result
            system_results[prompt_id] = {
                "syntax_valid": result.syntax_valid,
                "syntax_error": result.syntax_error,
                "executes": result.executes,
                "execution_error": result.execution_error,
                "error_type": result.error_type,
                "has_required_patterns": result.has_required_patterns,
                "found_patterns": result.found_patterns,
                "missing_patterns": result.missing_patterns,
            }

            # Print summary
            status = []
            if result.syntax_valid:
                status.append("✓ Syntax")
            else:
                status.append("✗ Syntax")

            if result.executes:
                status.append("✓ Exec")
            else:
                status.append(f"✗ Exec ({result.error_type})")

            if result.has_required_patterns:
                status.append("✓ Patterns")
            else:
                status.append(f"✗ Patterns ({len(result.missing_patterns)} missing)")

            print(f"  {prompt_id:25} {' | '.join(status)}")

        all_results[system] = system_results

    # Aggregate statistics
    print("\n" + "=" * 80)
    print("AGGREGATE STATISTICS")
    print("=" * 80)

    print("\n{:<20} {:>12} {:>12} {:>12}".format(
        "System", "Syntax Valid", "Executes", "Has Patterns"
    ))
    print("-" * 60)

    for system in SYSTEMS:
        if system not in all_results:
            continue

        results = all_results[system]
        total = len(results)

        syntax_valid = sum(1 for r in results.values() if r["syntax_valid"])
        executes = sum(1 for r in results.values() if r["executes"])
        has_patterns = sum(1 for r in results.values() if r["has_required_patterns"])

        print("{:<20} {:>12} {:>12} {:>12}".format(
            system,
            f"{syntax_valid}/{total}",
            f"{executes}/{total}",
            f"{has_patterns}/{total}"
        ))

    # Save detailed results
    output_file = results_dir / "code_evaluation_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n✓ Detailed results saved to: {output_file}")

    # Error analysis
    print("\n" + "=" * 80)
    print("ERROR ANALYSIS")
    print("=" * 80)

    error_counts = {}
    for system, results in all_results.items():
        for prompt_id, result in results.items():
            if not result["executes"] and result["error_type"]:
                error_type = result["error_type"]
                if error_type not in error_counts:
                    error_counts[error_type] = []
                error_counts[error_type].append(f"{system}/{prompt_id}")

    if error_counts:
        print("\nMost Common Execution Errors:")
        for error_type in sorted(error_counts.keys(), key=lambda k: len(error_counts[k]), reverse=True):
            occurrences = error_counts[error_type]
            print(f"\n  {error_type}: {len(occurrences)} occurrences")
            for occurrence in occurrences[:5]:  # Show first 5
                print(f"    - {occurrence}")
            if len(occurrences) > 5:
                print(f"    ... and {len(occurrences) - 5} more")
    else:
        print("\nNo execution errors found!")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
