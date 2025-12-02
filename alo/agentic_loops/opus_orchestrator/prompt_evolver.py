"""
=============================================================================
SCRIPT NAME: prompt_evolver.py
=============================================================================

Prompt Evolver - Learns from errors to improve system prompts over time.

INPUT FILES:
- Challenge results with error traces
- Current system prompt

OUTPUT FILES:
- Evolved system prompt with learned lessons
- Evolution history log

VERSION: 1.0
LAST UPDATED: 2025-11-27

DESCRIPTION:
Implements a reinforcement learning loop for system prompts:
1. Run challenge with current prompt
2. Analyze errors and failure patterns
3. Extract lessons learned
4. Evolve prompt with new guidance
5. Validate improvement on next challenge

This creates a feedback loop where the system gets smarter over time
by encoding successful patterns into the prompt itself.

DEPENDENCIES:
- json (standard library)
- datetime (standard library)

=============================================================================
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict

from .multi_provider_client import MultiProviderClient, CompletionResult
from .model_registry import get_model


@dataclass
class ChallengeResult:
    """Result from a single challenge attempt."""
    challenge_id: str
    challenge_description: str
    success: bool
    verification_passed: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    generated_code: Optional[str] = None
    execution_time: float = 0.0
    cost: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Lesson:
    """A lesson learned from an error."""
    error_pattern: str  # What went wrong
    root_cause: str     # Why it went wrong
    fix_guidance: str   # How to avoid it
    priority: int = 1   # Higher = more important (based on frequency)
    examples: List[str] = field(default_factory=list)


@dataclass
class PromptVersion:
    """A versioned system prompt with its performance history."""
    version: int
    prompt: str
    lessons_incorporated: List[str]
    challenges_attempted: int = 0
    challenges_passed: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def success_rate(self) -> float:
        if self.challenges_attempted == 0:
            return 0.0
        return self.challenges_passed / self.challenges_attempted


# =============================================================================
# BASE SYSTEM PROMPT - Starting point for evolution
# =============================================================================

BASE_ENGINEERING_PROMPT = '''You are an expert Python engineer implementing a feature.

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

# =============================================================================
# PROMPT ANALYSIS PROMPT - Used to extract lessons from errors
# =============================================================================

LESSON_EXTRACTION_PROMPT = '''Analyze this coding error and extract a lesson to prevent it in future.

CHALLENGE: {challenge}

GENERATED CODE:
```python
{code}
```

ERROR TYPE: {error_type}
ERROR MESSAGE: {error_message}

Analyze the root cause and provide a lesson in this JSON format:
{{
    "error_pattern": "Brief description of the error pattern (e.g., 'Missing required __init__ parameters')",
    "root_cause": "Why this happened (e.g., 'Model assumed default constructor when tests expected specific signature')",
    "fix_guidance": "Specific instruction to add to prompt (e.g., 'Always check test code for expected constructor signatures before implementing')",
    "code_example": "A brief correct example if applicable"
}}
'''

# =============================================================================
# PROMPT EVOLUTION PROMPT - Used to integrate lessons into prompt
# =============================================================================

PROMPT_EVOLUTION_PROMPT = '''You are evolving a system prompt based on lessons learned from errors.

CURRENT PROMPT:
{current_prompt}

NEW LESSONS TO INCORPORATE:
{lessons}

EVOLUTION RULES:
1. Add specific, actionable guidance based on each lesson
2. Keep the prompt concise - consolidate similar lessons
3. Prioritize lessons by frequency (higher priority = seen more often)
4. Place most critical guidance early in the prompt
5. Remove any redundant or conflicting guidance
6. Maintain the core structure and output format

Return the evolved prompt. Keep it under 1000 words.
'''


class PromptEvolver:
    """
    Evolves system prompts based on error feedback.

    Implements a simple reinforcement learning loop:
    1. Challenge -> Error -> Lesson -> Prompt Update
    2. Track success rates across prompt versions
    3. Rollback if performance degrades
    """

    def __init__(
        self,
        client: MultiProviderClient,
        storage_path: str = "prompt_evolution",
        analyzer_model: str = "opus-4.5"
    ):
        """
        Initialize the prompt evolver.

        Args:
            client: Multi-provider client for API calls
            storage_path: Directory to store evolution history
            analyzer_model: Model to use for lesson extraction (Opus for quality)
        """
        self.client = client
        self.storage_path = storage_path
        self.analyzer_config = get_model(analyzer_model)

        # Initialize storage
        os.makedirs(storage_path, exist_ok=True)

        # Load or initialize state
        self.lessons: Dict[str, Lesson] = {}
        self.prompt_history: List[PromptVersion] = []
        self.challenge_history: List[ChallengeResult] = []

        self._load_state()

        # Initialize with base prompt if no history
        if not self.prompt_history:
            self.prompt_history.append(PromptVersion(
                version=1,
                prompt=BASE_ENGINEERING_PROMPT,
                lessons_incorporated=[]
            ))

    @property
    def current_prompt(self) -> str:
        """Get the current evolved prompt."""
        return self.prompt_history[-1].prompt

    @property
    def current_version(self) -> int:
        """Get current prompt version number."""
        return self.prompt_history[-1].version

    def record_result(self, result: ChallengeResult) -> Optional[Lesson]:
        """
        Record a challenge result and extract lessons if it failed.

        Args:
            result: The challenge result to record

        Returns:
            Extracted lesson if failure, None if success
        """
        self.challenge_history.append(result)

        # Update current prompt stats
        current = self.prompt_history[-1]
        current.challenges_attempted += 1
        if result.verification_passed:
            current.challenges_passed += 1

        # Extract lesson if failed
        lesson = None
        if not result.verification_passed and result.error_message:
            lesson = self._extract_lesson(result)
            if lesson:
                # Track lesson frequency
                key = lesson.error_pattern
                if key in self.lessons:
                    self.lessons[key].priority += 1
                    if result.generated_code:
                        self.lessons[key].examples.append(result.generated_code[:500])
                else:
                    self.lessons[key] = lesson

        self._save_state()
        return lesson

    def _extract_lesson(self, result: ChallengeResult) -> Optional[Lesson]:
        """Extract a lesson from a failed challenge using Opus."""
        try:
            messages = [{
                "role": "user",
                "content": LESSON_EXTRACTION_PROMPT.format(
                    challenge=result.challenge_description,
                    code=result.generated_code[:4000] if result.generated_code else "No code generated",
                    error_type=result.error_type or "Unknown",
                    error_message=result.error_message or "Unknown error"
                )
            }]

            response = self.client.complete(
                model_config=self.analyzer_config,
                messages=messages,
                max_tokens=1000,
                temperature=0
            )

            # Parse JSON response
            import re
            match = re.search(r'\{[\s\S]*\}', response.content)
            if match:
                data = json.loads(match.group())
                return Lesson(
                    error_pattern=data.get("error_pattern", "Unknown pattern"),
                    root_cause=data.get("root_cause", "Unknown cause"),
                    fix_guidance=data.get("fix_guidance", ""),
                    examples=[data.get("code_example", "")] if data.get("code_example") else []
                )
        except Exception as e:
            print(f"  Lesson extraction failed: {e}")

        return None

    def evolve_prompt(self, min_lessons: int = 3) -> bool:
        """
        Evolve the prompt if enough new lessons have accumulated.

        Args:
            min_lessons: Minimum new lessons before evolving

        Returns:
            True if prompt was evolved, False otherwise
        """
        # Get lessons not yet incorporated
        current_lessons = set(self.prompt_history[-1].lessons_incorporated)
        new_lessons = [
            lesson for key, lesson in self.lessons.items()
            if key not in current_lessons
        ]

        if len(new_lessons) < min_lessons:
            print(f"  Not enough new lessons ({len(new_lessons)}/{min_lessons})")
            return False

        # Sort by priority (frequency)
        new_lessons.sort(key=lambda x: x.priority, reverse=True)

        # Format lessons for prompt
        lessons_text = "\n\n".join([
            f"LESSON {i+1} (priority {lesson.priority}):\n"
            f"Pattern: {lesson.error_pattern}\n"
            f"Cause: {lesson.root_cause}\n"
            f"Fix: {lesson.fix_guidance}"
            for i, lesson in enumerate(new_lessons[:10])  # Top 10
        ])

        # Use Opus to evolve the prompt
        try:
            messages = [{
                "role": "user",
                "content": PROMPT_EVOLUTION_PROMPT.format(
                    current_prompt=self.current_prompt,
                    lessons=lessons_text
                )
            }]

            response = self.client.complete(
                model_config=self.analyzer_config,
                messages=messages,
                max_tokens=2000,
                temperature=0.3  # Slight creativity for prompt writing
            )

            evolved_prompt = response.content.strip()

            # Create new version
            new_version = PromptVersion(
                version=self.current_version + 1,
                prompt=evolved_prompt,
                lessons_incorporated=list(self.lessons.keys())
            )
            self.prompt_history.append(new_version)

            print(f"  Evolved to v{new_version.version} with {len(new_lessons)} lessons")
            self._save_state()
            return True

        except Exception as e:
            print(f"  Prompt evolution failed: {e}")
            return False

    def rollback(self) -> bool:
        """
        Rollback to previous prompt version if current is performing worse.

        Returns:
            True if rolled back, False otherwise
        """
        if len(self.prompt_history) < 2:
            return False

        current = self.prompt_history[-1]
        previous = self.prompt_history[-2]

        # Only rollback if we have enough data and current is worse
        if current.challenges_attempted >= 5 and previous.challenges_attempted >= 5:
            if current.success_rate < previous.success_rate * 0.8:  # 20% worse
                print(f"  Rolling back: v{current.version} ({current.success_rate:.0%}) < v{previous.version} ({previous.success_rate:.0%})")
                self.prompt_history.pop()
                self._save_state()
                return True

        return False

    def get_stats(self) -> Dict:
        """Get evolution statistics."""
        return {
            "current_version": self.current_version,
            "total_lessons": len(self.lessons),
            "total_challenges": len(self.challenge_history),
            "success_rate": self.prompt_history[-1].success_rate if self.prompt_history else 0,
            "prompt_versions": len(self.prompt_history),
            "top_errors": [
                {"pattern": k, "count": v.priority}
                for k, v in sorted(self.lessons.items(), key=lambda x: x[1].priority, reverse=True)[:5]
            ]
        }

    def _save_state(self):
        """Save evolution state to disk."""
        state = {
            "lessons": {k: asdict(v) for k, v in self.lessons.items()},
            "prompt_history": [asdict(p) for p in self.prompt_history],
            "challenge_history": [asdict(c) for c in self.challenge_history[-100:]]  # Keep last 100
        }

        state_path = os.path.join(self.storage_path, "evolution_state.json")
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)

    def _load_state(self):
        """Load evolution state from disk."""
        state_path = os.path.join(self.storage_path, "evolution_state.json")
        if os.path.exists(state_path):
            try:
                with open(state_path, 'r') as f:
                    state = json.load(f)

                self.lessons = {
                    k: Lesson(**v) for k, v in state.get("lessons", {}).items()
                }
                self.prompt_history = [
                    PromptVersion(**p) for p in state.get("prompt_history", [])
                ]
                self.challenge_history = [
                    ChallengeResult(**c) for c in state.get("challenge_history", [])
                ]
            except Exception as e:
                print(f"  Failed to load state: {e}")


# =============================================================================
# CHALLENGE BANK - Diverse challenges for training
# =============================================================================

CHALLENGE_BANK = [
    {
        "id": "lru_cache",
        "description": """Implement an LRUCache class:
