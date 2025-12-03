#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_swebench.py
=============================================================================

Run Opus Ensemble on SWE-bench Verified dataset.

INPUT FILES:
- SWE-bench JSONL file with tasks

OUTPUT FILES:
- predictions.jsonl: Model predictions in SWE-bench format
- results.json: Detailed results with metrics

USAGE:
    # Run on SWE-bench Verified (500 tasks)
    python scripts/run_swebench.py --dataset verified --output predictions.jsonl

    # Run on subset
    python scripts/run_swebench.py --dataset verified --num 25 --random

    # Test mode (free model)
    python scripts/run_swebench.py --test --num 5

    # Production mode (Opus)
    python scripts/run_swebench.py --production --num 100

DEPENDENCIES:
    pip install datasets anthropic openai

=============================================================================
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ModelMode
from swebench_orchestrator import SWEBenchOrchestrator, SWEBenchTask, SWEBenchResult


def setup_logging(log_file: Optional[str] = None, verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def load_swebench_verified() -> List[SWEBenchTask]:
    """Load SWE-bench Verified dataset from HuggingFace."""
    try:
        from datasets import load_dataset
        ds = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")

        tasks = []
        for item in ds:
            # Use from_dict to properly parse FAIL_TO_PASS
            tasks.append(SWEBenchTask.from_dict(dict(item)))

        logging.info(f"Loaded {len(tasks)} tasks from SWE-bench Verified")
        return tasks

    except ImportError:
        logging.error("datasets library not installed. Run: pip install datasets")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to load SWE-bench Verified: {e}")
        sys.exit(1)


def load_swebench_lite() -> List[SWEBenchTask]:
    """Load SWE-bench Lite dataset."""
    try:
        from datasets import load_dataset
        ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

        tasks = []
        for item in ds:
            # Use from_dict to properly parse FAIL_TO_PASS
            tasks.append(SWEBenchTask.from_dict(dict(item)))

        logging.info(f"Loaded {len(tasks)} tasks from SWE-bench Lite")
        return tasks

    except Exception as e:
        logging.error(f"Failed to load SWE-bench Lite: {e}")
        sys.exit(1)


def load_from_file(filepath: str) -> List[SWEBenchTask]:
    """Load tasks from JSONL file."""
    tasks = []
    with open(filepath) as f:
        for line in f:
            data = json.loads(line)
            tasks.append(SWEBenchTask.from_dict(data))

    logging.info(f"Loaded {len(tasks)} tasks from {filepath}")
    return tasks


def save_results(
    results: List[SWEBenchResult],
    predictions_file: str,
    summary_file: Optional[str] = None
):
    """Save results to files."""
    # Save predictions (SWE-bench format)
    with open(predictions_file, 'w') as f:
        for result in results:
            f.write(json.dumps(result.to_prediction()) + '\n')

    logging.info(f"Saved predictions to {predictions_file}")

    # Save detailed summary
    if summary_file:
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(results),
            "solved": sum(1 for r in results if r.success),
            "solve_rate": sum(1 for r in results if r.success) / len(results) if results else 0,
            "total_cost": sum(r.total_cost for r in results),
            "total_time": sum(r.total_time for r in results),
            "avg_time_per_task": sum(r.total_time for r in results) / len(results) if results else 0,
            "results": [
                {
                    "instance_id": r.instance_id,
                    "success": r.success,
                    "total_time": r.total_time,
                    "patches_generated": r.patches_generated,
                    "patches_passing": r.patches_passing,
                    "error": r.error,
                }
                for r in results
            ]
        }

        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        logging.info(f"Saved summary to {summary_file}")


def print_summary(results: List[SWEBenchResult]):
    """Print results summary."""
    total = len(results)
    solved = sum(1 for r in results if r.success)
    total_cost = sum(r.total_cost for r in results)
    total_time = sum(r.total_time for r in results)

    print("\n" + "="*60)
    print("OPUS ENSEMBLE - SWE-bench Results")
    print("="*60)
    print(f"Tasks: {total}")
    print(f"Solved: {solved} ({100*solved/total:.1f}%)")
    print(f"Total Cost: ${total_cost:.2f}")
    print(f"Total Time: {total_time/60:.1f} minutes")
    print(f"Avg Time/Task: {total_time/total:.1f}s")
    print("="*60)

    # Strategy breakdown
    # Would need to track this in results


def main():
    parser = argparse.ArgumentParser(
        description="Run Opus Ensemble on SWE-bench",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run on SWE-bench Verified
    python scripts/run_swebench.py --dataset verified

    # Run subset with random selection
    python scripts/run_swebench.py --dataset verified --num 25 --random

    # Test mode (free model)
    python scripts/run_swebench.py --test --num 5

    # Production mode
    python scripts/run_swebench.py --production --dataset verified
        """
    )

    # Dataset options
    parser.add_argument(
        "--dataset",
        choices=["verified", "lite", "file"],
        default="verified",
        help="Which dataset to use (default: verified)"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="JSONL file path when using --dataset file"
    )
    parser.add_argument(
        "--num",
        type=int,
        help="Number of tasks to run (default: all)"
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="Randomly select tasks"
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Start index (for resuming)"
    )

    # Mode options
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use test mode (free model via OpenRouter)"
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Use production mode (Claude Opus)"
    )

    # Feature toggles
    parser.add_argument(
        "--no-localization",
        action="store_true",
        help="Disable localization phase"
    )
    parser.add_argument(
        "--no-reproduction",
        action="store_true",
        help="Disable reproduction test generation"
    )
    parser.add_argument(
        "--no-correction",
        action="store_true",
        help="Disable self-correction loop"
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="predictions.jsonl",
        help="Output predictions file"
    )
    parser.add_argument(
        "--summary",
        type=str,
        help="Output summary JSON file"
    )
    parser.add_argument(
        "--log",
        type=str,
        help="Log file path"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log, args.verbose)

    # Determine mode
    if args.production:
        mode = ModelMode.PRODUCTION
        logging.info("Running in PRODUCTION mode (Claude Opus)")
    else:
        mode = ModelMode.TEST
        logging.info("Running in TEST mode (Free model via OpenRouter)")

    # Load dataset
    if args.dataset == "verified":
        tasks = load_swebench_verified()
    elif args.dataset == "lite":
        tasks = load_swebench_lite()
    elif args.dataset == "file":
        if not args.file:
            parser.error("--file required when using --dataset file")
        tasks = load_from_file(args.file)
    else:
        parser.error(f"Unknown dataset: {args.dataset}")

    # Select subset
    if args.random and args.num:
        tasks = random.sample(tasks, min(args.num, len(tasks)))
        logging.info(f"Randomly selected {len(tasks)} tasks")
    elif args.num:
        tasks = tasks[args.start:args.start + args.num]
        logging.info(f"Selected tasks {args.start} to {args.start + len(tasks)}")

    if not tasks:
        logging.error("No tasks to run!")
        sys.exit(1)

    # Initialize orchestrator
    orchestrator = SWEBenchOrchestrator(
        mode=mode,
        enable_localization=not args.no_localization,
        enable_reproduction=not args.no_reproduction,
        enable_correction=not args.no_correction,
    )

    # Run
    logging.info(f"Starting Opus Ensemble on {len(tasks)} tasks...")
    start_time = time.time()

    results = orchestrator.solve_batch(
        tasks,
        output_file=args.output
    )

    elapsed = time.time() - start_time

    # Save results
    summary_file = args.summary or args.output.replace('.jsonl', '_summary.json')
    save_results(results, args.output, summary_file)

    # Print summary
    print_summary(results)

    logging.info(f"Completed in {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()
