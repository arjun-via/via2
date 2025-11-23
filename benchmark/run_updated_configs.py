"""Run updated ALO-Open and ALO-Optimized configurations and get scores."""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.runners.alo_open_runner import ALOOpenRunner
from benchmark.runners.alo_optimized_runner import ALOOptimizedRunner

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import openai


HARD_PROMPTS = [
    {"id": "rate_limiter", "prompt": "Implement a rate limiter using the token bucket algorithm in Python. Include thread safety and support for multiple users."},
    {"id": "lru_cache", "prompt": "Design and implement a thread-safe LRU cache in Python with O(1) get/put operations. Support TTL expiration."},
    {"id": "byzantine_consensus", "prompt": "Implement the Byzantine Generals Problem solution using a simplified consensus algorithm. Handle up to f faulty nodes in a network of 3f+1 nodes."},
    {"id": "compiler_parser", "prompt": "Write a recursive descent parser for a simple programming language with variables, arithmetic operations, and if/else statements. Include error recovery."},
    {"id": "database_btree", "prompt": "Implement a B-tree data structure for a database index. Support insertion, deletion, and range queries. Handle node splitting and merging."},
    {"id": "distributed_lock", "prompt": "Design a distributed lock manager using Redis. Handle lock acquisition, renewal, and graceful release. Include deadlock detection."},
    {"id": "async_task_queue", "prompt": "Build an async task queue system with priority scheduling, retry logic with exponential backoff, and dead letter queue. Support task dependencies."},
    {"id": "timeseries_anomaly", "prompt": "Implement a time series anomaly detection system using statistical methods (Z-score, moving average). Handle seasonality and detect point/contextual anomalies."},
    {"id": "graph_cycle_detection", "prompt": "Write algorithms to detect cycles in directed and undirected graphs. Include Tarjan's algorithm for strongly connected components."},
    {"id": "regex_engine", "prompt": "Build a simple regex engine supporting . * + ? [] operators. Use Thompson's construction and NFA simulation."}
]


JUDGE_PROMPT = """You are a STRICT, SENIOR-LEVEL software engineering evaluator conducting a code review for production deployment.

You have 20+ years of experience and have seen countless bugs in production. You are SKEPTICAL and look for problems.

**IMPORTANT SCORING CALIBRATION:**
- **1-2/10**: Fundamentally broken, missing core requirements
- **3-4/10**: Has major flaws that would cause serious production issues
- **5-6/10**: Decent attempt, works for basic cases, but missing critical edge cases
- **7-8/10**: Good solution, handles most real-world cases correctly
- **9-10/10**: Exceptional, production-ready code with comprehensive error handling

**DEFAULT ASSUMPTION: Most solutions are 5-6/10. Only exceptional work earns 9-10.**

---

## Task

Evaluate this solution to the following programming challenge:

**Original Prompt:**
{original_prompt}

**Solution:**
{solution}

---

## Your Task

Evaluate the solution on 5 dimensions (1-10 scale):

1. **Correctness**: Does it work? Does it solve the problem?
2. **Completeness**: Are all requirements met? Edge cases handled?
3. **Code Quality**: Is it well-structured, modular, maintainable?
4. **Security**: Thread safety, input validation, vulnerabilities?
5. **Clarity**: Documentation, comments, readability?

Return ONLY valid JSON in this exact format:

```json
{{
  "correctness": {{"score": X, "reasoning": "..."}},
  "completeness": {{"score": X, "reasoning": "..."}},
  "code_quality": {{"score": X, "reasoning": "..."}},
  "security": {{"score": X, "reasoning": "..."}},
  "clarity": {{"score": X, "reasoning": "..."}},
  "overall": X.X,
  "strengths": ["...", "...", "..."],
  "weaknesses": ["...", "..."]
}}
```

**Be harsh. Be thorough. Think about edge cases and production failure modes.**
"""


def run_single_test(runner_name: str, runner, prompt_data: dict) -> dict:
    """Run a single test and return result."""
    print(f"[{runner_name}] Starting: {prompt_data['id']}")
    start = time.time()

    try:
        result = runner.run(prompt_data["prompt"])
        elapsed = time.time() - start
        print(f"[{runner_name}] ✓ {prompt_data['id']} - ${result.cost:.4f} - {elapsed:.1f}s")

        return {
            "runner": runner_name,
            "prompt_id": prompt_data["id"],
            "success": True,
            "result": result,
            "elapsed": elapsed
        }
    except Exception as e:
        elapsed = time.time() - start
        print(f"[{runner_name}] ✗ {prompt_data['id']} - ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            "runner": runner_name,
            "prompt_id": prompt_data["id"],
            "success": False,
            "error": str(e),
            "elapsed": elapsed
        }


