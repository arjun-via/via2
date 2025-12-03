"""
=============================================================================
SCRIPT NAME: debate.py
=============================================================================

Opus-Conductor Debate Pattern

Multi-agent debate for complex problems where different models argue
for their solutions and a judge selects the best one.

Key Features:
- Multiple agents propose solutions
- Agents critique each other's solutions
- Structured debate rounds with rebuttals
- Judge (Opus) selects winner based on arguments

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from conductor.state import ConductorState
from conductor.clients import ResilientModelClient


class DebateRole(Enum):
    """Roles in a debate."""
    PROPOSER = "proposer"
    CRITIC = "critic"
    JUDGE = "judge"


@dataclass
class DebateArgument:
    """A single argument in the debate."""
    agent_id: str
    role: DebateRole
    content: str
    code: Optional[str] = None
    round_number: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "content": self.content,
            "code": self.code,
            "round": self.round_number,
            "timestamp": self.timestamp,
        }


@dataclass
class DebateRound:
    """A single round of debate."""
    round_number: int
    proposals: List[DebateArgument] = field(default_factory=list)
    critiques: List[DebateArgument] = field(default_factory=list)
    rebuttals: List[DebateArgument] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round": self.round_number,
            "proposals": [p.to_dict() for p in self.proposals],
            "critiques": [c.to_dict() for c in self.critiques],
            "rebuttals": [r.to_dict() for r in self.rebuttals],
        }


@dataclass
class DebateResult:
    """Result of a debate."""
    winner_agent: str
    winning_code: str
    winning_reasoning: str
    rounds: List[DebateRound]
    total_cost: float
    total_time: float
    judge_reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "winner": self.winner_agent,
            "code": self.winning_code,
            "reasoning": self.winning_reasoning,
            "rounds": [r.to_dict() for r in self.rounds],
            "cost": self.total_cost,
            "time": self.total_time,
            "judge_reasoning": self.judge_reasoning,
        }


class DebateOrchestrator:
    """
    Orchestrates multi-agent debates for complex problems.

    Flow:
    1. Multiple agents propose solutions
    2. Each agent critiques others' solutions
    3. Agents provide rebuttals
    4. Judge (Opus) selects the winner

    Usage:
        debate = DebateOrchestrator(
            agents={"sonnet": sonnet_client, "gpt4": gpt4_client},
            judge=opus_client,
        )
        result = debate.run(state)
    """

    def __init__(
        self,
        agents: Dict[str, ResilientModelClient],
        judge: ResilientModelClient,
        max_rounds: int = 2,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize debate orchestrator.

        Args:
            agents: Dictionary of agent_id -> model client
            judge: Model client for the judge (typically Opus)
            max_rounds: Maximum debate rounds
            logger: Optional logger
        """
        self.agents = agents
        self.judge = judge
        self.max_rounds = max_rounds
        self.logger = logger or logging.getLogger(__name__)

        self.total_cost = 0.0
        self.total_tokens = 0

    def _log(self, message: str) -> None:
        """Log a message."""
        self.logger.info(f"[DEBATE] {message}")

    def run(self, state: ConductorState) -> DebateResult:
        """
        Run a debate on the given task.

        Args:
            state: Current conductor state with task info

        Returns:
            DebateResult with winner and code
        """
        start_time = time.time()
        self._log(f"Starting debate with {len(self.agents)} agents")

        rounds = []

        for round_num in range(self.max_rounds):
            self._log(f"Round {round_num + 1}/{self.max_rounds}")

            debate_round = DebateRound(round_number=round_num + 1)

            # Phase 1: Proposals (or revisions in later rounds)
            proposals = self._get_proposals(state, rounds, round_num)
            debate_round.proposals = proposals

            # Phase 2: Critiques
            critiques = self._get_critiques(state, proposals)
            debate_round.critiques = critiques

            # Phase 3: Rebuttals
            rebuttals = self._get_rebuttals(state, proposals, critiques)
            debate_round.rebuttals = rebuttals

            rounds.append(debate_round)

        # Final judgment
        result = self._judge_debate(state, rounds)
        result.total_time = time.time() - start_time
        result.total_cost = self.total_cost

        self._log(f"Debate complete. Winner: {result.winner_agent}")

        return result

    def _get_proposals(
        self,
        state: ConductorState,
        previous_rounds: List[DebateRound],
        round_num: int,
    ) -> List[DebateArgument]:
        """Get proposals from all agents."""
        proposals = []

        for agent_id, client in self.agents.items():
            prompt = self._build_proposal_prompt(state, previous_rounds, agent_id, round_num)

            messages = [{"role": "user", "content": prompt}]
            system = self._get_proposer_system_prompt()

            response = client.complete(messages, system=system)
            self.total_cost += response.cost
            self.total_tokens += response.total_tokens

            # Extract code from response
            code = self._extract_code(response.content)

            proposals.append(DebateArgument(
                agent_id=agent_id,
                role=DebateRole.PROPOSER,
                content=response.content,
                code=code,
                round_number=round_num + 1,
            ))

            self._log(f"  {agent_id} proposed ({len(code) if code else 0} chars code)")

        return proposals

    def _get_critiques(
        self,
        state: ConductorState,
        proposals: List[DebateArgument],
    ) -> List[DebateArgument]:
        """Get critiques of each proposal from other agents."""
        critiques = []

        for critic_id, client in self.agents.items():
            # Critique each other agent's proposal
            for proposal in proposals:
                if proposal.agent_id == critic_id:
                    continue  # Don't critique own proposal

                prompt = self._build_critique_prompt(state, proposal)

                messages = [{"role": "user", "content": prompt}]
                system = self._get_critic_system_prompt()

                response = client.complete(messages, system=system)
                self.total_cost += response.cost
                self.total_tokens += response.total_tokens

                critiques.append(DebateArgument(
                    agent_id=critic_id,
                    role=DebateRole.CRITIC,
                    content=response.content,
                    round_number=proposal.round_number,
                ))

                self._log(f"  {critic_id} critiqued {proposal.agent_id}")

        return critiques

    def _get_rebuttals(
        self,
        state: ConductorState,
        proposals: List[DebateArgument],
        critiques: List[DebateArgument],
    ) -> List[DebateArgument]:
        """Get rebuttals from agents responding to critiques."""
        rebuttals = []

        for proposal in proposals:
            agent_id = proposal.agent_id
            client = self.agents[agent_id]

            # Find critiques of this proposal
            agent_critiques = [c for c in critiques if c.agent_id != agent_id]

            if not agent_critiques:
                continue

            prompt = self._build_rebuttal_prompt(state, proposal, agent_critiques)

            messages = [{"role": "user", "content": prompt}]
            system = self._get_rebuttal_system_prompt()

            response = client.complete(messages, system=system)
            self.total_cost += response.cost
            self.total_tokens += response.total_tokens

            # Extract any updated code
            code = self._extract_code(response.content)

            rebuttals.append(DebateArgument(
                agent_id=agent_id,
                role=DebateRole.PROPOSER,
                content=response.content,
                code=code or proposal.code,  # Keep original if no update
                round_number=proposal.round_number,
            ))

            self._log(f"  {agent_id} rebutted")

        return rebuttals

    def _judge_debate(
        self,
        state: ConductorState,
        rounds: List[DebateRound],
    ) -> DebateResult:
        """Have the judge select the winner."""
        prompt = self._build_judge_prompt(state, rounds)

        messages = [{"role": "user", "content": prompt}]
        system = self._get_judge_system_prompt()

        response = self.judge.complete(messages, system=system)
        self.total_cost += response.cost
        self.total_tokens += response.total_tokens

        # Parse judge decision
        winner, reasoning = self._parse_judge_response(response.content)

        # Find winning code
        winning_code = ""
        winning_reasoning = ""

        # Look in final round rebuttals first, then proposals
        final_round = rounds[-1]
        for rebuttal in final_round.rebuttals:
            if rebuttal.agent_id == winner and rebuttal.code:
                winning_code = rebuttal.code
                winning_reasoning = rebuttal.content
                break

        if not winning_code:
            for proposal in final_round.proposals:
                if proposal.agent_id == winner and proposal.code:
                    winning_code = proposal.code
                    winning_reasoning = proposal.content
                    break

        return DebateResult(
            winner_agent=winner,
            winning_code=winning_code,
            winning_reasoning=winning_reasoning,
            rounds=rounds,
            total_cost=0.0,  # Set by caller
            total_time=0.0,  # Set by caller
            judge_reasoning=reasoning,
        )

    def _get_proposer_system_prompt(self) -> str:
        return """You are participating in a multi-agent debate to solve a coding problem.
Your role is PROPOSER - you must provide a solution with code.

Output format:
1. Your approach and reasoning
2. Your code solution in a ```python block
3. Why your solution is correct and handles edge cases

Be thorough but concise. Focus on correctness."""

    def _get_critic_system_prompt(self) -> str:
        return """You are participating in a multi-agent debate to solve a coding problem.
Your role is CRITIC - you must find flaws in another agent's solution.

Be constructive but thorough. Look for:
1. Logical errors
2. Missing edge cases
3. Performance issues
4. Code quality problems

Provide specific, actionable feedback."""

    def _get_rebuttal_system_prompt(self) -> str:
        return """You are responding to critiques of your solution.

Address each criticism directly. If valid:
- Acknowledge the issue
- Provide corrected code in a ```python block

If invalid:
- Explain why the critique is incorrect

Be professional and focused on technical accuracy."""

    def _get_judge_system_prompt(self) -> str:
        return """You are the JUDGE in a multi-agent debate.

Evaluate all proposals and select the best one based on:
1. Correctness - Does it solve the problem?
2. Completeness - Are all edge cases handled?
3. Quality - Is the code clean and efficient?
4. Defense - Did the agent respond well to critiques?

Output your decision as JSON:
{
    "winner": "agent_id",
    "reasoning": "Detailed explanation of why this agent won"
}

Be fair and objective."""

    def _build_proposal_prompt(
        self,
        state: ConductorState,
        previous_rounds: List[DebateRound],
        agent_id: str,
        round_num: int,
    ) -> str:
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

        if round_num > 0 and previous_rounds:
            parts.extend(["", "## PREVIOUS ROUND"])
            last_round = previous_rounds[-1]

            # Show previous proposal
            for p in last_round.proposals:
                if p.agent_id == agent_id:
                    parts.extend([
                        f"Your previous solution:",
                        "```python",
                        p.code or "No code",
                        "```",
                    ])

            # Show critiques received
            parts.append("\nCritiques of your solution:")
            for c in last_round.critiques:
                if c.agent_id != agent_id:
                    parts.append(f"- {c.content[:500]}")

        parts.extend([
            "",
            "Provide your solution with code.",
        ])

        return "\n".join(parts)

    def _build_critique_prompt(
        self,
        state: ConductorState,
        proposal: DebateArgument,
    ) -> str:
        return f"""## TASK
{state.original_task}

## CONSTRAINTS
{chr(10).join('- ' + c for c in state.constraints)}

## SOLUTION TO CRITIQUE (from {proposal.agent_id})

{proposal.content[:2000]}

```python
{proposal.code or 'No code provided'}
```

Critique this solution. Find any issues or weaknesses."""

    def _build_rebuttal_prompt(
        self,
        state: ConductorState,
        proposal: DebateArgument,
        critiques: List[DebateArgument],
    ) -> str:
        critique_text = "\n\n".join([
            f"**Critique from {c.agent_id}:**\n{c.content[:500]}"
            for c in critiques
        ])

        return f"""## YOUR ORIGINAL SOLUTION

{proposal.content[:1000]}

```python
{proposal.code or 'No code'}
```

## CRITIQUES RECEIVED

{critique_text}

Respond to these critiques. If valid, provide corrected code."""

    def _build_judge_prompt(
        self,
        state: ConductorState,
        rounds: List[DebateRound],
    ) -> str:
        parts = [
            "## TASK",
            state.original_task,
            "",
            "## DEBATE SUMMARY",
        ]

        for round_data in rounds:
            parts.append(f"\n### Round {round_data.round_number}")

            parts.append("\n**Proposals:**")
            for p in round_data.proposals:
                parts.extend([
                    f"\n{p.agent_id}:",
                    "```python",
                    (p.code or "No code")[:1000],
                    "```",
                ])

            if round_data.critiques:
                parts.append("\n**Key Critiques:**")
                for c in round_data.critiques[:4]:
                    parts.append(f"- {c.agent_id}: {c.content[:200]}")

            if round_data.rebuttals:
                parts.append("\n**Rebuttals:**")
                for r in round_data.rebuttals:
                    parts.append(f"- {r.agent_id}: {r.content[:200]}")

        parts.extend([
            "",
            "## DECISION",
            "Select the winner and explain your reasoning in JSON format.",
        ])

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

    def _parse_judge_response(self, response: str) -> Tuple[str, str]:
        """Parse judge's response to get winner and reasoning."""
        import json
        import re

        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("winner", "unknown"), data.get("reasoning", response)
        except json.JSONDecodeError:
            pass

        # Fallback: look for agent names in response
        for agent_id in self.agents.keys():
            if agent_id.lower() in response.lower():
                return agent_id, response

        return list(self.agents.keys())[0], response
