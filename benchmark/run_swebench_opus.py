"""
=============================================================================
SCRIPT NAME: run_swebench_opus.py
=============================================================================

Run Opus Meta-Orchestrator (with integrated learners) on SWE-bench instances.

This uses the NEW Opus orchestrator with:
- CompoundingLearner (evolved prompts with 340 patterns)
- ModelSelectionLearner (learned model routing)

Usage:
    python benchmark/run_swebench_opus.py --variant opus-optimized --instances "id1,id2,id3"
    python benchmark/run_swebench_opus.py --variant opus-optimized --num 5  # first 5 instances

VERSION: 1.0
LAST UPDATED: 2025-11-27

=============================================================================
"""
import argparse
import json
import subprocess
import sys
import time
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from datasets import load_dataset

from alo.agentic_loops.opus_orchestrator import (
    MultiProviderClient,
    OpusMetaOrchestrator,
)
from alo.agentic_loops.opus_orchestrator.presets import get_preset, PRESETS


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
        print(f"  Cloning {repo_name}...")
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

    print(f"  Creating workspace for {instance_id}...")
    import shutil
    shutil.copytree(repo_cache, workspace)

    print(f"  Checking out {base_commit[:8]}...")
    subprocess.run(
        ["git", "-C", str(workspace), "checkout", base_commit],
        capture_output=True,
        check=True
    )

    return str(workspace)


def clean_patch(raw_diff: str) -> str:
    """
    Clean patch by removing binary files and non-code paths.

    Filters out:
    - Binary file hunks (no @@ markers, contains "Binary files")
    - Documentation assets (docs/_theme/, *.png, *.gif, *.jpg, etc.)
    - Other non-code files that can corrupt patches

    Args:
        raw_diff: Raw git diff output

    Returns:
        Cleaned diff with only text-based code changes
    """
    if not raw_diff:
        return ""

    # Patterns for paths to exclude
    EXCLUDE_PATTERNS = [
        'docs/_theme/',
        'docs/_static/',
        '.png',
        '.gif',
        '.jpg',
        '.jpeg',
        '.ico',
        '.svg',
        '.woff',
        '.woff2',
        '.ttf',
        '.eot',
        '.pdf',
        '.pyc',
        '__pycache__/',
    ]

    cleaned_hunks = []
    current_hunk = []
    current_file = None
    is_binary = False
    should_exclude = False

    for line in raw_diff.split('\n'):
        # New file header
        if line.startswith('diff --git'):
            # Save previous hunk if valid
            if current_hunk and current_file and not is_binary and not should_exclude:
                cleaned_hunks.extend(current_hunk)

            # Start new hunk
            current_hunk = [line]
            current_file = line
            is_binary = False
            should_exclude = False

            # Check if file path should be excluded
            for pattern in EXCLUDE_PATTERNS:
                if pattern in line:
                    should_exclude = True
                    break

        elif line.startswith('Binary files'):
            # Mark current hunk as binary
            is_binary = True
            current_hunk.append(line)

        else:
            current_hunk.append(line)

    # Don't forget last hunk
    if current_hunk and current_file and not is_binary and not should_exclude:
        cleaned_hunks.extend(current_hunk)

    result = '\n'.join(cleaned_hunks)

    # Validate: must have at least one @@ hunk marker to be a valid patch
    if '@@' not in result:
        return ""

    return result


def extract_patch(workspace_path: str) -> str:
    """Extract git diff from workspace after orchestrator applies changes.

    Filters out binary files and non-code paths to produce clean patches
    that can be applied without errors.
    """
    try:
        result = subprocess.run(
            ["git", "-C", workspace_path, "diff"],
            capture_output=True,
            text=True,
            check=True
        )
        raw_diff = result.stdout

        # Clean the patch to remove binary/non-code files
        cleaned = clean_patch(raw_diff)

        if raw_diff and not cleaned:
            print(f"    Warning: Patch contained only binary/non-code files, cleaned to empty")
        elif len(cleaned) < len(raw_diff):
            removed = len(raw_diff) - len(cleaned)
            print(f"    Cleaned patch: removed {removed} chars of binary/non-code content")

        return cleaned
    except Exception as e:
        print(f"    Warning: Error extracting patch: {e}")
        return ""


