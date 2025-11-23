"""Benchmark ALO vs ALO-Sonnet vs Sonnet+Context on 10 hard prompts."""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.evaluators.o3_mini_judge import O3MiniJudge
from benchmark.runners.alo_runner import ALORunner
from benchmark.runners.alo_sonnet_runner import ALOSonnetRunner
from benchmark.runners.sonnet_runner import SonnetContextRunner

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# Only the 10 HARD prompts
HARD_PROMPTS = [
    "01_byzantine_consensus",
    "02_memory_leak_forensics",
    "03_options_pricing_greeks",
    "04_lockfree_queue",
    "05_market_maker_adverse_selection",
    "06_fuzzy_matching_scale",
    "07_distributed_transaction_coordinator",
    "08_timeseries_anomaly_detection",
    "09_circuit_breaker_backoff",
    "10_zero_downtime_migration"
]


def load_prompts(prompts_dir: str = "benchmark/prompts") -> List[Dict]:
    """Load only the hard prompt YAML files."""
    prompts = []
    prompts_path = Path(prompts_dir)

    for prompt_id in HARD_PROMPTS:
        yaml_file = prompts_path / f"{prompt_id}.yaml"
        if yaml_file.exists():
            with open(yaml_file, 'r') as f:
                prompt_data = yaml.safe_load(f)
                prompts.append(prompt_data)

    return prompts


def run_single_prompt(
    prompt_data: Dict,
    runners: Dict[str, any],
    judge: O3MiniJudge,
    output_dir: Path
) -> Dict:
    """Run 3 systems on a single prompt and evaluate."""
    prompt_id = prompt_data["id"]
    prompt_text = prompt_data["prompt"]

    print(f"\n{'='*80}")
    print(f"Running prompt: {prompt_id} - {prompt_data['title']}")
    print(f"Category: {prompt_data['category']}")
    print(f"{'='*80}\n")

    prompt_output_dir = output_dir / prompt_id
    prompt_output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # 1. Run ALO (mixed models)
    print("[1/3] Running ALO (mixed models)...")
    try:
        alo_result = runners["alo"].run(prompt_text)
        results["alo"] = alo_result

        with open(prompt_output_dir / "alo_output.txt", "w") as f:
            f.write(alo_result.output)
        with open(prompt_output_dir / "alo_metadata.json", "w") as f:
            json.dump({
                "elapsed_time": alo_result.elapsed_time,
                "cost": alo_result.cost,
                "metadata": alo_result.metadata
            }, f, indent=2)

        context_for_sonnet = alo_result.context_used or ""
        print(f"   ✓ Complete - Time: {alo_result.elapsed_time:.2f}s, Cost: ${alo_result.cost:.4f}")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        results["alo"] = None
        context_for_sonnet = ""

    # 2. Run ALO-Sonnet (all Sonnet)
    print("[2/3] Running ALO-Sonnet (all Sonnet)...")
    try:
        alo_sonnet_result = runners["alo_sonnet"].run(prompt_text)
        results["alo_sonnet"] = alo_sonnet_result

        with open(prompt_output_dir / "alo_sonnet_output.txt", "w") as f:
            f.write(alo_sonnet_result.output)
        with open(prompt_output_dir / "alo_sonnet_metadata.json", "w") as f:
            json.dump({
                "elapsed_time": alo_sonnet_result.elapsed_time,
                "cost": alo_sonnet_result.cost,
                "metadata": alo_sonnet_result.metadata
            }, f, indent=2)

        print(f"   ✓ Complete - Time: {alo_sonnet_result.elapsed_time:.2f}s, Cost: ${alo_sonnet_result.cost:.4f}")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        results["alo_sonnet"] = None

    # 3. Run Sonnet+Context
    print("[3/3] Running Sonnet+Context (single call)...")
    try:
        sonnet_context_result = runners["sonnet_context"].run(prompt_text, context=context_for_sonnet)
        results["sonnet_context"] = sonnet_context_result

        with open(prompt_output_dir / "sonnet_context_output.txt", "w") as f:
            f.write(sonnet_context_result.output)
        with open(prompt_output_dir / "sonnet_context_metadata.json", "w") as f:
            json.dump({
                "elapsed_time": sonnet_context_result.elapsed_time,
                "cost": sonnet_context_result.cost,
                "metadata": sonnet_context_result.metadata
            }, f, indent=2)

        print(f"   ✓ Complete - Time: {sonnet_context_result.elapsed_time:.2f}s, Cost: ${sonnet_context_result.cost:.4f}")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        results["sonnet_context"] = None

    # 4. Judge evaluation
    print("\n[Evaluation] Running judge...")
    if all(results.get(k) for k in ["alo", "alo_sonnet", "sonnet_context"]):
        try:
            evaluation, eval_metadata = judge.evaluate(
                original_prompt=prompt_text,
                context_summary=context_for_sonnet,
                alo_output=results["alo"].output,
                sonnet_context_output=results["alo_sonnet"].output,  # Map to solution_b
                sonnet_raw_output=results["sonnet_context"].output   # Map to solution_c
            )

            # Save evaluation
            eval_data = {
                "alo": {
                    "overall": evaluation.solution_a.overall,
                    "correctness": evaluation.solution_a.correctness.score,
                    "completeness": evaluation.solution_a.completeness.score,
                    "code_quality": evaluation.solution_a.code_quality.score,
                    "security": evaluation.solution_a.security.score,
                    "clarity": evaluation.solution_a.clarity.score,
                    "strengths": evaluation.solution_a.strengths,
                    "weaknesses": evaluation.solution_a.weaknesses
                },
                "alo_sonnet": {
                    "overall": evaluation.solution_b.overall,
                    "correctness": evaluation.solution_b.correctness.score,
                    "completeness": evaluation.solution_b.completeness.score,
                    "code_quality": evaluation.solution_b.code_quality.score,
                    "security": evaluation.solution_b.security.score,
                    "clarity": evaluation.solution_b.clarity.score,
                    "strengths": evaluation.solution_b.strengths,
                    "weaknesses": evaluation.solution_b.weaknesses
                },
                "sonnet_context": {
                    "overall": evaluation.solution_c.overall,
                    "correctness": evaluation.solution_c.correctness.score,
                    "completeness": evaluation.solution_c.completeness.score,
                    "code_quality": evaluation.solution_c.code_quality.score,
                    "security": evaluation.solution_c.security.score,
                    "clarity": evaluation.solution_c.clarity.score,
                    "strengths": evaluation.solution_c.strengths,
                    "weaknesses": evaluation.solution_c.weaknesses
                },
                "winner": evaluation.winner,
                "winner_reasoning": evaluation.winner_reasoning,
                "comparative_analysis": evaluation.comparative_analysis,
                "judge_metadata": eval_metadata
            }

            with open(prompt_output_dir / "evaluation.json", "w") as f:
                json.dump(eval_data, f, indent=2)

            # Map solution letters to system names
            winner_map = {
                "solution_a": "ALO",
                "solution_b": "ALO-Sonnet",
                "solution_c": "Sonnet+Context"
            }
            winner_name = winner_map.get(evaluation.winner, evaluation.winner)

            print(f"   ✓ Evaluation complete")
            print(f"      Winner: {winner_name}")
            print(f"      Scores: ALO={evaluation.solution_a.overall:.1f}, "
                  f"ALO-Sonnet={evaluation.solution_b.overall:.1f}, "
                  f"Sonnet+Ctx={evaluation.solution_c.overall:.1f}")

            results["evaluation"] = evaluation

        except Exception as e:
            print(f"   ✗ Evaluation failed: {e}")
            import traceback
            traceback.print_exc()
            results["evaluation"] = None
    else:
        print("   ⊘ Skipping evaluation (some runs failed)")
        results["evaluation"] = None

    return results


