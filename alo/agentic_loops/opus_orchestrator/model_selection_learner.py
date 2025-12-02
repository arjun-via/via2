"""
=============================================================================
SCRIPT NAME: model_selection_learner.py
=============================================================================

Model Selection Learner - Learns which LLMs excel at different task types.

Core principle: Different models have different strengths. Learn from experience
which model to route each task to based on:
- Task type (data_structures, algorithms, error_handling, etc.)
- Context size (small, medium, large)
- Difficulty level (easy, medium, hard)

This compounds with prompt learning - we learn BOTH:
1. What patterns work (CompoundingLearner)
2. Which model to use (ModelSelectionLearner)

VERSION: 1.0
LAST UPDATED: 2025-11-27

=============================================================================
"""

import json
import os
import re
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from .multi_provider_client import MultiProviderClient
from .model_registry import get_model, MODEL_REGISTRY
from .code_executor import CodeExecutor


@dataclass
class TaskProfile:
    """Profile of a task for model selection."""
    task_type: str          # data_structures, algorithms, error_handling, etc.
    context_size: str       # small (<500 chars), medium (500-2000), large (>2000)
    difficulty: str         # easy, medium, hard
    estimated_complexity: int  # 1-10 scale


@dataclass
class ModelPerformance:
    """Performance record for a model on a specific task profile."""
    model_id: str
    task_type: str
    context_size: str
    difficulty: str
    attempts: int = 0
    successes: int = 0
    total_time: float = 0.0
    total_cost: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts > 0 else 0.0

    @property
    def avg_time(self) -> float:
        return self.total_time / self.attempts if self.attempts > 0 else 0.0

    @property
    def avg_cost(self) -> float:
        return self.total_cost / self.attempts if self.attempts > 0 else 0.0


@dataclass
class ModelSelectionState:
    """Full state of the model selection learner."""
    # Performance matrix: {model_id: {task_type: {context_size: {difficulty: ModelPerformance}}}}
    performance_data: Dict = field(default_factory=dict)

    # Routing rules learned from data
    routing_rules: Dict[str, str] = field(default_factory=dict)  # {profile_key: best_model}

    # Total statistics
    total_tasks: int = 0
    total_successes: int = 0

    # Models we've tested
    models_tested: List[str] = field(default_factory=list)


# Task classification prompt
CLASSIFY_TASK_PROMPT = '''Classify this programming task.

TASK:
{task_description}

Return JSON with:
{{
    "task_type": "data_structures|algorithms|error_handling|string_processing|math|concurrency|io_operations|testing",
    "difficulty": "easy|medium|hard",
    "estimated_complexity": 1-10,
    "reasoning": "brief explanation"
}}

Classification guidelines:
- data_structures: Lists, trees, graphs, hash maps, linked lists, stacks, queues
- algorithms: Sorting, searching, dynamic programming, recursion, optimization
- error_handling: Exception handling, validation, edge cases, defensive coding
- string_processing: Parsing, formatting, regex, text manipulation
- math: Numerical computation, statistics, geometry, number theory
- concurrency: Threading, async, locks, synchronization
- io_operations: File handling, network, serialization
- testing: Unit tests, mocking, test fixtures

Difficulty:
- easy: Single function, straightforward logic, <50 lines expected
- medium: Multiple functions/classes, moderate complexity, 50-200 lines
- hard: Complex algorithms, multiple interacting components, >200 lines
'''


