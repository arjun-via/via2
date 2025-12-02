"""
=============================================================================
SCRIPT NAME: diverse_challenges.py
=============================================================================

Diverse Challenge Bank for Model Selection Learning.

Covers ALL task types to properly differentiate model strengths:
- data_structures: Trees, graphs, linked lists, hash maps
- algorithms: Sorting, searching, dynamic programming, recursion
- string_processing: Parsing, regex, text manipulation
- math: Numerical computation, statistics, number theory
- error_handling: Validation, exceptions, edge cases
- concurrency: Threading, async patterns
- io_operations: File handling, serialization

VERSION: 1.0
LAST UPDATED: 2025-11-27

=============================================================================
"""

import random
from typing import List, Dict

# =============================================================================
# DATA STRUCTURES CHALLENGES (Trees, Graphs, Lists, Maps)
# =============================================================================

DATA_STRUCTURE_CHALLENGES = [
    {
        "id": "lru_cache",
        "category": "data_structures",
        "difficulty": "hard",
        "description": """Implement an LRU (Least Recently Used) Cache with O(1) get and put operations.

class LRUCache:
    def __init__(self, capacity: int):
        # Initialize cache with given capacity
        pass

    def get(self, key: int) -> int:
        # Return value if key exists, -1 otherwise
        # Mark as recently used
        pass

    def put(self, key: int, value: int) -> None:
        # Insert or update key-value pair
        # Evict least recently used if at capacity
        pass

Requirements:
- Both operations must be O(1) time complexity
- Use a combination of hash map and doubly linked list
- Handle edge cases (empty cache, single element, etc.)
""",
        "test": """
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1, "Get existing key"
cache.put(3, 3)  # Evicts key 2
assert cache.get(2) == -1, "Key 2 should be evicted"
cache.put(4, 4)  # Evicts key 1
assert cache.get(1) == -1, "Key 1 should be evicted"
assert cache.get(3) == 3, "Key 3 should exist"
assert cache.get(4) == 4, "Key 4 should exist"

# Edge cases
cache2 = LRUCache(1)
cache2.put(1, 1)
cache2.put(2, 2)
assert cache2.get(1) == -1, "Key 1 evicted in size-1 cache"
assert cache2.get(2) == 2, "Key 2 exists"
print("LRU Cache tests passed!")
"""
    },
    {
        "id": "red_black_tree",
        "category": "data_structures",
        "difficulty": "hard",
        "description": """Implement a simplified Red-Black Tree with insert and search operations.

class RBTree:
    def __init__(self):
        pass

    def insert(self, key: int) -> None:
        # Insert key maintaining RB properties
        pass

    def search(self, key: int) -> bool:
        # Return True if key exists
        pass

    def inorder(self) -> List[int]:
        # Return sorted list of all keys
        pass

Requirements:
- Maintain Red-Black tree properties after insert
- Root must be black
- No two consecutive red nodes
- Black height must be equal on all paths
""",
        "test": """
tree = RBTree()
for val in [7, 3, 18, 10, 22, 8, 11, 26]:
    tree.insert(val)

assert tree.search(10) == True, "Should find 10"
assert tree.search(8) == True, "Should find 8"
assert tree.search(100) == False, "Should not find 100"
assert tree.inorder() == [3, 7, 8, 10, 11, 18, 22, 26], "Inorder should be sorted"
print("Red-Black Tree tests passed!")
"""
    },
    {
        "id": "graph_shortest_path",
        "category": "data_structures",
        "difficulty": "medium",
        "description": """Implement Dijkstra's algorithm for shortest path in a weighted graph.

class Graph:
    def __init__(self):
        pass

    def add_edge(self, u: int, v: int, weight: int) -> None:
        # Add weighted edge (undirected)
        pass

    def shortest_path(self, start: int, end: int) -> int:
        # Return shortest path distance, -1 if unreachable
        pass

Requirements:
- Handle disconnected nodes
- Efficiently find minimum distance node
- Return -1 if no path exists
""",
        "test": """
g = Graph()
g.add_edge(0, 1, 4)
g.add_edge(0, 2, 1)
g.add_edge(2, 1, 2)
g.add_edge(1, 3, 1)
g.add_edge(2, 3, 5)

assert g.shortest_path(0, 3) == 4, "Shortest 0->3 is 0->2->1->3 = 4"
assert g.shortest_path(0, 1) == 3, "Shortest 0->1 is 0->2->1 = 3"
assert g.shortest_path(3, 0) == 4, "Undirected: 3->0 = 4"
assert g.shortest_path(0, 5) == -1, "No path to non-existent node"
print("Graph shortest path tests passed!")
"""
    },
    {
        "id": "skip_list",
        "category": "data_structures",
        "difficulty": "hard",
        "description": """Implement a Skip List with probabilistic balancing.

class SkipList:
    def __init__(self, max_level: int = 16, p: float = 0.5):
        pass

    def insert(self, val: int) -> None:
        # Insert value with random level
        pass

    def search(self, val: int) -> bool:
        # Return True if value exists
        pass

    def delete(self, val: int) -> bool:
        # Remove value, return True if found
        pass

Requirements:
- Probabilistic level generation
- O(log n) average operations
- Handle duplicates (allow or reject - your choice)
""",
        "test": """
sl = SkipList()
for i in [3, 6, 7, 9, 12, 19, 17, 26, 21, 25]:
    sl.insert(i)

assert sl.search(19) == True, "Should find 19"
assert sl.search(7) == True, "Should find 7"
assert sl.search(100) == False, "Should not find 100"

assert sl.delete(19) == True, "Should delete 19"
assert sl.search(19) == False, "19 should be gone"
assert sl.delete(19) == False, "Can't delete twice"
print("Skip List tests passed!")
"""
    },
]

