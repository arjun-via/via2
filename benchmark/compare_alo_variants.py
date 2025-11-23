"""Compare ALO (mixed models) vs ALO-Sonnet (all Sonnet) vs Sonnet+Context."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.runners.alo_runner import ALORunner
from benchmark.runners.alo_sonnet_runner import ALOSonnetRunner
from benchmark.runners.sonnet_runner import SonnetContextRunner

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def compare_on_prompt(prompt_text: str, prompt_id: str, output_dir: Path):
    """Run all three systems on a single prompt and compare."""
    print(f"\n{'='*80}")
    print(f"Comparing on: {prompt_id}")
    print(f"{'='*80}\n")

    results = {}

    # 1. Run ALO (mixed models)
    print("[1/3] Running ALO (Gemini context + GLM engineering + Kimi review)...")
    try:
        alo_runner = ALORunner()
        alo_result = results["alo"] = alo_runner.run(prompt_text)
        print(f"   ✓ Time: {alo_result.elapsed_time:.2f}s, Cost: ${alo_result.cost:.4f}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        results["alo"] = None

    # 2. Run ALO-Sonnet (all Sonnet)
    print("[2/3] Running ALO-Sonnet (Sonnet for ALL phases)...")
    try:
        alo_sonnet_runner = ALOSonnetRunner()
        alo_sonnet_result = results["alo_sonnet"] = alo_sonnet_runner.run(prompt_text)
        print(f"   ✓ Time: {alo_sonnet_result.elapsed_time:.2f}s, Cost: ${alo_sonnet_result.cost:.4f}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        results["alo_sonnet"] = None

    # 3. Run Sonnet+Context (single shot with context from ALO)
    print("[3/3] Running Sonnet+Context (single call)...")
    try:
        # Use context from ALO if available
        context = results["alo"].context_used if results.get("alo") else None
        sonnet_runner = SonnetContextRunner()
        sonnet_result = results["sonnet_context"] = sonnet_runner.run(prompt_text, context=context)
        print(f"   ✓ Time: {sonnet_result.elapsed_time:.2f}s, Cost: ${sonnet_result.cost:.4f}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        results["sonnet_context"] = None

    # Save outputs
    prompt_output_dir = output_dir / prompt_id
    prompt_output_dir.mkdir(parents=True, exist_ok=True)

    for system_name, result in results.items():
        if result:
            with open(prompt_output_dir / f"{system_name}_output.txt", "w") as f:
                f.write(result.output)
            with open(prompt_output_dir / f"{system_name}_metadata.json", "w") as f:
                json.dump({
                    "elapsed_time": result.elapsed_time,
                    "cost": result.cost,
                    "metadata": result.metadata
                }, f, indent=2)

    # Print comparison summary
    print(f"\n{'='*80}")
    print("COMPARISON SUMMARY")
    print(f"{'='*80}")
    print(f"{'System':<20} {'Time':<12} {'Cost':<12} {'Output Length'}")
    print(f"{'-'*80}")

    for system_name, result in results.items():
        if result:
            time_str = f"{result.elapsed_time:.2f}s"
            cost_str = f"${result.cost:.4f}"
            length_str = f"{len(result.output)} chars"
            print(f"{system_name:<20} {time_str:<12} {cost_str:<12} {length_str}")

    # Speed/cost ratios
    if results.get("alo") and results.get("alo_sonnet"):
        alo_time = results["alo"].elapsed_time
        sonnet_time = results["alo_sonnet"].elapsed_time
        alo_cost = results["alo"].cost
        sonnet_cost = results["alo_sonnet"].cost

        print(f"\n{'='*80}")
        print("ALO vs ALO-Sonnet:")
        print(f"  Speed: ALO is {sonnet_time/alo_time:.2f}x {'faster' if alo_time < sonnet_time else 'slower'}")
        print(f"  Cost: ALO is {sonnet_cost/alo_cost:.2f}x {'cheaper' if alo_cost < sonnet_cost else 'more expensive'}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Compare ALO variants")
    parser.add_argument("--prompt", required=True, help="Prompt text to test")
    parser.add_argument("--prompt-id", default="test", help="ID for this prompt")
    parser.add_argument("--output-dir", default="benchmark/results/alo_variant_comparison", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"run_{timestamp}"

    print(f"\nALO Variant Comparison")
    print(f"Output: {run_dir}\n")

    compare_on_prompt(args.prompt, args.prompt_id, run_dir)

    print(f"\nResults saved to: {run_dir}")


if __name__ == "__main__":
    main()
