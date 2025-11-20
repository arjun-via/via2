# Project Specification: Agentic Loops Orchestrator (ALO)

## 1. Executive Summary
**Agentic Loops Orchestrator (ALO)** is a next-generation autonomous software engineering agent that replaces the traditional linear "waterfall" LLM pipeline with a dynamic, iterative **Loop Architecture**. 

By assigning specialized State-of-the-Art (SOTA) models to distinct roles (Context, Reproduction, Engineering, Review) and allowing them to loop autonomously until success, ALO achieves **2x faster execution** and **higher reliability** than single-model baselines (e.g., Claude Sonnet 4.5 alone).

## 2. Core Architecture
The system is composed of an **Orchestrator** managing a shared **LoopState**, which is passed through four specialized **Agentic Loops**.

### The 5 Roles
0.  **🧠 Orchestrator (The Manager)**
    *   **Model:** `Claude Sonnet 4.5` (Anthropic Direct)
    *   **Role:** The high-level planner and decision maker. It analyzes the initial user request, decomposes complex tasks, manages the `LoopState`, and coordinates the handoffs between the specialized loops. It ensures the overall goal is met.
    *   **Superpower:** Balanced reasoning, planning, and "Executive Function".

1.  **🔍 Context Loop (The Librarian)**
    *   **Model:** `Gemini 3` (Google Direct)
    *   **Role:** Ingests the entire repository, identifies relevant files, and produces a "Context Map" explaining the bug's location and dependencies.
    *   **Superpower:** Massive context window (1M+ tokens).

2.  **🧪 Reproduction Loop (The Scientist)**
    *   **Model:** `GPT-5.1` (OpenAI Direct)
    *   **Role:** Creates a standalone reproduction script (`reproduce_issue.py`) that fails *only* when the bug is present. Iterates until the script reliably reproduces the issue.
    *   **Superpower:** Superior logical reasoning and test design.

3.  **🛠️ Engineering Loop (The Builder)**
    *   **Model:** `GLM-4.6` (Cerebras/OpenAI Compatible)
    *   **Role:** Reads the code and the reproduction script, plans a fix, and applies edits. Runs the reproduction script to verify the fix.
    *   **Superpower:** Fast, high-quality code generation and instruction following.

4.  **👀 Review Loop (The Auditor)**
    *   **Model:** `Kimi K2` (OpenRouter/Groq)
    *   **Role:** Strict code reviewer. Checks the "fix" against security best practices (SQLi, XSS) and logic correctness. Can **reject** a fix, sending the Engineering Loop back to work.
    *   **Superpower:** Critical analysis and "Refusal to Hallucinate" success.

### Data Flow
`Issue Description` -> **Orchestrator (Plan)** -> **Context Loop** -> `Context Map` -> **Repro Loop** -> `Repro Script` -> **Engineering Loop** <-> **Review Loop** -> `Final Fix` -> **Orchestrator (Verify & Report)**

## 3. Technical Specifications

### 3.1 Tech Stack
*   **Language:** Python 3.10+
*   **Environment Management:** `dotenv` for API keys.
*   **LLM Clients:**
    *   `openai` (Standard client for GPT-5, GLM-4, Kimi).
    *   `google.generativeai` (Native SDK for Gemini).
*   **Tools:** Custom `ToolRegistry` providing:
    *   `list_files`, `read_file`, `write_file`
    *   `run_command` (shell execution)
    *   `grep_search`

### 3.2 Directory Structure
```
alo/
├── agentic_loops/
│   ├── core/
│   │   ├── orchestrator.py  # Main workflow logic
│   │   ├── state.py         # LoopState dataclass
│   │   └── tools.py         # ToolRegistry
│   ├── context_loop/
│   │   └── agent.py         # Gemini 3 Agent
│   ├── repro_loop/
│   │   └── agent.py         # GPT-5.1 Agent
│   ├── engineering_loop/
│   │   └── agent.py         # GLM-4.6 Agent
│   └── review_loop/
│       └── agent.py         # Kimi K2 Agent
├── backend/
│   └── clients/             # API Client wrappers
├── main.py                  # CLI Entry point
├── .env                     # API Keys
└── requirements.txt
```

### 3.3 Key Components

#### `LoopState`
A dataclass that persists across loops:
*   `issue_description`: str
*   `repo_path`: str
*   `relevant_files`: List[str]
*   `context_summary`: str (The Context Map)
*   `repro_script_content`: str
*   `repro_success`: bool
*   `history`: List[Dict] (Audit log of all steps)