def score_solution(prompt_data: dict, solution: str) -> dict:
    """Score a single solution."""
    judge_prompt = JUDGE_PROMPT.format(
        original_prompt=prompt_data["prompt"],
        solution=solution
    )

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a senior software engineering evaluator."},
                {"role": "user", "content": judge_prompt}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"  Judge error: {e}")
        return None


def main():
    print("=" * 80)
    print("UPDATED CONFIGS BENCHMARK: ALO-Open + ALO-Optimized")
    print("=" * 80)
    print("Phase 1: Run both systems on 10 prompts (parallel)")
    print("Phase 2: Score each solution individually")
    print("=" * 80)

    # Phase 1: Run tests
    print("\n" + "=" * 80)
    print("PHASE 1: RUNNING TESTS")
    print("=" * 80)

    runners = {
        "alo_open_v2": ALOOpenRunner(),
        "alo_optimized_v2": ALOOptimizedRunner()
    }

    tasks = []
    for prompt_data in HARD_PROMPTS:
        for runner_name, runner in runners.items():
            tasks.append((runner_name, runner, prompt_data))

    print(f"\nStarting {len(tasks)} tests with 4 workers...")

    overall_start = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(run_single_test, runner_name, runner, prompt_data): (runner_name, prompt_data["id"])
            for runner_name, runner, prompt_data in tasks
        }

        for future in as_completed(futures):
            runner_name, prompt_id = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"  Progress: {len(results)}/{len(tasks)}")
            except Exception as e:
                print(f"[{runner_name}] FATAL: {e}")

    phase1_elapsed = time.time() - overall_start

    # Save outputs
    output_dir = Path("benchmark/results/updated_configs")
    output_dir.mkdir(parents=True, exist_ok=True)

    solutions_by_system = {"alo_open_v2": {}, "alo_optimized_v2": {}}

    for r in results:
        if r["success"]:
            runner_name = r["runner"]
            prompt_id = r["prompt_id"]
            solutions_by_system[runner_name][prompt_id] = r["result"].output

            # Save file
            runner_dir = output_dir / runner_name
            runner_dir.mkdir(exist_ok=True)
            (runner_dir / f"{prompt_id}.txt").write_text(r["result"].output)

    successes = [r for r in results if r["success"]]
    print(f"\nPhase 1 complete: {len(successes)}/{len(results)} tests - {phase1_elapsed:.1f}s")

    # Phase 2: Score solutions
    print("\n" + "=" * 80)
    print("PHASE 2: SCORING SOLUTIONS")
    print("=" * 80)

    all_scores = {"alo_open_v2": {}, "alo_optimized_v2": {}}

    for runner_name in ["alo_open_v2", "alo_optimized_v2"]:
        print(f"\nScoring {runner_name.upper()}...")

        for i, prompt_data in enumerate(HARD_PROMPTS, 1):
            prompt_id = prompt_data["id"]
            solution = solutions_by_system[runner_name].get(prompt_id)

            if not solution:
                print(f"  [{i}/10] {prompt_id} - SKIPPED (no output)")
                continue

            print(f"  [{i}/10] Scoring {prompt_id}...")
            score = score_solution(prompt_data, solution)

            if score:
                all_scores[runner_name][prompt_id] = score
                print(f"    ✓ Overall: {score.get('overall', 0):.1f}/10")

            time.sleep(1)

    # Calculate averages
    print("\n" + "=" * 80)
    print("FINAL SCORES")
    print("=" * 80)

    for runner_name in ["alo_open_v2", "alo_optimized_v2"]:
        scores = all_scores[runner_name]
        if not scores:
            continue

        overalls = [s["overall"] for s in scores.values()]
        avg_overall = sum(overalls) / len(overalls)

        dims = ["correctness", "completeness", "code_quality", "security", "clarity"]
        dim_avgs = {}
        for dim in dims:
            vals = [s[dim]["score"] for s in scores.values()]
            dim_avgs[dim] = sum(vals) / len(vals)

        print(f"\n{runner_name.upper()}:")
        print(f"  Overall: {avg_overall:.2f}/10")
        print(f"  Correctness: {dim_avgs['correctness']:.2f}")
        print(f"  Completeness: {dim_avgs['completeness']:.2f}")
        print(f"  Code Quality: {dim_avgs['code_quality']:.2f}")
        print(f"  Security: {dim_avgs['security']:.2f}")
        print(f"  Clarity: {dim_avgs['clarity']:.2f}")

    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    summary_file = output_dir / f"scores_{timestamp}.json"

    with open(summary_file, "w") as f:
        json.dump({
            "metadata": {"timestamp": timestamp, "phase1_time": phase1_elapsed},
            "scores": all_scores
        }, f, indent=2)

    print(f"\n✓ Results saved: {summary_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
