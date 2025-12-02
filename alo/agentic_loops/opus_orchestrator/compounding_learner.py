"""
=============================================================================
SCRIPT NAME: compounding_learner.py
=============================================================================

Compounding Learner - Learns from BOTH successes and failures.

Inspired by: https://github.com/EveryInc/compounding-engineering-plugin

Core principle: "Each unit of engineering work should make subsequent
units of work easier."

INPUT FILES:
- Challenge results (success AND failure)
- Current pattern library

OUTPUT FILES:
- Pattern library (successful patterns)
- Anti-pattern library (failure patterns)
- Evolved system prompt with both

VERSION: 1.0
LAST UPDATED: 2025-11-27

DESCRIPTION:
Unlike simple error-based learning, this system:
1. Extracts PATTERNS from successful code (what worked)
2. Extracts ANTI-PATTERNS from failures (what to avoid)
3. Builds a growing CONVENTION LIBRARY
4. Compounds knowledge over time

The key insight: learning only from failures is like studying only
wrong answers. We need to also codify what works.

=============================================================================
"""

import json
import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict

from .multi_provider_client import MultiProviderClient
from .model_registry import get_model
from .code_executor import CodeExecutor


@dataclass
class Pattern:
    """A successful pattern extracted from working code."""
    name: str                    # e.g., "doubly_linked_list_with_sentinels"
    category: str                # e.g., "data_structures", "error_handling"
    description: str             # What this pattern does
    code_template: str           # Example code
    when_to_use: str            # When to apply this pattern
    frequency: int = 1          # How often this pattern succeeded
    challenges_solved: List[str] = field(default_factory=list)


@dataclass
class AntiPattern:
    """A failure pattern to avoid."""
    name: str                    # e.g., "mutable_default_argument"
    category: str                # e.g., "common_bugs", "interface_mismatch"
    description: str             # What went wrong
    bad_example: str            # Code that failed
    fix_guidance: str           # How to avoid
    frequency: int = 1          # How often this caused failure


@dataclass
class Convention:
    """A coding convention derived from patterns."""
    rule: str                    # e.g., "Always use sentinel nodes for linked lists"
    rationale: str              # Why this convention exists
    examples: List[str]         # Code examples
    priority: int = 1           # Higher = more important


@dataclass
class CompoundingState:
    """Full state of the compounding learner."""
    patterns: Dict[str, Pattern] = field(default_factory=dict)
    anti_patterns: Dict[str, AntiPattern] = field(default_factory=dict)
    conventions: List[Convention] = field(default_factory=list)
    challenges_completed: int = 0
    challenges_passed: int = 0
    prompt_version: int = 1
    current_prompt: str = ""


# =============================================================================
# PATTERN EXTRACTION PROMPTS
# =============================================================================

EXTRACT_SUCCESS_PATTERN_PROMPT = '''Analyze this SUCCESSFUL code and extract reusable patterns.

CHALLENGE: {challenge}

WORKING CODE:
```python
{code}
```

Extract patterns that made this code work. Return JSON:
{{
    "patterns": [
        {{
            "name": "short_snake_case_name",
            "category": "data_structures|algorithms|error_handling|interfaces|testing",
            "description": "What this pattern does",
            "code_template": "Minimal code showing the pattern",
            "when_to_use": "When to apply this pattern"
        }}
    ],
    "conventions": [
        {{
            "rule": "A coding rule derived from this success",
            "rationale": "Why this works"
        }}
    ]
}}

Focus on REUSABLE patterns, not task-specific code.
'''

EXTRACT_FAILURE_PATTERN_PROMPT = '''Analyze this FAILED code and extract anti-patterns to avoid.

CHALLENGE: {challenge}

FAILED CODE:
```python
{code}
```

ERROR: {error_type} - {error_message}

Extract anti-patterns that caused this failure. Return JSON:
{{
    "anti_patterns": [
        {{
            "name": "short_snake_case_name",
            "category": "common_bugs|interface_mismatch|edge_cases|logic_errors",
            "description": "What went wrong",
            "bad_example": "Minimal code showing the anti-pattern",
            "fix_guidance": "How to avoid this"
        }}
    ]
}}
'''