def run_opus_on_instance(instance, variant, use_learners=True, verbose=False):
    """Run Opus Meta-Orchestrator on a single SWE-bench instance."""
    instance_id = instance['instance_id']
    problem_statement = instance['problem_statement']

    print(f"\n{'='*80}")
    print(f"Instance: {instance_id}")
    print(f"Repo: {instance['repo']}")
    print(f"Variant: {variant} (learners={'ON' if use_learners else 'OFF'})")
    print(f"{'='*80}")

    # Clone and setup workspace
    try:
        workspace = clone_and_checkout(instance)
    except Exception as e:
        print(f"  FAILED to setup workspace: {e}")
        return {
            "instance_id": instance_id,
            "model_patch": "",
            "model_name_or_path": f"opus-{variant}",
            "variant": variant,
            "error": f"Workspace setup failed: {e}"
        }

    # Create orchestrator
    print(f"  Running Opus Meta-Orchestrator (SWE-bench Mode)...")

    try:
        client = MultiProviderClient()
        preset = get_preset(variant)

        orchestrator = OpusMetaOrchestrator(
            client=client,
            preset=preset,
            use_learned_prompt=use_learners,
            use_learned_model_selection=use_learners,
            max_retries_per_feature=3,
        )

        # Show learner status
        if use_learners:
            if orchestrator.compounding_learner:
                print(f"    CompoundingLearner: v{orchestrator.compounding_learner.state.prompt_version}")
            if orchestrator.model_selection_learner:
                stats = orchestrator.model_selection_learner.get_stats()
                print(f"    ModelSelectionLearner: {stats['total_tasks']} tasks, {stats['routing_rules_learned']} rules")

        start = time.time()

        # Run orchestrator in SWE-bench mode (generates and applies file edits)
        result = orchestrator.run_swebench(
            issue=problem_statement,
            repo_path=workspace
        )

        elapsed = time.time() - start

        # Extract patch from git diff
        patch = extract_patch(workspace)

        print(f"  Complete - {elapsed:.1f}s - ${result.total_cost:.4f}")
        print(f"    Files modified: {result.features_completed}")
        print(f"    Patch size: {len(patch)} chars")

        if verbose and patch:
            print(f"\n  Patch preview:")
            print("  " + "\n  ".join(patch.split("\n")[:20]))

        # Success = patch was generated
        success = len(patch) > 0

        return {
            "instance_id": instance_id,
            "model_patch": patch,
            "model_name_or_path": f"opus-{variant}{'_learned' if use_learners else ''}",
            "variant": variant,
            "use_learners": use_learners,
            "elapsed_time": elapsed,
            "cost": result.total_cost,
            "files_modified": result.features_completed,
            "success": success
        }

    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()

        return {
            "instance_id": instance_id,
            "model_patch": "",
            "model_name_or_path": f"opus-{variant}",
            "variant": variant,
            "error": str(e)
        }