def main():
    parser = argparse.ArgumentParser(description="Compare ALO vs ALO-Sonnet vs Sonnet+Context on 10 hard prompts")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args()

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"benchmark/results/alo_comparison_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"ALO Comparison Benchmark")
    print(f"Systems: ALO (mixed) vs ALO-Sonnet (all Sonnet) vs Sonnet+Context")
    print(f"Prompts: 10 hard prompts")
    print(f"Output: {output_dir}")
    print(f"{'='*80}\n")

    # Initialize runners
    print("Initializing runners...")
    runners = {
        "alo": ALORunner(),
        "alo_sonnet": ALOSonnetRunner(),
        "sonnet_context": SonnetContextRunner()
    }
    print("   ✓ Runners initialized\n")

    # Initialize judge
    print("Initializing GPT-4o judge...")
    with open("benchmark/config_benchmark.yaml", "r") as f:
        bench_config = yaml.safe_load(f)

    judge = O3MiniJudge(
        model=bench_config["judge"]["model"],
        base_url=bench_config["judge"]["base_url"],
        temperature=bench_config["judge"]["temperature"]
    )
    print("   ✓ Judge initialized\n")

    # Load hard prompts
    prompts_to_run = load_prompts()
    print(f"Running {len(prompts_to_run)} hard prompts:\n")
    for p in prompts_to_run:
        print(f"  - {p['id']}: {p['title']}")
    print()

    # Run benchmark
    all_results = []
    for prompt_data in prompts_to_run:
        results = run_single_prompt(prompt_data, runners, judge, output_dir)
        all_results.append({
            "prompt": prompt_data,
            "results": results
        })

    # Save summary
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "prompts_run": len(prompts_to_run),
            "systems": ["alo", "alo_sonnet", "sonnet_context"],
            "config": bench_config
        }, f, indent=2)

    print(f"\n{'='*80}")
    print(f"Benchmark complete!")
    print(f"Results saved to: {output_dir}")
    print(f"{'='*80}\n")

    return all_results


if __name__ == "__main__":
    main()
