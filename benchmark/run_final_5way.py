"""Run final 5-way comparison: ALO-Optimized, ALO-Open, ALO-BestInClass, ALO-Sonnet, ALO-Opus."""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.runners.alo_optimized_runner import ALOOptimizedRunner
from benchmark.runners.alo_open_runner import ALOOpenRunner
from benchmark.runners.alo_bestinclass_runner import ALOBestInClassRunner
from benchmark.runners.alo_sonnet_runner import ALOSonnetRunner
from benchmark.runners.alo_opus_runner import ALOOpusRunner

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

**IMPORTANT SCORING CALIBRATION:**
- **1-2/10**: Fundamentally broken, missing core requirements
- **3-4/10**: Has major flaws that would cause serious production issues
- **5-6/10**: Decent attempt, works for basic cases, but missing critical edge cases
- **7-8/10**: Good solution, handles most real-world cases correctly
- **9-10/10**: Exceptional, production-ready code with comprehensive error handling

**DEFAULT ASSUMPTION: Most solutions are 5-6/10. Only exceptional work earns 9-10.**

---

Evaluate this solution:

**Original Prompt:**
{original_prompt}

**Solution:**
{solution}

---

Evaluate on 5 dimensions (1-10 scale):

1. **Correctness**: Does it work? Does it solve the problem?
2. **Completeness**: Are all requirements met? Edge cases handled?
3. **Code Quality**: Is it well-structured, modular, maintainable?
4. **Security**: Thread safety, input validation, vulnerabilities?
5. **Clarity**: Documentation, comments, readability?

Return ONLY valid JSON:

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
    print("FINAL 5-WAY ALO COMPARISON")
    print("=" * 80)
    print("Systems:")
    print("  1. ALO-Optimized (Gemini + Qwen3-Coder + Kimi-K2-Thinking)")
    print("  2. ALO-Open (GLM-4.6 + Qwen3-Coder + Kimi-K2-Thinking)")
    print("  3. ALO-BestInClass (Gemini 3 Pro + Sonnet 4.5 + GPT-5.1)")
    print("  4. ALO-Sonnet (Sonnet 4.5 for all agents)")
    print("  5. ALO-Opus (Opus 4.5 for all agents)")
    print("=" * 80)

    # Initialize runners
    runners = {
        "alo_optimized": ALOOptimizedRunner(),
        "alo_open": ALOOpenRunner(),
        "alo_bestinclass": ALOBestInClassRunner(),
        "alo_sonnet": ALOSonnetRunner(),
        "alo_opus": ALOOpusRunner()
    }

    # Run all tests in parallel
    num_systems = len(runners)
    num_prompts = len(HARD_PROMPTS)
    total_tests = num_systems * num_prompts
    print(f"\nPhase 1: Running all {num_systems} systems on {num_prompts} prompts ({total_tests} tests total)...")
    print("-" * 80)

    tasks = []
    for prompt_data in HARD_PROMPTS:
        for runner_name, runner in runners.items():
            tasks.append((runner_name, runner, prompt_data))

    overall_start = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=10) as executor:
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
    output_dir = Path("benchmark/results/final_5way")
    output_dir.mkdir(parents=True, exist_ok=True)

    solutions_by_system = {name: {} for name in runners.keys()}

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

    # Score solutions
    print("\n" + "=" * 80)
    print("Phase 2: Scoring all solutions...")
    print("=" * 80)

    all_scores = {name: {} for name in runners.keys()}

    for runner_name in runners.keys():
        print(f"\nScoring {runner_name.upper()}...")

        for i, prompt_data in enumerate(HARD_PROMPTS, 1):
            prompt_id = prompt_data["id"]
            solution = solutions_by_system[runner_name].get(prompt_id)

            if not solution:
                print(f"  [{i}/{num_prompts}] {prompt_id} - SKIPPED")
                continue

            print(f"  [{i}/{num_prompts}] Scoring {prompt_id}...")
            score = score_solution(prompt_data, solution)

            if score:
                all_scores[runner_name][prompt_id] = score
                print(f"    ✓ Overall: {score['overall']:.1f}/10")

            time.sleep(1)

    # Calculate averages and generate report
    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)

    summary = {}

    for runner_name in runners.keys():
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

        # Get cost/time
        system_results = [r for r in successes if r["runner"] == runner_name]
        avg_cost = sum(r["result"].cost for r in system_results) / len(system_results) if system_results else 0
        avg_time = sum(r["elapsed"] for r in system_results) / len(system_results) if system_results else 0

        summary[runner_name] = {
            "overall": avg_overall,
            "dimensions": dim_avgs,
            "avg_cost": avg_cost,
            "avg_time": avg_time
        }

        print(f"\n{runner_name.upper()}:")
        print(f"  Overall: {avg_overall:.2f}/10")
        print(f"  Correctness: {dim_avgs['correctness']:.2f}")
        print(f"  Completeness: {dim_avgs['completeness']:.2f}")
        print(f"  Code Quality: {dim_avgs['code_quality']:.2f}")
        print(f"  Security: {dim_avgs['security']:.2f}")
        print(f"  Clarity: {dim_avgs['clarity']:.2f}")
        print(f"  Avg Cost: ${avg_cost:.4f}")
        print(f"  Avg Time: {avg_time:.1f}s")

    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    summary_file = output_dir / f"summary_{timestamp}.json"

    with open(summary_file, "w") as f:
        json.dump({
            "metadata": {"timestamp": timestamp, "phase1_time": phase1_elapsed},
            "summary": summary,
            "all_scores": all_scores
        }, f, indent=2)

    print(f"\n✓ Results saved: {summary_file}")

    # Determine winner
    if summary:
        winner = max(summary.items(), key=lambda x: x[1]["overall"])
        print("\n" + "=" * 80)
        print(f"🏆 WINNER: {winner[0].upper()}")
        print(f"   Score: {winner[1]['overall']:.2f}/10")
        print(f"   Cost: ${winner[1]['avg_cost']:.4f}")
        print(f"   Time: {winner[1]['avg_time']:.1f}s")
        print("=" * 80)

        # Print ranking
        print("\n📊 FULL RANKING:")
        sorted_summary = sorted(summary.items(), key=lambda x: x[1]["overall"], reverse=True)
        for rank, (name, data) in enumerate(sorted_summary, 1):
            print(f"  {rank}. {name.upper()}: {data['overall']:.2f}/10 | ${data['avg_cost']:.4f} | {data['avg_time']:.1f}s")


if __name__ == "__main__":
    main()
