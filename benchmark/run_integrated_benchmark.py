"""Phase 5: Operationalized Benchmark - Combines LLM Judge + Code Evaluation.

This script runs a complete benchmark that includes:
1. Generate outputs from all systems
2. LLM judge evaluation (subjective quality)
3. Code-based evaluation (objective metrics)
4. Combined scoring and analysis
"""
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.evaluators import CodeEvaluator, CodeEvalResult
from benchmark.evaluators.o3_mini_judge import O3MiniJudge


# Import all runners
from benchmark.runners.alo_optimized_runner import ALOOptimizedRunner
from benchmark.runners.alo_open_runner import ALOOpenRunner
from benchmark.runners.alo_bestinclass_runner import ALOBestInClassRunner
from benchmark.runners.alo_sonnet_runner import ALOSonnetRunner
from benchmark.runners.alo_opus_runner import ALOOpusRunner


HARD_PROMPTS = [
    {"id": "rate_limiter", "prompt": "Implement a rate limiter using the token bucket algorithm in Python. Include thread safety and support for multiple users."},
    {"id": "lru_cache", "prompt": "Design and implement a thread-safe LRU cache in Python with O(1) get/put operations. Support TTL expiration."},
    {"id": "byzantine_consensus", "prompt": "Implement the Byzantine Generals Problem solution using a simplified consensus algorithm. Handle up to f faulty nodes in a network of 3f+1 nodes."},
    {"id": "compiler_parser", "prompt": "Build a parser for a simple programming language with variables, arithmetic, if/else, and while loops. Include lexer, parser, and AST."},
    {"id": "database_btree", "prompt": "Implement a B-tree index structure for a database engine. Support insertion, deletion, range queries, and handle node splits/merges."},
    {"id": "distributed_lock", "prompt": "Design a distributed lock manager using Redis. Handle lock acquisition, expiration, deadlock detection, and client failures."},
    {"id": "async_task_queue", "prompt": "Create an async task queue system with priority scheduling, task dependencies, retries, and worker pool management."},
    {"id": "timeseries_anomaly", "prompt": "Build a real-time anomaly detection system for time series data using statistical methods. Detect outliers, trends, and seasonality."},
    {"id": "graph_cycle_detection", "prompt": "Implement Tarjan's algorithm for detecting strongly connected components and cycles in a directed graph."},
    {"id": "regex_engine", "prompt": "Build a regex engine that supports basic patterns (*, +, ?, |), character classes, and captures. Use Thompson's NFA construction."}
]


def load_prompts() -> Dict[str, str]:
    """Load prompts from HARD_PROMPTS."""
    return {item["id"]: item["prompt"] for item in HARD_PROMPTS}


def calculate_code_score(result: CodeEvalResult) -> float:
    """Calculate a 0-10 score from code evaluation results.

    Scoring rubric:
    - Syntax valid: 4 points (pass/fail)
    - Executes: 4 points (pass/fail)
    - Has patterns: 2 points (pass/fail)
    """
    score = 0.0

    if result.syntax_valid:
        score += 4.0

    if result.executes:
        score += 4.0

    if result.has_required_patterns:
        score += 2.0

    return score


def calculate_combined_score(llm_scores: Dict[str, float], code_score: float, alpha: float = 0.5) -> float:
    """Calculate combined score from LLM judge and code evaluation.

    Args:
        llm_scores: Dict with 'correctness', 'completeness', 'efficiency'
        code_score: Code evaluation score (0-10)
        alpha: Weight for code score (0-1), LLM gets (1-alpha)

    Returns:
        Combined score (0-10)
    """
    # Average LLM scores
    llm_avg = sum(llm_scores.values()) / len(llm_scores)

    # Weighted combination
    combined = alpha * code_score + (1 - alpha) * llm_avg

    return combined