- __init__(self, capacity: int)
- get(self, key: int) -> int: Return value or -1, mark as recently used
- put(self, key: int, value: int) -> None: Insert/update, evict LRU if at capacity
Use doubly linked list + hash map for O(1) operations. No OrderedDict.""",
        "test": '''
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1
cache.put(3, 3)
assert cache.get(2) == -1
assert cache.get(3) == 3
cache.put(4, 4)
assert cache.get(1) == -1
print("LRU Cache: PASSED")
'''
    },
    {
        "id": "trie",
        "description": """Implement a Trie (prefix tree):
- insert(word: str) -> None
- search(word: str) -> bool: Returns True if word exists
- startsWith(prefix: str) -> bool: Returns True if any word has prefix
Handle empty strings and case sensitivity (case-sensitive).""",
        "test": '''
trie = Trie()
trie.insert("apple")
assert trie.search("apple") == True
assert trie.search("app") == False
assert trie.startsWith("app") == True
trie.insert("app")
assert trie.search("app") == True
assert trie.search("") == False
assert trie.startsWith("") == True
print("Trie: PASSED")
'''
    },
    {
        "id": "rate_limiter",
        "description": """Implement a token bucket RateLimiter:
- __init__(self, capacity: int, refill_rate: float): tokens per second
- allow(self) -> bool: Returns True if request allowed, consumes 1 token
- tokens_available(self) -> int: Current token count
Use time.time() for timing. Handle partial refills.""",
        "test": '''
import time
limiter = RateLimiter(capacity=5, refill_rate=10.0)
assert limiter.tokens_available() == 5
for _ in range(5):
    assert limiter.allow() == True
assert limiter.allow() == False
time.sleep(0.2)
assert limiter.allow() == True  # ~2 tokens refilled
print("Rate Limiter: PASSED")
'''
    },
    {
        "id": "event_emitter",
        "description": """Implement an EventEmitter:
