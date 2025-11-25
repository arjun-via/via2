#!/usr/bin/env python
"""
Quick 4-way comparison test to verify orchestrator improvements.

Tests one prompt on all 4 systems to show they're working with:
- Structured prompts
- Variable temperature
- API retry with backoff
- History capping
- Flattened review loop (available)
- FAIL IS FAIL policy
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Check for API keys
REQUIRED_KEYS = ["OPENAI_API_KEY", "OPENROUTER_API_KEY"]
missing = [k for k in REQUIRED_KEYS if not os.getenv(k)]
if missing:
    print(f"Missing API keys: {missing}")
    print("Please set these environment variables")
    sys.exit(1)

from benchmark.runners.alo_optimized_runner import ALOOptimizedRunner
from benchmark.runners.alo_open_runner import ALOOpenRunner
from benchmark.runners.alo_bestinclass_runner import ALOBestInClassRunner
from benchmark.runners.sonnet_runner import SonnetContextRunner


# Single test prompt
TEST_PROMPT = {
    "id": "rate_limiter",
    "prompt": "Implement a rate limiter using the token bucket algorithm in Python. Include thread safety and support for multiple users."
}


def run_test():
    print("=" * 80)
    print("QUICK 4-WAY TEST - Orchestrator Improvements Verification")
    print("=" * 80)
    print("\nTesting with:", TEST_PROMPT["id"])
    print("Prompt:", TEST_PROMPT["prompt"][:60] + "...")
    print("\nOrchestrator improvements applied:")
    print("  1. Structured Prompts (JSON schemas, examples, guidelines)")
    print("  2. Variable Temperature (context=0, repro=0, engineering=0.3, review=0)")
    print("  3. API Retry with Backoff (exponential, jitter)")
    print("  4. History Capping (max 100 entries)")
    print("  5. FAIL IS FAIL policy (no silent fallbacks)")
    print("=" * 80)

    # Initialize runners
    runners = {
        "ALO-Optimized": ALOOptimizedRunner,
        "ALO-Open": ALOOpenRunner,
        "ALO-BestInClass": ALOBestInClassRunner,
        "Sonnet+Context": SonnetContextRunner,
    }

    results = {}

    for name, RunnerClass in runners.items():
        print(f"\n{'='*40}")
        print(f"Testing: {name}")
        print("=" * 40)

        try:
            runner = RunnerClass()
            start = time.time()
            result = runner.run(TEST_PROMPT["prompt"])
            elapsed = time.time() - start

            print(f"  Status: SUCCESS")
            print(f"  Time: {elapsed:.1f}s")
            print(f"  Cost: ${result.cost:.4f}")
            print(f"  Output length: {len(result.output)} chars")

            # Show first 500 chars of output
            preview = result.output[:500].replace('\n', '\n    ')
            print(f"\n  Output preview:")
            print(f"    {preview}...")

            results[name] = {
                "success": True,
                "time": elapsed,
                "cost": result.cost,
                "output_length": len(result.output),
                "output": result.output,
                "metadata": result.metadata
            }

        except Exception as e:
            print(f"  Status: FAILED")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()

            results[name] = {
                "success": False,
                "error": str(e)
            }

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    successful = {k: v for k, v in results.items() if v.get("success")}
    failed = {k: v for k, v in results.items() if not v.get("success")}

    if successful:
        print(f"\nSuccessful: {len(successful)}/{len(results)}")
        print("\n{:<20} {:>10} {:>10} {:>12}".format("System", "Time (s)", "Cost ($)", "Output Len"))
        print("-" * 55)
        for name, data in successful.items():
            print("{:<20} {:>10.1f} {:>10.4f} {:>12}".format(
                name, data["time"], data["cost"], data["output_length"]
            ))

    if failed:
        print(f"\nFailed: {len(failed)}/{len(results)}")
        for name, data in failed.items():
            print(f"  {name}: {data.get('error', 'Unknown error')}")

    # Save results
    output_dir = Path("benchmark/results/quick_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")

    for name, data in results.items():
        if data.get("success"):
            safe_name = name.lower().replace("+", "_").replace("-", "_")
            output_file = output_dir / f"{safe_name}_{timestamp}.txt"
            output_file.write_text(data["output"])
            print(f"\nSaved {name} output to: {output_file}")

    summary_file = output_dir / f"summary_{timestamp}.json"
    with open(summary_file, "w") as f:
        # Remove full output from summary (too large)
        summary_data = {}
        for name, data in results.items():
            summary_data[name] = {k: v for k, v in data.items() if k != "output"}
        json.dump(summary_data, f, indent=2, default=str)

    print(f"\nSummary saved to: {summary_file}")

    return 0 if len(successful) > 0 else 1


if __name__ == "__main__":
    sys.exit(run_test())
