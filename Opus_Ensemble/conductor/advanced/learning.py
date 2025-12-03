"""
=============================================================================
SCRIPT NAME: learning.py
=============================================================================

Opus-Conductor Learning Module

Adaptive learning components that improve over time:
1. Prompt Evolution - Evolve prompts based on success/failure
2. Model Selection - Learn which models work best for which tasks
3. Compounding Knowledge - Build knowledge base from successes

VERSION: 1.0
LAST UPDATED: 2025-12-03
=============================================================================
"""

import time
import json
import logging
import random
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from enum import Enum

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from conductor.state import ConductorState, TaskArchetype, Complexity


@dataclass
class PromptVariant:
    """A prompt variant with performance metrics."""
    id: str
    template: str
    success_count: int = 0
    failure_count: int = 0
    avg_score: float = 0.0
    total_uses: int = 0
    created_at: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptVariant":
        return cls(**data)


@dataclass
class ModelPerformance:
    """Performance data for a model on specific task types."""
    model_id: str
    task_archetype: str
    complexity: str
    success_count: int = 0
    failure_count: int = 0
    avg_cost: float = 0.0
    avg_time: float = 0.0
    total_uses: int = 0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    @property
    def efficiency_score(self) -> float:
        """Score combining success rate and cost efficiency."""
        if self.total_uses == 0:
            return 0.0
        # Higher is better: high success, low cost
        cost_factor = 1.0 / (1.0 + self.avg_cost * 10)  # Normalize cost
        return self.success_rate * 0.7 + cost_factor * 0.3

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelPerformance":
        return cls(**data)