# =============================================================================
# ALGORITHM CHALLENGES (Sorting, DP, Recursion)
# =============================================================================

ALGORITHM_CHALLENGES = [
    {
        "id": "merge_sort_linked_list",
        "category": "algorithms",
        "difficulty": "medium",
        "description": """Implement merge sort for a singly linked list.

class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def sort_list(head: ListNode) -> ListNode:
    # Sort linked list using merge sort
    # Return new head
    pass

Requirements:
- O(n log n) time complexity
- O(log n) space for recursion stack (or O(1) iterative)
- Stable sort
""",
        "test": """
def to_list(node):
    result = []
    while node:
        result.append(node.val)
        node = node.next
    return result

def from_list(vals):
    if not vals:
        return None
    head = ListNode(vals[0])
    curr = head
    for v in vals[1:]:
        curr.next = ListNode(v)
        curr = curr.next
    return head

# Test 1: Random order
head = from_list([4, 2, 1, 3])
sorted_head = sort_list(head)
assert to_list(sorted_head) == [1, 2, 3, 4], "Should sort to [1,2,3,4]"

# Test 2: Already sorted
head = from_list([1, 2, 3])
sorted_head = sort_list(head)
assert to_list(sorted_head) == [1, 2, 3], "Already sorted"

# Test 3: Reverse sorted
head = from_list([5, 4, 3, 2, 1])
sorted_head = sort_list(head)
assert to_list(sorted_head) == [1, 2, 3, 4, 5], "Reverse sorted"

# Test 4: Empty and single
assert sort_list(None) is None, "Empty list"
assert to_list(sort_list(from_list([1]))) == [1], "Single element"
print("Merge sort linked list tests passed!")
"""
    },
    {
        "id": "longest_increasing_subsequence",
        "category": "algorithms",
        "difficulty": "medium",
        "description": """Find the length of the longest strictly increasing subsequence.

def length_of_lis(nums: List[int]) -> int:
    # Return length of longest increasing subsequence
    pass

Requirements:
- O(n log n) time complexity using binary search
- Subsequence elements don't need to be contiguous
- Strictly increasing (not equal)
""",
        "test": """
from typing import List

assert length_of_lis([10, 9, 2, 5, 3, 7, 101, 18]) == 4, "[2,3,7,101] or [2,5,7,101]"
assert length_of_lis([0, 1, 0, 3, 2, 3]) == 4, "[0,1,2,3]"
assert length_of_lis([7, 7, 7, 7, 7, 7, 7]) == 1, "All same = 1"
assert length_of_lis([]) == 0, "Empty = 0"
assert length_of_lis([1]) == 1, "Single = 1"
assert length_of_lis([1, 3, 6, 7, 9, 4, 10, 5, 6]) == 6, "LIS is [1,3,6,7,9,10]"
print("LIS tests passed!")
"""
    },
    {
        "id": "knapsack_01",
        "category": "algorithms",
        "difficulty": "medium",
        "description": """Solve the 0/1 Knapsack problem using dynamic programming.

def knapsack(weights: List[int], values: List[int], capacity: int) -> int:
    # Return maximum value that fits in knapsack
    # Each item can only be used once
    pass

Requirements:
- O(n * capacity) time and space
- Cannot use fractions of items
- Return maximum achievable value
""",
        "test": """
from typing import List

# Test 1: Basic case
assert knapsack([1, 2, 3], [6, 10, 12], 5) == 22, "Items 2,3 = 10+12"

# Test 2: Capacity exactly fits all
assert knapsack([1, 2, 3], [10, 20, 30], 6) == 60, "All items fit"

# Test 3: Nothing fits
assert knapsack([5, 6, 7], [10, 20, 30], 4) == 0, "Nothing fits"

# Test 4: Empty
assert knapsack([], [], 10) == 0, "Empty = 0"

# Test 5: Complex
assert knapsack([2, 3, 4, 5], [3, 4, 5, 6], 5) == 7, "Items 1,2 = 3+4"
print("Knapsack tests passed!")
"""
    },
    {
        "id": "topological_sort",
        "category": "algorithms",
        "difficulty": "medium",
        "description": """Implement topological sort for a directed acyclic graph (DAG).

def topological_sort(num_nodes: int, edges: List[tuple]) -> List[int]:
    # edges: list of (from, to) tuples
    # Return topological ordering, empty if cycle detected
    pass

Requirements:
- Detect cycles and return empty list
- Return valid topological order if DAG
- Use Kahn's algorithm or DFS
""",
        "test": """
from typing import List

# Test 1: Linear chain
result = topological_sort(4, [(0, 1), (1, 2), (2, 3)])
assert result == [0, 1, 2, 3], "Linear chain"

# Test 2: DAG with multiple valid orderings
result = topological_sort(4, [(0, 1), (0, 2), (1, 3), (2, 3)])
# Valid: [0,1,2,3] or [0,2,1,3]
assert result[0] == 0 and result[-1] == 3, "0 first, 3 last"

# Test 3: Cycle detection
result = topological_sort(3, [(0, 1), (1, 2), (2, 0)])
assert result == [], "Cycle should return empty"

# Test 4: No edges
result = topological_sort(3, [])
assert len(result) == 3, "All nodes in some order"
print("Topological sort tests passed!")
"""
    },
]