class ModelSelectionLearner:
    """
    Learns which LLM to use for different types of tasks.

    Key insight: Models have different strengths:
    - Some excel at data structures
    - Some are better at complex algorithms
    - Some handle large contexts better
    - Some are faster but less accurate

    This system learns these patterns from experience.
    """

    def __init__(
        self,
        client: MultiProviderClient,
        storage_path: str = "model_selection_knowledge",
        classifier_model: str = "sonnet-4.5",  # Fast for classification
        candidate_models: List[str] = None
    ):
        self.client = client
        self.storage_path = storage_path
        self.classifier_config = get_model(classifier_model)
        self.executor = CodeExecutor(timeout=30)

        # Default candidate models to test (must match MODEL_REGISTRY)
        self.candidate_models = candidate_models or [
            "qwen3-235b",       # Large, powerful (Cerebras)
            "glm-4.6",          # Fast (Cerebras)
            "gemini-3-pro",     # Latest Gemini, large context (Google via OpenRouter)
            "sonnet-4.5",       # High quality (Anthropic via OpenRouter)
        ]

        os.makedirs(storage_path, exist_ok=True)
        self.state = self._load_state()

    def classify_task(self, task_description: str) -> TaskProfile:
        """Classify a task to determine its profile."""
        # Determine context size
        desc_len = len(task_description)
        if desc_len < 500:
            context_size = "small"
        elif desc_len < 2000:
            context_size = "medium"
        else:
            context_size = "large"

        try:
            messages = [{
                "role": "user",
                "content": CLASSIFY_TASK_PROMPT.format(task_description=task_description[:3000])
            }]

            response = self.client.complete(
                model_config=self.classifier_config,
                messages=messages,
                max_tokens=500,
                temperature=0
            )

            # Parse JSON response
            match = re.search(r'\{[\s\S]*\}', response.content)
            if match:
                data = json.loads(match.group())
                return TaskProfile(
                    task_type=data.get("task_type", "algorithms"),
                    context_size=context_size,
                    difficulty=data.get("difficulty", "medium"),
                    estimated_complexity=data.get("estimated_complexity", 5)
                )
        except Exception as e:
            print(f"  Classification failed: {e}")

        # Default profile
        return TaskProfile(
            task_type="algorithms",
            context_size=context_size,
            difficulty="medium",
            estimated_complexity=5
        )

    def get_profile_key(self, profile: TaskProfile) -> str:
        """Generate a unique key for a task profile."""
        return f"{profile.task_type}:{profile.context_size}:{profile.difficulty}"

    def select_model(self, task_description: str) -> Tuple[str, TaskProfile]:
        """
        Select the best model for a task based on learned performance.

        Returns (model_id, task_profile)
        """
        profile = self.classify_task(task_description)
        profile_key = self.get_profile_key(profile)

        # Check if we have a learned routing rule
        if profile_key in self.state.routing_rules:
            best_model = self.state.routing_rules[profile_key]
            print(f"  Routing to learned best: {best_model} for {profile_key}")
            return best_model, profile

        # Find best model from performance data
        best_model = None
        best_score = -1

        for model_id in self.candidate_models:
            perf = self._get_performance(model_id, profile)
            if perf and perf.attempts >= 3:  # Need minimum data
                # Score = success_rate * 100 - avg_time (reward accuracy, penalize slowness)
                score = perf.success_rate * 100 - perf.avg_time * 0.1
                if score > best_score:
                    best_score = score
                    best_model = model_id

        if best_model:
            print(f"  Selected {best_model} (score: {best_score:.1f}) for {profile_key}")
            return best_model, profile

        # No data yet - use default based on task type heuristics
        default = self._get_heuristic_model(profile)
        print(f"  Using heuristic default: {default} for {profile_key}")
        return default, profile

    def _get_heuristic_model(self, profile: TaskProfile) -> str:
        """Get default model based on heuristics when no learned data."""
        # Heuristics based on general model strengths
        if profile.difficulty == "hard":
            return "qwen3-235b"  # Use most powerful for hard tasks
        elif profile.context_size == "large":
            return "gemini-2.5-pro"  # Good at large context
        elif profile.task_type in ["data_structures", "algorithms"]:
            return "sonnet-4.5"  # Good at structured problems
        else:
            return "glm-4.6"  # Fast general purpose

    def record_result(
        self,
        model_id: str,
        profile: TaskProfile,
        success: bool,
        execution_time: float,
        cost: float
    ):
        """Record the result of a model on a task."""
        self.state.total_tasks += 1
        if success:
            self.state.total_successes += 1

        if model_id not in self.state.models_tested:
            self.state.models_tested.append(model_id)

        # Update performance data directly in dict (not via dataclass copy)
        self._ensure_performance_entry(model_id, profile)
        data = self.state.performance_data[model_id][profile.task_type][profile.context_size][profile.difficulty]
        data["attempts"] += 1
        if success:
            data["successes"] += 1
        data["total_time"] += execution_time
        data["total_cost"] += cost

        # Update routing rules if we have enough data
        self._update_routing_rules(profile)

        self._save_state()

    def _get_performance(self, model_id: str, profile: TaskProfile) -> Optional[ModelPerformance]:
        """Get performance record for a model/profile combination."""
        try:
            return ModelPerformance(**self.state.performance_data
                .get(model_id, {})
                .get(profile.task_type, {})
                .get(profile.context_size, {})
                .get(profile.difficulty, {}))
        except:
            return None

    def _ensure_performance_entry(self, model_id: str, profile: TaskProfile):
        """Ensure performance entry exists in state dict."""
        if model_id not in self.state.performance_data:
            self.state.performance_data[model_id] = {}
        if profile.task_type not in self.state.performance_data[model_id]:
            self.state.performance_data[model_id][profile.task_type] = {}
        if profile.context_size not in self.state.performance_data[model_id][profile.task_type]:
            self.state.performance_data[model_id][profile.task_type][profile.context_size] = {}
        if profile.difficulty not in self.state.performance_data[model_id][profile.task_type][profile.context_size]:
            self.state.performance_data[model_id][profile.task_type][profile.context_size][profile.difficulty] = {
                "model_id": model_id,
                "task_type": profile.task_type,
                "context_size": profile.context_size,
                "difficulty": profile.difficulty,
                "attempts": 0,
                "successes": 0,
                "total_time": 0.0,
                "total_cost": 0.0
            }

    def _update_routing_rules(self, profile: TaskProfile):
        """Update routing rules based on accumulated data."""
        profile_key = self.get_profile_key(profile)

        best_model = None
        best_success_rate = 0
        min_attempts = 5  # Need at least 5 attempts to make a routing decision

        for model_id in self.candidate_models:
            perf = self._get_performance(model_id, profile)
            if perf and perf.attempts >= min_attempts:
                if perf.success_rate > best_success_rate:
                    best_success_rate = perf.success_rate
                    best_model = model_id

        if best_model and best_success_rate > 0.7:  # Only route if >70% success
            self.state.routing_rules[profile_key] = best_model

    def get_stats(self) -> Dict:
        """Get learning statistics."""
        overall_rate = (
            self.state.total_successes / self.state.total_tasks
            if self.state.total_tasks > 0 else 0
        )

        # Build model performance summary
        model_stats = {}
        for model_id in self.state.models_tested:
            model_data = self.state.performance_data.get(model_id, {})
            total_attempts = 0
            total_successes = 0

            for task_type in model_data.values():
                for context_size in task_type.values():
                    for difficulty in context_size.values():
                        total_attempts += difficulty.get("attempts", 0)
                        total_successes += difficulty.get("successes", 0)

            if total_attempts > 0:
                model_stats[model_id] = {
                    "attempts": total_attempts,
                    "successes": total_successes,
                    "success_rate": f"{total_successes/total_attempts:.1%}"
                }

        return {
            "total_tasks": self.state.total_tasks,
            "total_successes": self.state.total_successes,
            "overall_success_rate": f"{overall_rate:.1%}",
            "models_tested": len(self.state.models_tested),
            "routing_rules_learned": len(self.state.routing_rules),
            "model_performance": model_stats,
            "routing_rules": self.state.routing_rules
        }

    def get_best_model_for_type(self, task_type: str) -> Optional[str]:
        """Get the best model for a specific task type across all contexts/difficulties."""
        best_model = None
        best_rate = 0

        for model_id, model_data in self.state.performance_data.items():
            if task_type in model_data:
                total_attempts = 0
                total_successes = 0
                for context_size in model_data[task_type].values():
                    for difficulty in context_size.values():
                        total_attempts += difficulty.get("attempts", 0)
                        total_successes += difficulty.get("successes", 0)

                if total_attempts >= 3:
                    rate = total_successes / total_attempts
                    if rate > best_rate:
                        best_rate = rate
                        best_model = model_id

        return best_model

    def print_performance_matrix(self):
        """Print a human-readable performance matrix."""
        print("\n" + "="*70)
        print("MODEL PERFORMANCE MATRIX")
        print("="*70)

        task_types = set()
        for model_data in self.state.performance_data.values():
            task_types.update(model_data.keys())

        for task_type in sorted(task_types):
            print(f"\n{task_type.upper()}:")
            print("-" * 50)

            for model_id in self.state.models_tested:
                model_data = self.state.performance_data.get(model_id, {})
                if task_type in model_data:
                    total_attempts = 0
                    total_successes = 0
                    for context_size in model_data[task_type].values():
                        for difficulty in context_size.values():
                            total_attempts += difficulty.get("attempts", 0)
                            total_successes += difficulty.get("successes", 0)

                    if total_attempts > 0:
                        rate = total_successes / total_attempts * 100
                        print(f"  {model_id:20} {total_successes:3}/{total_attempts:3} ({rate:5.1f}%)")

        print("\n" + "="*70)
        print("LEARNED ROUTING RULES")
        print("="*70)
        for profile_key, model_id in self.state.routing_rules.items():
            print(f"  {profile_key:40} -> {model_id}")

    def _save_state(self):
        """Save state to disk."""
        state_dict = {
            "performance_data": self.state.performance_data,
            "routing_rules": self.state.routing_rules,
            "total_tasks": self.state.total_tasks,
            "total_successes": self.state.total_successes,
            "models_tested": self.state.models_tested,
        }

        state_path = os.path.join(self.storage_path, "model_selection_state.json")
        with open(state_path, 'w') as f:
            json.dump(state_dict, f, indent=2)

    def _load_state(self) -> ModelSelectionState:
        """Load state from disk."""
        state_path = os.path.join(self.storage_path, "model_selection_state.json")

        if os.path.exists(state_path):
            try:
                with open(state_path, 'r') as f:
                    data = json.load(f)

                state = ModelSelectionState()
                state.performance_data = data.get("performance_data", {})
                state.routing_rules = data.get("routing_rules", {})
                state.total_tasks = data.get("total_tasks", 0)
                state.total_successes = data.get("total_successes", 0)
                state.models_tested = data.get("models_tested", [])

                return state
            except Exception as e:
                print(f"  Failed to load model selection state: {e}")

        return ModelSelectionState()
