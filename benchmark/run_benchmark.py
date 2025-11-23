"""Main benchmark orchestrator script."""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import yaml

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.evaluators.o3_mini_judge import O3MiniJudge
from benchmark.runners.alo_runner import ALORunner
from benchmark.runners.sonnet_runner import SonnetContextRunner, SonnetRawRunner

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def load_prompts(prompts_dir: str = "benchmark/prompts") -> List[Dict]:
    """Load all prompt YAML files."""
    prompts = []
    prompts_path = Path(prompts_dir)

    for yaml_file in sorted(prompts_path.glob("*.yaml")):
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
    """Run all systems on a single prompt and evaluate."""
    prompt_id = prompt_data["id"]
    prompt_text = prompt_data["prompt"]

    print(f"\n{'='*80}")
    print(f"Running prompt: {prompt_id} - {prompt_data['title']}")
    print(f"Category: {prompt_data['category']}")
    print(f"{'='*80}\n")

    # Create output directory for this prompt
    prompt_output_dir = output_dir / prompt_id
    prompt_output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # 1. Run ALO first (generates context)
    print("[1/3] Running ALO...")
    try:
        alo_result = runners["alo"].run(prompt_text)
        results["alo"] = alo_result

        # Save ALO output
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

    # 2. Run Sonnet + Context
    print("[2/3] Running Sonnet + Context...")
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

    # 3. Run Sonnet Raw
    print("[3/3] Running Sonnet Raw...")
    try:
        sonnet_raw_result = runners["sonnet_raw"].run(prompt_text)
        results["sonnet_raw"] = sonnet_raw_result

        with open(prompt_output_dir / "sonnet_raw_output.txt", "w") as f:
            f.write(sonnet_raw_result.output)
        with open(prompt_output_dir / "sonnet_raw_metadata.json", "w") as f:
            json.dump({
                "elapsed_time": sonnet_raw_result.elapsed_time,
                "cost": sonnet_raw_result.cost,
                "metadata": sonnet_raw_result.metadata
            }, f, indent=2)

        print(f"   ✓ Complete - Time: {sonnet_raw_result.elapsed_time:.2f}s, Cost: ${sonnet_raw_result.cost:.4f}")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        results["sonnet_raw"] = None

    # 4. Judge evaluation
    print("\n[Evaluation] Running judge...")
    if all(results.get(k) for k in ["alo", "sonnet_context", "sonnet_raw"]):
        try:
            evaluation, eval_metadata = judge.evaluate(
                original_prompt=prompt_text,
                context_summary=context_for_sonnet,
                alo_output=results["alo"].output,
                sonnet_context_output=results["sonnet_context"].output,
                sonnet_raw_output=results["sonnet_raw"].output
            )

            # Save evaluation
            eval_data = {
                "solution_a": {
                    "overall": evaluation.solution_a.overall,
                    "correctness": evaluation.solution_a.correctness.score,
                    "completeness": evaluation.solution_a.completeness.score,
                    "code_quality": evaluation.solution_a.code_quality.score,
                    "security": evaluation.solution_a.security.score,
                    "clarity": evaluation.solution_a.clarity.score,
                    "strengths": evaluation.solution_a.strengths,
                    "weaknesses": evaluation.solution_a.weaknesses
                },
                "solution_b": {
                    "overall": evaluation.solution_b.overall,
                    "correctness": evaluation.solution_b.correctness.score,
                    "completeness": evaluation.solution_b.completeness.score,
                    "code_quality": evaluation.solution_b.code_quality.score,
                    "security": evaluation.solution_b.security.score,
                    "clarity": evaluation.solution_b.clarity.score,
                    "strengths": evaluation.solution_b.strengths,
                    "weaknesses": evaluation.solution_b.weaknesses
                },
                "solution_c": {
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

            print(f"   ✓ Evaluation complete")
            print(f"      Winner: {evaluation.winner}")
            print(f"      Scores: ALO={evaluation.solution_a.overall:.1f}, "
                  f"Sonnet+Ctx={evaluation.solution_b.overall:.1f}, "
                  f"Sonnet Raw={evaluation.solution_c.overall:.1f}")

            results["evaluation"] = evaluation

        except Exception as e:
            print(f"   ✗ Evaluation failed: {e}")
            results["evaluation"] = None
    else:
        print("   ⊘ Skipping evaluation (some runs failed)")
        results["evaluation"] = None

    return results


def main():
    parser = argparse.ArgumentParser(description="Run ALO vs Sonnet benchmark suite")
    parser.add_argument("--prompts", default="all", help="Comma-separated prompt IDs or 'all'")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: benchmark/results/run_TIMESTAMP)")
    args = parser.parse_args()

    # Create output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"benchmark/results/run_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"ALO vs Sonnet 4.5 Benchmark")
    print(f"Output directory: {output_dir}")
    print(f"{'='*80}\n")

    # Load benchmark config
    with open("benchmark/config_benchmark.yaml", "r") as f:
        bench_config = yaml.safe_load(f)

    # Initialize runners
    print("Initializing runners...")
    runners = {
        "alo": ALORunner(),
        "sonnet_context": SonnetContextRunner(),
        "sonnet_raw": SonnetRawRunner()
    }
    print("   ✓ Runners initialized\n")

    # Initialize judge
    judge_model = bench_config["judge"]["model"]
    print(f"Initializing {judge_model} judge...")
    judge = O3MiniJudge(
        model=judge_model,
        base_url=bench_config["judge"]["base_url"],
        temperature=bench_config["judge"]["temperature"]
    )
    print("   ✓ Judge initialized\n")

    # Load prompts
    all_prompts = load_prompts()
    if args.prompts == "all":
        prompts_to_run = all_prompts
    else:
        prompt_ids = [p.strip() for p in args.prompts.split(",")]
        prompts_to_run = [p for p in all_prompts if p["id"] in prompt_ids]

    print(f"Running {len(prompts_to_run)} prompts:\n")
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
            "config": bench_config
        }, f, indent=2)

    print(f"\n{'='*80}")
    print(f"Benchmark complete!")
    print(f"Results saved to: {output_dir}")
    print(f"{'='*80}\n")

    return all_results


if __name__ == "__main__":
    main()
