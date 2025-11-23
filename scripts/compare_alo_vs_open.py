"""Compare ALO (original mixed models) vs ALO-Open (all open-source)."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.runners.alo_runner import ALORunner
from benchmark.runners.alo_open_runner import ALOOpenRunner

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def compare_on_prompt(prompt_text: str, prompt_id: str, output_dir: Path):
    """Run both ALO and ALO-Open on a single prompt and compare."""
    print(f"\n{'='*80}")
    print(f"Comparing on: {prompt_id}")
    print(f"{'='*80}\n")

    results = {}

    # 1. Run ALO (mixed models: Gemini + GLM + Kimi)
    print("[1/2] Running ALO (Gemini context + GLM engineering + Kimi review)...")
    try:
        alo_runner = ALORunner()
        alo_result = results["alo"] = alo_runner.run(prompt_text)
        print(f"   ✓ Time: {alo_result.elapsed_time:.2f}s, Cost: ${alo_result.cost:.4f}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        results["alo"] = None

    # 2. Run ALO-Open (all open-source: Kimi-K2-Thinking + Qwen3-Coder + Kimi-K2)
    print("[2/2] Running ALO-Open (all open-source via OpenRouter)...")
    try:
        alo_open_runner = ALOOpenRunner()
        alo_open_result = results["alo_open"] = alo_open_runner.run(prompt_text)
        print(f"   ✓ Time: {alo_open_result.elapsed_time:.2f}s, Cost: ${alo_open_result.cost:.4f}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        results["alo_open"] = None

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
    if results.get("alo") and results.get("alo_open"):
        alo_time = results["alo"].elapsed_time
        open_time = results["alo_open"].elapsed_time
        alo_cost = results["alo"].cost
        open_cost = results["alo_open"].cost

        print(f"\n{'='*80}")
        print("ALO-Open vs ALO:")
        if alo_time > 0:
            print(f"  Speed: ALO-Open is {alo_time/open_time:.2f}x {'faster' if open_time < alo_time else 'slower'}")
        if alo_cost > 0:
            print(f"  Cost: ALO-Open is {alo_cost/open_cost:.2f}x {'cheaper' if open_cost < alo_cost else 'more expensive'}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Compare ALO vs ALO-Open")
    parser.add_argument("--prompt", required=True, help="Prompt text to test")
    parser.add_argument("--prompt-id", default="test", help="ID for this prompt")
    parser.add_argument("--output-dir", default="benchmark/results/alo_vs_open", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"run_{timestamp}"

    print(f"\nALO vs ALO-Open Comparison")
    print(f"Output: {run_dir}\n")

    compare_on_prompt(args.prompt, args.prompt_id, run_dir)

    print(f"\nResults saved to: {run_dir}")


if __name__ == "__main__":
    main()
