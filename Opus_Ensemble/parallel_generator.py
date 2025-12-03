"""
Parallel patch generation - Phase 3 of the Opus Ensemble.

Spawns N parallel model instances with different strategies.
"""

import asyncio
import re
import time
from typing import List, Optional

try:
    from .config import get_config, STRATEGY_SYSTEM_PROMPTS, PATCH_GENERATION_TEMPLATE, ModelMode
    from .api_client import EnsembleAPIClient, get_client
    from .data_types import PatchCandidate, Strategy
except ImportError:
    from config import get_config, STRATEGY_SYSTEM_PROMPTS, PATCH_GENERATION_TEMPLATE, ModelMode
    from api_client import EnsembleAPIClient, get_client
    from data_types import PatchCandidate, Strategy


class ParallelGenerator:
    """
    Generate patches from multiple parallel model instances.

    Each instance uses a different strategy (minimal, extended_thinking, etc.)
    """

    def __init__(self, mode: Optional[ModelMode] = None):
        """
        Initialize the generator.

        Args:
            mode: ModelMode.PRODUCTION or ModelMode.TEST
        """
        self.config = get_config(mode)
        self.client = get_client(mode)

    async def generate(
        self,
        issue: str,
        code: str,
        test_code: str = "",
        num_instances: Optional[int] = None,
    ) -> List[PatchCandidate]:
        """
        Generate patches from N parallel instances.

        Args:
            issue: The issue/task description
            code: The relevant code to fix
            test_code: Test code that should pass after fix
            num_instances: Override number of parallel instances

        Returns:
            List of PatchCandidate objects
        """
        n = num_instances or self.config.num_parallel_instances

        # Build requests for each instance
        requests = []
        instance_strategies = []

        instance_id = 0
        for strategy_name, count in self.config.strategy_distribution.items():
            strategy = Strategy(strategy_name)
            system_prompt = STRATEGY_SYSTEM_PROMPTS.get(strategy_name, "")
            temperature = self.config.strategy_temperatures.get(strategy_name, 0.0)

            for _ in range(count):
                if instance_id >= n:
                    break

                # Build the user message
                user_message = PATCH_GENERATION_TEMPLATE.format(
                    issue=issue,
                    code=code,
                    reproduction_test=test_code or "No reproduction test provided.",
                )

                requests.append({
                    "messages": [{"role": "user", "content": user_message}],
                    "system_prompt": system_prompt,
                    "temperature": temperature,
                    "max_tokens": self.config.model.max_tokens,
                })

                instance_strategies.append((instance_id, strategy))
                instance_id += 1

        # Run all in parallel
        start_time = time.time()
        results = await self.client.complete_parallel(requests)
        total_time = time.time() - start_time

        # Convert to PatchCandidate objects
        patches = []
        for i, result in enumerate(results):
            instance_id, strategy = instance_strategies[i]

            # Extract code from response
            code_content = self._extract_code(result.content)

            patches.append(PatchCandidate(
                instance_id=instance_id,
                strategy=strategy,
                code=code_content,
                raw_response=result.content,
                model_id=result.model_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost=result.cost,
                generation_time_seconds=result.elapsed_seconds,
            ))

        return patches

    def _extract_code(self, response: str) -> str:
        """
        Extract code from model response.

        Looks for code in:
        1. SEARCH/REPLACE blocks (new format)
        2. ```python ... ``` blocks
        3. ```diff ... ``` blocks
        4. ``` ... ``` blocks
        5. Raw response if no blocks found
        """
        # Try SEARCH/REPLACE format first (new format)
        search_replace_pattern = r"<<<<<<< SEARCH\s*(.*?)>>>>>>> REPLACE"
        sr_matches = re.findall(search_replace_pattern, response, re.DOTALL)
        if sr_matches:
            # Return all search/replace blocks joined
            blocks = []
            for match in sr_matches:
                blocks.append(f"<<<<<<< SEARCH\n{match.strip()}\n>>>>>>> REPLACE")
            return "\n\n".join(blocks)

        # Try diff blocks
        diff_match = re.search(r"```diff\s*(.*?)```", response, re.DOTALL)
        if diff_match:
            return diff_match.group(1).strip()

        # Try python blocks
        python_match = re.search(r"```python\s*(.*?)```", response, re.DOTALL)
        if python_match:
            return python_match.group(1).strip()

        # Try any code block
        code_match = re.search(r"```\s*(.*?)```", response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Return raw response (might still be valid)
        return response.strip()


async def generate_patches(
    issue: str,
    code: str,
    test_code: str = "",
    num_instances: int = 40,
    mode: Optional[ModelMode] = None,
) -> List[PatchCandidate]:
    """
    Convenience function to generate patches.

    Args:
        issue: Task description
        code: Code to fix
        test_code: Test code
        num_instances: Number of parallel instances
        mode: Model mode

    Returns:
        List of PatchCandidate objects
    """
    generator = ParallelGenerator(mode)
    return await generator.generate(issue, code, test_code, num_instances)
