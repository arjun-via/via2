#!/usr/bin/env python
"""
Direct test runner for Variable Temperature tests.

Demonstrates:
- BEFORE: All agents use temperature=0 (fully deterministic)
- AFTER: Role-specific temperatures for optimal results
  - Context: 0.0 (deterministic file selection)
  - Repro: 0.0 (accurate code generation)
  - Engineering: 0.3 (moderate creativity for fixes)
  - Review: 0.0 (strict pass/fail decisions)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock


def print_test(name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    print(f"  {status}: {name}")
    if details and not passed:
        print(f"         {details}")


def run_tests():
    print("\n" + "=" * 70)
    print("VARIABLE TEMPERATURE - Test Results")
    print("=" * 70)

    passed = 0
    failed = 0

    from alo.agentic_loops.core.temperature import (
        RECOMMENDED_TEMPERATURES,
        TEMPERATURE_RATIONALE,
        TemperatureConfig,
        get_recommended_temperature,
        get_temperature_from_config,
        validate_temperature,
    )

    # =========================================================================
    # TEST GROUP 1: Recommended Temperatures
    # =========================================================================
    print("\n--- Group 1: Recommended Temperatures ---")

    # Test 1.1: Context temperature is 0.0
    try:
        if RECOMMENDED_TEMPERATURES["context"] == 0.0:
            print_test("Context temperature is 0.0 (deterministic)", True)
            passed += 1
        else:
            print_test("Context temperature is 0.0 (deterministic)", False,
                       f"Got {RECOMMENDED_TEMPERATURES['context']}")
            failed += 1
    except Exception as e:
        print_test("Context temperature is 0.0 (deterministic)", False, str(e))
        failed += 1

    # Test 1.2: Repro temperature is 0.0
    try:
        if RECOMMENDED_TEMPERATURES["repro"] == 0.0:
            print_test("Repro temperature is 0.0 (accurate)", True)
            passed += 1
        else:
            print_test("Repro temperature is 0.0 (accurate)", False)
            failed += 1
    except Exception as e:
        print_test("Repro temperature is 0.0 (accurate)", False, str(e))
        failed += 1

    # Test 1.3: Engineering temperature is 0.3
    try:
        if RECOMMENDED_TEMPERATURES["engineering"] == 0.3:
            print_test("Engineering temperature is 0.3 (creative)", True)
            passed += 1
        else:
            print_test("Engineering temperature is 0.3 (creative)", False,
                       f"Got {RECOMMENDED_TEMPERATURES['engineering']}")
            failed += 1
    except Exception as e:
        print_test("Engineering temperature is 0.3 (creative)", False, str(e))
        failed += 1

    # Test 1.4: Review temperature is 0.0
    try:
        if RECOMMENDED_TEMPERATURES["review"] == 0.0:
            print_test("Review temperature is 0.0 (strict)", True)
            passed += 1
        else:
            print_test("Review temperature is 0.0 (strict)", False)
            failed += 1
    except Exception as e:
        print_test("Review temperature is 0.0 (strict)", False, str(e))
        failed += 1

    # Test 1.5: All roles have rationale documented
    try:
        roles = ["context", "repro", "engineering", "review"]
        all_have_rationale = all(r in TEMPERATURE_RATIONALE for r in roles)
        if all_have_rationale:
            print_test("All roles have documented rationale", True)
            passed += 1
        else:
            print_test("All roles have documented rationale", False)
            failed += 1
    except Exception as e:
        print_test("All roles have documented rationale", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 2: TemperatureConfig Class
    # =========================================================================
    print("\n--- Group 2: TemperatureConfig Class ---")

    # Test 2.1: Default config has recommended values
    try:
        config = TemperatureConfig()
        checks = [
            config.context == 0.0,
            config.repro == 0.0,
            config.engineering == 0.3,
            config.review == 0.0,
        ]
        if all(checks):
            print_test("Default TemperatureConfig has recommended values", True)
            passed += 1
        else:
            print_test("Default TemperatureConfig has recommended values", False)
            failed += 1
    except Exception as e:
        print_test("Default TemperatureConfig has recommended values", False, str(e))
        failed += 1

    # Test 2.2: all_zero() preset
    try:
        config = TemperatureConfig.all_zero()
        if config.context == 0.0 and config.engineering == 0.0:
            print_test("all_zero() preset works", True)
            passed += 1
        else:
            print_test("all_zero() preset works", False)
            failed += 1
    except Exception as e:
        print_test("all_zero() preset works", False, str(e))
        failed += 1

    # Test 2.3: creative() preset
    try:
        config = TemperatureConfig.creative()
        if config.engineering == 0.5 and config.repro == 0.1:
            print_test("creative() preset has higher temps", True)
            passed += 1
        else:
            print_test("creative() preset has higher temps", False)
            failed += 1
    except Exception as e:
        print_test("creative() preset has higher temps", False, str(e))
        failed += 1

    # Test 2.4: to_dict() and from_dict()
    try:
        config = TemperatureConfig(engineering=0.5)
        d = config.to_dict()
        restored = TemperatureConfig.from_dict(d)
        if restored.engineering == 0.5:
            print_test("to_dict()/from_dict() roundtrip works", True)
            passed += 1
        else:
            print_test("to_dict()/from_dict() roundtrip works", False)
            failed += 1
    except Exception as e:
        print_test("to_dict()/from_dict() roundtrip works", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 3: Helper Functions
    # =========================================================================
    print("\n--- Group 3: Helper Functions ---")

    # Test 3.1: get_recommended_temperature() works
    try:
        temp = get_recommended_temperature("engineering")
        if temp == 0.3:
            print_test("get_recommended_temperature() retrieves correctly", True)
            passed += 1
        else:
            print_test("get_recommended_temperature() retrieves correctly", False)
            failed += 1
    except Exception as e:
        print_test("get_recommended_temperature() retrieves correctly", False, str(e))
        failed += 1

    # Test 3.2: get_recommended_temperature() raises KeyError for unknown role
    try:
        try:
            get_recommended_temperature("unknown")
            print_test("get_recommended_temperature() raises KeyError for unknown", False)
            failed += 1
        except KeyError:
            print_test("get_recommended_temperature() raises KeyError for unknown", True)
            passed += 1
    except Exception as e:
        print_test("get_recommended_temperature() raises KeyError for unknown", False, str(e))
        failed += 1

    # Test 3.3: get_temperature_from_config() uses config value
    try:
        model_config = {"temperature": 0.7}
        temp = get_temperature_from_config(model_config, "engineering")
        if temp == 0.7:
            print_test("get_temperature_from_config() uses config value", True)
            passed += 1
        else:
            print_test("get_temperature_from_config() uses config value", False)
            failed += 1
    except Exception as e:
        print_test("get_temperature_from_config() uses config value", False, str(e))
        failed += 1

    # Test 3.4: get_temperature_from_config() falls back to recommended
    try:
        model_config = {}  # No temperature key
        temp = get_temperature_from_config(model_config, "engineering", use_recommended=True)
        if temp == 0.3:
            print_test("get_temperature_from_config() falls back to recommended", True)
            passed += 1
        else:
            print_test("get_temperature_from_config() falls back to recommended", False,
                       f"Got {temp}")
            failed += 1
    except Exception as e:
        print_test("get_temperature_from_config() falls back to recommended", False, str(e))
        failed += 1

    # Test 3.5: validate_temperature() clamps to valid range
    try:
        clamped_high = validate_temperature(5.0)
        clamped_low = validate_temperature(-1.0)
        if clamped_high == 2.0 and clamped_low == 0.0:
            print_test("validate_temperature() clamps to 0-2 range", True)
            passed += 1
        else:
            print_test("validate_temperature() clamps to 0-2 range", False)
            failed += 1
    except Exception as e:
        print_test("validate_temperature() clamps to 0-2 range", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 4: Agent Integration
    # =========================================================================
    print("\n--- Group 4: Agent Integration ---")

    # Test 4.1: ContextLoopAgent uses default temperature
    try:
        from alo.agentic_loops.context_loop.agent import ContextLoopAgent

        mock_client = MagicMock()
        agent = ContextLoopAgent(mock_client)

        if agent.temperature == 0.0:
            print_test("ContextLoopAgent defaults to temp=0.0", True)
            passed += 1
        else:
            print_test("ContextLoopAgent defaults to temp=0.0", False,
                       f"Got {agent.temperature}")
            failed += 1
    except Exception as e:
        print_test("ContextLoopAgent defaults to temp=0.0", False, str(e))
        failed += 1

    # Test 4.2: ReproLoopAgent uses default temperature
    try:
        from alo.agentic_loops.repro_loop.agent import ReproLoopAgent

        agent = ReproLoopAgent(MagicMock())

        if agent.temperature == 0.0:
            print_test("ReproLoopAgent defaults to temp=0.0", True)
            passed += 1
        else:
            print_test("ReproLoopAgent defaults to temp=0.0", False)
            failed += 1
    except Exception as e:
        print_test("ReproLoopAgent defaults to temp=0.0", False, str(e))
        failed += 1

    # Test 4.3: EngineeringLoopAgent uses default temperature
    try:
        from alo.agentic_loops.engineering_loop.agent import EngineeringLoopAgent

        agent = EngineeringLoopAgent(MagicMock())

        if agent.temperature == 0.3:
            print_test("EngineeringLoopAgent defaults to temp=0.3", True)
            passed += 1
        else:
            print_test("EngineeringLoopAgent defaults to temp=0.3", False,
                       f"Got {agent.temperature}")
            failed += 1
    except Exception as e:
        print_test("EngineeringLoopAgent defaults to temp=0.3", False, str(e))
        failed += 1

    # Test 4.4: ReviewLoopAgent uses default temperature
    try:
        from alo.agentic_loops.review_loop.agent import ReviewLoopAgent

        agent = ReviewLoopAgent(MagicMock())

        if agent.temperature == 0.0:
            print_test("ReviewLoopAgent defaults to temp=0.0", True)
            passed += 1
        else:
            print_test("ReviewLoopAgent defaults to temp=0.0", False)
            failed += 1
    except Exception as e:
        print_test("ReviewLoopAgent defaults to temp=0.0", False, str(e))
        failed += 1

    # Test 4.5: Custom temperature override works
    try:
        from alo.agentic_loops.context_loop.agent import ContextLoopAgent

        agent = ContextLoopAgent(MagicMock(), temperature=0.5)

        if agent.temperature == 0.5:
            print_test("Custom temperature override works", True)
            passed += 1
        else:
            print_test("Custom temperature override works", False)
            failed += 1
    except Exception as e:
        print_test("Custom temperature override works", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 5: Temperature Passed to Client
    # =========================================================================
    print("\n--- Group 5: Temperature Passed to Client ---")

    # Test 5.1: Context agent passes temperature to chat()
    try:
        from alo.agentic_loops.context_loop.agent import ContextLoopAgent
        from alo.agentic_loops.core.state import LoopState

        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": '{"relevant_files": [], "summary": "test"}'}

        agent = ContextLoopAgent(mock_client, temperature=0.0)
        state = LoopState(issue_description="test", repo_path="/tmp")
        agent.run(state)

        # Verify temperature was passed
        call_kwargs = mock_client.chat.call_args[1]
        if call_kwargs.get("temperature") == 0.0:
            print_test("Context agent passes temperature to chat()", True)
            passed += 1
        else:
            print_test("Context agent passes temperature to chat()", False,
                       f"Got kwargs: {call_kwargs}")
            failed += 1
    except Exception as e:
        print_test("Context agent passes temperature to chat()", False, str(e))
        failed += 1

    # Test 5.2: Engineering agent passes temperature to chat()
    try:
        from alo.agentic_loops.engineering_loop.agent import EngineeringLoopAgent
        from alo.agentic_loops.core.state import LoopState

        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "diff --git..."}

        # Use repro_runner to avoid tool_registry requirement
        agent = EngineeringLoopAgent(
            mock_client,
            temperature=0.3,
            repro_runner=lambda x: True,
        )
        state = LoopState(issue_description="test", repo_path="/tmp")
        state.context_summary = "test context"
        state.relevant_files = []
        agent.run(state)

        # Verify temperature was passed
        call_kwargs = mock_client.chat.call_args[1]
        if call_kwargs.get("temperature") == 0.3:
            print_test("Engineering agent passes temperature to chat()", True)
            passed += 1
        else:
            print_test("Engineering agent passes temperature to chat()", False,
                       f"Got kwargs: {call_kwargs}")
            failed += 1
    except Exception as e:
        print_test("Engineering agent passes temperature to chat()", False, str(e))
        failed += 1

    # Test 5.3: Review agent passes temperature to chat()
    try:
        from alo.agentic_loops.review_loop.agent import ReviewLoopAgent
        from alo.agentic_loops.core.state import LoopState

        mock_client = MagicMock()
        mock_client.chat.return_value = {"content": "PASS"}

        agent = ReviewLoopAgent(mock_client, temperature=0.0)
        state = LoopState(issue_description="test", repo_path="/tmp")
        state.current_patch = "diff --git..."
        agent.run(state)

        # Verify temperature was passed
        call_kwargs = mock_client.chat.call_args[1]
        if call_kwargs.get("temperature") == 0.0:
            print_test("Review agent passes temperature to chat()", True)
            passed += 1
        else:
            print_test("Review agent passes temperature to chat()", False,
                       f"Got kwargs: {call_kwargs}")
            failed += 1
    except Exception as e:
        print_test("Review agent passes temperature to chat()", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 6: Config File Values
    # =========================================================================
    print("\n--- Group 6: Config File Values ---")

    # Test 6.1: config.yaml has variable temperatures
    try:
        import yaml
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "config.yaml"
        )
        with open(config_path) as f:
            config = yaml.safe_load(f)

        temps = {
            "context": config["models"]["context"].get("temperature"),
            "repro": config["models"]["repro"].get("temperature"),
            "engineering": config["models"]["engineering"].get("temperature"),
            "review": config["models"]["review"].get("temperature"),
        }

        # Check that engineering has different temp (0.3)
        if temps["engineering"] == 0.3 and temps["context"] == 0:
            print_test("config.yaml has variable temperatures", True)
            passed += 1
        else:
            print_test("config.yaml has variable temperatures", False,
                       f"Got: {temps}")
            failed += 1
    except Exception as e:
        print_test("config.yaml has variable temperatures", False, str(e))
        failed += 1

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    total = passed + failed
    print(f"SUMMARY: {passed}/{total} tests passed")

    if failed > 0:
        print(f"\n{failed} test(s) FAILED")
        return 1
    else:
        print(f"\nAll {passed} tests PASSED - Variable Temperature working!")

        # Print comparison summary
        print("\n" + "-" * 70)
        print("BEFORE vs AFTER Comparison:")
        print("-" * 70)
        print("  BEFORE: All agents used temperature=0 (fully deterministic)")
        print("  AFTER:  Role-specific temperatures:")
        print(f"    - Context:     {RECOMMENDED_TEMPERATURES['context']} (deterministic file selection)")
        print(f"    - Repro:       {RECOMMENDED_TEMPERATURES['repro']} (accurate code generation)")
        print(f"    - Engineering: {RECOMMENDED_TEMPERATURES['engineering']} (moderate creativity)")
        print(f"    - Review:      {RECOMMENDED_TEMPERATURES['review']} (strict decisions)")
        print("\n  Rationale documented for each role in TEMPERATURE_RATIONALE")
        return 0


if __name__ == "__main__":
    sys.exit(run_tests())
