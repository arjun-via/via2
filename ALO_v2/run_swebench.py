"""
=============================================================================
ALO v2.0 SWE-bench Runner
=============================================================================

Run ALO v2 on SWE-bench instances with full reporting.

USAGE:
    # Test on specific instances
    python -m ALO_v2.run_swebench --instances django__django-11292 django__django-11400

    # Test on N random instances
    python -m ALO_v2.run_swebench --random 10

    # Test all available instances
    python -m ALO_v2.run_swebench --all

    # Test specific repo
    python -m ALO_v2.run_swebench --repo django --num 5
=============================================================================
"""

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import random

from .orchestrator import ALOv2Orchestrator
from .config import Config


# SWE-bench instance metadata (problem statements and test commands)
INSTANCE_METADATA = {
    # Django instances
    "django__django-11292": {
        "problem": "QuerySet.union() with values_list() returns columns in wrong order due to extra_select dict unpacking keys instead of values.",
        "test_cmd": "python tests/runtests.py queries.test_qs_combinators --settings=test_sqlite -v2"
    },
    "django__django-11400": {
        "problem": "Using an empty Q() object in an exclude() clause produces incorrect SQL. The empty Q() should be a no-op but affects the query.",
        "test_cmd": "python tests/runtests.py queries --settings=test_sqlite -v2"
    },
    "django__django-11532": {
        "problem": "EmailMessage.reply_to field doesn't properly validate email addresses, allowing invalid formats.",
        "test_cmd": "python tests/runtests.py mail --settings=test_sqlite -v2"
    },
    "django__django-12125": {
        "problem": "makemigrations produces inconsistent migration files when there's a ForeignKey to a model in the same app that hasn't been migrated yet.",
        "test_cmd": "python tests/runtests.py migrations --settings=test_sqlite -v2"
    },
    "django__django-13401": {
        "problem": "Abstract model fields are not included in the model's _meta.fields which causes issues with model inheritance.",
        "test_cmd": "python tests/runtests.py model_meta --settings=test_sqlite -v2"
    },
    "django__django-13417": {
        "problem": "QuerySet.order_by() with an expression that has no ordering fails silently instead of raising an error.",
        "test_cmd": "python tests/runtests.py ordering --settings=test_sqlite -v2"
    },
    "django__django-13551": {
        "problem": "Changing a field from a ForeignKey to a regular field doesn't properly drop the foreign key constraint in migrations.",
        "test_cmd": "python tests/runtests.py migrations --settings=test_sqlite -v2"
    },
    "django__django-13741": {
        "problem": "Form fields with disabled=True still allow data to be submitted and saved.",
        "test_cmd": "python tests/runtests.py forms_tests --settings=test_sqlite -v2"
    },
    "django__django-16100": {
        "problem": "Add an option to disable number formatting in the Django admin list display.",
        "test_cmd": "python tests/runtests.py admin_views --settings=test_sqlite -v2"
    },

    # Astropy instances
    "astropy__astropy-14539": {
        "problem": "WCS object comparison with == raises an error instead of returning False for incompatible objects.",
        "test_cmd": "python -m pytest astropy/wcs/tests/test_wcs.py -v"
    },
    "astropy__astropy-14995": {
        "problem": "NDData arithmetic operations don't properly propagate metadata.",
        "test_cmd": "python -m pytest astropy/nddata/tests/test_nddata.py -v"
    },
    "astropy__astropy-7166": {
        "problem": "InheritDocstrings metaclass doesn't work properly with properties.",
        "test_cmd": "python -m pytest astropy/utils/tests/test_misc.py -v"
    },

    # Matplotlib instances
    "matplotlib__matplotlib-20859": {
        "problem": "Setting axis limits after creating a 3D plot doesn't work correctly.",
        "test_cmd": "python -m pytest lib/mpl_toolkits/tests/test_mplot3d.py -v"
    },
    "matplotlib__matplotlib-25479": {
        "problem": "Colorbar doesn't properly handle discrete colormaps with extend='both'.",
        "test_cmd": "python -m pytest lib/matplotlib/tests/test_colorbar.py -v"
    },

    # Pytest instances
    "pytest-dev__pytest-7571": {
        "problem": "pytest.raises doesn't work correctly with match parameter when exception message contains special regex characters.",
        "test_cmd": "python -m pytest testing/python/raises.py -v"
    },

    # Scikit-learn instances
    "scikit-learn__scikit-learn-25973": {
        "problem": "TransformedTargetRegressor doesn't properly handle sample_weight parameter.",
        "test_cmd": "python -m pytest sklearn/compose/tests/test_target.py -v"
    },

    # Sympy instances
    "sympy__sympy-16766": {
        "problem": "The gamma function has incorrect behavior for certain complex arguments.",
        "test_cmd": "python -m pytest sympy/functions/special/tests/test_gamma_functions.py -v"
    },

    # Seaborn instances
    "mwaskom__seaborn-3069": {
        "problem": "PairGrid hue parameter doesn't work correctly with certain data types.",
        "test_cmd": "python -m pytest tests/test_axisgrid.py -v"
    },

    # Xarray instances
    "pydata__xarray-3677": {
        "problem": "DataArray.where() with drop=True doesn't work correctly for multi-dimensional coordinates.",
        "test_cmd": "python -m pytest xarray/tests/test_dataarray.py -v"
    },
    "pydata__xarray-4687": {
        "problem": "concat function doesn't properly handle conflicting coordinate values.",
        "test_cmd": "python -m pytest xarray/tests/test_concat.py -v"
    },
}


