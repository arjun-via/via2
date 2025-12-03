"""
=============================================================================
SCRIPT NAME: ensemble.py
=============================================================================

Opus-Conductor Ensemble Pattern

Parallel code generation with multiple models and intelligent selection
of the best solution based on various strategies.

Key Features:
- Parallel generation from multiple models
- Multiple selection strategies (voting, execution, semantic)
- Automatic fallback on failures
- Cost-efficient parallel execution

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import time
import logging
import concurrent.futures
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from conductor.state import ConductorState
from conductor.clients import ResilientModelClient


class EnsembleStrategy(Enum):
    """Strategy for selecting the best solution."""
    EXECUTION = "execution"      # Select based on execution success
    VOTING = "voting"            # Semantic voting by judge
    MAJORITY = "majority"        # Majority voting on correctness
    FASTEST = "fastest"          # First to complete successfully
    BEST_OF_N = "best_of_n"      # Generate N, pick best


@dataclass
class CandidateSolution:
    """A candidate solution from one model."""
    model_id: str
    code: str
    reasoning: str
    execution_passed: bool = False
    execution_output: str = ""
    votes: int = 0
    cost: float = 0.0
    duration: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "code": self.code,
            "reasoning": self.reasoning[:500],
            "execution_passed": self.execution_passed,
            "votes": self.votes,
            "cost": self.cost,
            "duration": self.duration,
            "error": self.error,
        }


@dataclass
class EnsembleResult:
    """Result of ensemble generation."""
    success: bool
    selected_solution: Optional[CandidateSolution]
    all_candidates: List[CandidateSolution]
    strategy_used: EnsembleStrategy
    selection_reasoning: str
    total_cost: float
    total_time: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "selected": self.selected_solution.to_dict() if self.selected_solution else None,
            "candidates": [c.to_dict() for c in self.all_candidates],
            "strategy": self.strategy_used.value,
            "reasoning": self.selection_reasoning,
            "cost": self.total_cost,
            "time": self.total_time,
        }


class EnsembleOrchestrator:
    """
    Orchestrates parallel code generation with ensemble selection.

    Usage:
        ensemble = EnsembleOrchestrator(
            generators={"sonnet": sonnet_client, "gpt4": gpt4_client},
            judge=opus_client,
            strategy=EnsembleStrategy.EXECUTION,
        )
        result = ensemble.run(state)
    """

    def __init__(
        self,
        generators: Dict[str, ResilientModelClient],
        judge: ResilientModelClient,
        strategy: EnsembleStrategy = EnsembleStrategy.EXECUTION,
        executor: Optional[Callable[[str], tuple]] = None,
        max_workers: int = 4,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize ensemble orchestrator.

        Args:
            generators: Dict of model_id -> client for code generation
            judge: Client for judging/voting (typically Opus)
            strategy: Selection strategy to use
            executor: Optional code execution function (code -> (output, success))
            max_workers: Max parallel workers
            logger: Optional logger
        """
        self.generators = generators
        self.judge = judge
        self.strategy = strategy
        self.executor = executor or self._default_executor
        self.max_workers = max_workers
        self.logger = logger or logging.getLogger(__name__)

        self.total_cost = 0.0

    def _log(self, message: str) -> None:
        """Log a message."""
        self.logger.info(f"[ENSEMBLE] {message}")

    def run(self, state: ConductorState) -> EnsembleResult:
        """
        Run ensemble generation and selection.

        Args:
            state: Current conductor state

        Returns:
            EnsembleResult with selected solution
        """
        start_time = time.time()
        self._log(f"Starting ensemble with {len(self.generators)} generators")
        self._log(f"Strategy: {self.strategy.value}")

        # Phase 1: Parallel generation
        candidates = self._generate_candidates(state)
        self._log(f"Generated {len(candidates)} candidates")

        # Phase 2: Selection based on strategy
        selected, reasoning = self._select_solution(state, candidates)

        total_time = time.time() - start_time

        if selected:
            self._log(f"Selected: {selected.model_id} (exec={selected.execution_passed})")
        else:
            self._log("No valid solution selected")

        return EnsembleResult(
            success=selected is not None and selected.execution_passed,
            selected_solution=selected,
            all_candidates=candidates,
            strategy_used=self.strategy,
            selection_reasoning=reasoning,
            total_cost=self.total_cost,
            total_time=total_time,
        )

    def _generate_candidates(self, state: ConductorState) -> List[CandidateSolution]:
        """Generate solutions from all models in parallel."""
        candidates = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_model = {
                executor.submit(self._generate_single, model_id, client, state): model_id
                for model_id, client in self.generators.items()
            }

            for future in concurrent.futures.as_completed(future_to_model):
                model_id = future_to_model[future]
                try:
                    candidate = future.result()
                    candidates.append(candidate)
                except Exception as e:
                    self._log(f"Error from {model_id}: {e}")
                    candidates.append(CandidateSolution(
                        model_id=model_id,
                        code="",
                        reasoning="",
                        error=str(e),
                    ))

        return candidates

    def _generate_single(
        self,
        model_id: str,
        client: ResilientModelClient,
        state: ConductorState,
    ) -> CandidateSolution:
        """Generate a single solution from one model."""
        start_time = time.time()

        prompt = self._build_generation_prompt(state)
        messages = [{"role": "user", "content": prompt}]
        system = self._get_generation_system_prompt()

        response = client.complete(messages, system=system)
        self.total_cost += response.cost

        code = self._extract_code(response.content)
        duration = time.time() - start_time

        candidate = CandidateSolution(
            model_id=model_id,
            code=code or "",
            reasoning=response.content,
            cost=response.cost,
            duration=duration,
        )

        # Run execution if we have code
        if code and self.strategy in [EnsembleStrategy.EXECUTION, EnsembleStrategy.BEST_OF_N]:
            try:
                output, success = self.executor(code)
                candidate.execution_passed = success
                candidate.execution_output = output
            except Exception as e:
                candidate.execution_passed = False
                candidate.execution_output = str(e)

        self._log(f"  {model_id}: {len(code) if code else 0} chars, "
                  f"exec={'PASS' if candidate.execution_passed else 'FAIL'}")

        return candidate

    def _select_solution(
        self,
        state: ConductorState,
        candidates: List[CandidateSolution],
    ) -> tuple:
        """Select the best solution based on strategy."""
        valid_candidates = [c for c in candidates if c.code and not c.error]

        if not valid_candidates:
            return None, "No valid candidates generated"

        if self.strategy == EnsembleStrategy.EXECUTION:
            return self._select_by_execution(valid_candidates)

        elif self.strategy == EnsembleStrategy.VOTING:
            return self._select_by_voting(state, valid_candidates)

        elif self.strategy == EnsembleStrategy.MAJORITY:
            return self._select_by_majority(state, valid_candidates)

        elif self.strategy == EnsembleStrategy.FASTEST:
            return self._select_fastest(valid_candidates)

        elif self.strategy == EnsembleStrategy.BEST_OF_N:
            return self._select_best_of_n(state, valid_candidates)

        return valid_candidates[0], "Default selection (first candidate)"

    def _select_by_execution(
        self,
        candidates: List[CandidateSolution],
    ) -> tuple:
        """Select based on execution success."""
        passing = [c for c in candidates if c.execution_passed]

        if passing:
            # Among passing, prefer fastest
            best = min(passing, key=lambda c: c.duration)
            return best, f"Selected {best.model_id}: execution passed, fastest"

        # No passing - return first that has code
        if candidates:
            return candidates[0], "No execution passed, selecting first candidate"

        return None, "No candidates available"

    def _select_by_voting(
        self,
        state: ConductorState,
        candidates: List[CandidateSolution],
    ) -> tuple:
        """Have the judge vote on solutions."""
        prompt = self._build_voting_prompt(state, candidates)
        messages = [{"role": "user", "content": prompt}]
        system = self._get_voting_system_prompt()

        response = self.judge.complete(messages, system=system)
        self.total_cost += response.cost

        # Parse winner from response
        winner_id = self._parse_voting_response(response.content, candidates)

        for candidate in candidates:
            if candidate.model_id == winner_id:
                return candidate, f"Judge selected {winner_id}: {response.content[:200]}"

        # Fallback
        return candidates[0], "Could not parse judge vote, selecting first"

    def _select_by_majority(
        self,
        state: ConductorState,
        candidates: List[CandidateSolution],
    ) -> tuple:
        """Have each model vote for others, majority wins."""
        # Each candidate model votes for another candidate (not themselves)
        for voter_id, voter_client in self.generators.items():
            other_candidates = [c for c in candidates if c.model_id != voter_id]
            if not other_candidates:
                continue

            prompt = self._build_majority_vote_prompt(state, other_candidates)
            messages = [{"role": "user", "content": prompt}]

            try:
                response = voter_client.complete(messages)
                self.total_cost += response.cost

                voted_for = self._parse_voting_response(response.content, other_candidates)
                for c in candidates:
                    if c.model_id == voted_for:
                        c.votes += 1
            except Exception:
                pass

        # Select by most votes
        best = max(candidates, key=lambda c: c.votes)
        return best, f"Majority vote: {best.model_id} with {best.votes} votes"

    def _select_fastest(
        self,
        candidates: List[CandidateSolution],
    ) -> tuple:
        """Select the fastest successful solution."""
        passing = [c for c in candidates if c.execution_passed]
        pool = passing if passing else candidates

        fastest = min(pool, key=lambda c: c.duration)
        status = "passing" if fastest.execution_passed else "any"
        return fastest, f"Fastest {status}: {fastest.model_id} ({fastest.duration:.1f}s)"

    def _select_best_of_n(
        self,
        state: ConductorState,
        candidates: List[CandidateSolution],
    ) -> tuple:
        """Select best among N using execution + judge fallback."""
        # First try execution-based
        passing = [c for c in candidates if c.execution_passed]

        if len(passing) == 1:
            return passing[0], f"Only one passing: {passing[0].model_id}"

        if len(passing) > 1:
            # Multiple passing - use judge to pick best
            return self._select_by_voting(state, passing)

        # None passing - use judge on all
        return self._select_by_voting(state, candidates)

    def _get_generation_system_prompt(self) -> str:
        return """You are an expert code generation agent.

Generate clean, correct, complete code that solves the given task.

Requirements:
1. Handle all edge cases mentioned
2. Include all necessary imports
3. Write production-quality code

Output your solution in a ```python code block."""

    def _get_voting_system_prompt(self) -> str:
        return """You are judging code solutions.

Evaluate each solution for:
1. Correctness
2. Completeness (edge cases)
3. Code quality

Output the winner's model_id in JSON:
{"winner": "model_id", "reason": "explanation"}"""

    def _build_generation_prompt(self, state: ConductorState) -> str:
        parts = [
            "## TASK",
            state.original_task,
            "",
            "## CONSTRAINTS",
        ]
        for c in state.constraints:
            parts.append(f"- {c}")

        parts.extend(["", "## EDGE CASES"])
        for e in state.edge_cases:
            parts.append(f"- {e}")

        parts.extend([
            "",
            "Provide your complete solution in Python.",
        ])

        return "\n".join(parts)

    def _build_voting_prompt(
        self,
        state: ConductorState,
        candidates: List[CandidateSolution],
    ) -> str:
        parts = [
            "## TASK",
            state.original_task,
            "",
            "## CANDIDATES",
        ]

        for c in candidates:
            exec_status = "PASSED" if c.execution_passed else "FAILED"
            parts.extend([
                f"\n### {c.model_id} (execution: {exec_status})",
                "```python",
                c.code[:2000],
                "```",
            ])

        parts.extend([
            "",
            "Select the best solution. Output JSON with winner model_id.",
        ])

        return "\n".join(parts)

    def _build_majority_vote_prompt(
        self,
        state: ConductorState,
        candidates: List[CandidateSolution],
    ) -> str:
        parts = [
            f"## TASK: {state.original_task[:200]}",
            "",
            "## SOLUTIONS TO VOTE ON",
        ]

        for c in candidates:
            parts.extend([
                f"\n### {c.model_id}",
                "```python",
                c.code[:1000],
                "```",
            ])

        parts.append("\nWhich solution is best? Reply with just the model_id.")

        return "\n".join(parts)

    def _extract_code(self, text: str) -> Optional[str]:
        """Extract Python code from text."""
        import re
        match = re.search(r'```python\s*(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'```\s*(.*?)```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _parse_voting_response(
        self,
        response: str,
        candidates: List[CandidateSolution],
    ) -> str:
        """Parse voting response to get winner."""
        import json
        import re

        # Try JSON first
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("winner", "")
        except json.JSONDecodeError:
            pass

        # Look for model IDs in response
        for c in candidates:
            if c.model_id.lower() in response.lower():
                return c.model_id

        return candidates[0].model_id if candidates else ""

    def _default_executor(self, code: str) -> tuple:
        """Default code executor using subprocess."""
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            result = subprocess.run(
                ['python', temp_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout + result.stderr
            success = result.returncode == 0
            return output, success
        except subprocess.TimeoutExpired:
            return "Timeout", False
        except Exception as e:
            return str(e), False
        finally:
            Path(temp_path).unlink(missing_ok=True)
