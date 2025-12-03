"""
Tests for orchestrator.py - Main Opus Ensemble orchestrator.
"""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_types import Strategy, PatchCandidate, VerificationResult, EnsembleResult
from orchestrator import OpusEnsemble, run_ensemble
from config import ModelMode


class TestOpusEnsemble:
    """Tests for OpusEnsemble class."""

    def test_init_test_mode(self):
        """Initialize ensemble in test mode."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            ensemble = OpusEnsemble(mode=ModelMode.TEST)
            assert ensemble.config.mode == ModelMode.TEST
            assert ensemble.config.model.model_id == "openai/gpt-oss-120b"

    def test_init_production_mode(self):
        """Initialize ensemble in production mode."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            ensemble = OpusEnsemble(mode=ModelMode.PRODUCTION)
            assert ensemble.config.mode == ModelMode.PRODUCTION
            assert ensemble.config.model.model_id == "claude-opus-4-5-20251101"


class TestRunAsync:
    """Tests for run_async method."""

    @pytest.mark.asyncio
    async def test_successful_run(self):
        """Successful run returns passing result."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            ensemble = OpusEnsemble(mode=ModelMode.TEST)

            # Create mock patches
            mock_patches = [
                PatchCandidate(
                    instance_id=i,
                    strategy=Strategy.MINIMAL,
                    code="def add(a, b): return a + b",
                    raw_response="Here's the fix",
                    model_id="test",
                    cost=0.0,
                )
                for i in range(5)
            ]

            # Create mock verification results (3 pass, 2 fail)
            mock_verifications = []
            for i, patch in enumerate(mock_patches):
                result = VerificationResult(
                    patch=patch,
                    syntax_valid=True,
                    patch_applies=True,
                    reproduction_passes=(i < 3),  # First 3 pass
                    regression_passes=(i < 3),
                    tests_passed=1 if i < 3 else 0,
                    tests_total=1,
                )
                mock_verifications.append(result)

            # Mock generator
            ensemble.generator.generate = AsyncMock(return_value=mock_patches)

            # Mock verifier
            ensemble.verifier.verify_all = MagicMock(return_value=mock_verifications)
            ensemble.verifier.filter_passing = MagicMock(
                return_value=(mock_verifications[:3], mock_verifications[3:])
            )
            ensemble.verifier.rank_passing = MagicMock(
                return_value=mock_verifications[:3]
            )

            result = await ensemble.run_async(
                issue="Fix the add function",
                code="def add(a, b): return a - b",
                test_code="assert add(1, 2) == 3",
                num_instances=5,
            )

            assert result.success is True
            assert result.total_patches_generated == 5
            assert result.patches_syntax_valid == 5
            assert result.patches_regression_pass == 3
            assert result.winning_strategy == Strategy.MINIMAL

    @pytest.mark.asyncio
    async def test_failed_run_no_passing(self):
        """Failed run when no patches pass."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            ensemble = OpusEnsemble(mode=ModelMode.TEST)

            # All patches fail syntax
            mock_patches = [
                PatchCandidate(
                    instance_id=i,
                    strategy=Strategy.MINIMAL,
                    code="def broken(",
                    raw_response="",
                    model_id="test",
                    cost=0.0,
                )
                for i in range(5)
            ]

            mock_verifications = [
                VerificationResult(
                    patch=patch,
                    syntax_valid=False,
                    syntax_error="SyntaxError",
                )
                for patch in mock_patches
            ]

            ensemble.generator.generate = AsyncMock(return_value=mock_patches)
            ensemble.verifier.verify_all = MagicMock(return_value=mock_verifications)
            ensemble.verifier.filter_passing = MagicMock(return_value=([], mock_verifications))

            result = await ensemble.run_async(
                issue="Fix something",
                code="broken code",
                num_instances=5,
            )

            assert result.success is False
            assert result.final_patch is None
            assert "No patches passed" in result.error_message


