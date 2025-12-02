# Opus Meta-Orchestrator Implementation Guide

## Overview

This guide provides step-by-step instructions for implementing the Opus Meta-Orchestrator system. The orchestrator uses Claude Opus 4.5 to dynamically select models from a registry based on task complexity.

**Key Design Principles** (from Anthropic's Claude Code research):
1. **Incremental Scope** - Solve ONE feature at a time, not everything at once
2. **JSON Specifications** - Use JSON for feature lists (models can't easily modify)
3. **Clean State Invariant** - No half-implemented features, no TODOs
4. **Progress Checkpointing** - Git commit after each successful feature
5. **Explicit Verification** - Agents don't test unless explicitly told

---

## Architecture (with Anthropic Patterns)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       OPUS META-ORCHESTRATOR                            │
│                    (Initializer Role - Anthropic Pattern)               │
├─────────────────────────────────────────────────────────────────────────┤
│  Phase 1: ANALYZE task → Classify archetype                            │
│  Phase 2: DECOMPOSE into features → JSON feature list                  │
│  Phase 3: SELECT models per feature → Provider diversification         │
│  Phase 4: GENERATE constraints → MUST/MUST_NOT/SHOULD                  │
│  Phase 5: DEFINE checkpoints → When to commit/verify                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │        MODEL REGISTRY         │
                    ├───────────────────────────────┤
                    │ Cerebras: GLM-4.6 (600 tok/s) │
                    │          Qwen3-235B (735 tok/s)│
                    │ Groq: Kimi K2 (323 tok/s)     │
                    │ OpenAI: GPT-5.1 (72 tok/s)    │
                    │ OpenRouter: Opus (45 tok/s)   │
                    │            Sonnet (77 tok/s)  │
                    │            Gemini (90 tok/s)  │
                    │            K2-Think (31 tok/s)│
                    └───────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │   FEATURE EXECUTION LOOP      │
                    │   (One feature at a time)     │
                    └───────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        ┌──────────┐         ┌──────────────┐      ┌──────────────┐
        │ Context  │    →    │ Engineering  │  →   │   Review     │
        │ Agent    │         │ Agent        │      │   Agent      │
        │          │         │              │      │              │
        │ 1. Init  │         │ 1. Init      │      │ 1. Verify    │
        │    check │         │    sequence  │      │    feature   │
        │ 2. Read  │         │ 2. ONE       │      │ 2. Clean     │
        │    state │         │    feature   │      │    state?    │
        │ 3. Get   │         │ 3. Verify    │      │ 3. Approve/  │
        │    context│        │    locally   │      │    Reject    │
        └──────────┘         └──────────────┘      └──────────────┘
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    ▼
                          ┌─────────────────┐
                          │ Feature Done?   │──No──→ Retry with
                          │ Clean State?    │        guidance
                          └─────────────────┘
                                    │
                                   Yes
                                    ▼
                    ┌───────────────────────────────┐
                    │ ✓ Checkpoint (git commit)     │
                    │ ✓ Update feature list JSON    │
                    │ ✓ Next feature or DONE        │
                    └───────────────────────────────┘
```

### Key Difference: Feature-by-Feature Execution

**Anti-Pattern (causes 20% execution rate):**
```
"Implement a complete thread-safe LRU cache with all features"
→ Model tries to do everything → Over-engineers → Fails to execute
```

**Correct Pattern (80% execution rate):**
```
Feature F1: "Implement basic get/put" → Verify → Checkpoint
Feature F2: "Add LRU eviction" → Verify → Checkpoint
Feature F3: "Add thread safety" → Verify → Checkpoint
→ Each feature is simple → Executes correctly
```

---

## Step 1: Create Model Registry

**File:** `alo/agentic_loops/core/model_registry.py`

```python
"""
Model Registry for Opus Meta-Orchestrator.
Provides unified access to all available models across providers.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import os


class Provider(Enum):
    CEREBRAS = "cerebras"
    GROQ = "groq"
    OPENAI = "openai"
    OPENROUTER = "openrouter"


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    id: str
    provider: Provider
    base_url: str
    speed_tok_s: float
    input_price_per_m: float
    output_price_per_m: float
    context_window: int
    capabilities: List[str]  # e.g., ["code", "reasoning", "context"]

    def get_api_key(self) -> str:
        """Get API key from environment."""
        env_map = {
            Provider.CEREBRAS: "CEREBRAS_API_KEY",
            Provider.GROQ: "GROQ_API_KEY",
            Provider.OPENAI: "OPENAI_API_KEY",
            Provider.OPENROUTER: "OPENROUTER_API_KEY",
        }
        key = os.getenv(env_map[self.provider])
        if not key:
            raise ValueError(f"Missing API key: {env_map[self.provider]}")
        return key


# Model Registry - All Available Models
MODEL_REGISTRY: Dict[str, ModelConfig] = {
    # Cerebras Native (Fastest)
    "glm-4.6": ModelConfig(
        id="zai-glm-4.6",
        provider=Provider.CEREBRAS,
        base_url="https://api.cerebras.ai/v1",
        speed_tok_s=600,
        input_price_per_m=0.60,
        output_price_per_m=2.00,
        context_window=128000,
        capabilities=["code", "context", "fast"],
    ),
    "qwen3-235b": ModelConfig(
        id="qwen-3-235b-a22b-instruct-2507",
        provider=Provider.CEREBRAS,
        base_url="https://api.cerebras.ai/v1",
        speed_tok_s=735,
        input_price_per_m=0.60,
        output_price_per_m=1.20,
        context_window=262000,
        capabilities=["code", "reasoning", "fast"],
    ),

    # Groq Native (Fast)
    "kimi-k2": ModelConfig(
        id="moonshotai/kimi-k2-instruct-0905",
        provider=Provider.GROQ,
        base_url="https://api.groq.com/openai/v1",
        speed_tok_s=323,
        input_price_per_m=0.20,
        output_price_per_m=0.20,
        context_window=131000,
        capabilities=["code", "review", "agentic", "fast"],
    ),

    # OpenAI Native (ZDR Compliance)
    "gpt-5.1": ModelConfig(
        id="gpt-5.1",
        provider=Provider.OPENAI,
        base_url="https://api.openai.com/v1",
        speed_tok_s=72,
        input_price_per_m=1.25,
        output_price_per_m=10.00,
        context_window=272000,
        capabilities=["code", "reasoning", "premium"],
    ),

    # OpenRouter (Premium Models)
    "opus-4.5": ModelConfig(
        id="anthropic/claude-opus-4",
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        speed_tok_s=45,
        input_price_per_m=5.00,
        output_price_per_m=25.00,
        context_window=200000,
        capabilities=["code", "reasoning", "architecture", "premium"],
    ),
    "sonnet-4.5": ModelConfig(
        id="anthropic/claude-sonnet-4",
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        speed_tok_s=77,
        input_price_per_m=3.00,
        output_price_per_m=15.00,
        context_window=200000,
        capabilities=["code", "reasoning", "review", "premium"],
    ),
    "gemini-2.5-pro": ModelConfig(
        id="google/gemini-2.5-pro-preview",
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        speed_tok_s=90,
        input_price_per_m=2.00,
        output_price_per_m=12.00,
        context_window=1000000,
        capabilities=["context", "reasoning", "large-context"],
    ),
    "kimi-k2-thinking": ModelConfig(
        id="moonshotai/kimi-k2-thinking",
        provider=Provider.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        speed_tok_s=31,
        input_price_per_m=1.00,
        output_price_per_m=3.00,
        context_window=131000,
        capabilities=["reasoning", "review", "deep-analysis"],
    ),
}


def get_model(name: str) -> ModelConfig:
    """Get model config by name."""
    if name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {name}. Available: {list(MODEL_REGISTRY.keys())}")
    return MODEL_REGISTRY[name]


def get_models_by_capability(capability: str) -> List[ModelConfig]:
    """Get all models with a specific capability."""
    return [m for m in MODEL_REGISTRY.values() if capability in m.capabilities]


def get_fastest_model(capability: str = None) -> ModelConfig:
    """Get the fastest model, optionally filtered by capability."""
    models = MODEL_REGISTRY.values()
    if capability:
        models = [m for m in models if capability in m.capabilities]
    return max(models, key=lambda m: m.speed_tok_s)


def get_cheapest_model(capability: str = None) -> ModelConfig:
    """Get the cheapest model, optionally filtered by capability."""
    models = MODEL_REGISTRY.values()
    if capability:
        models = [m for m in models if capability in m.capabilities]
    return min(models, key=lambda m: m.output_price_per_m)
```

---

## Step 2: Create Multi-Provider Client

**File:** `alo/backend/clients/multi_provider_client.py`

```python
"""
Multi-Provider Client for Opus Meta-Orchestrator.
Unified interface for all model providers.
"""
from typing import Dict, List, Optional, Any
import requests
import time
from dataclasses import dataclass

from alo.agentic_loops.core.model_registry import ModelConfig, Provider


@dataclass
class CompletionResult:
    """Result from a model completion."""
    content: str
    input_tokens: int
    output_tokens: int
    elapsed_time: float
    tokens_per_second: float
    cost: float
    model: str
    provider: str


class MultiProviderClient:
    """Unified client for all model providers."""

    def __init__(self, cost_tracker=None):
        self.cost_tracker = cost_tracker

    def complete(
        self,
        model_config: ModelConfig,
        messages: List[Dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0,
        **kwargs
    ) -> CompletionResult:
        """
        Send completion request to any provider.

        Args:
            model_config: Model configuration from registry
            messages: Chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            CompletionResult with response and metrics
        """
        headers = self._get_headers(model_config)
        payload = self._build_payload(model_config, messages, max_tokens, temperature)

        start_time = time.time()

        response = requests.post(
            f"{model_config.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=300
        )

        elapsed_time = time.time() - start_time

        if response.status_code != 200:
            raise Exception(f"API Error {response.status_code}: {response.text[:500]}")

        data = response.json()

        # Extract response
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        # Calculate metrics
        tokens_per_second = output_tokens / elapsed_time if elapsed_time > 0 else 0
        cost = (
            (input_tokens / 1_000_000) * model_config.input_price_per_m +
            (output_tokens / 1_000_000) * model_config.output_price_per_m
        )

        # Track costs if tracker provided
        if self.cost_tracker:
            self.cost_tracker.track_usage(
                model=model_config.id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost
            )

        return CompletionResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            elapsed_time=elapsed_time,
            tokens_per_second=tokens_per_second,
            cost=cost,
            model=model_config.id,
            provider=model_config.provider.value
        )

    def _get_headers(self, model_config: ModelConfig) -> Dict[str, str]:
        """Get headers for provider."""
        api_key = model_config.get_api_key()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # OpenRouter specific headers
        if model_config.provider == Provider.OPENROUTER:
            headers["HTTP-Referer"] = "https://github.com/alo-orchestrator"
            headers["X-Title"] = "ALO Opus Meta-Orchestrator"

        return headers

    def _build_payload(
        self,
        model_config: ModelConfig,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Build request payload for provider."""
        payload = {
            "model": model_config.id,
            "messages": messages,
            "temperature": temperature
        }

        # Different providers use different token limit params
        if model_config.provider == Provider.OPENAI:
            # GPT-5.x uses max_completion_tokens
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens

        return payload
```

---

## Step 2.5: Feature List Data Structure (Anthropic Pattern)

**File:** `alo/agentic_loops/core/feature_list.py`

```python
"""
Feature List for incremental task execution.
Based on Anthropic's agent harness research.

Key insight: Use JSON to prevent models from modifying specifications.
"It is unacceptable to remove or edit tests because this could lead
to missing or buggy functionality."
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import json


class FeatureStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Feature:
    """A single feature to implement."""
    id: str
    description: str
    status: FeatureStatus = FeatureStatus.PENDING
    tests: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    assigned_model: Optional[str] = None
    attempts: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "tests": self.tests,
            "constraints": self.constraints,
            "assigned_model": self.assigned_model,
            "attempts": self.attempts,
            "last_error": self.last_error
        }


@dataclass
class FeatureList:
    """
    Immutable feature list for task execution.

    INVARIANT: Features can only have their STATUS changed.
    Descriptions and tests are IMMUTABLE once created.
    """
    task_id: str
    task_description: str
    features: List[Feature]
    global_constraints: List[str] = field(default_factory=list)
    checkpoints: List[Dict] = field(default_factory=list)

    # This is the key Anthropic insight
    INVARIANT = "NEVER remove or modify feature requirements or tests"

    def get_next_pending(self) -> Optional[Feature]:
        """Get the next pending feature to work on."""
        for feature in self.features:
            if feature.status == FeatureStatus.PENDING:
                return feature
        return None

    def mark_in_progress(self, feature_id: str):
        """Mark a feature as in progress."""
        for feature in self.features:
            if feature.id == feature_id:
                feature.status = FeatureStatus.IN_PROGRESS
                feature.attempts += 1
                return

    def mark_completed(self, feature_id: str):
        """Mark a feature as completed."""
        for feature in self.features:
            if feature.id == feature_id:
                feature.status = FeatureStatus.COMPLETED
                return

    def mark_failed(self, feature_id: str, error: str):
        """Mark a feature as failed with error message."""
        for feature in self.features:
            if feature.id == feature_id:
                feature.status = FeatureStatus.FAILED
                feature.last_error = error
                return

    def all_completed(self) -> bool:
        """Check if all features are completed."""
        return all(f.status == FeatureStatus.COMPLETED for f in self.features)

    def add_checkpoint(self, feature_id: str, git_commit: str):
        """Record a checkpoint after successful feature completion."""
        self.checkpoints.append({
            "feature_id": feature_id,
            "git_commit": git_commit,
            "timestamp": datetime.now().isoformat()
        })

    def to_json(self) -> str:
        """Export as JSON (prevents model modification)."""
        return json.dumps({
            "task_id": self.task_id,
            "task_description": self.task_description,
            "invariant": self.INVARIANT,
            "features": [f.to_dict() for f in self.features],
            "global_constraints": self.global_constraints,
            "checkpoints": self.checkpoints,
            "progress": {
                "completed": len([f for f in self.features if f.status == FeatureStatus.COMPLETED]),
                "total": len(self.features)
            }
        }, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "FeatureList":
        """Load from JSON."""
        data = json.loads(json_str)
        features = [
            Feature(
                id=f["id"],
                description=f["description"],
                status=FeatureStatus(f["status"]),
                tests=f.get("tests", []),
                constraints=f.get("constraints", []),
                assigned_model=f.get("assigned_model"),
                attempts=f.get("attempts", 0),
                last_error=f.get("last_error")
            )
            for f in data["features"]
        ]
        return cls(
            task_id=data["task_id"],
            task_description=data["task_description"],
            features=features,
            global_constraints=data.get("global_constraints", []),
            checkpoints=data.get("checkpoints", [])
        )
```

**Example Feature List (generated by Opus):**

```json
{
  "task_id": "lru_cache_001",
  "task_description": "Implement a thread-safe LRU cache",
  "invariant": "NEVER remove or modify feature requirements or tests",
  "features": [
    {
      "id": "F1",
      "description": "Basic get/put operations with O(1) complexity",
      "status": "pending",
      "tests": ["test_get_existing", "test_get_missing", "test_put_new", "test_put_update"],
      "constraints": ["Use dict for O(1) lookup", "Use list for order tracking"],
      "assigned_model": "qwen3-235b"
    },
    {
      "id": "F2",
      "description": "LRU eviction when capacity exceeded",
      "status": "pending",
      "tests": ["test_eviction_triggers", "test_eviction_removes_lru", "test_capacity_maintained"],
      "constraints": ["Evict least recently used on put", "Update order on get"],
      "assigned_model": "qwen3-235b"
    },
    {
      "id": "F3",
      "description": "Thread-safe operations with locking",
      "status": "pending",
      "tests": ["test_concurrent_get", "test_concurrent_put", "test_no_deadlock"],
      "constraints": ["Use threading.Lock", "Lock on all public methods"],
      "assigned_model": "gpt-5.1"
    }
  ],
  "global_constraints": [
    "MUST: Single Python file",
    "MUST: Standard library only",
    "MUST_NOT: No external dependencies"
  ],
  "progress": {
    "completed": 0,
    "total": 3
  }
}
```

---

## Step 3: Create Strategic Planner

**File:** `alo/agentic_loops/opus_orchestrator/strategic_planner.py`

```python
"""
Strategic Planner - Opus analyzes tasks and selects models.
"""
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from alo.agentic_loops.core.model_registry import (
    MODEL_REGISTRY, ModelConfig, get_model
)
from alo.backend.clients.multi_provider_client import MultiProviderClient


@dataclass
class ExecutionPlan:
    """Plan generated by Opus for task execution."""
    task_id: str
    complexity: str  # simple, medium, complex, expert
    domain: str  # algorithms, systems, data-structures, ml, etc.

    # Model selections
    context_model: str
    engineering_model: str
    review_model: str

    # Selection rationale
    model_rationale: Dict[str, str] = field(default_factory=dict)

    # Constraints for agents
    constraints: List[Dict[str, str]] = field(default_factory=list)

    # Success criteria
    success_criteria: List[str] = field(default_factory=list)

    # Predicted issues
    predicted_failure_modes: List[str] = field(default_factory=list)


PLANNING_PROMPT = '''You are the Opus Meta-Orchestrator - the strategic brain of an autonomous coding system.
Your job is NOT to write code. It is to ANALYZE tasks and CREATE EXECUTION PLANS that maximize the probability of working, executable code.

═══════════════════════════════════════════════════════════════════════════════
CRITICAL PRINCIPLE: EXECUTION > ELEGANCE
═══════════════════════════════════════════════════════════════════════════════
Historical data shows:
- Over-engineered solutions: 20% execution rate
- Simple, focused solutions: 80% execution rate

Your job is to CONSTRAIN agents to produce WORKING code, not impressive code.

═══════════════════════════════════════════════════════════════════════════════
AVAILABLE MODELS
═══════════════════════════════════════════════════════════════════════════════
{model_menu}

═══════════════════════════════════════════════════════════════════════════════
USER REQUEST
═══════════════════════════════════════════════════════════════════════════════
{task}

═══════════════════════════════════════════════════════════════════════════════
PHASE 1: PROBLEM ARCHETYPE CLASSIFICATION
═══════════════════════════════════════════════════════════════════════════════

Classify into ONE archetype:

┌─────────────────────┬────────────────────────────────────────────────────────┐
│ ARCHETYPE           │ STRATEGY                                               │
├─────────────────────┼────────────────────────────────────────────────────────┤
│ "The Quick Fix"     │ SPEED. Simple bug/typo. Use Cerebras/Groq fastest.    │
│                     │ Models: qwen3-235b, glm-4.6, kimi-k2                   │
├─────────────────────┼────────────────────────────────────────────────────────┤
│ "The Feature Build" │ BALANCE. New isolated functionality. Medium models.    │
│                     │ Models: gpt-5.1, sonnet-4.5                            │
├─────────────────────┼────────────────────────────────────────────────────────┤
│ "The Architecture"  │ INTELLIGENCE. Core system changes. Premium models.     │
│                     │ Models: opus-4.5, sonnet-4.5                           │
├─────────────────────┼────────────────────────────────────────────────────────┤
│ "The Haystack"      │ CONTEXT. Debug across many files. Large context.       │
│                     │ Models: gemini-2.5-pro (1M context)                    │
├─────────────────────┼────────────────────────────────────────────────────────┤
│ "The Concurrency"   │ PRECISION. Thread-safety, race conditions. Careful.    │
│                     │ Models: sonnet-4.5, gpt-5.1 + kimi-k2-thinking review  │
└─────────────────────┴────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
PHASE 2: PROVIDER DIVERSIFICATION (Avoid Model Collapse)
═══════════════════════════════════════════════════════════════════════════════

Use DIFFERENT providers for Engineering vs Review to avoid same biases:

Good combinations:
- Engineering: OpenAI (gpt-5.1) → Review: Anthropic (sonnet-4.5)
- Engineering: Cerebras (qwen3-235b) → Review: Groq (kimi-k2)
- Engineering: Anthropic (sonnet-4.5) → Review: OpenAI or Groq

Bad combinations (same provider bias):
- Engineering: sonnet-4.5 → Review: opus-4.5 (both Anthropic)
- Engineering: gpt-5.1 → Review: gpt-5.1 (same model!)

═══════════════════════════════════════════════════════════════════════════════
PHASE 3: CONSTRAINT ENGINEERING
═══════════════════════════════════════════════════════════════════════════════

Generate constraints at THREE levels:

🔴 MUST (Violation = Automatic Rejection):
   - "Implement as single self-contained Python file"
   - "Use Python standard library only"
   - "Handle edge cases: empty input, None, type errors"

🔴 MUST_NOT (Violation = Automatic Rejection):
   - "Do NOT use external packages (requests, redis, pandas)"
   - "Do NOT create multiple files or modules"
   - "Do NOT create abstract base classes"
   - "Do NOT implement unrequested features"

🟡 SHOULD (Strong Recommendations):
   - "Prefer iterative over recursive"
   - "Include docstrings with complexity analysis"
   - "Use type hints for all parameters"

Add DOMAIN-SPECIFIC constraints based on archetype:

FOR "The Concurrency":
  MUST: "Use threading.Lock for all shared state"
  MUST: "Use context managers for lock acquisition"
  MUST_NOT: "Do NOT use global variables for shared state"

FOR "The Feature Build" with algorithms:
  MUST: "Include time/space complexity in docstring"
  SHOULD: "Handle empty/single-element edge cases explicitly"

═══════════════════════════════════════════════════════════════════════════════
PHASE 4: FEATURE DECOMPOSITION (Anthropic Pattern)
═══════════════════════════════════════════════════════════════════════════════

Break the task into INCREMENTAL FEATURES. Each feature should be:
- Small enough to implement in one pass
- Independently testable
- Building on previous features

CRITICAL: Do NOT try to implement everything at once.
"Incremental scope limitation prevents the failure mode where agents
attempt to one-shot the app, leading to incomplete implementations."

Example decomposition for "Thread-safe LRU Cache":
  F1: Basic get/put with O(1) lookup → Simple, use fast model
  F2: LRU eviction on capacity → Medium, may need better model
  F3: Thread safety with locks → Complex, use premium model

Assign DIFFERENT MODELS to features based on complexity:
- Simple features → qwen3-235b, glm-4.6 (fast)
- Medium features → gpt-5.1 (balanced)
- Complex features → sonnet-4.5 (careful)

═══════════════════════════════════════════════════════════════════════════════
PHASE 5: FAILURE PREDICTION
═══════════════════════════════════════════════════════════════════════════════

Predict what could go wrong and how constraints prevent it:

Common failures to predict:
- ImportError (external dependency) → Constraint: stdlib only
- Multi-file import error → Constraint: single file
- Race condition → Constraint: Lock required
- Stack overflow → Constraint: prefer iterative
- Half-implemented feature → Constraint: clean state invariant

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT (JSON with Feature List)
═══════════════════════════════════════════════════════════════════════════════

{{
  "archetype": "quick_fix|feature_build|architecture|haystack|concurrency",
  "complexity": "simple|medium|complex|expert",
  "domain": "algorithms|data-structures|systems|concurrency|web|ml|devops",

  "features": [
    {{
      "id": "F1",
      "description": "<what this feature does>",
      "tests": ["<test1>", "<test2>"],
      "constraints": ["<feature-specific constraint>"],
      "assigned_model": "<model for this feature>",
      "depends_on": []
    }},
    {{
      "id": "F2",
      "description": "<what this feature does>",
      "tests": ["<test1>", "<test2>"],
      "constraints": ["<feature-specific constraint>"],
      "assigned_model": "<model for this feature>",
      "depends_on": ["F1"]
    }}
  ],

  "model_selections": {{
    "context": {{
      "model": "<model_name>",
      "provider": "<cerebras|groq|openai|openrouter>",
      "rationale": "<specific reason>"
    }},
    "default_engineering": {{
      "model": "<default model if not specified per-feature>",
      "provider": "<provider>",
      "rationale": "<specific reason>"
    }},
    "review": {{
      "model": "<model_name>",
      "provider": "<different_provider - avoid model collapse>",
      "rationale": "<specific reason>"
    }}
  }},

  "global_constraints": {{
    "must": [
      {{"rule": "<constraint>", "validation": "<how to check>"}}
    ],
    "must_not": [
      {{"rule": "<forbidden action>", "violation_signal": "<what to look for>"}}
    ],
    "should": [
      {{"rule": "<recommendation>", "benefit": "<why>"}}
    ]
  }},

  "clean_state_invariant": {{
    "checks": [
      "No syntax errors",
      "No TODO/FIXME for critical functionality",
      "No placeholder implementations",
      "All features complete or not started (no half-done)"
    ]
  }},

  "failure_predictions": [
    {{
      "risk": "<what could fail>",
      "likelihood": "low|medium|high",
      "constraint_mitigation": "<which constraint prevents this>"
    }}
  ]
}}
'''


class StrategicPlanner:
    """Uses Opus to analyze tasks and create execution plans."""

    def __init__(self, client: MultiProviderClient):
        self.client = client
        self.opus_config = get_model("opus-4.5")

    def create_plan(self, task: str, task_id: str = None) -> ExecutionPlan:
        """
        Analyze task and create execution plan.

        Args:
            task: Task description
            task_id: Optional task identifier

        Returns:
            ExecutionPlan with model selections and constraints
        """
        # Build model menu for prompt
        model_menu = self._format_model_menu()

        # Call Opus for planning
        messages = [
            {"role": "user", "content": PLANNING_PROMPT.format(
                model_menu=model_menu,
                task=task
            )}
        ]

        result = self.client.complete(
            model_config=self.opus_config,
            messages=messages,
            max_tokens=2000,
            temperature=0
        )

        # Parse response
        plan_data = self._parse_plan(result.content)

        return ExecutionPlan(
            task_id=task_id or "task_001",
            complexity=plan_data.get("complexity", "medium"),
            domain=plan_data.get("domain", "general"),
            context_model=plan_data["model_selections"]["context"]["model"],
            engineering_model=plan_data["model_selections"]["engineering"]["model"],
            review_model=plan_data["model_selections"]["review"]["model"],
            model_rationale={
                "context": plan_data["model_selections"]["context"]["rationale"],
                "engineering": plan_data["model_selections"]["engineering"]["rationale"],
                "review": plan_data["model_selections"]["review"]["rationale"],
            },
            constraints=plan_data.get("constraints", []),
            success_criteria=plan_data.get("success_criteria", []),
            predicted_failure_modes=plan_data.get("predicted_failure_modes", [])
        )

    def _format_model_menu(self) -> str:
        """Format model registry as menu for prompt."""
        lines = []
        for name, config in MODEL_REGISTRY.items():
            lines.append(
                f"- {name}: {config.speed_tok_s} tok/s, "
                f"${config.output_price_per_m}/M output, "
                f"capabilities: {', '.join(config.capabilities)}"
            )
        return "\n".join(lines)

    def _parse_plan(self, content: str) -> Dict:
        """Parse JSON from Opus response."""
        # Extract JSON from response
        try:
            # Try direct parse
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON in response
            import re
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Could not parse plan from response: {content[:500]}")
```

---

## Step 4: Create Opus Meta-Orchestrator (Feature-Based Execution)

**File:** `alo/agentic_loops/opus_orchestrator/meta_orchestrator.py`

```python
"""
Opus Meta-Orchestrator - Main orchestration class.

Implements Anthropic's agent harness patterns:
1. Feature-by-feature execution (not all-at-once)
2. Clean state invariant after each feature
3. Checkpointing with git commits
4. Explicit verification before marking complete
"""
from typing import Tuple, List, Optional
from dataclasses import dataclass
import time
import subprocess

from alo.agentic_loops.core.state import LoopState
from alo.agentic_loops.core.model_registry import get_model
from alo.agentic_loops.core.feature_list import FeatureList, Feature, FeatureStatus
from alo.agentic_loops.core.tools import ToolRegistry
from alo.backend.clients.multi_provider_client import MultiProviderClient, CompletionResult

from .strategic_planner import StrategicPlanner, ExecutionPlan
from .adaptive_validator import AdaptiveValidator, ValidationResult


@dataclass
class OrchestrationResult:
    """Final result from orchestration."""
    state: LoopState
    plan: ExecutionPlan
    feature_list: FeatureList
    validations: List[ValidationResult]
    total_cost: float
    total_time: float
    features_completed: int
    features_total: int


class OpusMetaOrchestrator:
    """
    Main orchestrator that uses Opus for planning and validation.

    KEY PATTERN: Feature-by-feature execution
    - Break task into features
    - Implement ONE feature at a time
    - Verify + checkpoint after each
    - Different models for different feature complexity
    """

    def __init__(
        self,
        client: MultiProviderClient,
        tool_registry: ToolRegistry,
        max_retries_per_feature: int = 3
    ):
        self.client = client
        self.tool_registry = tool_registry
        self.max_retries_per_feature = max_retries_per_feature

        self.planner = StrategicPlanner(client)
        self.validator = AdaptiveValidator(client)

    def run(
        self,
        issue: str,
        repo_path: Optional[str] = None
    ) -> OrchestrationResult:
        """
        Execute task using feature-by-feature pattern.

        Based on Anthropic's research:
        "Incremental scope limitation prevents the failure mode where agents
        attempt to one-shot the app, leading to incomplete implementations."
        """
        start_time = time.time()
        total_cost = 0.0
        all_validations = []

        # Initialize state
        state = LoopState(issue=issue, repo_path=repo_path or ".")
        state.add_history("orchestrator", "Starting Opus Meta-Orchestrator (Feature-Based)")

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 1: Strategic Planning + Feature Decomposition (Opus)
        # ═══════════════════════════════════════════════════════════════════
        state.add_history("planning", "Opus analyzing task and decomposing into features...")
        plan, feature_list = self.planner.create_plan_with_features(issue)

        state.add_history("planning",
            f"Plan created: {len(feature_list.features)} features, "
            f"archetype={plan.archetype}")

        # Log feature list (JSON format prevents modification)
        state.add_history("features", feature_list.to_json())

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 2: Context Gathering (Once for all features)
        # ═══════════════════════════════════════════════════════════════════
        context_result = self._run_context_agent(state, plan)
        total_cost += context_result.cost

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 3: Feature Execution Loop (One at a time)
        # ═══════════════════════════════════════════════════════════════════
        accumulated_code = ""  # Build up code across features

        while not feature_list.all_completed():
            feature = feature_list.get_next_pending()
            if not feature:
                break

            state.add_history("feature_start",
                f"Starting feature {feature.id}: {feature.description}")

            feature_list.mark_in_progress(feature.id)

            # Try to implement this feature
            for attempt in range(self.max_retries_per_feature):
                state.add_history("attempt",
                    f"Feature {feature.id} attempt {attempt + 1}/{self.max_retries_per_feature}")

                # ─────────────────────────────────────────────────────────
                # Engineering: Implement ONE feature
                # ─────────────────────────────────────────────────────────
                engineering_result = self._run_feature_engineering(
                    state, plan, feature, accumulated_code
                )
                total_cost += engineering_result.cost

                # ─────────────────────────────────────────────────────────
                # Review: Verify this feature + clean state check
                # ─────────────────────────────────────────────────────────
                review_result = self._run_feature_review(
                    state, plan, feature, engineering_result.content
                )
                total_cost += review_result.cost

                # ─────────────────────────────────────────────────────────
                # Validation: Opus validates against plan
                # ─────────────────────────────────────────────────────────
                validation = self.validator.validate_feature(
                    state, plan, feature, engineering_result.content
                )
                all_validations.append(validation)

                if validation.passed:
                    # Feature complete!
                    accumulated_code = engineering_result.content
                    feature_list.mark_completed(feature.id)

                    # Checkpoint (git commit)
                    commit_hash = self._create_checkpoint(feature, repo_path)
                    feature_list.add_checkpoint(feature.id, commit_hash)

                    state.add_history("feature_complete",
                        f"✓ Feature {feature.id} complete, checkpoint: {commit_hash[:8]}")
                    break
                else:
                    # Retry with guidance
                    state.add_history("feature_retry",
                        f"Feature {feature.id} failed: {validation.failure_type}")

                    # Apply retry strategy
                    if validation.retry_strategy == "upgrade" and attempt < 2:
                        feature.assigned_model = self._get_upgrade_model(feature.assigned_model)
                        state.add_history("model_upgrade",
                            f"Upgrading to {feature.assigned_model}")

            else:
                # All retries exhausted for this feature
                feature_list.mark_failed(feature.id, validation.failure_details or "Max retries")
                state.add_history("feature_failed",
                    f"✗ Feature {feature.id} failed after {self.max_retries_per_feature} attempts")

                # Opus takeover for remaining features
                if not feature_list.all_completed():
                    state.add_history("opus_takeover",
                        "Opus taking over remaining features")
                    self._opus_takeover(state, plan, feature_list, accumulated_code)
                break

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 4: Final State
        # ═══════════════════════════════════════════════════════════════════
        state.proposed_solution = accumulated_code
        total_time = time.time() - start_time

        completed = len([f for f in feature_list.features
                        if f.status == FeatureStatus.COMPLETED])

        return OrchestrationResult(
            state=state,
            plan=plan,
            feature_list=feature_list,
            validations=all_validations,
            total_cost=total_cost,
            total_time=total_time,
            features_completed=completed,
            features_total=len(feature_list.features)
        )

    def _run_feature_engineering(
        self,
        state: LoopState,
        plan: ExecutionPlan,
        feature: Feature,
        existing_code: str
    ) -> CompletionResult:
        """
        Implement ONE feature, building on existing code.

        Key Anthropic insight: "Work on one feature at a time"
        """
        model_name = feature.assigned_model or plan.default_engineering_model
        model_config = get_model(model_name)

        prompt = self._build_feature_engineering_prompt(
            plan, feature, existing_code, state.context_summary
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Implement ONLY feature {feature.id}: {feature.description}"}
        ]

        result = self.client.complete(model_config, messages, max_tokens=8192)
        state.add_history("engineering",
            f"Feature {feature.id} implemented using {model_name}")

        return result

    def _build_feature_engineering_prompt(
        self,
        plan: ExecutionPlan,
        feature: Feature,
        existing_code: str,
        context: str
    ) -> str:
        """Build prompt for single-feature implementation."""
        return f'''You are implementing ONE SPECIFIC FEATURE. Do not implement anything else.

═══════════════════════════════════════════════════════════════════════════════
INITIALIZATION PROTOCOL (Anthropic Pattern)
═══════════════════════════════════════════════════════════════════════════════
Before writing code:
1. ✓ Read the existing code below
2. ✓ Understand what feature {feature.id} requires
3. ✓ Plan how to add it WITHOUT breaking existing functionality
4. ✓ Implement ONLY this feature

═══════════════════════════════════════════════════════════════════════════════
FEATURE TO IMPLEMENT
═══════════════════════════════════════════════════════════════════════════════
ID: {feature.id}
Description: {feature.description}
Tests that must pass: {', '.join(feature.tests)}
Feature-specific constraints: {', '.join(feature.constraints)}

═══════════════════════════════════════════════════════════════════════════════
EXISTING CODE (Build on this, do NOT rewrite from scratch)
═══════════════════════════════════════════════════════════════════════════════
{existing_code if existing_code else "# No existing code yet - this is the first feature"}

═══════════════════════════════════════════════════════════════════════════════
GLOBAL CONSTRAINTS (Apply to all features)
═══════════════════════════════════════════════════════════════════════════════
{self._format_constraints(plan.global_constraints)}

═══════════════════════════════════════════════════════════════════════════════
CLEAN STATE INVARIANT
═══════════════════════════════════════════════════════════════════════════════
Your output must:
□ Have no syntax errors
□ Have no TODO/FIXME for this feature
□ Have no placeholder implementations
□ Be immediately runnable

Return the COMPLETE updated code (existing + new feature).
'''

    def _create_checkpoint(self, feature: Feature, repo_path: str) -> str:
        """Create git commit checkpoint after successful feature."""
        try:
            # Stage and commit
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
            result = subprocess.run(
                ["git", "commit", "-m", f"feat({feature.id}): {feature.description}"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            # Get commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            return hash_result.stdout.strip()
        except Exception as e:
            return f"checkpoint_failed_{feature.id}"

    def _get_upgrade_model(self, current_model: str) -> str:
        """Get next model in upgrade path."""
        upgrade_path = {
            "qwen3-235b": "gpt-5.1",
            "glm-4.6": "gpt-5.1",
            "gpt-5.1": "sonnet-4.5",
            "sonnet-4.5": "opus-4.5",
        }
        return upgrade_path.get(current_model, "opus-4.5")

    def _run_context_agent(self, state: LoopState, plan: ExecutionPlan) -> CompletionResult:
        """Run context gathering with selected model."""
        model_config = get_model(plan.context_model)

        messages = [
            {"role": "system", "content": self._build_context_prompt(plan)},
            {"role": "user", "content": f"Analyze the codebase for this task:\n\n{state.issue}"}
        ]

        result = self.client.complete(model_config, messages, max_tokens=4096)
        state.context_summary = result.content
        state.add_history("context", f"Context gathered using {plan.context_model}")

        return result

    def _run_engineering_agent(self, state: LoopState, plan: ExecutionPlan) -> CompletionResult:
        """Run code generation with selected model."""
        model_config = get_model(plan.engineering_model)

        messages = [
            {"role": "system", "content": self._build_engineering_prompt(plan)},
            {"role": "user", "content": f"Task: {state.issue}\n\nContext:\n{state.context_summary}"}
        ]

        result = self.client.complete(model_config, messages, max_tokens=8192)
        state.proposed_solution = result.content
        state.add_history("engineering", f"Solution generated using {plan.engineering_model}")

        return result

    def _run_review_agent(self, state: LoopState, plan: ExecutionPlan) -> CompletionResult:
        """Run code review with selected model."""
        model_config = get_model(plan.review_model)

        messages = [
            {"role": "system", "content": self._build_review_prompt(plan)},
            {"role": "user", "content": f"Review this solution:\n\n{state.proposed_solution}"}
        ]

        result = self.client.complete(model_config, messages, max_tokens=2048)
        state.review_feedback = result.content
        state.add_history("review", f"Review completed using {plan.review_model}")

        return result

    def _build_context_prompt(self, plan: ExecutionPlan) -> str:
        """Build system prompt for context agent."""
        constraints = self._format_constraints(plan.constraints)
        return f"""You are a context-gathering agent. Analyze the codebase to understand:
1. Relevant files and their purposes
2. Dependencies and imports
3. Existing patterns to follow

CONSTRAINTS:
{constraints}

Return a concise summary of relevant context."""

    def _build_engineering_prompt(self, plan: ExecutionPlan) -> str:
        """Build system prompt for engineering agent."""
        constraints = self._format_constraints(plan.constraints)
        criteria = "\n".join(f"- {c}" for c in plan.success_criteria)

        return f"""You are a code generation agent. Write clean, working code.

OPUS STRATEGIC CONSTRAINTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━
{constraints}
━━━━━━━━━━━━━━━━━━━━━━━━━━

SUCCESS CRITERIA:
{criteria}

Violation of MUST constraints will result in automatic rejection.
Return ONLY the code solution, properly formatted."""

    def _build_review_prompt(self, plan: ExecutionPlan) -> str:
        """Build system prompt for review agent."""
        constraints = self._format_constraints(plan.constraints)

        return f"""You are a code review agent. Check the solution for:
1. Constraint compliance
2. Correctness and edge cases
3. Security issues
4. Code quality

CONSTRAINTS TO VERIFY:
{constraints}

Return: APPROVED or REJECTED with specific feedback."""

    def _format_constraints(self, constraints: List[dict]) -> str:
        """Format constraints for prompts."""
        lines = []
        for c in constraints:
            lines.append(f"{c['level']}: {c['description']}")
        return "\n".join(lines) if lines else "None specified"

    def _run_feature_review(
        self,
        state: LoopState,
        plan: ExecutionPlan,
        feature: Feature,
        code: str
    ) -> CompletionResult:
        """
        Review a single feature implementation.

        Uses DIFFERENT provider than engineering to avoid model collapse
        (same-provider blind spots).
        """
        model_config = get_model(plan.review_model)

        prompt = f'''Review this implementation of feature {feature.id}.

═══════════════════════════════════════════════════════════════════════════════
FEATURE BEING REVIEWED
═══════════════════════════════════════════════════════════════════════════════
ID: {feature.id}
Description: {feature.description}
Required tests: {', '.join(feature.tests)}
Constraints: {', '.join(feature.constraints)}

═══════════════════════════════════════════════════════════════════════════════
CODE TO REVIEW
═══════════════════════════════════════════════════════════════════════════════
{code}

═══════════════════════════════════════════════════════════════════════════════
CLEAN STATE INVARIANT CHECKLIST
═══════════════════════════════════════════════════════════════════════════════
Verify all of:
□ No syntax errors
□ No TODO/FIXME comments for this feature
□ No placeholder implementations (pass, ...)
□ Feature {feature.id} is fully implemented
□ Previous features still work (no regressions)
□ Code is immediately runnable

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════
Return JSON:
{{
    "approved": true|false,
    "clean_state": true|false,
    "issues": ["<issue1>", "<issue2>"],
    "specific_feedback": "<actionable feedback if rejected>"
}}
'''

        messages = [{"role": "user", "content": prompt}]
        result = self.client.complete(model_config, messages, max_tokens=1024)

        state.add_history("review",
            f"Feature {feature.id} reviewed by {plan.review_model}")

        return result

    def _opus_takeover(
        self,
        state: LoopState,
        plan: ExecutionPlan,
        feature_list: FeatureList,
        current_code: str
    ) -> CompletionResult:
        """
        Opus takes over when other models fail repeatedly.

        This is the "nuclear option" - Opus implements all remaining
        features directly.
        """
        opus_config = get_model("opus-4.5")

        # Get remaining features
        remaining = [f for f in feature_list.features
                    if f.status != FeatureStatus.COMPLETED]

        remaining_str = "\n".join(
            f"- {f.id}: {f.description}" for f in remaining
        )

        prompt = f'''OPUS TAKEOVER MODE

Previous models failed to implement these features. You must complete them.

═══════════════════════════════════════════════════════════════════════════════
ORIGINAL TASK
═══════════════════════════════════════════════════════════════════════════════
{state.issue}

═══════════════════════════════════════════════════════════════════════════════
REMAINING FEATURES TO IMPLEMENT
═══════════════════════════════════════════════════════════════════════════════
{remaining_str}

═══════════════════════════════════════════════════════════════════════════════
CURRENT CODE (Build on this)
═══════════════════════════════════════════════════════════════════════════════
{current_code if current_code else "# No code implemented yet"}

═══════════════════════════════════════════════════════════════════════════════
FAILURE HISTORY
═══════════════════════════════════════════════════════════════════════════════
{self._get_failure_summary(feature_list)}

═══════════════════════════════════════════════════════════════════════════════
GLOBAL CONSTRAINTS
═══════════════════════════════════════════════════════════════════════════════
{self._format_constraints(plan.global_constraints)}

═══════════════════════════════════════════════════════════════════════════════
REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════
1. Implement ALL remaining features
2. Maintain clean state invariant
3. Ensure code is immediately executable
4. Include all tests mentioned in feature specs

Return the COMPLETE implementation.
'''

        messages = [{"role": "user", "content": prompt}]
        result = self.client.complete(opus_config, messages, max_tokens=16384)

        state.add_history("opus_takeover",
            f"Opus completed {len(remaining)} remaining features")
        state.proposed_solution = result.content

        # Mark all remaining as completed (Opus is authoritative)
        for feature in remaining:
            feature_list.mark_completed(feature.id)

        return result

    def _get_failure_summary(self, feature_list: FeatureList) -> str:
        """Summarize failures for Opus takeover context."""
        failures = []
        for f in feature_list.features:
            if f.last_error:
                failures.append(f"- {f.id}: {f.last_error} (attempts: {f.attempts})")
        return "\n".join(failures) if failures else "No specific errors recorded"

    def _upgrade_model(self, plan: ExecutionPlan, validation: ValidationResult) -> ExecutionPlan:
        """Upgrade model based on validation feedback."""
        upgrade_path = {
            "qwen3-235b": "gpt-5.1",
            "glm-4.6": "sonnet-4.5",
            "gpt-5.1": "sonnet-4.5",
            "sonnet-4.5": "opus-4.5",
            "kimi-k2": "kimi-k2-thinking",
        }

        current = plan.engineering_model
        if current in upgrade_path:
            plan.engineering_model = upgrade_path[current]

        return plan
```

---

## Step 5: Create Adaptive Validator

**File:** `alo/agentic_loops/opus_orchestrator/adaptive_validator.py`

```python
"""
Adaptive Validator - Opus validates outputs against plan.
"""
import json
from typing import Optional
from dataclasses import dataclass

from alo.agentic_loops.core.state import LoopState
from alo.agentic_loops.core.model_registry import get_model
from alo.backend.clients.multi_provider_client import MultiProviderClient

from .strategic_planner import ExecutionPlan


@dataclass
class ValidationResult:
    """Result from validation phase."""
    passed: bool
    constraint_results: dict  # constraint -> pass/fail
    failure_type: Optional[str] = None  # constraint_violation, architectural_error, edge_case_missing
    failure_details: Optional[str] = None
    retry_strategy: Optional[str] = None  # emphatic, upgrade, opus_takeover
    specific_guidance: Optional[str] = None


VALIDATION_PROMPT = '''Review this implementation against the strategic plan.

ORIGINAL PLAN:
- Complexity: {complexity}
- Domain: {domain}
- Constraints:
{constraints}
- Success Criteria:
{success_criteria}

IMPLEMENTATION:
{solution}

Evaluate and return JSON:
{{
    "passed": true|false,
    "constraint_results": {{
        "<constraint>": true|false
    }},
    "failure_type": "constraint_violation|architectural_error|edge_case_missing|null",
    "failure_details": "<specific issue or null>",
    "retry_strategy": "emphatic|upgrade|opus_takeover|null",
    "specific_guidance": "<actionable fix guidance or null>"
}}

VALIDATION RULES:
- Any MUST constraint violation = automatic FAIL
- Check for ImportError risks (external dependencies)
- Check for edge cases (empty input, None, type errors)
- Predict if code will execute successfully
'''


class AdaptiveValidator:
    """Uses Opus to validate outputs against execution plan."""

    def __init__(self, client: MultiProviderClient):
        self.client = client
        self.opus_config = get_model("opus-4.5")

    def validate_feature(
        self,
        state: LoopState,
        plan: ExecutionPlan,
        feature: Feature,
        code: str
    ) -> ValidationResult:
        """
        Validate a single feature implementation.

        Checks:
        1. Feature requirements met
        2. Clean state invariant maintained
        3. No regressions in previous features
        """
        prompt = f'''Validate this implementation of feature {feature.id}.

═══════════════════════════════════════════════════════════════════════════════
FEATURE REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════
ID: {feature.id}
Description: {feature.description}
Tests that must pass: {', '.join(feature.tests)}
Constraints: {', '.join(feature.constraints)}

═══════════════════════════════════════════════════════════════════════════════
IMPLEMENTATION
═══════════════════════════════════════════════════════════════════════════════
{code[:8000]}

═══════════════════════════════════════════════════════════════════════════════
CLEAN STATE INVARIANT
═══════════════════════════════════════════════════════════════════════════════
The code must:
□ Have no syntax errors
□ Have no TODO/FIXME for this feature
□ Have no placeholder implementations (pass, ...)
□ Be immediately runnable
□ Not break previous features

═══════════════════════════════════════════════════════════════════════════════
OUTPUT (JSON)
═══════════════════════════════════════════════════════════════════════════════
{{
    "passed": true|false,
    "constraint_results": {{"<constraint>": true|false}},
    "failure_type": "constraint_violation|incomplete|regression|syntax_error|null",
    "failure_details": "<specific issue or null>",
    "retry_strategy": "emphatic|upgrade|opus_takeover|null",
    "specific_guidance": "<actionable fix or null>"
}}
'''

        messages = [{"role": "user", "content": prompt}]
        result = self.client.complete(self.opus_config, messages, max_tokens=1000)
        return self._parse_validation(result.content)

    def validate(self, state: LoopState, plan: ExecutionPlan) -> ValidationResult:
        """
        Validate solution against plan.

        Args:
            state: Current loop state with proposed solution
            plan: Original execution plan

        Returns:
            ValidationResult with pass/fail and guidance
        """
        constraints_str = "\n".join(
            f"  - [{c['level']}] {c['description']}"
            for c in plan.constraints
        )
        criteria_str = "\n".join(f"  - {c}" for c in plan.success_criteria)

        messages = [
            {"role": "user", "content": VALIDATION_PROMPT.format(
                complexity=plan.complexity,
                domain=plan.domain,
                constraints=constraints_str,
                success_criteria=criteria_str,
                solution=state.proposed_solution[:8000]  # Truncate if needed
            )}
        ]

        result = self.client.complete(
            model_config=self.opus_config,
            messages=messages,
            max_tokens=1000,
            temperature=0
        )

        return self._parse_validation(result.content)

    def _parse_validation(self, content: str) -> ValidationResult:
        """Parse validation result from Opus response."""
        try:
            # Try direct parse
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON
            import re
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                data = json.loads(match.group())
            else:
                # Default to failed if can't parse
                return ValidationResult(
                    passed=False,
                    constraint_results={},
                    failure_type="parse_error",
                    failure_details="Could not parse validation response",
                    retry_strategy="emphatic"
                )

        return ValidationResult(
            passed=data.get("passed", False),
            constraint_results=data.get("constraint_results", {}),
            failure_type=data.get("failure_type"),
            failure_details=data.get("failure_details"),
            retry_strategy=data.get("retry_strategy"),
            specific_guidance=data.get("specific_guidance")
        )
```

---

## Step 6: Create Variant Presets

**File:** `alo/agentic_loops/opus_orchestrator/presets.py`

```python
"""
Variant Presets - Constrain which models Opus can select.
"""
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class VariantPreset:
    """Preset that constrains model selection."""
    name: str
    description: str
    allowed_models: List[str]
    default_context: str
    default_engineering: str
    default_review: str


# Variant Presets
PRESETS = {
    "opus-open": VariantPreset(
        name="Opus-Open",
        description="Fast OSS models via native APIs",
        allowed_models=["glm-4.6", "qwen3-235b", "kimi-k2", "kimi-k2-thinking"],
        default_context="glm-4.6",
        default_engineering="qwen3-235b",
        default_review="kimi-k2",
    ),

    "opus-optimized": VariantPreset(
        name="Opus-Optimized",
        description="Best cost/quality balance",
        allowed_models=["gemini-2.5-pro", "qwen3-235b", "kimi-k2", "kimi-k2-thinking", "gpt-5.1"],
        default_context="gemini-2.5-pro",
        default_engineering="qwen3-235b",
        default_review="kimi-k2",
    ),

    "opus-bestinclass": VariantPreset(
        name="Opus-BestInClass",
        description="Maximum quality",
        allowed_models=["gemini-2.5-pro", "gpt-5.1", "sonnet-4.5", "opus-4.5", "kimi-k2-thinking"],
        default_context="gemini-2.5-pro",
        default_engineering="gpt-5.1",
        default_review="sonnet-4.5",
    ),

    "opus-opus": VariantPreset(
        name="Opus-Opus",
        description="Full Opus stack",
        allowed_models=["opus-4.5"],
        default_context="opus-4.5",
        default_engineering="opus-4.5",
        default_review="opus-4.5",
    ),
}


def get_preset(name: str) -> VariantPreset:
    """Get preset by name."""
    if name not in PRESETS:
        raise ValueError(f"Unknown preset: {name}. Available: {list(PRESETS.keys())}")
    return PRESETS[name]
```

---

## Step 7: Wire Into Main

**File:** Update `main.py`

```python
# Add to imports
from alo.agentic_loops.opus_orchestrator.meta_orchestrator import OpusMetaOrchestrator
from alo.agentic_loops.opus_orchestrator.presets import get_preset
from alo.backend.clients.multi_provider_client import MultiProviderClient

# Add new CLI argument
parser.add_argument(
    "--opus-orchestrator",
    action="store_true",
    help="Use Opus Meta-Orchestrator (dynamic model selection)"
)
parser.add_argument(
    "--preset",
    type=str,
    default="opus-optimized",
    help="Variant preset: opus-open, opus-optimized, opus-bestinclass, opus-opus"
)

# In main():
if args.opus_orchestrator:
    client = MultiProviderClient(cost_tracker=cost_tracker)
    tool_registry = ToolRegistry(args.repo)

    orchestrator = OpusMetaOrchestrator(
        client=client,
        tool_registry=tool_registry,
        preset=get_preset(args.preset) if args.preset else None
    )

    result = orchestrator.run(
        issue=args.issue,
        repo_path=args.repo
    )

    print(f"\n{'='*60}")
    print(f"OPUS META-ORCHESTRATOR RESULT")
    print(f"{'='*60}")
    print(f"Complexity: {result.plan.complexity}")
    print(f"Models used: {result.plan.context_model}, {result.plan.engineering_model}, {result.plan.review_model}")
    print(f"Retries: {result.retries}")
    print(f"Total cost: ${result.total_cost:.4f}")
    print(f"Total time: {result.total_time:.2f}s")
    print(f"{'='*60}")
```

---

## File Structure

```
alo/
├── agentic_loops/
│   ├── core/
│   │   ├── model_registry.py      # Step 1: Model registry
│   │   ├── state.py               # Existing
│   │   └── tools.py               # Existing
│   │
│   └── opus_orchestrator/
│       ├── __init__.py
│       ├── meta_orchestrator.py   # Step 4: Main orchestrator
│       ├── strategic_planner.py   # Step 3: Opus planning
│       ├── adaptive_validator.py  # Step 5: Opus validation
│       └── presets.py             # Step 6: Variant presets
│
├── backend/
│   └── clients/
│       ├── multi_provider_client.py  # Step 2: Unified client
│       └── ... existing clients
│
└── main.py                        # Step 7: CLI integration
```

---

## Testing

```bash
# Run with Opus Meta-Orchestrator
python main.py --opus-orchestrator --issue "Implement a thread-safe LRU cache" --repo ./target

# Use specific preset
python main.py --opus-orchestrator --preset opus-open --issue "Write binary search"

# Use best-in-class for complex tasks
python main.py --opus-orchestrator --preset opus-bestinclass --issue "Design a distributed rate limiter"
```

---

## API Keys Required

```bash
# .env file
CEREBRAS_API_KEY=csk-...      # For GLM-4.6, Qwen3-235B
GROQ_API_KEY=gsk_...          # For Kimi K2
OPENAI_API_KEY=sk-proj-...    # For GPT-5.1
OPENROUTER_API_KEY=sk-or-...  # For Opus, Sonnet, Gemini, K2-Thinking
```

---

## Next Steps

1. Run benchmark suite with all presets
2. Compare against Opus-Baseline
3. Tune model selection heuristics based on results
4. Add execution rate tracking