# =============================================================================
# STRING PROCESSING CHALLENGES
# =============================================================================

STRING_CHALLENGES = [
    {
        "id": "regex_matcher",
        "category": "string_processing",
        "difficulty": "hard",
        "description": """Implement a simple regex matcher supporting '.' and '*'.

def is_match(s: str, p: str) -> bool:
    # '.' matches any single character
    # '*' matches zero or more of the preceding element
    # Match must cover entire string
    pass

Requirements:
- Support . (any char) and * (zero or more of previous)
- Full string match required
- Handle edge cases (empty string/pattern)
""",
        "test": """
assert is_match("aa", "a") == False, "aa != a"
assert is_match("aa", "a*") == True, "a* matches aa"
assert is_match("ab", ".*") == True, ".* matches anything"
assert is_match("aab", "c*a*b") == True, "c*=empty, a*=aa, b=b"
assert is_match("mississippi", "mis*is*p*.") == False, "Complex mismatch"
assert is_match("", "") == True, "Empty matches empty"
assert is_match("", "a*") == True, "a* can match empty"
assert is_match("abc", "a.c") == True, ". matches b"
print("Regex matcher tests passed!")
"""
    },
    {
        "id": "json_parser",
        "category": "string_processing",
        "difficulty": "hard",
        "description": """Implement a simple JSON parser (objects, arrays, strings, numbers, booleans, null).

def parse_json(json_str: str):
    # Parse JSON string and return Python object
    # Support: objects {}, arrays [], strings "", numbers, true/false/null
    pass

Requirements:
- Handle nested structures
- Proper error handling for invalid JSON
- Support all JSON primitive types
""",
        "test": """
# Test primitives
assert parse_json("123") == 123, "Number"
assert parse_json('"hello"') == "hello", "String"
assert parse_json("true") == True, "Boolean true"
assert parse_json("false") == False, "Boolean false"
assert parse_json("null") is None, "Null"

# Test array
assert parse_json("[1, 2, 3]") == [1, 2, 3], "Simple array"

# Test object
result = parse_json('{"a": 1, "b": 2}')
assert result == {"a": 1, "b": 2}, "Simple object"

# Test nested
result = parse_json('{"arr": [1, 2], "obj": {"x": 10}}')
assert result == {"arr": [1, 2], "obj": {"x": 10}}, "Nested"
print("JSON parser tests passed!")
"""
    },
    {
        "id": "text_justification",
        "category": "string_processing",
        "difficulty": "hard",
        "description": """Implement text justification (full justify).

def full_justify(words: List[str], max_width: int) -> List[str]:
    # Justify text to max_width
    # Distribute spaces evenly between words
    # Last line left-justified
    pass

Requirements:
- Even space distribution (extra spaces go left)
- Last line left-justified with trailing spaces
- Handle single-word lines
""",
        "test": """
from typing import List

result = full_justify(["This", "is", "an", "example", "of", "text", "justification."], 16)
assert len(result) == 3, "Should have 3 lines"
assert all(len(line) == 16 for line in result), "All lines 16 chars"
assert result[0] == "This    is    an", "Line 1"
assert result[-1] == "justification.  ", "Last line left-justified"

# Single word per line
result = full_justify(["What", "must", "be"], 6)
assert result == ["What  ", "must  ", "be    "], "Single word lines"
print("Text justification tests passed!")
"""
    },
]