- on(event: str, callback: Callable) -> None: Register callback
- off(event: str, callback: Callable) -> None: Remove callback
- emit(event: str, *args, **kwargs) -> None: Call all callbacks with args
- once(event: str, callback: Callable) -> None: One-time callback
Callbacks should be called in registration order.""",
        "test": '''
results = []
emitter = EventEmitter()

def handler1(x): results.append(f"h1:{x}")
def handler2(x): results.append(f"h2:{x}")

emitter.on("data", handler1)
emitter.on("data", handler2)
emitter.emit("data", 42)
assert results == ["h1:42", "h2:42"], f"Got {results}"

results.clear()
emitter.off("data", handler1)
emitter.emit("data", 99)
assert results == ["h2:99"], f"Got {results}"

results.clear()
emitter.once("done", lambda x: results.append(x))
emitter.emit("done", "first")
emitter.emit("done", "second")
assert results == ["first"], f"Got {results}"
print("Event Emitter: PASSED")
'''
    },
    {
        "id": "binary_search_tree",
        "description": """Implement a BinarySearchTree:
- insert(val: int) -> None
- search(val: int) -> bool
- delete(val: int) -> bool: Returns True if deleted, False if not found
- inorder() -> List[int]: Returns sorted list of values
Handle duplicates by ignoring them (no duplicate values stored).""",
        "test": '''
bst = BinarySearchTree()
for val in [5, 3, 7, 1, 4, 6, 8]:
    bst.insert(val)
assert bst.inorder() == [1, 3, 4, 5, 6, 7, 8]
assert bst.search(4) == True
assert bst.search(99) == False
assert bst.delete(3) == True
assert bst.inorder() == [1, 4, 5, 6, 7, 8]
assert bst.delete(3) == False
bst.insert(5)  # Duplicate, should be ignored
assert bst.inorder() == [1, 4, 5, 6, 7, 8]
print("BST: PASSED")
'''
    },
    {
        "id": "promise",
        "description": """Implement a simple Promise class:
- __init__(self, executor: Callable[[resolve, reject], None])
- then(self, on_fulfilled: Callable) -> 'Promise'
- catch(self, on_rejected: Callable) -> 'Promise'
- resolve value immediately for this sync implementation
Track state: pending, fulfilled, rejected. Chain promises.""",
        "test": '''
results = []

def executor(resolve, reject):
    resolve(42)

p = Promise(executor)
p.then(lambda x: results.append(x * 2))
assert results == [84], f"Got {results}"

results.clear()
def fail_executor(resolve, reject):
    reject("error")

p2 = Promise(fail_executor)
p2.catch(lambda e: results.append(f"caught:{e}"))
assert results == ["caught:error"], f"Got {results}"
print("Promise: PASSED")
'''
    },
    {
        "id": "interval_merge",
        "description": """Implement IntervalSet:
- add(start: int, end: int) -> None: Add interval [start, end)
- remove(start: int, end: int) -> None: Remove interval [start, end)
- query(point: int) -> bool: Returns True if point is in any interval
- get_intervals() -> List[Tuple[int, int]]: Return merged intervals sorted
Merge overlapping intervals automatically.""",
        "test": '''
iset = IntervalSet()
iset.add(1, 5)
iset.add(10, 15)
assert iset.get_intervals() == [(1, 5), (10, 15)]
iset.add(3, 12)  # Overlaps both
assert iset.get_intervals() == [(1, 15)]
assert iset.query(7) == True
assert iset.query(20) == False
iset.remove(5, 10)
assert iset.get_intervals() == [(1, 5), (10, 15)]
print("Interval Set: PASSED")
'''
    },
    {
        "id": "state_machine",
        "description": """Implement a StateMachine:
- __init__(self, initial_state: str)
- add_transition(from_state: str, event: str, to_state: str, action: Callable = None)
- trigger(event: str) -> bool: Transition and call action. Returns True if valid.
- current_state -> str: Property for current state
- can_trigger(event: str) -> bool: Check if event is valid from current state""",
        "test": '''
actions = []
sm = StateMachine("idle")
sm.add_transition("idle", "start", "running", lambda: actions.append("started"))
sm.add_transition("running", "stop", "idle", lambda: actions.append("stopped"))
sm.add_transition("running", "pause", "paused")
sm.add_transition("paused", "resume", "running")

assert sm.current_state == "idle"
assert sm.can_trigger("start") == True
assert sm.can_trigger("stop") == False
assert sm.trigger("start") == True
assert sm.current_state == "running"
assert actions == ["started"]
assert sm.trigger("invalid") == False
assert sm.current_state == "running"
print("State Machine: PASSED")
'''
    },
    {
        "id": "async_queue",
        "description": """Implement an AsyncQueue (for sync simulation):
- put(item) -> None: Add item to queue
- get() -> item: Remove and return item (FIFO)
- peek() -> item: Return next item without removing
- empty() -> bool: True if empty
- size() -> int: Number of items
- get_nowait() -> item: Raise Empty exception if empty
Define Empty exception class.""",
        "test": '''
q = AsyncQueue()
assert q.empty() == True
assert q.size() == 0
q.put(1)
q.put(2)
q.put(3)
assert q.size() == 3
assert q.peek() == 1
assert q.get() == 1
assert q.get_nowait() == 2
assert q.size() == 1
try:
    q.get()  # Gets 3
    q.get_nowait()  # Should raise Empty
    assert False, "Should have raised Empty"
except Empty:
    pass
print("Async Queue: PASSED")
'''
    },
    {
        "id": "bloom_filter",
        "description": """Implement a BloomFilter:
- __init__(self, size: int, num_hashes: int)
- add(item: str) -> None
- might_contain(item: str) -> bool: Returns True if possibly in set
- false_positive_rate() -> float: Estimated FP rate
Use hash() with different seeds for multiple hash functions.""",
        "test": '''
bf = BloomFilter(size=1000, num_hashes=3)
bf.add("apple")
bf.add("banana")
bf.add("cherry")
assert bf.might_contain("apple") == True
assert bf.might_contain("banana") == True
assert bf.might_contain("cherry") == True
# Unknown items might return True (false positive) but these specific ones shouldn't
# This is probabilistic, but with size=1000 and 3 items, FP rate should be very low
fp_rate = bf.false_positive_rate()
assert 0 <= fp_rate <= 1, f"Invalid FP rate: {fp_rate}"
print("Bloom Filter: PASSED")
'''
    },
]


def get_challenge(challenge_id: str) -> Optional[Dict]:
    """Get a specific challenge by ID."""
    for c in CHALLENGE_BANK:
        if c["id"] == challenge_id:
            return c
    return None


def get_random_challenges(n: int = 5) -> List[Dict]:
    """Get n random challenges for training."""
    import random
    return random.sample(CHALLENGE_BANK, min(n, len(CHALLENGE_BANK)))
