# Via2 Benchmark Suite

Comprehensive evaluation framework for the three Via2 agent systems.

## Three Systems

| System | Description | Entry Point | Best For |
|--------|-------------|-------------|----------|
| **ALO** | Multi-model pipeline (Gemini→GPT→GLM→Kimi) | `python main.py` | Complex multi-step tasks |
| **Opus Orchestrator** | Single-model Docker loop (Opus 4.5) | `python benchmark/run_opus_agentic.py` | SWE-bench bug fixes |
| **Dynamic** | Adaptive model selection | Config-based | Cost-optimized execution |

---

## Running Benchmarks

### Opus Orchestrator (SWE-bench)

```bash
# Run 5 random instances
python benchmark/run_opus_agentic.py --num 5 --random --output results.jsonl

# Run 25 with specific seed
python benchmark/run_opus_agentic.py --num 25 --random --seed 2024 --cost-limit 15.0 --output test.jsonl

# Run sequential
python benchmark/run_opus_agentic.py --num 10 --start 0 --output sequential.jsonl
```

### ALO System (General Benchmarks)

```bash
# Run prompt benchmark
python benchmark/run_benchmark.py --prompts all

# Run specific prompts
python benchmark/run_benchmark.py --prompts "01_sharpe_ratio,02_websocket_server"
```

### Dynamic System

Uses configuration files in `config/config_opus_meta_*.yaml`

---

## Prerequisites

```bash
# Install dependencies
pip install anthropic datasets docker

# Set environment variables in .env
ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...
GEMINI_API_KEY=...
CEREBRAS_API_KEY=...
```

---

## Benchmark Structure

### SWE-bench Benchmarks (Opus Orchestrator)

Uses `princeton-nlp/SWE-bench_Verified` dataset (500 instances).

**Output Structure:**
```
opus_agentic_results.jsonl              # Predictions (SWE-bench format)
opus_agentic_results_trajectories/      # Detailed trajectories
├── astropy__astropy-12907.traj.json
├── django__django-11299.traj.json
└── ...
```

### Prompt Benchmarks (ALO)

10 diverse prompts across categories:
1. **Code Generation**: Python, Node.js, Rust
2. **Bug Fixing**: Threading, SQL optimization
3. **Architecture**: System design
4. **Refactoring**: Legacy code cleanup

**Output Structure:**
```
benchmark/results/run_TIMESTAMP/
├── summary.json
├── report.md
├── 01_sharpe_ratio/
│   ├── alo_output.txt
│   ├── sonnet_context_output.txt
│   └── evaluation.json
└── ...
```

---

## Key Metrics

### Opus Orchestrator Metrics
- **Patch Rate**: % instances with generated patches
- **Resolution Rate**: % instances passing SWE-bench evaluation
- **Cost per Instance**: ~$2/instance average
- **Steps per Instance**: 12-21 typical

### ALO Metrics
- **Quality Score**: 1-10 from o3-mini judge
- **Cost**: USD per response
- **Cost-Efficiency**: $ per quality point
- **Win Rate**: % of prompts where system won

---

## Evaluation

### SWE-bench Evaluation
```bash
# Run evaluation harness
python -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Verified \
    --predictions_path results.jsonl \
    --max_workers 8 \
    --run_id my_eval
```

### Report Generation
```bash
# After benchmark completes
python benchmark/analysis/report_generator.py benchmark/results/run_TIMESTAMP
```

---

## Adding New Benchmarks

### New SWE-bench Run
Edit `benchmark/run_opus_agentic.py`:
- `--num`: Number of instances
- `--random`: Random vs sequential selection
- `--seed`: Reproducibility seed
- `--cost-limit`: Max cost per instance

### New Prompt
Create YAML in `benchmark/prompts/`:
```yaml
id: "11_new_prompt"
category: "code_generation"
title: "Short Title"
prompt: |
  Full prompt text...
```

---

## Configuration

### Opus Orchestrator Config
- Model: `claude-opus-4-5-20251101`
- Max steps: 30
- Cost limit: $10-15/instance

### ALO Config
See `config/config.yaml` and variants.

---

*Part of the Via2 Agent Systems Repository*