def get_available_instances() -> List[str]:
    """Get list of SWE-bench instances with Docker images available locally"""
    result = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}"],
        capture_output=True, text=True
    )

    instances = []
    for line in result.stdout.split("\n"):
        if "sweb.eval.x86_64" in line:
            # Parse: swebench/sweb.eval.x86_64.django_1776_django-11292
            parts = line.replace("swebench/sweb.eval.x86_64.", "").split("_1776_")
            if len(parts) == 2:
                instance_id = f"{parts[0]}__{parts[1]}"
                instances.append(instance_id)

    return sorted(set(instances))


def get_instance_metadata(instance_id: str) -> Dict[str, str]:
    """Get problem statement and test command for an instance"""
    if instance_id in INSTANCE_METADATA:
        return INSTANCE_METADATA[instance_id]

    # Default fallback for unknown instances
    repo = instance_id.split("__")[0]
    return {
        "problem": f"Fix the bug described in {instance_id}",
        "test_cmd": get_default_test_cmd(repo)
    }


def get_default_test_cmd(repo: str) -> str:
    """Get default test command for a repository"""
    test_commands = {
        "django": "python tests/runtests.py --settings=test_sqlite -v2",
        "astropy": "python -m pytest -v",
        "matplotlib": "python -m pytest -v",
        "pytest-dev": "python -m pytest -v",
        "scikit-learn": "python -m pytest -v",
        "sympy": "python -m pytest -v",
        "mwaskom": "python -m pytest -v",
        "pydata": "python -m pytest -v",
        "pylint-dev": "python -m pytest -v",
    }
    return test_commands.get(repo, "python -m pytest -v")


def run_single_instance(
    orchestrator: ALOv2Orchestrator,
    instance_id: str,
    verbose: bool = True
) -> Dict[str, Any]:
    """Run ALO v2 on a single SWE-bench instance"""
    metadata = get_instance_metadata(instance_id)

    if verbose:
        print(f"\n{'='*60}")
        print(f"Instance: {instance_id}")
        print(f"Problem: {metadata['problem'][:100]}...")
        print(f"{'='*60}")

    start_time = time.time()

    try:
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
            "elapsed_seconds": time.time() - start_time,
            "error": str(e),
            "history": []
        }

    if verbose:
        status = "PASS" if result["success"] else "FAIL"
        print(f"Result: {status}")
        print(f"  Attempts: {result['attempts']}")
        print(f"  Cost: ${result['total_cost']:.4f}")
        print(f"  Time: {result['elapsed_seconds']:.1f}s")
        if result.get("error"):
            print(f"  Error: {result['error']}")

    return result


def run_batch(
    instances: List[str],
    output_file: str,
    verbose: bool = True
) -> Dict[str, Any]:
    """Run ALO v2 on a batch of instances"""
    print(f"\n{'#'*60}")
    print(f"ALO v2.0 SWE-bench Batch Run")
    print(f"Instances: {len(instances)}")
    print(f"Output: {output_file}")
    print(f"{'#'*60}")

    orchestrator = ALOv2Orchestrator()

    results = []
    successes = 0
    total_cost = 0
    total_time = 0

    for i, instance_id in enumerate(instances, 1):
        print(f"\n[{i}/{len(instances)}] Processing {instance_id}...")

        result = run_single_instance(orchestrator, instance_id, verbose)
        results.append(result)

        if result["success"]:
            successes += 1
        total_cost += result["total_cost"]
        total_time += result["elapsed_seconds"]

        # Save intermediate results
        with open(output_file, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "completed": i,
                "total": len(instances),
                "success_rate": successes / i,
                "total_cost": total_cost,
                "total_time": total_time,
                "results": results
            }, f, indent=2)

    # Final summary
    print(f"\n{'#'*60}")
    print(f"FINAL RESULTS")
    print(f"{'#'*60}")
    print(f"Success: {successes}/{len(instances)} ({100*successes/len(instances):.1f}%)")
    print(f"Total Cost: ${total_cost:.4f}")
    print(f"Total Time: {total_time:.1f}s")
    print(f"Avg Time: {total_time/len(instances):.1f}s per instance")
    print(f"Results saved to: {output_file}")

    return {
        "success_count": successes,
        "total_count": len(instances),
        "success_rate": successes / len(instances),
        "total_cost": total_cost,
        "total_time": total_time,
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(description="Run ALO v2 on SWE-bench instances")
    parser.add_argument("--instances", nargs="+", help="Specific instance IDs to test")
    parser.add_argument("--random", type=int, help="Test N random instances")
    parser.add_argument("--repo", type=str, help="Test instances from specific repo (e.g., django)")
    parser.add_argument("--num", type=int, default=5, help="Number of instances when using --repo")
    parser.add_argument("--all", action="store_true", help="Test all available instances")
    parser.add_argument("--output", type=str, help="Output JSONL file")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")

    args = parser.parse_args()

    # Get available instances
    available = get_available_instances()
    print(f"Found {len(available)} available SWE-bench instances")

    # Select instances to test
    if args.instances:
        instances = [i for i in args.instances if i in available]
        if len(instances) != len(args.instances):
            missing = set(args.instances) - set(instances)
            print(f"Warning: Missing images for: {missing}")
    elif args.random:
        instances = random.sample(available, min(args.random, len(available)))
    elif args.repo:
        repo_instances = [i for i in available if i.startswith(f"{args.repo}__")]
        instances = repo_instances[:args.num]
    elif args.all:
        instances = available
    else:
        # Default: test a small sample
        instances = available[:3]

    if not instances:
        print("No instances to test!")
        return

    # Output file
    output_file = args.output or f"alo_v2_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Run batch
    run_batch(instances, output_file, verbose=not args.quiet)


if __name__ == "__main__":
    main()