class PromptEvolver:
    """
    Evolves prompts over time based on success/failure feedback.

    Techniques:
    - Mutation: Small random changes to successful prompts
    - Crossover: Combine parts of successful prompts
    - Selection: Keep best performers, prune worst
    """

    def __init__(
        self,
        base_prompt: str,
        storage_path: Optional[Path] = None,
        population_size: int = 10,
        mutation_rate: float = 0.1,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize prompt evolver.

        Args:
            base_prompt: Initial prompt template
            storage_path: Path to persist variants
            population_size: Number of variants to maintain
            mutation_rate: Probability of mutations
            logger: Optional logger
        """
        self.storage_path = storage_path
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.logger = logger or logging.getLogger(__name__)

        # Initialize population
        self.variants: List[PromptVariant] = []
        self._load_or_init(base_prompt)

    def _log(self, message: str) -> None:
        self.logger.info(f"[PROMPT_EVOLVER] {message}")

    def _load_or_init(self, base_prompt: str) -> None:
        """Load existing variants or initialize with base."""
        if self.storage_path and self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                self.variants = [PromptVariant.from_dict(v) for v in data]
                self._log(f"Loaded {len(self.variants)} variants")
                return
            except Exception as e:
                self._log(f"Error loading variants: {e}")

        # Initialize with base prompt
        self.variants = [PromptVariant(id="base", template=base_prompt)]
        self._log("Initialized with base prompt")

    def save(self) -> None:
        """Save variants to storage."""
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = [v.to_dict() for v in self.variants]
            self.storage_path.write_text(json.dumps(data, indent=2))

    def get_prompt(self, exploit: float = 0.7) -> PromptVariant:
        """
        Get a prompt variant to use.

        Args:
            exploit: Probability of using best variant vs exploring

        Returns:
            Selected PromptVariant
        """
        if not self.variants:
            raise ValueError("No prompt variants available")

        if random.random() < exploit:
            # Exploit: use best performer
            best = max(self.variants, key=lambda v: v.success_rate)
            return best
        else:
            # Explore: weighted random selection
            weights = [max(0.1, v.success_rate + 0.1) for v in self.variants]
            return random.choices(self.variants, weights=weights, k=1)[0]

    def record_outcome(
        self,
        variant: PromptVariant,
        success: bool,
        score: float = 0.0,
    ) -> None:
        """
        Record the outcome of using a prompt variant.

        Args:
            variant: The variant that was used
            success: Whether it succeeded
            score: Optional quality score (0-1)
        """
        variant.total_uses += 1
        if success:
            variant.success_count += 1
        else:
            variant.failure_count += 1

        # Update running average score
        if score > 0:
            n = variant.total_uses
            variant.avg_score = ((n - 1) * variant.avg_score + score) / n

        self._maybe_evolve()
        self.save()

    def _maybe_evolve(self) -> None:
        """Potentially evolve the population."""
        # Only evolve after enough data
        total_uses = sum(v.total_uses for v in self.variants)
        if total_uses < 10:
            return

        # Check if we need new variants
        if len(self.variants) < self.population_size:
            self._generate_variants()

        # Prune worst performers
        self._prune_variants()

    def _generate_variants(self) -> None:
        """Generate new variants through mutation/crossover."""
        # Get top performers
        sorted_variants = sorted(self.variants, key=lambda v: v.success_rate, reverse=True)
        top_variants = sorted_variants[:3]

        new_count = self.population_size - len(self.variants)

        for i in range(new_count):
            if random.random() < 0.5 and len(top_variants) >= 2:
                # Crossover
                parent1, parent2 = random.sample(top_variants, 2)
                child = self._crossover(parent1, parent2)
            else:
                # Mutation
                parent = random.choice(top_variants)
                child = self._mutate(parent)

            child.id = f"gen_{len(self.variants)}_{i}"
            self.variants.append(child)

        self._log(f"Generated {new_count} new variants")

    def _mutate(self, parent: PromptVariant) -> PromptVariant:
        """Create a mutated version of a prompt."""
        template = parent.template

        # Simple mutations: add emphasis, reorder, add instructions
        mutations = [
            lambda t: t.replace(".", ". IMPORTANT:"),
            lambda t: t + "\n\nBe thorough and careful.",
            lambda t: t + "\n\nHandle all edge cases.",
            lambda t: "CRITICAL TASK:\n\n" + t,
            lambda t: t.replace("must", "MUST"),
        ]

        if random.random() < self.mutation_rate:
            mutation = random.choice(mutations)
            template = mutation(template)

        return PromptVariant(id="", template=template)

    def _crossover(self, p1: PromptVariant, p2: PromptVariant) -> PromptVariant:
        """Combine two prompts."""
        # Split at sentence boundaries and combine
        sentences1 = p1.template.split('. ')
        sentences2 = p2.template.split('. ')

        # Take first half from p1, second half from p2
        mid = len(sentences1) // 2
        combined = sentences1[:mid] + sentences2[mid:]

        return PromptVariant(id="", template='. '.join(combined))

    def _prune_variants(self) -> None:
        """Remove poorly performing variants."""
        if len(self.variants) <= 3:
            return

        # Only prune variants with enough uses
        prunable = [v for v in self.variants if v.total_uses >= 5]
        if len(prunable) <= 3:
            return

        # Remove worst performer
        worst = min(prunable, key=lambda v: v.success_rate)
        if worst.success_rate < 0.3:  # Only prune if really bad
            self.variants.remove(worst)
            self._log(f"Pruned variant {worst.id} (rate={worst.success_rate:.2f})")


class ModelSelector:
    """
    Learns which models work best for which task types.

    Uses Thompson Sampling for exploration/exploitation balance.
    """

    def __init__(
        self,
        available_models: List[str],
        storage_path: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize model selector.

        Args:
            available_models: List of model IDs to choose from
            storage_path: Path to persist performance data
            logger: Optional logger
        """
        self.available_models = available_models
        self.storage_path = storage_path
        self.logger = logger or logging.getLogger(__name__)

        # Performance data: (archetype, complexity) -> {model_id: ModelPerformance}
        self.performance: Dict[Tuple[str, str], Dict[str, ModelPerformance]] = {}
        self._load()

    def _log(self, message: str) -> None:
        self.logger.info(f"[MODEL_SELECTOR] {message}")

    def _load(self) -> None:
        """Load performance data from storage."""
        if self.storage_path and self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                for key_str, model_data in data.items():
                    archetype, complexity = key_str.split("|")
                    key = (archetype, complexity)
                    self.performance[key] = {
                        model_id: ModelPerformance.from_dict(perf)
                        for model_id, perf in model_data.items()
                    }
                self._log(f"Loaded performance data for {len(self.performance)} task types")
            except Exception as e:
                self._log(f"Error loading performance data: {e}")

    def save(self) -> None:
        """Save performance data to storage."""
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for (archetype, complexity), model_data in self.performance.items():
                key_str = f"{archetype}|{complexity}"
                data[key_str] = {
                    model_id: perf.to_dict()
                    for model_id, perf in model_data.items()
                }
            self.storage_path.write_text(json.dumps(data, indent=2))

    def select_model(
        self,
        archetype: TaskArchetype,
        complexity: Complexity,
        explore: float = 0.2,
    ) -> str:
        """
        Select the best model for a task type.

        Args:
            archetype: Task archetype
            complexity: Task complexity
            explore: Exploration probability

        Returns:
            Selected model ID
        """
        key = (archetype.value, complexity.value)

        # Get performance data for this task type
        task_perf = self.performance.get(key, {})

        # Explore: random selection
        if random.random() < explore or not task_perf:
            selected = random.choice(self.available_models)
            self._log(f"Exploring: selected {selected}")
            return selected

        # Exploit: Thompson Sampling
        samples = {}
        for model_id in self.available_models:
            perf = task_perf.get(model_id)
            if perf and perf.total_uses > 0:
                # Beta distribution sampling
                alpha = perf.success_count + 1
                beta = perf.failure_count + 1
                samples[model_id] = random.betavariate(alpha, beta)
            else:
                # Prior: uniform
                samples[model_id] = random.betavariate(1, 1)

        selected = max(samples, key=samples.get)
        self._log(f"Selected {selected} for {archetype.value}/{complexity.value}")
        return selected

    def record_outcome(
        self,
        model_id: str,
        archetype: TaskArchetype,
        complexity: Complexity,
        success: bool,
        cost: float = 0.0,
        time_taken: float = 0.0,
    ) -> None:
        """
        Record the outcome of using a model.

        Args:
            model_id: Model that was used
            archetype: Task archetype
            complexity: Task complexity
            success: Whether it succeeded
            cost: API cost
            time_taken: Time in seconds
        """
        key = (archetype.value, complexity.value)

        if key not in self.performance:
            self.performance[key] = {}

        if model_id not in self.performance[key]:
            self.performance[key][model_id] = ModelPerformance(
                model_id=model_id,
                task_archetype=archetype.value,
                complexity=complexity.value,
            )

        perf = self.performance[key][model_id]
        perf.total_uses += 1
        if success:
            perf.success_count += 1
        else:
            perf.failure_count += 1

        # Update running averages
        n = perf.total_uses
        perf.avg_cost = ((n - 1) * perf.avg_cost + cost) / n
        perf.avg_time = ((n - 1) * perf.avg_time + time_taken) / n

        self.save()

    def get_recommendations(self, archetype: TaskArchetype, complexity: Complexity) -> List[Dict]:
        """Get model recommendations with confidence levels."""
        key = (archetype.value, complexity.value)
        task_perf = self.performance.get(key, {})

        recommendations = []
        for model_id in self.available_models:
            perf = task_perf.get(model_id)
            if perf:
                recommendations.append({
                    "model_id": model_id,
                    "success_rate": perf.success_rate,
                    "efficiency_score": perf.efficiency_score,
                    "total_uses": perf.total_uses,
                    "avg_cost": perf.avg_cost,
                    "confidence": min(1.0, perf.total_uses / 20),  # Max confidence at 20 uses
                })
            else:
                recommendations.append({
                    "model_id": model_id,
                    "success_rate": 0.5,  # Prior
                    "efficiency_score": 0.5,
                    "total_uses": 0,
                    "avg_cost": 0.0,
                    "confidence": 0.0,
                })

        # Sort by efficiency score
        recommendations.sort(key=lambda x: x["efficiency_score"], reverse=True)
        return recommendations


@dataclass
class KnowledgeEntry:
    """An entry in the compounding knowledge base."""
    task_pattern: str
    solution_pattern: str
    edge_cases: List[str]
    success_count: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeEntry":
        return cls(**data)


class LearningModule:
    """
    Unified learning module combining all learning components.

    Provides a simple interface for the conductor to:
    - Get optimized prompts
    - Select best models
    - Access compounding knowledge
    """

    def __init__(
        self,
        models: List[str],
        base_prompts: Dict[str, str],
        storage_dir: Optional[Path] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize learning module.

        Args:
            models: Available model IDs
            base_prompts: Base prompts by stage name
            storage_dir: Directory for persistent storage
            logger: Optional logger
        """
        self.logger = logger or logging.getLogger(__name__)
        storage_dir = storage_dir or Path("data/learning")

        # Initialize components
        self.model_selector = ModelSelector(
            available_models=models,
            storage_path=storage_dir / "model_performance.json",
            logger=logger,
        )

        self.prompt_evolvers: Dict[str, PromptEvolver] = {}
        for stage, prompt in base_prompts.items():
            self.prompt_evolvers[stage] = PromptEvolver(
                base_prompt=prompt,
                storage_path=storage_dir / f"prompts_{stage}.json",
                logger=logger,
            )

        # Knowledge base
        self.knowledge_path = storage_dir / "knowledge_base.json"
        self.knowledge: List[KnowledgeEntry] = self._load_knowledge()

    def _load_knowledge(self) -> List[KnowledgeEntry]:
        """Load knowledge base from storage."""
        if self.knowledge_path.exists():
            try:
                data = json.loads(self.knowledge_path.read_text())
                return [KnowledgeEntry.from_dict(e) for e in data]
            except Exception:
                pass
        return []

    def _save_knowledge(self) -> None:
        """Save knowledge base to storage."""
        self.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.to_dict() for e in self.knowledge]
        self.knowledge_path.write_text(json.dumps(data, indent=2))

    def get_prompt(self, stage: str) -> str:
        """Get the best prompt for a stage."""
        if stage in self.prompt_evolvers:
            variant = self.prompt_evolvers[stage].get_prompt()
            return variant.template
        return ""

    def get_model(self, state: ConductorState) -> str:
        """Get the best model for current task."""
        return self.model_selector.select_model(
            archetype=state.task_archetype,
            complexity=state.complexity,
        )

    def record_success(
        self,
        state: ConductorState,
        stage: str,
        model_id: str,
        cost: float = 0.0,
        time_taken: float = 0.0,
    ) -> None:
        """Record a successful outcome."""
        # Update model selector
        self.model_selector.record_outcome(
            model_id=model_id,
            archetype=state.task_archetype,
            complexity=state.complexity,
            success=True,
            cost=cost,
            time_taken=time_taken,
        )

        # Update prompt evolver
        if stage in self.prompt_evolvers:
            variant = self.prompt_evolvers[stage].get_prompt(exploit=1.0)
            self.prompt_evolvers[stage].record_outcome(variant, success=True)

        # Add to knowledge base
        self._add_knowledge(state)

    def record_failure(
        self,
        state: ConductorState,
        stage: str,
        model_id: str,
        cost: float = 0.0,
        time_taken: float = 0.0,
    ) -> None:
        """Record a failed outcome."""
        self.model_selector.record_outcome(
            model_id=model_id,
            archetype=state.task_archetype,
            complexity=state.complexity,
            success=False,
            cost=cost,
            time_taken=time_taken,
        )

        if stage in self.prompt_evolvers:
            variant = self.prompt_evolvers[stage].get_prompt(exploit=1.0)
            self.prompt_evolvers[stage].record_outcome(variant, success=False)

    def _add_knowledge(self, state: ConductorState) -> None:
        """Add successful task to knowledge base."""
        if not state.implementation_code:
            return

        # Simple pattern extraction
        entry = KnowledgeEntry(
            task_pattern=state.original_task[:200],
            solution_pattern=state.implementation_code[:500],
            edge_cases=state.edge_cases[:5],
        )

        # Check for similar existing entries
        for existing in self.knowledge:
            if self._similarity(existing.task_pattern, entry.task_pattern) > 0.8:
                existing.success_count += 1
                self._save_knowledge()
                return

        self.knowledge.append(entry)
        self._save_knowledge()

    def _similarity(self, s1: str, s2: str) -> float:
        """Simple word overlap similarity."""
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())
        if not words1 or not words2:
            return 0.0
        overlap = len(words1 & words2)
        return overlap / max(len(words1), len(words2))

    def get_similar_solutions(self, task: str, k: int = 3) -> List[KnowledgeEntry]:
        """Find similar past solutions."""
        scored = [
            (entry, self._similarity(task, entry.task_pattern))
            for entry in self.knowledge
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [entry for entry, score in scored[:k] if score > 0.3]

    def get_statistics(self) -> Dict[str, Any]:
        """Get learning statistics."""
        return {
            "knowledge_entries": len(self.knowledge),
            "model_task_combos": len(self.model_selector.performance),
            "prompt_variants": {
                stage: len(evolver.variants)
                for stage, evolver in self.prompt_evolvers.items()
            },
        }
