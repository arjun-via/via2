"""
Main Opus Ensemble orchestrator.

Coordinates: Parallel Generation → Execution Verification → Selection
"""

import asyncio
import time
from typing import Optional

try:
    from .config import get_config, ModelMode
    from .data_types import EnsembleResult, Strategy
    from .parallel_generator import ParallelGenerator
    from .verification import Verifier
except ImportError:
    from config import get_config, ModelMode
    from data_types import EnsembleResult, Strategy
    from parallel_generator import ParallelGenerator
    from verification import Verifier


class OpusEnsemble:
    """
    The complete Opus Ensemble orchestrator.

    Goal: Beat single Opus through massive parallelism + execution-based filtering.

    Pipeline:
    1. Generate N patches in parallel (different strategies)
    2. Filter by execution (syntax → apply → repro → regression)
    3. Rank passing patches and select best
    """

    def __init__(self, mode: Optional[ModelMode] = None):
        """
        Initialize the orchestrator.

        Args:
            mode: ModelMode.PRODUCTION (Opus) or ModelMode.TEST (gpt-oss-120b)
        """
        self.config = get_config(mode)
        self.generator = ParallelGenerator(mode)
        self.verifier = Verifier(timeout=self.config.docker_timeout_seconds)

    async def run_async(
        self,
        issue: str,
        code: str = "",
        test_code: str = "",
        num_instances: Optional[int] = None,
    ) -> EnsembleResult:
        """
        Run the full ensemble pipeline (async version).

        Args:
            issue: Task/issue description
            code: Relevant code context (optional for standalone tasks)
            test_code: Test code that should pass after fix
            num_instances: Override number of parallel instances

        Returns:
            EnsembleResult with final patch and metrics
        """
        start_time = time.time()
        n = num_instances or self.config.num_parallel_instances

        print(f"[Opus Ensemble] Starting with {n} parallel instances...")
        print(f"[Opus Ensemble] Model: {self.config.model.model_id}")

        # Phase 1: Parallel generation
        print(f"[Opus Ensemble] Phase 1: Generating {n} patches in parallel...")
        gen_start = time.time()

        patches = await self.generator.generate(
            issue=issue,
            code=code,
            test_code=test_code,
            num_instances=n,
        )

        gen_time = time.time() - gen_start
        print(f"[Opus Ensemble] Generated {len(patches)} patches in {gen_time:.1f}s")

        # Phase 2: Verification
        print(f"[Opus Ensemble] Phase 2: Verifying patches...")
        verify_start = time.time()

        results = self.verifier.verify_all(patches, test_code)
        passing, failing = self.verifier.filter_passing(results)

        verify_time = time.time() - verify_start

        # Count stages
        syntax_valid = sum(1 for r in results if r.syntax_valid)
        apply_ok = sum(1 for r in results if r.patch_applies)
        repro_ok = sum(1 for r in results if r.reproduction_passes)
        regression_ok = sum(1 for r in results if r.regression_passes)

        print(f"[Opus Ensemble] Verification complete in {verify_time:.1f}s:")
        print(f"  Syntax valid: {syntax_valid}/{len(results)}")
        print(f"  Patch applies: {apply_ok}/{len(results)}")
        print(f"  Repro passes: {repro_ok}/{len(results)}")
        print(f"  Regression passes: {regression_ok}/{len(results)}")
        print(f"  TOTAL PASSING: {len(passing)}/{len(results)}")

        # Phase 3: Selection
        if passing:
            ranked = self.verifier.rank_passing(passing)
            best = ranked[0]

            print(f"[Opus Ensemble] Best patch: instance {best.patch.instance_id}, strategy {best.patch.strategy.value}")

            total_time = time.time() - start_time
            total_cost = sum(p.cost for p in patches)

            return EnsembleResult(
                success=True,
                final_patch=best.patch.raw_response,
                final_code=best.patch.code,
                total_patches_generated=len(patches),
                patches_syntax_valid=syntax_valid,
                patches_apply_clean=apply_ok,
                patches_repro_pass=repro_ok,
                patches_regression_pass=regression_ok,
                winning_strategy=best.patch.strategy,
                winning_instance_id=best.patch.instance_id,
                total_cost=total_cost,
                total_time_seconds=total_time,
                generation_time_seconds=gen_time,
                verification_time_seconds=verify_time,
                all_verifications=results,
            )
        else:
            print(f"[Opus Ensemble] No patches passed verification!")

            total_time = time.time() - start_time
            total_cost = sum(p.cost for p in patches)

            return EnsembleResult(
                success=False,
                total_patches_generated=len(patches),
                patches_syntax_valid=syntax_valid,
                patches_apply_clean=apply_ok,
                patches_repro_pass=repro_ok,
                patches_regression_pass=regression_ok,
                total_cost=total_cost,
                total_time_seconds=total_time,
                generation_time_seconds=gen_time,
                verification_time_seconds=verify_time,
                all_verifications=results,
                error_message="No patches passed all verification stages",
            )

    def run(
        self,
        issue: str,
        code: str = "",
        test_code: str = "",
        num_instances: Optional[int] = None,
    ) -> EnsembleResult:
        """
        Run the full ensemble pipeline (sync wrapper).

        Args:
            issue: Task/issue description
            code: Relevant code context
            test_code: Test code
            num_instances: Override parallel instances

        Returns:
            EnsembleResult
        """
        return asyncio.run(self.run_async(issue, code, test_code, num_instances))


def run_ensemble(
    issue: str,
    code: str = "",
    test_code: str = "",
    num_instances: int = 40,
    mode: Optional[ModelMode] = None,
) -> EnsembleResult:
    """
    Convenience function to run the ensemble.

    Args:
        issue: Task description
        code: Code context
        test_code: Test code
        num_instances: Parallel instances
        mode: Model mode

    Returns:
        EnsembleResult
    """
    ensemble = OpusEnsemble(mode)
    return ensemble.run(issue, code, test_code, num_instances)