#### `ToolRegistry`
Must implement a secure-ish interface for agents to interact with the filesystem.
*   **Crucial:** Agents must be able to see the output of their commands (stdout/stderr).

## 4. Implementation Guide (Step-by-Step)

### Phase 1: Foundation
1.  **Setup:** Create directory structure and `requirements.txt` (openai, google-generativeai, python-dotenv).
2.  **Clients:** Implement `OpenAICompatibleClient` (handling `extra_body` for OpenRouter/Cerebras) and `GeminiClient`.
3.  **Tools:** Implement `ToolRegistry` with the 5 core tools.

### Phase 2: The Agents
4.  **Context Agent:** Implement `ContextLoopAgent`. Use Gemini's long context to analyze file structure.
5.  **Repro Agent:** Implement `ReproLoopAgent`. Use a ReAct loop (Think -> Act -> Observe) to write and run `reproduce_issue.py`.
6.  **Review Agent:** Implement `ReviewLoopAgent`. Simple "Read diff -> Pass/Fail" logic.
7.  **Engineering Agent:** Implement `EngineeringLoopAgent`. The most complex loop. It must:
    *   Read code.
    *   Write fix.
    *   Run repro script.
    *   **Call Review Agent** before declaring success.
    *   Loop back if Review fails or Test fails.

### Phase 3: Orchestration
8.  **Orchestrator:** Wire them together in `run_pipeline`.
9.  **CLI:** Create `main.py` that accepts an issue description and a target repo path.

### Phase 4: Production Readiness (Crucial)
10. **Observability:** Implement structured logging (not just `print`). Every step, tool call, and model response must be logged to `alo.log` and a JSONL trace file.
11. **Cost Tracking:** Implement a `CostTracker` singleton that intercepts all client calls, counts tokens, and calculates cost based on model pricing. Report total cost at the end of the run.
12. **Configuration:** Move all model IDs, temperature settings, and system prompts into `config.yaml` so they can be tuned without code changes.
13. **Benchmarks:** Port the `benchmark/` directory (Race Condition, SQL Injection) into the new repo to ensure no regression.

## 5. Success Criteria
*   **Speed:** Should solve complex logic bugs (e.g., Race Conditions) in < 60 seconds.
*   **Reliability:** Must pass 100% of "SWE-bench Lite" style challenges (specifically SQL Injection and Async Logic).
*   **Cost:** Should be cheaper than a brute-force "Devin" style agent by using cheaper models (GLM/Gemini) for the heavy lifting.
*   **Observability:** Must provide a clear trace of *why* a decision was made.

## 6. README.md Draft
(See below for the content to put in the new repo's README)

---

# Agentic Loops Orchestrator (ALO) 🚀

ALO is an autonomous coding agent architecture that uses a team of specialized LLMs to solve complex software engineering tasks faster and more reliably than single-model agents.

## 🤖 The Team
*   **Manager (Claude Sonnet 4.5):** Plans the work and coordinates the agents.
*   **Librarian (Gemini 3):** Reads the whole repo to understand context.
*   **Scientist (GPT-5.1):** Writes reproduction scripts to prove bugs exist.
*   **Builder (GLM-4.6):** Writes the code to fix the bugs.
*   **Auditor (Kimi K2):** Reviews the code for security and correctness.

## ⚡ Quick Start

1.  **Clone & Install:**
    ```bash
    git clone https://github.com/your-org/alo.git
    cd alo
    pip install -r requirements.txt
    ```

2.  **Configure Keys:**
    Copy `.env.example` to `.env` and add your keys:
    ```
    GEMINI_API_KEY=...
    OPENAI_API_KEY=...
    CEREBRAS_API_KEY=...
    OPENROUTER_API_KEY=...
    ```

3.  **Run:**
    ```bash
    python main.py --issue "Fix the race condition in cache.py" --repo /path/to/target/repo
    ```

## 🏗️ Architecture
ALO uses a **Stateful Loop** architecture. Instead of a single linear chain, agents enter autonomous loops where they can iterate (Think -> Code -> Test -> Refine) until they satisfy their specific exit criteria.

## 📊 Benchmarks
| Challenge | ALO Time | Baseline (Sonnet) Time |
|-----------|----------|------------------------|
| Race Cond | **50s**  | 93s                    |
| SQL Inject| **38s**  | 85s                    |

---