# =============================================================================
# MATH CHALLENGES
# =============================================================================

MATH_CHALLENGES = [
    {
        "id": "matrix_multiply",
        "category": "math",
        "difficulty": "medium",
        "description": """Implement efficient matrix multiplication.

def matrix_multiply(a: List[List[int]], b: List[List[int]]) -> List[List[int]]:
    # Multiply matrices A (m x n) and B (n x p)
    # Return result matrix (m x p)
    pass

Requirements:
- Handle matrices of any valid dimensions
- Raise ValueError if dimensions don't match
- Return new matrix (don't modify inputs)
""",
        "test": """
from typing import List

# Test 1: 2x2 * 2x2
a = [[1, 2], [3, 4]]
b = [[5, 6], [7, 8]]
result = matrix_multiply(a, b)
assert result == [[19, 22], [43, 50]], "2x2 multiplication"

# Test 2: 2x3 * 3x2
a = [[1, 2, 3], [4, 5, 6]]
b = [[7, 8], [9, 10], [11, 12]]
result = matrix_multiply(a, b)
assert result == [[58, 64], [139, 154]], "2x3 * 3x2"

# Test 3: Identity
a = [[1, 0], [0, 1]]
b = [[5, 6], [7, 8]]
assert matrix_multiply(a, b) == b, "Identity * B = B"

# Test 4: Dimension mismatch
try:
    matrix_multiply([[1, 2]], [[1], [2], [3]])
    assert False, "Should raise ValueError"
except ValueError:
    pass
print("Matrix multiply tests passed!")
"""
    },
    {
        "id": "prime_factorization",
        "category": "math",
        "difficulty": "easy",
        "description": """Find the prime factorization of a number.

def prime_factors(n: int) -> List[int]:
    # Return sorted list of prime factors (with repetition)
    pass

Requirements:
- Return factors in ascending order
- Include repeated factors (e.g., 12 = [2, 2, 3])
- Handle n <= 1 appropriately
""",
        "test": """
from typing import List

assert prime_factors(12) == [2, 2, 3], "12 = 2*2*3"
assert prime_factors(100) == [2, 2, 5, 5], "100 = 2*2*5*5"
assert prime_factors(17) == [17], "17 is prime"
assert prime_factors(1) == [], "1 has no prime factors"
assert prime_factors(2) == [2], "2 is prime"
assert prime_factors(84) == [2, 2, 3, 7], "84 = 2*2*3*7"
print("Prime factorization tests passed!")
"""
    },
    {
        "id": "newton_sqrt",
        "category": "math",
        "difficulty": "easy",
        "description": """Implement square root using Newton's method.

def sqrt(x: float, epsilon: float = 1e-10) -> float:
    # Return square root of x using Newton-Raphson
    # Converge until |guess^2 - x| < epsilon
    pass

Requirements:
- Handle x >= 0 (raise ValueError for negative)
- Converge to specified precision
- Handle special cases (0, 1)
""",
        "test": """
import math

assert abs(sqrt(4) - 2.0) < 1e-9, "sqrt(4) = 2"
assert abs(sqrt(2) - math.sqrt(2)) < 1e-9, "sqrt(2)"
assert abs(sqrt(9) - 3.0) < 1e-9, "sqrt(9) = 3"
assert sqrt(0) == 0, "sqrt(0) = 0"
assert abs(sqrt(0.25) - 0.5) < 1e-9, "sqrt(0.25) = 0.5"

try:
    sqrt(-1)
    assert False, "Should raise for negative"
except ValueError:
    pass
print("Newton sqrt tests passed!")
"""
    },
]

