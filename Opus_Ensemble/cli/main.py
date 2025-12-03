#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: main.py (CLI)
=============================================================================

Opus-Conductor Command Line Interface

Entry point for running the Opus-Conductor orchestration system.

Usage:
    python -m cli.main --task "Fix the bug" --repo /path/to/repo
    python -m cli.main --config config/conductor_config.yaml --task "..."

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import argparse
import logging
import sys
import json
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from conductor import OpusConductor, ConductorResult


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> logging.Logger:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
    )

    return logging.getLogger("opus-conductor")


def print_banner():
    """Print the Opus-Conductor banner."""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗ ██████╗ ██╗   ██╗███████╗     ██████╗ ██████╗ ███╗   ██╗██████╗   ║
║  ██╔═══██╗██╔══██╗██║   ██║██╔════╝    ██╔════╝██╔═══██╗████╗  ██║██╔══██╗  ║
║  ██║   ██║██████╔╝██║   ██║███████╗    ██║     ██║   ██║██╔██╗ ██║██║  ██║  ║
║  ██║   ██║██╔═══╝ ██║   ██║╚════██║    ██║     ██║   ██║██║╚██╗██║██║  ██║  ║
║  ╚██████╔╝██║     ╚██████╔╝███████║    ╚██████╗╚██████╔╝██║ ╚████║██████╔╝  ║
║   ╚═════╝ ╚═╝      ╚═════╝ ╚══════╝     ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚═════╝   ║
║                                                                              ║
║                    Multi-Agent Orchestration with Opus                       ║
║                    Continuous Validation at Every Stage                      ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_result(result: ConductorResult):
    """Print the orchestration result."""
    print("\n" + "=" * 80)
    print("ORCHESTRATION RESULT")
    print("=" * 80)

    status = "SUCCESS" if result.success else "FAILED"
    status_color = "\033[92m" if result.success else "\033[91m"
    reset_color = "\033[0m"

    print(f"Status: {status_color}{status}{reset_color}")
    print(f"Stages Completed: {result.stages_completed}/4")
    print(f"Retries Used: {result.retries_used}")
    print(f"Total Cost: ${result.total_cost:.4f}")
    print(f"Total Tokens: {result.total_tokens:,}")
    print(f"Total Time: {result.total_time:.1f}s")

    if result.failure_reason:
        print(f"\nFailure Reason: {result.failure_reason}")

    if result.final_code:
        print("\n" + "-" * 80)
        print("GENERATED CODE")
        print("-" * 80)
        # Show first 2000 chars
        code_preview = result.final_code[:2000]
        if len(result.final_code) > 2000:
            code_preview += f"\n... [{len(result.final_code) - 2000} more characters]"
        print(code_preview)

    print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Opus-Conductor: Multi-Agent Orchestration with Continuous Validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --task "Fix the cache invalidation bug in cache.py"
  %(prog)s --task "Implement a binary search function" --repo /path/to/repo
  %(prog)s --config custom_config.yaml --task "Add logging to api.py"
        """
    )

    # Required arguments
    parser.add_argument(
        "--task", "-t",
        required=True,
        help="The task description (issue/request to solve)"
    )

    # Optional arguments
    parser.add_argument(
        "--repo", "-r",
        help="Path to the target repository"
    )

    parser.add_argument(
        "--config", "-c",
        default="config/conductor_config.yaml",
        help="Path to configuration file (default: config/conductor_config.yaml)"
    )

    parser.add_argument(
        "--output", "-o",
        help="Output file for the generated code"
    )

    parser.add_argument(
        "--output-json",
        help="Output file for full result as JSON"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--log-file",
        help="Write logs to file"
    )

    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Don't print the banner"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without running"
    )

    args = parser.parse_args()

    # Print banner
    if not args.no_banner:
        print_banner()

    # Setup logging
    logger = setup_logging(args.verbose, args.log_file)

    # Resolve config path
    config_path = Path(args.config)
    if not config_path.is_absolute():
        # Try relative to script location
        script_dir = Path(__file__).parent.parent
        config_path = script_dir / args.config

    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)

    print(f"Configuration: {config_path}")
    print(f"Task: {args.task[:100]}{'...' if len(args.task) > 100 else ''}")
    if args.repo:
        print(f"Repository: {args.repo}")
    print()

    # Dry run - just validate config
    if args.dry_run:
        try:
            conductor = OpusConductor.from_config(str(config_path), logger)
            print("Configuration validated successfully!")
            print(f"  Supervisor: {conductor.supervisor_client.primary.id}")
            print(f"  Context: {conductor.context_client.primary.id}")
            print(f"  Engineering: {conductor.engineering_client.primary.id}")
            print(f"  Review: {conductor.review_client.primary.id}")
            sys.exit(0)
        except Exception as e:
            print(f"Configuration error: {e}")
            sys.exit(1)

    # Run the conductor
    try:
        conductor = OpusConductor.from_config(str(config_path), logger)

        print("Starting orchestration...")
        print("-" * 80)

        result = conductor.run(
            task=args.task,
            repo_path=args.repo,
        )

        # Print result
        print_result(result)

        # Save code output
        if args.output and result.final_code:
            output_path = Path(args.output)
            output_path.write_text(result.final_code)
            print(f"\nCode saved to: {output_path}")

        # Save JSON output
        if args.output_json:
            output_data = {
                "success": result.success,
                "final_code": result.final_code,
                "total_cost": result.total_cost,
                "total_tokens": result.total_tokens,
                "total_time": result.total_time,
                "stages_completed": result.stages_completed,
                "retries_used": result.retries_used,
                "failure_reason": result.failure_reason,
                "state": result.state.to_dict(),
            }
            json_path = Path(args.output_json)
            json_path.write_text(json.dumps(output_data, indent=2))
            print(f"Result JSON saved to: {json_path}")

        # Print cost summary
        print("\nCost Summary:")
        print(conductor.get_cost_summary())

        # Exit code
        sys.exit(0 if result.success else 1)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Orchestration failed: {e}")
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
