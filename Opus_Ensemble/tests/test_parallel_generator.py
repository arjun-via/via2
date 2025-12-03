"""
Tests for parallel_generator.py - Parallel patch generation.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_types import Strategy, PatchCandidate
from parallel_generator import ParallelGenerator
from api_client import CompletionResult
from config import ModelMode


class TestParallelGenerator:
    """Tests for ParallelGenerator class."""

    def test_init_with_test_mode(self):
        """Initialize with test mode."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            generator = ParallelGenerator(mode=ModelMode.TEST)
            assert generator.config.mode == ModelMode.TEST
            assert generator.config.model.model_id == "openai/gpt-oss-120b"

    def test_init_with_production_mode(self):
        """Initialize with production mode."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            generator = ParallelGenerator(mode=ModelMode.PRODUCTION)
            assert generator.config.mode == ModelMode.PRODUCTION
            assert generator.config.model.model_id == "claude-opus-4-5-20250514"


class TestCodeExtraction:
    """Tests for _extract_code method."""

    def test_extract_python_block(self):
        """Extract code from ```python block."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            generator = ParallelGenerator(mode=ModelMode.TEST)

            response = """Here's the fix:

```python
def fixed_function():
    return 42
```

This should work."""

            code = generator._extract_code(response)
            assert code == "def fixed_function():\n    return 42"

    def test_extract_diff_block(self):
        """Extract code from ```diff block."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            generator = ParallelGenerator(mode=ModelMode.TEST)

            response = """```diff
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
-old line
+new line
```"""

            code = generator._extract_code(response)
            assert "--- a/file.py" in code
            assert "+new line" in code

    def test_extract_generic_block(self):
        """Extract code from ``` block (no language)."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            generator = ParallelGenerator(mode=ModelMode.TEST)

            response = """```
def foo():
    pass
```"""

            code = generator._extract_code(response)
            assert code == "def foo():\n    pass"

    def test_extract_no_block(self):
        """Return raw response when no code block found."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            generator = ParallelGenerator(mode=ModelMode.TEST)

            response = "def inline_code(): return True"
            code = generator._extract_code(response)
            assert code == response

    def test_python_block_takes_priority(self):
        """Python block is extracted over generic block."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            generator = ParallelGenerator(mode=ModelMode.TEST)

            response = """```
generic code
```

```python
python code
```"""

            code = generator._extract_code(response)
            assert code == "python code"


class TestGeneratePatches:
    """Tests for generate method (with mocked API)."""

    @pytest.mark.asyncio
    async def test_generate_patches_mocked(self):
        """Generate patches with mocked API client."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            generator = ParallelGenerator(mode=ModelMode.TEST)

            # Mock the client
            mock_results = [
                CompletionResult(
                    content=f"```python\ndef fix_{i}(): pass\n```",
                    input_tokens=100,
                    output_tokens=50,
                    cost=0.0,
                    model_id="openai/gpt-oss-120b",
                    elapsed_seconds=1.0,
                )
                for i in range(5)
            ]

            generator.client.complete_parallel = AsyncMock(return_value=mock_results)

            patches = await generator.generate(
                issue="Fix the bug",
                code="def broken(): pass",
                num_instances=5,
            )

            assert len(patches) == 5
            for i, patch in enumerate(patches):
                assert isinstance(patch, PatchCandidate)
                assert f"fix_{i}" in patch.code
                assert patch.model_id == "openai/gpt-oss-120b"

    @pytest.mark.asyncio
    async def test_strategies_distributed(self):
        """Strategies are distributed across instances."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            from config import get_test_config
            generator = ParallelGenerator(mode=ModelMode.TEST)
            generator.config = get_test_config()  # Uses reduced distribution

            mock_results = [
                CompletionResult(
                    content="```python\npass\n```",
                    input_tokens=100,
                    output_tokens=50,
                    cost=0.0,
                    model_id="test",
                    elapsed_seconds=1.0,
                )
                for _ in range(5)
            ]

            generator.client.complete_parallel = AsyncMock(return_value=mock_results)

            patches = await generator.generate(
                issue="Test",
                code="test",
                num_instances=5,
            )

            # Check we get different strategies
            strategies = [p.strategy for p in patches]
            strategy_names = [s.value for s in strategies]

            # Should have at least 2 different strategies in 5 patches
            assert len(set(strategy_names)) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