# =============================================================================
# ERROR HANDLING CHALLENGES
# =============================================================================

ERROR_HANDLING_CHALLENGES = [
    {
        "id": "retry_decorator",
        "category": "error_handling",
        "difficulty": "medium",
        "description": """Implement a retry decorator with exponential backoff.

def retry(max_attempts: int = 3, base_delay: float = 1.0, exceptions: tuple = (Exception,)):
    # Decorator that retries function on failure
    # Exponential backoff: delay = base_delay * 2^attempt
    # Only catch specified exceptions
    pass

Requirements:
- Retry up to max_attempts times
- Exponential backoff between retries
- Re-raise after all attempts exhausted
- Only catch specified exception types
""",
        "test": """
import time

call_count = 0

@retry(max_attempts=3, base_delay=0.01)
def flaky_function():
    global call_count
    call_count += 1
    if call_count < 3:
        raise ValueError("Fail")
    return "success"

call_count = 0
result = flaky_function()
assert result == "success", "Should succeed on 3rd try"
assert call_count == 3, "Should have tried 3 times"

# Test exhausting retries
@retry(max_attempts=2, base_delay=0.01)
def always_fails():
    raise RuntimeError("Always fails")

try:
    always_fails()
    assert False, "Should have raised"
except RuntimeError:
    pass

print("Retry decorator tests passed!")
"""
    },
    {
        "id": "result_type",
        "category": "error_handling",
        "difficulty": "medium",
        "description": """Implement a Result type for error handling (like Rust's Result).

class Result:
    @staticmethod
    def ok(value):
        # Create success result
        pass

    @staticmethod
    def err(error):
        # Create error result
        pass

    def is_ok(self) -> bool:
        pass

    def is_err(self) -> bool:
        pass

    def unwrap(self):
        # Return value or raise if error
        pass

    def unwrap_or(self, default):
        # Return value or default if error
        pass

    def map(self, fn):
        # Apply fn to value if ok, pass through if error
        pass

Requirements:
- Immutable Result objects
- Chain operations with map
- Safe unwrapping with unwrap_or
""",
        "test": """
# Test ok
ok = Result.ok(42)
assert ok.is_ok() == True
assert ok.is_err() == False
assert ok.unwrap() == 42

# Test err
err = Result.err("failure")
assert err.is_ok() == False
assert err.is_err() == True
assert err.unwrap_or(0) == 0

try:
    err.unwrap()
    assert False, "Should raise on unwrap of error"
except Exception:
    pass

# Test map
result = Result.ok(10).map(lambda x: x * 2)
assert result.unwrap() == 20, "Map on ok"

result = Result.err("bad").map(lambda x: x * 2)
assert result.is_err(), "Map on err stays err"

print("Result type tests passed!")
"""
    },
]

# =============================================================================
# CONCURRENCY CHALLENGES
# =============================================================================