class TestRunSync:
    """Tests for synchronous run method."""

    def test_run_sync_wrapper(self):
        """Sync run wraps async run."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            ensemble = OpusEnsemble(mode=ModelMode.TEST)

            # Mock the async method
            mock_result = EnsembleResult(
                success=True,
                final_patch="patch",
                total_patches_generated=5,
            )

            async def mock_run_async(*args, **kwargs):
                return mock_result

            ensemble.run_async = mock_run_async

            result = ensemble.run(
                issue="Test",
                code="test code",
            )

            assert result.success is True
            assert result.total_patches_generated == 5


class TestRunEnsembleConvenience:
    """Tests for run_ensemble convenience function."""

    def test_run_ensemble_creates_instance(self):
        """run_ensemble creates OpusEnsemble and runs."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            # Mock OpusEnsemble
            mock_result = EnsembleResult(
                success=True,
                final_patch="test patch",
            )

            with patch("orchestrator.OpusEnsemble") as MockEnsemble:
                mock_instance = MagicMock()
                mock_instance.run.return_value = mock_result
                MockEnsemble.return_value = mock_instance

                result = run_ensemble(
                    issue="Test issue",
                    code="test code",
                    num_instances=10,
                    mode=ModelMode.TEST,
                )

                MockEnsemble.assert_called_once_with(ModelMode.TEST)
                mock_instance.run.assert_called_once_with(
                    "Test issue", "test code", "", 10
                )
                assert result.success is True


class TestEnsembleMetrics:
    """Tests for ensemble metrics tracking."""

    @pytest.mark.asyncio
    async def test_cost_tracking(self):
        """Total cost is tracked across all patches."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            ensemble = OpusEnsemble(mode=ModelMode.TEST)

            mock_patches = [
                PatchCandidate(
                    instance_id=i,
                    strategy=Strategy.MINIMAL,
                    code="pass",
                    raw_response="",
                    model_id="test",
                    cost=0.10,  # Each patch costs $0.10
                )
                for i in range(5)
            ]

            mock_verifications = [
                VerificationResult(
                    patch=patch,
                    syntax_valid=True,
                    patch_applies=True,
                    reproduction_passes=True,
                    regression_passes=True,
                )
                for patch in mock_patches
            ]

            ensemble.generator.generate = AsyncMock(return_value=mock_patches)
            ensemble.verifier.verify_all = MagicMock(return_value=mock_verifications)
            ensemble.verifier.filter_passing = MagicMock(
                return_value=(mock_verifications, [])
            )
            ensemble.verifier.rank_passing = MagicMock(return_value=mock_verifications)

            result = await ensemble.run_async(issue="Test", code="test", num_instances=5)

            # Total cost should be 5 * $0.10 = $0.50
            assert result.total_cost == 0.50

    @pytest.mark.asyncio
    async def test_time_tracking(self):
        """Time is tracked for generation and verification."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            ensemble = OpusEnsemble(mode=ModelMode.TEST)

            mock_patches = [
                PatchCandidate(
                    instance_id=0,
                    strategy=Strategy.MINIMAL,
                    code="pass",
                    raw_response="",
                    model_id="test",
                )
            ]

            mock_verifications = [
                VerificationResult(
                    patch=mock_patches[0],
                    syntax_valid=True,
                    patch_applies=True,
                    reproduction_passes=True,
                    regression_passes=True,
                )
            ]

            ensemble.generator.generate = AsyncMock(return_value=mock_patches)
            ensemble.verifier.verify_all = MagicMock(return_value=mock_verifications)
            ensemble.verifier.filter_passing = MagicMock(
                return_value=(mock_verifications, [])
            )
            ensemble.verifier.rank_passing = MagicMock(return_value=mock_verifications)

            result = await ensemble.run_async(issue="Test", code="test", num_instances=1)

            assert result.total_time_seconds >= 0
            assert result.generation_time_seconds >= 0
            assert result.verification_time_seconds >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
