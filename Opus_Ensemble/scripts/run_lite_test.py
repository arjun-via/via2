#!/usr/bin/env python3
"""
Test opus_conductor_final on SWE-bench Lite (different from Verified).
Runs on tasks that are in Lite but NOT in Verified - truly unseen data.
"""
import json
import os
import sys
import random
from datasets import load_dataset

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.opus_conductor_final import OpusConductor, SWEBenchTask, setup_logging
from docker_executor import DockerExecutor, get_swebench_image


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--num", type=int, default=15)
    parser.add_argument("--output", default="lite_test_15.jsonl")
    parser.add_argument("--seed", type=int, default=123)
    args = parser.parse_args()

    setup_logging(verbose=False)

    sep = "=" * 70
    print(sep)
    print("OPUS-CONDUCTOR FINAL - Testing on SWE-bench Lite")
    print(sep)

    # Load both datasets
    print("Loading datasets...")
    ds_lite = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    ds_verified = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")

    # Get IDs in Verified
    verified_ids = set(t["instance_id"] for t in ds_verified)
    print(f"Verified has {len(verified_ids)} tasks")

    # Filter Lite to tasks NOT in Verified (truly unseen)
    lite_only = [t for t in ds_lite if t["instance_id"] not in verified_ids]
    print(f"Lite-only (not in Verified): {len(lite_only)} tasks")

    # Random sample
    random.seed(args.seed)
    tasks_data = random.sample(lite_only, min(args.num, len(lite_only)))

    print(f"Selected {len(tasks_data)} tasks:")
    for t in tasks_data:
        iid = t["instance_id"]
        print(f"  {iid}")
    print()

    # Check for completed
    output_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), args.output)
    completed = set()
    if os.path.exists(output_file):
        with open(output_file) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    completed.add(r.get("instance_id"))
        print(f"Already completed: {len(completed)}")

    tasks_data = [t for t in tasks_data if t["instance_id"] not in completed]
    print(f"Tasks to run: {len(tasks_data)}")

    results = []
    for i, task_data in enumerate(tasks_data):
        iid = task_data["instance_id"]
        print(f"\n[{i+1}/{len(tasks_data)}] {iid}")

        task = SWEBenchTask.from_dict(dict(task_data))
        docker_image = get_swebench_image(task.instance_id, use_epoch=True)
        print(f"  Docker: {docker_image}")

        docker = DockerExecutor(image=docker_image, cwd="/testbed", timeout=300)

        try:
            if not docker.start():
                print("  ERROR: Docker failed to start")
                continue

            conductor = OpusConductor(docker_executor=docker, max_steps=30, max_test_iterations=3)
            result = conductor.run(task)
            results.append(result)

            status = "PASS" if result.success else "FAIL"
            print(f"  Result: {status}, cost=${result.cost:.4f}, applies={result.patch_applies}")

            with open(output_file, "a") as f:
                f.write(json.dumps(result.to_dict()) + "\n")
        finally:
            docker.cleanup()

    # Summary
    if results:
        passed = sum(1 for r in results if r.success)
        print(f"\n{sep}")
        print(f"RESULTS: {passed}/{len(results)} PASS ({100*passed/len(results):.1f}%)")
        print(f"Total cost: ${sum(r.cost for r in results):.4f}")


if __name__ == "__main__":
    main()
