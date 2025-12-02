# Opus Orchestrator - SWE-bench Bug Fixer

> **System**: Opus Orchestrator (one of three systems in Via2)
> **Type**: Single-model iterative Docker loop
> **Model**: Claude Opus 4.5 (`claude-opus-4-5-20251101`)

## What It Does

The **Opus Orchestrator** is an autonomous software engineering agent that fixes real-world GitHub bugs. It runs Claude Opus 4.5 in an iterative **THINK → ACT → OBSERVE** loop inside Docker containers with the actual repository code.

This is one of three systems in the Via2 repository:
- **ALO**: Multi-model pipeline (Gemini, GPT, GLM, Kimi)
- **Opus Orchestrator**: Single-model Docker loop (this system)
- **Dynamic**: Adaptive model selection with learning

## How It Works

### Core Loop Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    AGENTIC LOOP CYCLE                          │
│                                                                │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────────┐   │
│  │  THINK   │────▶│     ACT      │────▶│    OBSERVE       │   │
│  │  Claude  │     │  Execute ONE │     │  Get real output │   │
│  │  Opus    │     │  bash command│     │  from Docker     │   │
│  └──────────┘     └──────────────┘     └──────────────────┘   │
│       ▲                                         │              │
│       │                                         │              │
│       └─────── Iterate until SUBMIT ────────────┘              │
│                  (12-21 steps typical)                         │
└────────────────────────────────────────────────────────────────┘
```

### Key Technique: One Command Per Response

The critical design principle is **ONE bash command per LLM response**:

```python
# The model outputs:
"Let me check the source file:\n```bash\ncat ./astropy/modeling/separable.py\n```"

# We execute ONLY that command and return REAL output
# Then wait for next response before executing anything else
```

This prevents the model from hallucinating outputs (imagining what commands would return).

### Hallucination Detection

When the model tries to write multiple commands or imagine output, we catch it:

```python
def detect_hallucinated_output(response: str) -> bool:
    # Catches patterns like:
    # ```bash\n...\n```\nOutput: (imagined result)
    # Multiple ```bash``` blocks in one response
    if len(bash_blocks) > 1:
        return True  # REJECT - too many commands
```

### Patch Validation

Before accepting a submission, we verify the patch contains **actual source changes**:

```python
def _validate_patch_has_source_changes(patch: str) -> bool:
    # ACCEPT: astropy/modeling/separable.py
    # REJECT: test_fix.py, reproduce_issue.py
```

---

## Running the Opus Orchestrator

```bash
# Run on 5 random instances
python benchmark/run_opus_agentic.py --num 5 --random --output results.jsonl

# Run on specific number with custom cost limit
python benchmark/run_opus_agentic.py --num 25 --random --seed 2024 --cost-limit 15.0 --output test.jsonl
```

**Key Files:**
- `alo/agentic_loops/opus_orchestrator/agentic_loop.py` - Core `AgenticLoop` class
- `alo/agentic_loops/opus_orchestrator/docker_executor.py` - `DockerExecutor` class
- `benchmark/run_opus_agentic.py` - SWE-bench benchmark runner

---

## Detailed Results (5 Instance Pilot)

| Instance | Problem Type | Steps | Time | Cost | Fix |
|----------|-------------|-------|------|------|-----|
| astropy-12907 | Separability matrix bug | 12 | ~54s | $0.98 | `= 1` → `= right` |
| astropy-13033 | Error message formatting | 16 | ~72s | $1.48 | Multi-line string fix |
| astropy-13236 | Unwanted ndarray conversion | 18 | ~81s | $0.96 | Remove 6 lines |
| astropy-13398 | ITRS coordinate transform | 21 | ~95s | $3.83 | New 102-line module |
| astropy-13453 | HTML format ignored | 17 | ~77s | $2.84 | Add 4 lines |

### Aggregate Metrics

| Metric | Value |
|--------|-------|
| **Patch Generation Rate** | 100% (5/5) |
| **Average Steps** | 16.8 |
| **Average Time** | ~76 seconds |
| **Average Cost** | $2.02 per problem |
| **Average Tokens** | ~60K tokens |
| **Total Cost** | $10.09 for 5 problems |

### Workflow Example (astropy-12907)

The agent's actual 12-step trajectory:

| Step | Action | Purpose |
|------|--------|---------|
| 1 | `find . -name "*.py" -path "*/modeling/*"` | Locate relevant files |
| 2 | `cat ./astropy/modeling/separable.py` | Read source code |
| 3 | `grep -A 20 "nested\|compound"` test file | Understand test patterns |
| 4 | `grep -n "Pix2Sky_TAN"` | Find specific usage |
| 5 | Create `reproduce_issue.py` | Write reproduction script |
| 6 | `python reproduce_issue.py` | Confirm bug exists |
| 7 | `grep -A 30 "def _cstack"` | Analyze buggy function |
| 8 | `sed -i 's/= 1/= right/g'` | **FIX THE BUG** |
| 9 | `grep -A5 "cright\[-right.shape"` | Verify edit applied |
| 10 | `python reproduce_issue.py` | Confirm fix works |
| 11 | `git add -A && git diff --cached` | Generate patch |
| 12 | `SUBMIT` | Done |

**Time breakdown**: ~54 seconds total, ~4.5s per step average

---

## System Prompt

The key prompt rules that make this work:

```
CRITICAL RULES:
1. ONLY write ONE bash command per response
2. WAIT for the actual output - DO NOT imagine/hallucinate command output
3. You MUST edit actual source files (not test files) to fix the bug
4. DO NOT submit until you have modified source code files

FORBIDDEN:
- DO NOT write test_*.py files as your fix
- DO NOT hallucinate command output
- DO NOT submit without editing source files
```

---

## Cost Analysis

Using Claude Opus 4.5 pricing ($15/M input, $75/M output):

| Problem Complexity | Steps | Tokens | Cost |
|-------------------|-------|--------|------|
| Simple (1-line fix) | 10-15 | ~45K | ~$1.00 |
| Medium (multi-file) | 15-20 | ~60K | ~$2.00 |
| Complex (new module) | 20-25 | ~80K | ~$4.00 |

Projected full benchmark (500 instances): **~$1,000-1,500**

---

## Comparison with Other Systems

| System | Model(s) | Approach | SWE-bench Target |
|--------|----------|----------|------------------|
| **Opus Orchestrator** | Claude Opus 4.5 | Single-model Docker loop | 75%+ |
| **ALO** | Gemini, GPT, GLM, Kimi | Multi-model pipeline | 33% baseline |
| **Dynamic** | Multiple (dynamic) | Adaptive selection | Cost-optimized |

---

*Last Updated: 2025-11-28 | Model: Claude Opus 4.5 (`claude-opus-4-5-20251101`)*