BUILD_PROMPT_FROM_KNOWLEDGE = '''Build an optimized system prompt from accumulated knowledge.

SUCCESSFUL PATTERNS ({num_patterns}):
{patterns_text}

ANTI-PATTERNS TO AVOID ({num_anti_patterns}):
{anti_patterns_text}

CONVENTIONS ({num_conventions}):
{conventions_text}

Create a system prompt that:
1. Incorporates the most important patterns as guidance
2. Warns against common anti-patterns
3. Enforces key conventions
4. Stays under 1500 words
5. Is actionable and specific

CRITICAL: The prompt MUST include exactly this placeholder for the task:
{{task_description}}

Use double curly braces for any literal braces in code examples.

Example structure:
```
You are an expert Python engineer...

TASK:
{{task_description}}

[Your patterns and guidance here]

OUTPUT:
Return ONLY the Python code in a ```python block.
```

Return the complete system prompt text.
'''


class CompoundingLearner:
    """
    Learns from both successes and failures to compound knowledge.

    Key difference from PromptEvolver:
    - Extracts patterns from SUCCESSFUL code (not just errors)
    - Builds a pattern library that grows over time
    - Creates conventions from repeated successes
    - Compounds knowledge: each success informs future attempts
    """

    def __init__(
        self,
        client: MultiProviderClient,
        storage_path: str = "compounding_knowledge",
        analyzer_model: str = "opus-4.5"
    ):
        self.client = client
        self.storage_path = storage_path
        self.analyzer_config = get_model(analyzer_model)
        self.executor = CodeExecutor()

        os.makedirs(storage_path, exist_ok=True)

        # Load or initialize state
        self.state = self._load_state()

        # Initialize base prompt if needed
        if not self.state.current_prompt:
            self.state.current_prompt = self._base_prompt()

    def _base_prompt(self) -> str:
        """Base prompt before any learning."""
        return '''You are an expert Python engineer implementing a feature.

TASK:
{task_description}

REQUIREMENTS:
- Write clean, working Python code
- Handle edge cases properly
- Follow the exact interface specified
- No external dependencies (stdlib only)
- Code must be immediately executable

OUTPUT:
Return ONLY the Python code in a ```python block. No explanations.
'''

    def record_success(
        self,
        challenge_id: str,
        challenge_desc: str,
        code: str
    ) -> List[Pattern]:
        """
        Record a successful challenge and extract patterns.

        This is the KEY difference from error-only learning:
        We learn what WORKS, not just what fails.
        """
        self.state.challenges_completed += 1
        self.state.challenges_passed += 1

        # Extract patterns from successful code
        patterns = self._extract_success_patterns(challenge_desc, code)

        for pattern in patterns:
            key = pattern.name
            if key in self.state.patterns:
                # Pattern seen before - increase frequency
                self.state.patterns[key].frequency += 1
                self.state.patterns[key].challenges_solved.append(challenge_id)
            else:
                pattern.challenges_solved = [challenge_id]
                self.state.patterns[key] = pattern

        self._save_state()
        return patterns

    def record_failure(
        self,
        challenge_id: str,
        challenge_desc: str,
        code: str,
        error_type: str,
        error_message: str
    ) -> List[AntiPattern]:
        """Record a failed challenge and extract anti-patterns."""
        self.state.challenges_completed += 1

        # Extract anti-patterns from failed code
        anti_patterns = self._extract_failure_patterns(
            challenge_desc, code, error_type, error_message
        )

        for ap in anti_patterns:
            key = ap.name
            if key in self.state.anti_patterns:
                self.state.anti_patterns[key].frequency += 1
            else:
                self.state.anti_patterns[key] = ap

        self._save_state()
        return anti_patterns

    def _extract_success_patterns(
        self,
        challenge: str,
        code: str
    ) -> List[Pattern]:
        """Extract reusable patterns from successful code."""
        try:
            messages = [{
                "role": "user",
                "content": EXTRACT_SUCCESS_PATTERN_PROMPT.format(
                    challenge=challenge,
                    code=code[:4000]
                )
            }]

            response = self.client.complete(
                model_config=self.analyzer_config,
                messages=messages,
                max_tokens=1500,
                temperature=0.2
            )

            # Parse JSON
            match = re.search(r'\{[\s\S]*\}', response.content)
            if match:
                data = json.loads(match.group())

                patterns = []
                for p in data.get("patterns", []):
                    patterns.append(Pattern(
                        name=p.get("name", "unnamed"),
                        category=p.get("category", "general"),
                        description=p.get("description", ""),
                        code_template=p.get("code_template", ""),
                        when_to_use=p.get("when_to_use", "")
                    ))

                # Also extract conventions
                for c in data.get("conventions", []):
                    self.state.conventions.append(Convention(
                        rule=c.get("rule", ""),
                        rationale=c.get("rationale", ""),
                        examples=[code[:500]]
                    ))

                return patterns

        except Exception as e:
            print(f"  Pattern extraction failed: {e}")

        return []

    def _extract_failure_patterns(
        self,
        challenge: str,
        code: str,
        error_type: str,
        error_message: str
    ) -> List[AntiPattern]:
        """Extract anti-patterns from failed code."""
        try:
            messages = [{
                "role": "user",
                "content": EXTRACT_FAILURE_PATTERN_PROMPT.format(
                    challenge=challenge,
                    code=code[:4000],
                    error_type=error_type,
                    error_message=error_message
                )
            }]

            response = self.client.complete(
                model_config=self.analyzer_config,
                messages=messages,
                max_tokens=1000,
                temperature=0
            )

            match = re.search(r'\{[\s\S]*\}', response.content)
            if match:
                data = json.loads(match.group())

                anti_patterns = []
                for ap in data.get("anti_patterns", []):
                    anti_patterns.append(AntiPattern(
                        name=ap.get("name", "unnamed"),
                        category=ap.get("category", "general"),
                        description=ap.get("description", ""),
                        bad_example=ap.get("bad_example", ""),
                        fix_guidance=ap.get("fix_guidance", "")
                    ))
                return anti_patterns

        except Exception as e:
            print(f"  Anti-pattern extraction failed: {e}")

        return []

    def rebuild_prompt(self, min_patterns: int = 3) -> bool:
        """
        Rebuild the system prompt from accumulated knowledge.

        This is where compounding happens: successful patterns
        get encoded into the prompt for future use.
        """
        total_patterns = len(self.state.patterns)
        total_anti = len(self.state.anti_patterns)

        if total_patterns < min_patterns:
            print(f"  Not enough patterns ({total_patterns}/{min_patterns})")
            return False

        # Format patterns (sorted by frequency)
        sorted_patterns = sorted(
            self.state.patterns.values(),
            key=lambda x: x.frequency,
            reverse=True
        )[:10]  # Top 10

        patterns_text = "\n\n".join([
            f"PATTERN: {p.name} (used {p.frequency}x)\n"
            f"Category: {p.category}\n"
            f"Description: {p.description}\n"
            f"When to use: {p.when_to_use}\n"
            f"Template:\n```python\n{p.code_template}\n```"
            for p in sorted_patterns
        ])

        # Format anti-patterns
        sorted_anti = sorted(
            self.state.anti_patterns.values(),
            key=lambda x: x.frequency,
            reverse=True
        )[:5]  # Top 5

        anti_text = "\n\n".join([
            f"AVOID: {ap.name} (caused {ap.frequency} failures)\n"
            f"Problem: {ap.description}\n"
            f"Fix: {ap.fix_guidance}"
            for ap in sorted_anti
        ])

        # Format conventions
        conventions_text = "\n".join([
            f"- {c.rule}"
            for c in self.state.conventions[:10]
        ])

        try:
            messages = [{
                "role": "user",
                "content": BUILD_PROMPT_FROM_KNOWLEDGE.format(
                    num_patterns=len(sorted_patterns),
                    patterns_text=patterns_text or "None yet",
                    num_anti_patterns=len(sorted_anti),
                    anti_patterns_text=anti_text or "None yet",
                    num_conventions=len(self.state.conventions),
                    conventions_text=conventions_text or "None yet"
                )
            }]

            response = self.client.complete(
                model_config=self.analyzer_config,
                messages=messages,
                max_tokens=2000,
                temperature=0.3
            )

            new_prompt = response.content.strip()

            # Validate the prompt has the required placeholder
            if "{task_description}" not in new_prompt:
                print("  WARNING: Generated prompt missing {task_description}, adding it")
                new_prompt = new_prompt + "\n\nTASK:\n{task_description}\n"

            self.state.current_prompt = new_prompt
            self.state.prompt_version += 1

            # Save the new prompt
            prompt_path = os.path.join(
                self.storage_path,
                f"prompt_v{self.state.prompt_version}.txt"
            )
            with open(prompt_path, 'w') as f:
                f.write(self.state.current_prompt)

            print(f"  Rebuilt prompt v{self.state.prompt_version}")
            print(f"  Incorporated: {len(sorted_patterns)} patterns, "
                  f"{len(sorted_anti)} anti-patterns, "
                  f"{len(self.state.conventions)} conventions")

            self._save_state()
            return True

        except Exception as e:
            print(f"  Prompt rebuild failed: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get learning statistics."""
        success_rate = (
            self.state.challenges_passed / self.state.challenges_completed
            if self.state.challenges_completed > 0 else 0
        )

        return {
            "challenges_completed": self.state.challenges_completed,
            "challenges_passed": self.state.challenges_passed,
            "success_rate": f"{success_rate:.1%}",
            "patterns_learned": len(self.state.patterns),
            "anti_patterns_learned": len(self.state.anti_patterns),
            "conventions_established": len(self.state.conventions),
            "prompt_version": self.state.prompt_version,
            "top_patterns": [
                {"name": p.name, "frequency": p.frequency}
                for p in sorted(
                    self.state.patterns.values(),
                    key=lambda x: x.frequency,
                    reverse=True
                )[:5]
            ],
            "top_anti_patterns": [
                {"name": ap.name, "frequency": ap.frequency}
                for ap in sorted(
                    self.state.anti_patterns.values(),
                    key=lambda x: x.frequency,
                    reverse=True
                )[:5]
            ]
        }

    def _save_state(self):
        """Save state to disk."""
        state_dict = {
            "patterns": {k: asdict(v) for k, v in self.state.patterns.items()},
            "anti_patterns": {k: asdict(v) for k, v in self.state.anti_patterns.items()},
            "conventions": [asdict(c) for c in self.state.conventions],
            "challenges_completed": self.state.challenges_completed,
            "challenges_passed": self.state.challenges_passed,
            "prompt_version": self.state.prompt_version,
            "current_prompt": self.state.current_prompt,
        }

        state_path = os.path.join(self.storage_path, "compounding_state.json")
        with open(state_path, 'w') as f:
            json.dump(state_dict, f, indent=2)

    def _load_state(self) -> CompoundingState:
        """Load state from disk."""
        state_path = os.path.join(self.storage_path, "compounding_state.json")

        if os.path.exists(state_path):
            try:
                with open(state_path, 'r') as f:
                    data = json.load(f)

                state = CompoundingState()
                state.patterns = {
                    k: Pattern(**v) for k, v in data.get("patterns", {}).items()
                }
                state.anti_patterns = {
                    k: AntiPattern(**v) for k, v in data.get("anti_patterns", {}).items()
                }
                state.conventions = [
                    Convention(**c) for c in data.get("conventions", [])
                ]
                state.challenges_completed = data.get("challenges_completed", 0)
                state.challenges_passed = data.get("challenges_passed", 0)
                state.prompt_version = data.get("prompt_version", 1)
                state.current_prompt = data.get("current_prompt", "")

                return state

            except Exception as e:
                print(f"  Failed to load state: {e}")

        return CompoundingState()