def run_benchmark(
    systems: Dict[str, any],
    prompts: Dict[str, str],
    output_dir: Path,
    run_generation: bool = True,
    llm_judge_weight: float = 0.5
):
    """Run integrated benchmark with LLM judge + code evaluation.

    Args:
        systems: Dict mapping system_name -> runner instance
        prompts: Dict mapping prompt_id -> prompt text
        output_dir: Directory to save results
        run_generation: If False, skip generation and evaluate existing outputs
        llm_judge_weight: Weight for LLM judge (0-1), code eval gets (1-weight)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize evaluators
    code_evaluator = CodeEvaluator(timeout=10)
    llm_judge = O3MiniJudge()

    # Store all results
    all_results = {
        "systems": {},
        "prompts": list(prompts.keys()),
        "evaluation_config": {
            "llm_judge_weight": llm_judge_weight,
            "code_eval_weight": 1 - llm_judge_weight
        }
    }

    print("=" * 80)
    print("INTEGRATED BENCHMARK - LLM Judge + Code Evaluation")
    print("=" * 80)
    print(f"Systems: {len(systems)}")
    print(f"Prompts: {len(prompts)}")
    print(f"LLM Judge Weight: {llm_judge_weight:.1f}")
    print(f"Code Eval Weight: {1-llm_judge_weight:.1f}")
    print("=" * 80)

    # Phase 1: Generation (if needed)
    if run_generation:
        print("\nPHASE 1: GENERATION")
        print("-" * 80)

        for system_name, runner in systems.items():
            system_dir = output_dir / system_name
            system_dir.mkdir(exist_ok=True)

            print(f"\n{system_name}:")

            for prompt_id, prompt in prompts.items():
                print(f"  {prompt_id}...", end=" ", flush=True)

                output_file = system_dir / f"{prompt_id}.txt"

                if output_file.exists():
                    print("CACHED")
                    continue

                try:
                    result = runner.run(prompt)
                    output_file.write_text(result.output)
                    print(f"OK ({result.elapsed_time:.1f}s)")
                except Exception as e:
                    print(f"ERROR: {e}")
                    continue

    # Phase 2: Code Evaluation
    print("\n\nPHASE 2: CODE EVALUATION")
    print("-" * 80)

    for system_name in systems.keys():
        print(f"\n{system_name}:")
        system_dir = output_dir / system_name

        if system_name not in all_results["systems"]:
            all_results["systems"][system_name] = {}

        for prompt_id in prompts.keys():
            output_file = system_dir / f"{prompt_id}.txt"

            if not output_file.exists():
                print(f"  {prompt_id:25} MISSING")
                continue

            output = output_file.read_text()

            # Code evaluation
            code_result = code_evaluator.evaluate(output, prompt_id)
            code_score = calculate_code_score(code_result)

            # Store results
            all_results["systems"][system_name][prompt_id] = {
                "code_eval": {
                    "syntax_valid": code_result.syntax_valid,
                    "executes": code_result.executes,
                    "has_patterns": code_result.has_required_patterns,
                    "score": code_score
                }
            }

            # Print status
            status = []
            if code_result.syntax_valid:
                status.append("✓ Syn")
            else:
                status.append("✗ Syn")

            if code_result.executes:
                status.append("✓ Exe")
            else:
                status.append("✗ Exe")

            if code_result.has_required_patterns:
                status.append("✓ Pat")
            else:
                status.append("✗ Pat")

            print(f"  {prompt_id:25} {' | '.join(status)} | Score: {code_score:.1f}/10")

    # Phase 3: LLM Judge Evaluation
    print("\n\nPHASE 3: LLM JUDGE EVALUATION")
    print("-" * 80)

    for system_name in systems.keys():
        print(f"\n{system_name}:")
        system_dir = output_dir / system_name

        for prompt_id, prompt in prompts.items():
            output_file = system_dir / f"{prompt_id}.txt"

            if not output_file.exists():
                continue

            output = output_file.read_text()

            # LLM judge evaluation
            try:
                eval_result = llm_judge.evaluate(
                    output=output,
                    prompt=prompt,
                    prompt_id=prompt_id
                )

                llm_scores = {
                    "correctness": eval_result.correctness,
                    "completeness": eval_result.completeness,
                    "efficiency": eval_result.efficiency
                }
                llm_avg = sum(llm_scores.values()) / len(llm_scores)

                # Add to results
                all_results["systems"][system_name][prompt_id]["llm_judge"] = llm_scores
                all_results["systems"][system_name][prompt_id]["llm_judge"]["average"] = llm_avg

                print(f"  {prompt_id:25} Cor: {eval_result.correctness:.1f} | "
                      f"Com: {eval_result.completeness:.1f} | Eff: {eval_result.efficiency:.1f} | "
                      f"Avg: {llm_avg:.1f}")

            except Exception as e:
                print(f"  {prompt_id:25} LLM ERROR: {e}")
                all_results["systems"][system_name][prompt_id]["llm_judge"] = {
                    "error": str(e)
                }

    # Phase 4: Combined Scoring
    print("\n\nPHASE 4: COMBINED SCORING")
    print("-" * 80)

    system_rankings = []

    for system_name in systems.keys():
        system_results = all_results["systems"][system_name]

        code_scores = []
        llm_scores = []
        combined_scores = []

        for prompt_id in prompts.keys():
            if prompt_id not in system_results:
                continue

            result = system_results[prompt_id]

            # Code score
            code_score = result["code_eval"]["score"]
            code_scores.append(code_score)

            # LLM score
            if "llm_judge" in result and "average" in result["llm_judge"]:
                llm_avg = result["llm_judge"]["average"]
                llm_scores.append(llm_avg)

                # Combined score
                combined = calculate_combined_score(
                    result["llm_judge"],
                    code_score,
                    alpha=1 - llm_judge_weight  # Note: inverted because code is alpha
                )
                combined_scores.append(combined)
                result["combined_score"] = combined

        # Calculate averages
        avg_code = sum(code_scores) / len(code_scores) if code_scores else 0
        avg_llm = sum(llm_scores) / len(llm_scores) if llm_scores else 0
        avg_combined = sum(combined_scores) / len(combined_scores) if combined_scores else 0

        all_results["systems"][system_name]["summary"] = {
            "avg_code_score": avg_code,
            "avg_llm_score": avg_llm,
            "avg_combined_score": avg_combined,
            "num_prompts": len(code_scores)
        }

        system_rankings.append((system_name, avg_combined, avg_code, avg_llm))

    # Sort by combined score
    system_rankings.sort(key=lambda x: x[1], reverse=True)

    print("\nFINAL RANKINGS:")
    print(f"\n{'System':<20} {'Combined':>10} {'Code Eval':>10} {'LLM Judge':>10}")
    print("-" * 55)

    for rank, (system_name, combined, code, llm) in enumerate(system_rankings, 1):
        print(f"{rank}. {system_name:<17} {combined:>10.2f} {code:>10.2f} {llm:>10.2f}")

    # Save results
    results_file = output_dir / "integrated_results.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n✓ Results saved to: {results_file}")

    # Generate comparison report
    print("\n" + "=" * 80)
    print("EVALUATION METHOD COMPARISON")
    print("=" * 80)

    print("\nCode Eval vs LLM Judge Correlation:")
    for system_name, combined, code, llm in system_rankings:
        diff = code - llm
        correlation = "aligned" if abs(diff) < 1.0 else ("code better" if diff > 0 else "LLM better")
        print(f"  {system_name:<20} Code: {code:>5.2f} | LLM: {llm:>5.2f} | Diff: {diff:>+6.2f} ({correlation})")

    print("\n" + "=" * 80)


def main():
    """Run integrated benchmark."""
    # Setup
    output_dir = Path("benchmark/results/final_5way")  # Use existing outputs

    # Load prompts
    prompts = load_prompts()

    # Initialize runners
    systems = {
        "alo_optimized": ALOOptimizedRunner(),
        "alo_open": ALOOpenRunner(),
        "alo_bestinclass": ALOBestInClassRunner(),
        "alo_sonnet": ALOSonnetRunner(),
        "alo_opus": ALOOpusRunner()
    }

    # Run benchmark
    # Set run_generation=False to use existing outputs
    # Set llm_judge_weight to control scoring balance (0.5 = equal weight)
    run_benchmark(
        systems=systems,
        prompts=prompts,
        output_dir=output_dir,
        run_generation=False,  # Use existing outputs from final_5way
        llm_judge_weight=0.5  # Equal weight for LLM judge and code eval
    )


if __name__ == "__main__":
    main()
