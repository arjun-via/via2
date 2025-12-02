#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_opus_agentic.py
=============================================================================

Run the Opus Agentic Loop on SWE-bench instances.

INPUT FILES:
- SWE-bench dataset (from HuggingFace)

OUTPUT FILES:
- Predictions JSONL file (compatible with swebench evaluator)
- Trajectory files for each instance

VERSION: 1.0
LAST UPDATED: 2025-11-28

DESCRIPTION:
Runs the new Opus Agentic Loop on SWE-bench Verified instances.
This is the system designed to achieve 75%+ accuracy.

Key features:
- Docker-based execution in SWE-bench containers
- Iterative problem solving with bash commands
- Optional context priming with Gemini

USAGE:
python benchmark/run_opus_agentic.py --num 5 --output opus_agentic_test.jsonl

DEPENDENCIES:
- datasets
- anthropic
- docker

=============================================================================
"""

import argparse
import json
import logging
import os
import random
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datasets import load_dataset
from alo.agentic_loops.opus_orchestrator.agentic_loop import AgenticLoop


# Cache for Docker image mapping
_IMAGE_CACHE: dict = {}


def build_image_cache() -> dict:
    """
    Build a mapping from instance_id to Docker image name by scanning local images.

    This function scans all locally available SWE-bench Docker images and creates
    a mapping from instance_id (e.g., "django__django-11299") to the full image name.

    Image format: swebench/sweb.eval.x86_64.{repo}_{version}_{repo}-{issue}:latest
    Example: swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest
             -> astropy__astropy-12907
    """
    import subprocess
    import re

    global _IMAGE_CACHE
    if _IMAGE_CACHE:
        return _IMAGE_CACHE

    try:
        result = subprocess.run(
            ['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}'],
            capture_output=True, text=True, check=True
        )

        # Pattern: sweb.eval.x86_64.{repo}_{version}_{repo}-{issue}
        # Example: sweb.eval.x86_64.astropy_1776_astropy-12907
        pattern = re.compile(r'sweb\.eval\.x86_64\.(\w+)_\d+_(\w+-\d+)')

        for line in result.stdout.splitlines():
            if 'sweb.eval' in line:
                match = pattern.search(line)
                if match:
                    repo = match.group(1)  # e.g., "astropy"
                    repo_issue = match.group(2)  # e.g., "astropy-12907"
                    instance_id = f"{repo}__{repo_issue}"
                    _IMAGE_CACHE[instance_id] = line.strip()

        logging.info(f"Built image cache with {len(_IMAGE_CACHE)} mappings")

    except subprocess.CalledProcessError as e:
        logging.warning(f"Failed to scan Docker images: {e}")

    return _IMAGE_CACHE


def get_docker_image(instance_id: str) -> str:
    """
    Get the Docker image name for a SWE-bench instance.

    The image naming convention is:
    swebench/sweb.eval.x86_64.{repo}_{version}_{repo}-{issue}:latest

    Where version is typically "1776".

    Args:
        instance_id: SWE-bench instance ID (e.g., "django__django-11299")

    Returns:
        Docker image name, or raises ValueError if not found
    """
    # First try the cache
    cache = build_image_cache()
    if instance_id in cache:
        return cache[instance_id]

    # Fallback: construct the image name with version "1776"
    # instance_id format: {repo}__{repo}-{issue}
    parts = instance_id.split("__")
    if len(parts) != 2:
        raise ValueError(f"Invalid instance ID format: {instance_id}")

    repo = parts[0]  # e.g., "django"
    repo_issue = parts[1]  # e.g., "django-11299"

    # Construct: swebench/sweb.eval.x86_64.{repo}_1776_{repo}-{issue}:latest
    image_name = f"swebench/sweb.eval.x86_64.{repo}_1776_{repo_issue}:latest"

    logging.warning(f"Image for {instance_id} not in cache, trying: {image_name}")
    return image_name


def run_single_instance(
    instance: dict,
    loop: AgenticLoop,
    output_dir: Path,
    verbose: bool = False
) -> dict:
    """
    Run the agentic loop on a single SWE-bench instance.

    Args:
        instance: SWE-bench instance dict
        loop: AgenticLoop instance
        output_dir: Directory for trajectory files
        verbose: Print detailed progress

    Returns:
        Prediction dict for swebench evaluator
    """
    instance_id = instance["instance_id"]
    problem_statement = instance["problem_statement"]

    # Get hints if available
    hints = instance.get("hints_text", "")
    if hints:
        problem_statement += f"\n\n## Hints\n{hints}"

    # Get Docker image
    # The actual image name comes from swebench harness
    # For verified instances, images are pre-built
    docker_image = get_docker_image(instance_id)

    logging.info(f"Processing {instance_id}")
    if verbose:
        print(f"\n{'='*60}")
        print(f"Instance: {instance_id}")
        print(f"{'='*60}")

    try:
        # Run the agentic loop
        result = loop.run(
            problem_statement=problem_statement,
            docker_image=docker_image
        )

        # Save trajectory
        traj_path = output_dir / f"{instance_id}.traj.json"
        loop.save_trajectory(result, str(traj_path))

        if verbose:
            print(f"Steps: {len(result.steps)}")
            print(f"Cost: ${result.total_cost:.4f}")
            print(f"Success: {result.success}")
            if result.patch:
                print(f"Patch length: {len(result.patch)} chars")

        return {
            "instance_id": instance_id,
            "model_patch": result.patch,
            "model_name_or_path": "opus-agentic-v1"
        }

    except Exception as e:
        logging.error(f"Error processing {instance_id}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()

        return {
            "instance_id": instance_id,
            "model_patch": "",
            "model_name_or_path": "opus-agentic-v1"
        }


def main():
    parser = argparse.ArgumentParser(description="Run Opus Agentic Loop on SWE-bench")
    parser.add_argument("--dataset", default="princeton-nlp/SWE-bench_Verified",
                       help="Dataset name")
    parser.add_argument("--split", default="test", help="Dataset split")
    parser.add_argument("--num", type=int, default=5, help="Number of instances")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--output", required=True, help="Output JSONL file")
    parser.add_argument("--max-steps", type=int, default=30, help="Max steps per instance")
    parser.add_argument("--cost-limit", type=float, default=10.0, help="Cost limit per instance")
    parser.add_argument("--model", default="claude-opus-4-5-20251101", help="Claude model")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--debug", action="store_true", help="Debug logging")
    parser.add_argument("--random", action="store_true", help="Select random instances instead of sequential")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create output directory
    output_path = Path(args.output)
    output_dir = output_path.parent / f"{output_path.stem}_trajectories"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load dataset
    logging.info(f"Loading dataset {args.dataset}")
    dataset = load_dataset(args.dataset, split=args.split)

    # Select instances
    if args.random:
        # Random sampling
        random.seed(args.seed)
        all_indices = list(range(len(dataset)))
        selected_indices = random.sample(all_indices, min(args.num, len(dataset)))
        instances = [dataset[i] for i in selected_indices]
        logging.info(f"Randomly selected {len(instances)} instances (seed={args.seed})")
        logging.info(f"Selected indices: {selected_indices[:10]}{'...' if len(selected_indices) > 10 else ''}")
    else:
        # Sequential selection
        end_idx = min(args.start + args.num, len(dataset))
        instances = [dataset[i] for i in range(args.start, end_idx)]
        logging.info(f"Processing {len(instances)} instances (index {args.start} to {end_idx-1})")

    # Initialize agentic loop
    loop = AgenticLoop(
        model=args.model,
        max_steps=args.max_steps,
        cost_limit=args.cost_limit
    )

    # Process instances
    predictions = []
    total_cost = 0.0

    for i, instance in enumerate(instances):
        logging.info(f"[{i+1}/{len(instances)}] {instance['instance_id']}")

        pred = run_single_instance(instance, loop, output_dir, args.verbose)
        predictions.append(pred)

        # Write incrementally
        with open(args.output, 'w') as f:
            for p in predictions:
                f.write(json.dumps(p) + '\n')

        logging.info(f"Saved {len(predictions)} predictions to {args.output}")

    # Summary
    successful = sum(1 for p in predictions if p["model_patch"])
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total instances: {len(predictions)}")
    print(f"Generated patches: {successful}")
    print(f"Patch rate: {successful/len(predictions)*100:.1f}%")
    print(f"Output: {args.output}")
    print(f"Trajectories: {output_dir}")


if __name__ == "__main__":
    main()
