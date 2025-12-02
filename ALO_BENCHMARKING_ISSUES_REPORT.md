# Summary of Issues for Gemini 3 Pro

## Context
Benchmarking **ALO (Agentic Loops Orchestrator)** - a multi-agent LLM system with 4 configurations on **macOS (M4 Max, 128GB RAM)**.
**Goal:** Evaluate code generation quality with challenging tests to differentiate between configurations.

---

## 1. What We Successfully Did

### ✅ HumanEval Base Tests (164 problems)
*   **Method:** Custom runner `run_humaneval_alo_simple.py` bypassing sandboxing.
*   **Execution:** Tests execute directly with `exec()` (no sandboxing).
*   **Results:** 95.1% - 97.6% pass rates across configurations.
*   **Status:** Works perfectly on macOS.

---

## 2. Critical Bugs Fixed
During the process, we identified and resolved several critical issues:
1.  **Test Execution Bug:** Tests weren't calling the `check()` function, leading to 100% false positives.
2.  **Missing Environment Loading:** `load_dotenv()` was not called, causing authentication failures.
3.  **Wrong Orchestrator Mode:** Initially used a bug-fixing orchestrator instead of the `PromptOrchestrator` intended for code generation.

---

## 3. Failed Approaches (macOS Sandboxing Issues)

### ❌ EvalPlus (HumanEval+)
*   **Description:** HumanEval with 80x more comprehensive tests.
*   **Failure Mode:** All tests timeout immediately.
*   **Error:** `ValueError: current limit exceeds maximum limit` when calling `resource.setrlimit(resource.RLIMIT_AS, ...)`
*   **Root Cause:** macOS **System Integrity Protection (SIP)** blocks `setrlimit` memory manipulation.
*   **Result:** Cannot run standard EvalPlus on macOS without disabling SIP (unsafe/impractical).

### ❌ SWE-bench & LiveCodeBench
*   **Status:** Both encountered similar macOS sandboxing and environment isolation restrictions preventing reliable local execution.

---

## 4. The Core Problem

**HumanEval base tests (164 problems) are TOO EASY.**
*   All configurations score **95-97%**.
*   There is only a **2.5 percentage point spread** between the best and worst configurations.
*   This lack of differentiation makes it impossible to judge improvements.

**EvalPlus would solve this, BUT:**
*   It relies on Linux-specific resource limits for sandboxing.
*   It is completely broken on macOS due to security restrictions.

---

## 5. Technical Constraints

**macOS Security Restrictions:**
*   Cannot use `resource.setrlimit()` for memory limits.
*   Cannot easily sandbox process execution like Linux (cgroups, namespaces) without Docker/VMs.
*   **System Integrity Protection (SIP)** blocks these operations by design.

**Requirements:**
*   Must work on **macOS M4 Max**.
*   Need **harder tests** than base HumanEval.
*   Need **safe execution** of LLM-generated code (or acceptable risk).
*   Need **real differentiation** between configs.

---

## 6. Question for Gemini 3 Pro

**How can we get harder/more comprehensive code generation tests that actually work on macOS?**

**Specific areas for advice:**
1.  **Alternative Benchmarks:** Are there harder benchmarks that don't require Linux-style sandboxing?
2.  **Workarounds:** Is there a way to run EvalPlus on macOS (e.g., patching it to skip sandboxing)?
3.  **Docker/VM:** Is a Docker container the only viable solution, and if so, what is the most lightweight setup for macOS?
4.  **Subset Selection:** Should we focus on a manually curated subset of "hard" HumanEval problems (e.g., #120-163)?
