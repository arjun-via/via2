"""GPT-4o judge evaluator."""
import json
import os
from typing import Dict, Any

from alo.backend.clients.openai_client import OpenAICompatibleClient
from benchmark.evaluators.evaluation_schema import (
    ComparativeEvaluation,
    DimensionScore,
    SolutionEvaluation,
    JUDGE_PROMPT_TEMPLATE
)


class O3MiniJudge:
    """Evaluator using GPT-4o as judge."""

    def __init__(
        self,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
        temperature: int = 1
    ):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable required")

        self.client = OpenAICompatibleClient(
            model=model,
            api_key=api_key,
            base_url=base_url
        )
        self.temperature = temperature
        self.model = model

    def evaluate(
        self,
        original_prompt: str,
        context_summary: str,
        alo_output: str,
        sonnet_context_output: str,
        sonnet_raw_output: str
    ) -> tuple[ComparativeEvaluation, Dict[str, Any]]:
        """
        Evaluate three solutions comparatively.

        Returns:
            Tuple of (ComparativeEvaluation, metadata dict with costs/tokens)
        """
        # Format judge prompt
        judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
            original_prompt=original_prompt,
            context_summary=context_summary or "None provided",
            alo_output=alo_output,
            sonnet_context_output=sonnet_context_output,
            sonnet_raw_output=sonnet_raw_output
        )

        # Call o3-mini-high
        response = self.client.chat(
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=self.temperature
        )

        content = response.get("content", "")
        raw_response = response.get("raw")

        # Parse JSON response
        try:
            # Extract JSON from response (may be wrapped in markdown code blocks)
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()

            evaluation_data = json.loads(json_str)
        except (json.JSONDecodeError, IndexError) as e:
            raise ValueError(f"Failed to parse judge response as JSON: {e}\n\nResponse: {content[:500]}")

        # Parse into structured objects
        comparative_eval = self._parse_evaluation(evaluation_data)

        # Extract metadata
        usage = getattr(raw_response, "usage", None)
        metadata = {
            "judge_model": self.model,
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
            "raw_response": content
        }

        return comparative_eval, metadata

    def _parse_evaluation(self, data: Dict[str, Any]) -> ComparativeEvaluation:
        """Parse JSON data into ComparativeEvaluation object."""
        def parse_solution(sol_data: Dict[str, Any]) -> SolutionEvaluation:
            return SolutionEvaluation(
                correctness=DimensionScore(
                    score=sol_data["correctness"]["score"],
                    reasoning=sol_data["correctness"]["reasoning"]
                ),
                completeness=DimensionScore(
                    score=sol_data["completeness"]["score"],
                    reasoning=sol_data["completeness"]["reasoning"]
                ),
                code_quality=DimensionScore(
                    score=sol_data["code_quality"]["score"],
                    reasoning=sol_data["code_quality"]["reasoning"]
                ),
                security=DimensionScore(
                    score=sol_data["security"]["score"],
                    reasoning=sol_data["security"]["reasoning"]
                ),
                clarity=DimensionScore(
                    score=sol_data["clarity"]["score"],
                    reasoning=sol_data["clarity"]["reasoning"]
                ),
                overall=sol_data["overall"],
                strengths=sol_data["strengths"],
                weaknesses=sol_data["weaknesses"]
            )

        return ComparativeEvaluation(
            solution_a=parse_solution(data["solution_a"]),
            solution_b=parse_solution(data["solution_b"]),
            solution_c=parse_solution(data["solution_c"]),
            comparative_analysis=data["comparative_analysis"],
            winner=data["winner"],
            winner_reasoning=data["winner_reasoning"]
        )