def main():
    parser = argparse.ArgumentParser(description="Run Opus Meta-Orchestrator on SWE-bench")
    parser.add_argument("--variant", default="opus-optimized",
                        choices=list(PRESETS.keys()),
                        help="Opus variant to use")
    parser.add_argument("--dataset", default="verified",
                        choices=["verified", "lite", "full"],
                        help="SWE-bench dataset: verified (500), lite, or full")
    parser.add_argument("--instances", help="Comma-separated instance IDs")
    parser.add_argument("--num", type=int, help="Number of instances to run (from start)")
    parser.add_argument("--output", help="Output JSONL file (auto-generated if not specified)")
    parser.add_argument("--no-learners", action="store_true",
                        help="Disable CompoundingLearner and ModelSelectionLearner")
    parser.add_argument("--verbose", action="store_true", help="Show patch previews")
    parser.add_argument("--compare", action="store_true",
                        help="Run both with and without learners for comparison")
    args = parser.parse_args()

    # Generate output path
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        learner_tag = "nolearn" if args.no_learners else "learn"
        args.output = f"swebench_{args.dataset}_{args.variant}_{learner_tag}_{timestamp}.jsonl"

    output_path = Path(args.output)

    # Dataset mapping
    dataset_map = {
        "verified": "princeton-nlp/SWE-bench_Verified",
        "lite": "princeton-nlp/SWE-bench_Lite",
        "full": "princeton-nlp/SWE-bench"
    }
    dataset_name = dataset_map[args.dataset]

    print("="*80)
    print("OPUS META-ORCHESTRATOR SWE-BENCH RUNNER")
    print("="*80)
    print(f"Dataset:     {args.dataset} ({dataset_name})")
    print(f"Variant:     {args.variant}")
    print(f"Learners:    {'DISABLED' if args.no_learners else 'ENABLED'}")
    print(f"Compare:     {args.compare}")
    print(f"Output:      {output_path}")
    print("="*80)

    # Load dataset
    print(f"\nLoading SWE-bench {args.dataset.capitalize()}...")
    dataset = load_dataset(dataset_name, split="test")

    # Filter to specified instances
    if args.instances:
        instance_ids = [id.strip() for id in args.instances.split(',')]
        dataset = dataset.filter(lambda x: x['instance_id'] in instance_ids)
        print(f"Filtered to {len(dataset)} specified instances")
    elif args.num:
        dataset = dataset.select(range(min(args.num, len(dataset))))
        print(f"Selected first {len(dataset)} instances")
    else:
        print(f"Total instances: {len(dataset)}")
        print("WARNING: No filtering specified. Use --instances or --num to limit.")
        return

    # Process instances
    results = []
    successful = 0
    use_learners = not args.no_learners

    for i, instance in enumerate(dataset, 1):
        print(f"\n[{i}/{len(dataset)}] Processing {instance['instance_id']}...")

        if args.compare:
            # Run both with and without learners
            result_with = run_opus_on_instance(instance, args.variant, use_learners=True, verbose=args.verbose)
            result_without = run_opus_on_instance(instance, args.variant, use_learners=False, verbose=args.verbose)

            results.append(result_with)
            results.append(result_without)

            if result_with.get("success", False):
                successful += 1
        else:
            result = run_opus_on_instance(instance, args.variant, use_learners=use_learners, verbose=args.verbose)
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

    total = len(dataset)
    print(f"Total instances:  {total}")
    print(f"Successful:       {successful} ({successful/total*100:.1f}%)")

    if args.compare:
        learn_results = [r for r in results if r.get("use_learners", False)]
        nolearn_results = [r for r in results if not r.get("use_learners", True)]

        learn_success = sum(1 for r in learn_results if r.get("success", False))
        nolearn_success = sum(1 for r in nolearn_results if r.get("success", False))

        print(f"\nWith Learners:    {learn_success}/{len(learn_results)} ({learn_success/len(learn_results)*100:.1f}%)")
        print(f"Without Learners: {nolearn_success}/{len(nolearn_results)} ({nolearn_success/len(nolearn_results)*100:.1f}%)")
        print(f"Improvement:      {learn_success - nolearn_success} instances")

    with_patch = sum(1 for r in results if len(r.get('model_patch', '')) > 0)
    print(f"With patch:       {with_patch}")

    costs = [r['cost'] for r in results if 'cost' in r]
    times = [r['elapsed_time'] for r in results if 'elapsed_time' in r]

    if costs:
        print(f"Total cost:       ${sum(costs):.4f}")
        print(f"Avg cost:         ${sum(costs)/len(costs):.4f}")
    if times:
        print(f"Total time:       {sum(times)/60:.1f} min")
        print(f"Avg time:         {sum(times)/len(times):.1f}s")

    print(f"\nSaved to: {output_path}")
    print("="*80)


if __name__ == "__main__":
    main()
