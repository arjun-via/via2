"""
=============================================================================
ALO v2.0 Parallel SWE-bench Runner
=============================================================================

Run multiple batches in parallel to maximize throughput.

USAGE:
    python -m ALO_v2.run_parallel --workers 4
    python -m ALO_v2.run_parallel --workers 6 --instances django__django-11292 ...
=============================================================================
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Any
import os

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_available_instances() -> List[str]:
    """Get list of available SWE-bench instances"""
    result = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}"],
        capture_output=True, text=True
    )

    instances = []
    for line in result.stdout.split("\n"):
        if "sweb.eval.x86_64" in line:
            parts = line.replace("swebench/sweb.eval.x86_64.", "").split("_1776_")
            if len(parts) == 2:
                instance_id = f"{parts[0]}__{parts[1]}"
                instances.append(instance_id)

    return sorted(set(instances))


def run_single_instance(instance_id: str, worker_id: int) -> Dict[str, Any]:
    """Run a single instance in a subprocess"""
    from ALO_v2 import ALOv2Orchestrator
    from ALO_v2.run_swebench import get_instance_metadata

    print(f"[Worker {worker_id}] Starting {instance_id}")

    metadata = get_instance_metadata(instance_id)

    try:
        orchestrator = ALOv2Orchestrator()
        result = orchestrator.solve(
            instance_id=instance_id,
            problem_statement=metadata["problem"],
            test_cmd=metadata["test_cmd"]
        )
        result["error"] = None
    except Exception as e:
        result = {
            "instance_id": instance_id,
            "success": False,
            "tests_passed": False,
            "patch": "",
            "attempts": 0,
            "total_cost": 0,
            "total_tokens": 0,
            "elapsed_seconds": 0,
            "error": str(e),
            "history": []
        }

    status = "PASS" if result["success"] else "FAIL"
    print(f"[Worker {worker_id}] {instance_id}: {status} ({result['attempts']} attempts, ${result['total_cost']:.3f})")

    return result


def run_batch_parallel(instances: List[str], num_workers: int, output_file: str):
    """Run instances in parallel using multiple workers"""
    print(f"\n{'#'*60}")
    print(f"ALO v2.0 PARALLEL SWE-bench Run")
    print(f"{'#'*60}")
    print(f"Instances: {len(instances)}")
    print(f"Workers: {num_workers}")
    print(f"Output: {output_file}")
    print(f"{'#'*60}\n")

    start_time = time.time()
    results = []
    completed = 0

    # Use ProcessPoolExecutor for true parallelism
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks
        future_to_instance = {
            executor.submit(run_single_instance, inst, i % num_workers): inst
            for i, inst in enumerate(instances)
        }

        # Collect results as they complete
        for future in as_completed(future_to_instance):
            instance_id = future_to_instance[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"[ERROR] {instance_id}: {e}")
                results.append({
                    "instance_id": instance_id,
                    "success": False,
                    "error": str(e)
                })

            completed += 1

            # Save intermediate results
            successes = sum(1 for r in results if r.get("success", False))
            total_cost = sum(r.get("total_cost", 0) for r in results)

            with open(output_file, "w") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "completed": completed,
                    "total": len(instances),
                    "success_count": successes,
                    "success_rate": successes / completed if completed > 0 else 0,
                    "total_cost": total_cost,
                    "elapsed_seconds": time.time() - start_time,
                    "results": results
                }, f, indent=2)

            print(f"\n[Progress] {completed}/{len(instances)} ({successes} passed, ${total_cost:.2f})")

    # Final summary
    elapsed = time.time() - start_time
    successes = sum(1 for r in results if r.get("success", False))
    total_cost = sum(r.get("total_cost", 0) for r in results)
    total_time = sum(r.get("elapsed_seconds", 0) for r in results)

    print(f"\n{'#'*60}")
    print(f"FINAL RESULTS")
    print(f"{'#'*60}")
    print(f"Success: {successes}/{len(instances)} ({100*successes/len(instances):.1f}%)")
    print(f"Total Cost: ${total_cost:.2f}")
    print(f"Wall Clock Time: {elapsed/60:.1f} minutes")
    print(f"Total Compute Time: {total_time/60:.1f} minutes")
    print(f"Speedup: {total_time/elapsed:.1f}x")
    print(f"Results saved to: {output_file}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Run ALO v2 in parallel")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--instances", nargs="+", help="Specific instances to test")
    parser.add_argument("--output", type=str, help="Output JSON file")

    args = parser.parse_args()

    # Get instances
    if args.instances:
        instances = args.instances
    else:
        instances = get_available_instances()

    print(f"Found {len(instances)} instances")

    # Output file
    output_file = args.output or f"alo_v2_parallel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Run
    run_batch_parallel(instances, args.workers, output_file)


if __name__ == "__main__":
    main()