CONCURRENCY_CHALLENGES = [
    {
        "id": "thread_pool",
        "category": "concurrency",
        "difficulty": "hard",
        "description": """Implement a simple thread pool.

class ThreadPool:
    def __init__(self, num_workers: int):
        pass

    def submit(self, fn, *args, **kwargs):
        # Submit function to be executed by pool
        # Return Future-like object
        pass

    def shutdown(self, wait: bool = True):
        # Stop accepting new tasks
        # If wait=True, wait for pending tasks
        pass

Requirements:
- Fixed number of worker threads
- Queue tasks for execution
- Clean shutdown
""",
        "test": """
import time

pool = ThreadPool(2)
results = []

def task(x):
    time.sleep(0.01)
    return x * 2

futures = [pool.submit(task, i) for i in range(4)]
for f in futures:
    results.append(f.result())

pool.shutdown()

assert sorted(results) == [0, 2, 4, 6], "All tasks completed"
print("Thread pool tests passed!")
"""
    },
    {
        "id": "rate_limiter",
        "category": "concurrency",
        "difficulty": "medium",
        "description": """Implement a token bucket rate limiter.

class RateLimiter:
    def __init__(self, rate: float, capacity: int):
        # rate: tokens per second
        # capacity: max tokens (bucket size)
        pass

    def acquire(self, tokens: int = 1) -> bool:
        # Try to acquire tokens, return True if successful
        pass

    def wait_and_acquire(self, tokens: int = 1) -> None:
        # Block until tokens available
        pass

Requirements:
- Thread-safe
- Smooth token replenishment
- Handle burst capacity
""",
        "test": """
import time

limiter = RateLimiter(rate=10, capacity=5)  # 10 tok/s, max 5

# Should allow initial burst up to capacity
for i in range(5):
    assert limiter.acquire() == True, f"Burst token {i+1}"

# Next should fail immediately (no tokens)
assert limiter.acquire() == False, "No tokens left"

# Wait for replenishment
time.sleep(0.2)  # Should have ~2 tokens
assert limiter.acquire() == True, "Replenished"
assert limiter.acquire() == True, "Second replenished"
print("Rate limiter tests passed!")
"""
    },
]

# =============================================================================
# COMBINED CHALLENGE BANK
# =============================================================================

DIVERSE_CHALLENGE_BANK = (
    DATA_STRUCTURE_CHALLENGES +
    ALGORITHM_CHALLENGES +
    STRING_CHALLENGES +
    MATH_CHALLENGES +
    ERROR_HANDLING_CHALLENGES +
    CONCURRENCY_CHALLENGES
)


def get_challenges_by_category(category: str) -> List[Dict]:
    """Get all challenges of a specific category."""
    return [c for c in DIVERSE_CHALLENGE_BANK if c["category"] == category]


def get_challenges_by_difficulty(difficulty: str) -> List[Dict]:
    """Get all challenges of a specific difficulty."""
    return [c for c in DIVERSE_CHALLENGE_BANK if c["difficulty"] == difficulty]


def get_random_diverse_challenges(n: int) -> List[Dict]:
    """Get n random challenges, ensuring category diversity."""
    categories = list(set(c["category"] for c in DIVERSE_CHALLENGE_BANK))
    selected = []

    # First, try to get one from each category
    for cat in categories:
        cat_challenges = get_challenges_by_category(cat)
        if cat_challenges and len(selected) < n:
            selected.append(random.choice(cat_challenges))

    # Fill remaining with random (avoiding duplicates)
    remaining = [c for c in DIVERSE_CHALLENGE_BANK if c not in selected]
    while len(selected) < n and remaining:
        choice = random.choice(remaining)
        selected.append(choice)
        remaining.remove(choice)

    random.shuffle(selected)
    return selected[:n]


def get_balanced_challenge_set(per_category: int = 2) -> List[Dict]:
    """Get a balanced set with N challenges per category."""
    categories = list(set(c["category"] for c in DIVERSE_CHALLENGE_BANK))
    selected = []

    for cat in categories:
        cat_challenges = get_challenges_by_category(cat)
        selected.extend(random.sample(cat_challenges, min(per_category, len(cat_challenges))))

    random.shuffle(selected)
    return selected


# Quick stats
if __name__ == "__main__":
    print("DIVERSE CHALLENGE BANK STATISTICS")
    print("=" * 50)
    print(f"Total challenges: {len(DIVERSE_CHALLENGE_BANK)}")

    categories = {}
    difficulties = {}
    for c in DIVERSE_CHALLENGE_BANK:
        categories[c["category"]] = categories.get(c["category"], 0) + 1
        difficulties[c["difficulty"]] = difficulties.get(c["difficulty"], 0) + 1

    print("\nBy Category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    print("\nBy Difficulty:")
    for diff, count in sorted(difficulties.items()):
        print(f"  {diff}: {count}")
