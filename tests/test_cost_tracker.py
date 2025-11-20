from concurrent.futures import ThreadPoolExecutor

from alo.agentic_loops.core.costs import CostTracker


def test_cost_tracker_accumulates_and_resets():
    tracker = CostTracker.get_instance()
    tracker.reset()

    tracker.record(
        model="gpt-test",
        prompt_tokens=100,
        completion_tokens=50,
        prompt_cost_per_1k=0.1,
        completion_cost_per_1k=0.2,
    )
    tracker.record(
        model="gpt-test",
        prompt_tokens=10,
        completion_tokens=5,
        prompt_cost_per_1k=0.1,
        completion_cost_per_1k=0.2,
    )

    summary = tracker.summary()
    assert summary["by_model"]["gpt-test"]["prompt_tokens"] == 110
    assert summary["by_model"]["gpt-test"]["completion_tokens"] == 55
    assert round(summary["by_model"]["gpt-test"]["cost"], 4) == round(
        (110 / 1000) * 0.1 + (55 / 1000) * 0.2, 4
    )

    tracker.reset()
    summary = tracker.summary()
    assert summary["total_cost"] == 0
    assert summary["by_model"] == {}


def test_cost_tracker_thread_safety():
    tracker = CostTracker.get_instance()
    tracker.reset()

    def _inc():
        tracker.record(
            model="thread",
            prompt_tokens=1,
            completion_tokens=1,
            prompt_cost_per_1k=1,
            completion_cost_per_1k=1,
        )

    with ThreadPoolExecutor(max_workers=10) as executor:
        for _ in range(50):
            executor.submit(_inc)

    summary = tracker.summary()
    assert summary["by_model"]["thread"]["prompt_tokens"] == 50
    assert summary["by_model"]["thread"]["completion_tokens"] == 50
