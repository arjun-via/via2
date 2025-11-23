"""
Run ALO (any variant) on SWE-bench instances.

Usage:
    python benchmark/run_swebench_alo.py --config config/config_alo_optimized.yaml --instances "id1,id2,id3"
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datasets import load_dataset
from main import build_orchestrator, load_config
from alo.agentic_loops.core.costs import CostTracker


def clone_and_checkout(instance, cache_dir="temp/swebench_repos"):
    """Clone repository and checkout specific commit for an instance."""
    repo_name = instance['repo']
    base_commit = instance['base_commit']
    instance_id = instance['instance_id']

    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    # Repo cache (shared across instances)
    repo_cache = cache_path / repo_name.replace("/", "_")

    if not repo_cache.exists():
        print(f"  📥 Cloning {repo_name}...")
        subprocess.run(
            ["git", "clone", f"https://github.com/{repo_name}.git", str(repo_cache)],
            capture_output=True,
            check=True
        )

    # Instance workspace
    workspace = cache_path / "workspaces" / instance_id
    if workspace.exists():
        import shutil
        shutil.rmtree(workspace)

    print(f"  📂 Creating workspace for {instance_id}...")
    import shutil
    shutil.copytree(repo_cache, workspace)

    print(f"  🔖 Checking out {base_commit[:8]}...")
    subprocess.run(
        ["git", "-C", str(workspace), "checkout", base_commit],
        capture_output=True,
        check=True
    )

    return str(workspace)


def extract_patch(workspace_path: str) -> str:
    """Extract git diff from workspace after ALO applies changes."""
    try:
        result = subprocess.run(
            ["git", "-C", workspace_path, "diff"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except Exception as e:
        print(f"    ⚠️  Error extracting patch: {e}")
        return ""


def run_alo_on_instance(instance, config_path, verbose=False):
    """Run ALO on a single SWE-bench instance."""
    instance_id = instance['instance_id']
    problem_statement = instance['problem_statement']

    print(f"\n{'='*80}")
    print(f"Instance: {instance_id}")
    print(f"Repo: {instance['repo']}")
    print(f"{'='*80}")

    # Clone and setup workspace
    try:
        workspace = clone_and_checkout(instance)
    except Exception as e:
        print(f"  ✗ Failed to setup workspace: {e}")
        return {
            "instance_id": instance_id,
            "model_patch": "",
            "model_name_or_path": config_path,
            "error": f"Workspace setup failed: {e}"
        }

    # Load config and build orchestrator
    print(f"  🚀 Running ALO...")
    config = load_config(config_path)

    try:
        orchestrator = build_orchestrator(config, workspace)
        cost_tracker = CostTracker.get_instance()
        cost_tracker.reset()

        start = time.time()

        # Run ALO
        state = orchestrator.run(issue_description=problem_statement, repo_path=workspace)

        elapsed = time.time() - start

        # Extract patch
        patch = extract_patch(workspace)

        # Get cost
        cost_summary = cost_tracker.summary()
        total_cost = cost_summary.get("total_cost", 0.0)

        print(f"  ✓ Complete - {elapsed:.1f}s - ${total_cost:.4f}")
        print(f"    Patch size: {len(patch)} chars")

        if verbose and patch:
            print(f"\n  Patch preview:")
            print("  " + "\n  ".join(patch.split("\n")[:20]))

        return {
            "instance_id": instance_id,
            "model_patch": patch,
            "model_name_or_path": config_path,
            "elapsed_time": elapsed,
            "cost": total_cost,
            "success": len(patch) > 0
        }

    except Exception as e:
        print(f"  ✗ ALO failed: {e}")
        import traceback
        traceback.print_exc()

        return {
            "instance_id": instance_id,
            "model_patch": "",
            "model_name_or_path": config_path,
            "error": str(e)
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config_alo_optimized.yaml", help="ALO config file")
    parser.add_argument("--instances", required=True, help="Comma-separated instance IDs")
    parser.add_argument("--output", help="Output JSONL file (auto-generated if not specified)")
    parser.add_argument("--verbose", action="store_true", help="Show patch previews")
    args = parser.parse_args()

    # Parse instance IDs
    instance_ids = [id.strip() for id in args.instances.split(',')]

    # Generate output path
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config_name = Path(args.config).stem
        args.output = f"predictions_swebench_{config_name}_{timestamp}.jsonl"

    output_path = Path(args.output)

    print("="*80)
    print("ALO SWE-BENCH RUNNER")
    print("="*80)
    print(f"Config:      {args.config}")
    print(f"Instances:   {len(instance_ids)}")
    print(f"Output:      {output_path}")
    print("="*80)

    # Load dataset
    print("\n📦 Loading SWE-bench Lite...")
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

    # Filter to specified instances
    dataset = dataset.filter(lambda x: x['instance_id'] in instance_ids)
    print(f"✅ Loaded {len(dataset)} instances\n")

    if len(dataset) != len(instance_ids):
        print(f"⚠️  Warning: Found {len(dataset)}/{len(instance_ids)} instances")

    # Process instances
    results = []
    successful = 0

    for i, instance in enumerate(dataset, 1):
        print(f"\n[{i}/{len(dataset)}] Processing {instance['instance_id']}...")

        result = run_alo_on_instance(instance, args.config, args.verbose)
        results.append(result)

        if result.get("success", False):
            successful += 1

        # Save incrementally
        with open(output_path, 'w') as f:
            for r in results:
                f.write(json.dumps(r) + '\n')

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total:       {len(results)}")
    print(f"Successful:  {successful} ({successful/len(results)*100:.1f}%)")
    print(f"With patch:  {sum(1 for r in results if len(r.get('model_patch', '')) > 0)}")

    if successful > 0:
        costs = [r['cost'] for r in results if 'cost' in r]
        times = [r['elapsed_time'] for r in results if 'elapsed_time' in r]

        if costs:
            print(f"Total cost:  ${sum(costs):.4f}")
            print(f"Avg cost:    ${sum(costs)/len(costs):.4f}")
        if times:
            print(f"Total time:  {sum(times)/60:.1f} min")
            print(f"Avg time:    {sum(times)/len(times):.1f}s")

    print(f"\n✅ Saved to: {output_path}")
    print("="*80)


if __name__ == "__main__":
    main()
