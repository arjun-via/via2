#!/usr/bin/env python
"""
Direct test runner for Structured Prompts tests.

Demonstrates:
- BEFORE: Minimal one-liner prompts with no structure
- AFTER: Rich prompts with JSON schema, examples, guidelines
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_test(name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    print(f"  {status}: {name}")
    if details and not passed:
        print(f"         {details}")


def run_tests():
    print("\n" + "=" * 70)
    print("STRUCTURED PROMPTS - Test Results")
    print("=" * 70)

    passed = 0
    failed = 0

    from alo.agentic_loops.core.prompts import (
        CONTEXT_PROMPT,
        REPRO_PROMPT,
        ENGINEERING_PROMPT,
        REVIEW_PROMPT,
        STRUCTURED_PROMPTS,
        get_structured_prompt,
    )

    # =========================================================================
    # TEST GROUP 1: Prompt Registry
    # =========================================================================
    print("\n--- Group 1: Prompt Registry ---")

    # Test 1.1: All prompts are registered
    try:
        expected_keys = {"context", "repro", "engineering", "review"}
        actual_keys = set(STRUCTURED_PROMPTS.keys())
        if expected_keys == actual_keys:
            print_test("All prompts registered in STRUCTURED_PROMPTS", True)
            passed += 1
        else:
            print_test("All prompts registered in STRUCTURED_PROMPTS", False,
                       f"Missing: {expected_keys - actual_keys}")
            failed += 1
    except Exception as e:
        print_test("All prompts registered in STRUCTURED_PROMPTS", False, str(e))
        failed += 1

    # Test 1.2: get_structured_prompt() retrieves correctly
    try:
        context = get_structured_prompt("context")
        if context == CONTEXT_PROMPT:
            print_test("get_structured_prompt() retrieves correct prompt", True)
            passed += 1
        else:
            print_test("get_structured_prompt() retrieves correct prompt", False)
            failed += 1
    except Exception as e:
        print_test("get_structured_prompt() retrieves correct prompt", False, str(e))
        failed += 1

    # Test 1.3: get_structured_prompt() raises KeyError for invalid type
    try:
        try:
            get_structured_prompt("invalid_type")
            print_test("get_structured_prompt() raises KeyError for invalid type", False)
            failed += 1
        except KeyError as e:
            if "invalid_type" in str(e):
                print_test("get_structured_prompt() raises KeyError for invalid type", True)
                passed += 1
            else:
                print_test("get_structured_prompt() raises KeyError for invalid type", False)
                failed += 1
    except Exception as e:
        print_test("get_structured_prompt() raises KeyError for invalid type", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 2: Context Prompt Structure
    # =========================================================================
    print("\n--- Group 2: Context Prompt Structure ---")

    # Test 2.1: Has role definition
    try:
        if "Context Librarian" in CONTEXT_PROMPT:
            print_test("Context prompt has role definition", True)
            passed += 1
        else:
            print_test("Context prompt has role definition", False)
            failed += 1
    except Exception as e:
        print_test("Context prompt has role definition", False, str(e))
        failed += 1

    # Test 2.2: Has JSON schema
    try:
        if "relevant_files" in CONTEXT_PROMPT and "summary" in CONTEXT_PROMPT and '```json' in CONTEXT_PROMPT:
            print_test("Context prompt has JSON output schema", True)
            passed += 1
        else:
            print_test("Context prompt has JSON output schema", False)
            failed += 1
    except Exception as e:
        print_test("Context prompt has JSON output schema", False, str(e))
        failed += 1

    # Test 2.3: Has selection criteria
    try:
        if "SELECTION CRITERIA" in CONTEXT_PROMPT and "priority" in CONTEXT_PROMPT.lower():
            print_test("Context prompt has prioritized selection criteria", True)
            passed += 1
        else:
            print_test("Context prompt has prioritized selection criteria", False)
            failed += 1
    except Exception as e:
        print_test("Context prompt has prioritized selection criteria", False, str(e))
        failed += 1

    # Test 2.4: Has example
    try:
        if "EXAMPLE" in CONTEXT_PROMPT and "Race condition" in CONTEXT_PROMPT:
            print_test("Context prompt has worked example", True)
            passed += 1
        else:
            print_test("Context prompt has worked example", False)
            failed += 1
    except Exception as e:
        print_test("Context prompt has worked example", False, str(e))
        failed += 1

    # Test 2.5: Has limits section
    try:
        if "LIMITS" in CONTEXT_PROMPT and "Maximum 8" in CONTEXT_PROMPT:
            print_test("Context prompt specifies limits", True)
            passed += 1
        else:
            print_test("Context prompt specifies limits", False)
            failed += 1
    except Exception as e:
        print_test("Context prompt specifies limits", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 3: Repro Prompt Structure
    # =========================================================================
    print("\n--- Group 3: Repro Prompt Structure ---")

    # Test 3.1: Has role definition
    try:
        if "Reproduction" in REPRO_PROMPT:
            print_test("Repro prompt has role definition", True)
            passed += 1
        else:
            print_test("Repro prompt has role definition", False)
            failed += 1
    except Exception as e:
        print_test("Repro prompt has role definition", False, str(e))
        failed += 1

    # Test 3.2: Has JSON output format
    try:
        if '"script"' in REPRO_PROMPT and '```json' in REPRO_PROMPT:
            print_test("Repro prompt has JSON output schema", True)
            passed += 1
        else:
            print_test("Repro prompt has JSON output schema", False)
            failed += 1
    except Exception as e:
        print_test("Repro prompt has JSON output schema", False, str(e))
        failed += 1

    # Test 3.3: Has script requirements
    try:
        requirements = ["Self-contained", "Exit code", "Timeout"]
        has_requirements = all(r in REPRO_PROMPT for r in requirements)
        if has_requirements:
            print_test("Repro prompt has script requirements", True)
            passed += 1
        else:
            print_test("Repro prompt has script requirements", False)
            failed += 1
    except Exception as e:
        print_test("Repro prompt has script requirements", False, str(e))
        failed += 1

    # Test 3.4: Has script template
    try:
        if "SCRIPT TEMPLATE" in REPRO_PROMPT and "def main():" in REPRO_PROMPT:
            print_test("Repro prompt has script template", True)
            passed += 1
        else:
            print_test("Repro prompt has script template", False)
            failed += 1
    except Exception as e:
        print_test("Repro prompt has script template", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 4: Engineering Prompt Structure
    # =========================================================================
    print("\n--- Group 4: Engineering Prompt Structure ---")

    # Test 4.1: Has role definition
    try:
        if "Code Engineer" in ENGINEERING_PROMPT:
            print_test("Engineering prompt has role definition", True)
            passed += 1
        else:
            print_test("Engineering prompt has role definition", False)
            failed += 1
    except Exception as e:
        print_test("Engineering prompt has role definition", False, str(e))
        failed += 1

    # Test 4.2: Has diff format specification
    try:
        if "unified diff" in ENGINEERING_PROMPT.lower() or "patch -p1" in ENGINEERING_PROMPT:
            print_test("Engineering prompt specifies diff format", True)
            passed += 1
        else:
            print_test("Engineering prompt specifies diff format", False)
            failed += 1
    except Exception as e:
        print_test("Engineering prompt specifies diff format", False, str(e))
        failed += 1

    # Test 4.3: Has patch requirements
    try:
        requirements = ["Minimal changes", "Backward compatible", "Error handling"]
        has_requirements = all(r in ENGINEERING_PROMPT for r in requirements)
        if has_requirements:
            print_test("Engineering prompt has patch requirements", True)
            passed += 1
        else:
            print_test("Engineering prompt has patch requirements", False)
            failed += 1
    except Exception as e:
        print_test("Engineering prompt has patch requirements", False, str(e))
        failed += 1

    # Test 4.4: Has common patterns section
    try:
        if "COMMON PATTERNS" in ENGINEERING_PROMPT and "Null checks" in ENGINEERING_PROMPT:
            print_test("Engineering prompt has common patterns", True)
            passed += 1
        else:
            print_test("Engineering prompt has common patterns", False)
            failed += 1
    except Exception as e:
        print_test("Engineering prompt has common patterns", False, str(e))
        failed += 1

    # Test 4.5: Has format placeholders
    try:
        placeholders = ["{issue}", "{context}", "{files}", "{code}"]
        has_placeholders = all(p in ENGINEERING_PROMPT for p in placeholders)
        if has_placeholders:
            print_test("Engineering prompt has all required placeholders", True)
            passed += 1
        else:
            print_test("Engineering prompt has all required placeholders", False)
            failed += 1
    except Exception as e:
        print_test("Engineering prompt has all required placeholders", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 5: Review Prompt Structure
    # =========================================================================
    print("\n--- Group 5: Review Prompt Structure ---")

    # Test 5.1: Has role definition
    try:
        if "Code Reviewer" in REVIEW_PROMPT:
            print_test("Review prompt has role definition", True)
            passed += 1
        else:
            print_test("Review prompt has role definition", False)
            failed += 1
    except Exception as e:
        print_test("Review prompt has role definition", False, str(e))
        failed += 1

    # Test 5.2: Has review checklist
    try:
        if "REVIEW CHECKLIST" in REVIEW_PROMPT:
            print_test("Review prompt has review checklist", True)
            passed += 1
        else:
            print_test("Review prompt has review checklist", False)
            failed += 1
    except Exception as e:
        print_test("Review prompt has review checklist", False, str(e))
        failed += 1

    # Test 5.3: Has security checks
    try:
        security_checks = ["sql injection", "command injection", "path traversal"]
        has_security = all(s in REVIEW_PROMPT.lower() for s in security_checks)
        if has_security:
            print_test("Review prompt has security checks", True)
            passed += 1
        else:
            print_test("Review prompt has security checks", False)
            failed += 1
    except Exception as e:
        print_test("Review prompt has security checks", False, str(e))
        failed += 1

    # Test 5.4: Has PASS/FAIL examples
    try:
        if "PASS example" in REVIEW_PROMPT and "FAIL examples" in REVIEW_PROMPT:
            print_test("Review prompt has PASS/FAIL examples", True)
            passed += 1
        else:
            print_test("Review prompt has PASS/FAIL examples", False)
            failed += 1
    except Exception as e:
        print_test("Review prompt has PASS/FAIL examples", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 6: Agent Integration
    # =========================================================================
    print("\n--- Group 6: Agent Integration ---")

    # Test 6.1: ContextLoopAgent uses structured prompt
    try:
        from alo.agentic_loops.context_loop.agent import ContextLoopAgent
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        agent = ContextLoopAgent(mock_client)

        if agent.prompt_template == CONTEXT_PROMPT:
            print_test("ContextLoopAgent uses structured prompt by default", True)
            passed += 1
        else:
            print_test("ContextLoopAgent uses structured prompt by default", False)
            failed += 1
    except Exception as e:
        print_test("ContextLoopAgent uses structured prompt by default", False, str(e))
        failed += 1

    # Test 6.2: ReproLoopAgent uses structured prompt
    try:
        from alo.agentic_loops.repro_loop.agent import ReproLoopAgent

        agent = ReproLoopAgent(MagicMock())

        if agent.prompt_template == REPRO_PROMPT:
            print_test("ReproLoopAgent uses structured prompt by default", True)
            passed += 1
        else:
            print_test("ReproLoopAgent uses structured prompt by default", False)
            failed += 1
    except Exception as e:
        print_test("ReproLoopAgent uses structured prompt by default", False, str(e))
        failed += 1

    # Test 6.3: EngineeringLoopAgent uses structured prompt
    try:
        from alo.agentic_loops.engineering_loop.agent import EngineeringLoopAgent

        agent = EngineeringLoopAgent(MagicMock())

        if agent.prompt_template == ENGINEERING_PROMPT:
            print_test("EngineeringLoopAgent uses structured prompt by default", True)
            passed += 1
        else:
            print_test("EngineeringLoopAgent uses structured prompt by default", False)
            failed += 1
    except Exception as e:
        print_test("EngineeringLoopAgent uses structured prompt by default", False, str(e))
        failed += 1

    # Test 6.4: ReviewLoopAgent uses structured prompt
    try:
        from alo.agentic_loops.review_loop.agent import ReviewLoopAgent

        agent = ReviewLoopAgent(MagicMock())

        if agent.prompt_template == REVIEW_PROMPT:
            print_test("ReviewLoopAgent uses structured prompt by default", True)
            passed += 1
        else:
            print_test("ReviewLoopAgent uses structured prompt by default", False)
            failed += 1
    except Exception as e:
        print_test("ReviewLoopAgent uses structured prompt by default", False, str(e))
        failed += 1

    # Test 6.5: Custom prompt override still works
    try:
        custom_prompt = "Custom test prompt: {issue}"
        agent = ContextLoopAgent(MagicMock(), prompt_template=custom_prompt)

        if agent.prompt_template == custom_prompt:
            print_test("Custom prompt override still works", True)
            passed += 1
        else:
            print_test("Custom prompt override still works", False)
            failed += 1
    except Exception as e:
        print_test("Custom prompt override still works", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 7: Prompt Quality Metrics (Before vs After)
    # =========================================================================
    print("\n--- Group 7: Prompt Quality Metrics ---")

    # Define old (minimal) prompts for comparison
    OLD_PROMPTS = {
        "context": (
            "You are the context librarian. Given an issue description, propose relevant files "
            "and a short context summary as JSON with keys relevant_files and summary.\n"
            "Issue: {issue}"
        ),
        "repro": 'Write a Python reproduction script for the issue as JSON {{"script": "..."}}.\nIssue: {issue}',
        "engineering": (
            "You are the builder. Propose a patch for the issue.\n"
            "Issue: {issue}\nContext: {context}\nRelevant files: {files}\n\nRelevant code:\n{code}"
        ),
        "review": (
            "Review the following patch. Reply with PASS if acceptable, otherwise FAIL.\n"
            "If FAIL, explain what needs to be fixed.\n"
            "Issue: {issue}\nPatch:\n{patch}"
        ),
    }

    # Test 7.1: New prompts are significantly longer (more detailed)
    try:
        old_total = sum(len(p) for p in OLD_PROMPTS.values())
        new_total = sum(len(p) for p in STRUCTURED_PROMPTS.values())

        # New prompts should be at least 5x longer (more detailed)
        ratio = new_total / old_total
        if ratio >= 5:
            print_test(f"New prompts are {ratio:.1f}x more detailed than old", True)
            passed += 1
        else:
            print_test(f"New prompts are {ratio:.1f}x more detailed (expected 5x+)", False)
            failed += 1
    except Exception as e:
        print_test("New prompts are more detailed", False, str(e))
        failed += 1

    # Test 7.2: New prompts have structured sections
    try:
        section_markers = ["###", "**", "```"]
        for name, prompt in STRUCTURED_PROMPTS.items():
            has_sections = any(marker in prompt for marker in section_markers)
            if not has_sections:
                print_test("All new prompts have structured sections", False,
                           f"{name} lacks section markers")
                failed += 1
                break
        else:
            print_test("All new prompts have structured sections", True)
            passed += 1
    except Exception as e:
        print_test("All new prompts have structured sections", False, str(e))
        failed += 1

    # Test 7.3: All prompts contain examples
    try:
        for name, prompt in STRUCTURED_PROMPTS.items():
            if "EXAMPLE" not in prompt.upper():
                print_test("All new prompts contain examples", False,
                           f"{name} lacks examples")
                failed += 1
                break
        else:
            print_test("All new prompts contain examples", True)
            passed += 1
    except Exception as e:
        print_test("All new prompts contain examples", False, str(e))
        failed += 1

    # Test 7.4: Count key structural elements
    try:
        elements = {
            "Role definitions": 0,
            "Output formats": 0,
            "Examples": 0,
            "Guidelines": 0,
        }

        for prompt in STRUCTURED_PROMPTS.values():
            prompt_lower = prompt.lower()
            if "you are" in prompt_lower:
                elements["Role definitions"] += 1
            if "output format" in prompt_lower or "```json" in prompt or "```diff" in prompt:
                elements["Output formats"] += 1
            if "example" in prompt_lower:
                elements["Examples"] += 1
            # Guidelines can be expressed as "not", "don't", "should", "must", "requirements"
            if any(g in prompt_lower for g in ["not ", "don't", "should", "must", "requirements"]):
                elements["Guidelines"] += 1

        # All 4 prompts should have all elements
        all_present = all(count == 4 for count in elements.values())
        if all_present:
            print_test("All prompts have role, format, examples, and guidelines", True)
            passed += 1
        else:
            missing = [k for k, v in elements.items() if v < 4]
            print_test("All prompts have role, format, examples, and guidelines", False,
                       f"Missing in some: {missing}")
            failed += 1
    except Exception as e:
        print_test("All prompts have all structural elements", False, str(e))
        failed += 1

    # =========================================================================
    # TEST GROUP 8: Format Compatibility
    # =========================================================================
    print("\n--- Group 8: Format Compatibility ---")

    # Test 8.1: Context prompt can be formatted
    try:
        formatted = CONTEXT_PROMPT.format(issue="Test issue description")
        if "Test issue description" in formatted:
            print_test("Context prompt format() works correctly", True)
            passed += 1
        else:
            print_test("Context prompt format() works correctly", False)
            failed += 1
    except Exception as e:
        print_test("Context prompt format() works correctly", False, str(e))
        failed += 1

    # Test 8.2: Repro prompt can be formatted
    try:
        formatted = REPRO_PROMPT.format(issue="Test issue description")
        if "Test issue description" in formatted:
            print_test("Repro prompt format() works correctly", True)
            passed += 1
        else:
            print_test("Repro prompt format() works correctly", False)
            failed += 1
    except Exception as e:
        print_test("Repro prompt format() works correctly", False, str(e))
        failed += 1

    # Test 8.3: Engineering prompt can be formatted
    try:
        formatted = ENGINEERING_PROMPT.format(
            issue="Test issue",
            context="Test context",
            files="file1.py, file2.py",
            code="# code here"
        )
        if all(x in formatted for x in ["Test issue", "Test context", "file1.py"]):
            print_test("Engineering prompt format() works correctly", True)
            passed += 1
        else:
            print_test("Engineering prompt format() works correctly", False)
            failed += 1
    except Exception as e:
        print_test("Engineering prompt format() works correctly", False, str(e))
        failed += 1

    # Test 8.4: Review prompt can be formatted
    try:
        formatted = REVIEW_PROMPT.format(issue="Test issue", patch="diff --git...")
        if "Test issue" in formatted and "diff --git" in formatted:
            print_test("Review prompt format() works correctly", True)
            passed += 1
        else:
            print_test("Review prompt format() works correctly", False)
            failed += 1
    except Exception as e:
        print_test("Review prompt format() works correctly", False, str(e))
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
        print(f"\nAll {passed} tests PASSED - Structured Prompts working!")

        # Print comparison summary
        print("\n" + "-" * 70)
        print("BEFORE vs AFTER Comparison:")
        print("-" * 70)
        old_total = sum(len(p) for p in OLD_PROMPTS.values())
        new_total = sum(len(p) for p in STRUCTURED_PROMPTS.values())
        print(f"  Old prompts total:  {old_total:5d} chars")
        print(f"  New prompts total:  {new_total:5d} chars")
        print(f"  Improvement ratio:  {new_total / old_total:.1f}x more detailed")
        print("\nNew prompts now include:")
        print("  - Clear role definitions")
        print("  - JSON/diff output schemas")
        print("  - Worked examples")
        print("  - Prioritized criteria and checklists")
        print("  - Explicit limits and guidelines")
        print("  - Security review checks")
        return 0


if __name__ == "__main__":
    sys.exit(run_tests())
