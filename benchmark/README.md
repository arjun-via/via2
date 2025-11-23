# ALO vs Sonnet 4.5 Benchmark Suite

Comprehensive evaluation framework comparing three approaches:
- **ALO**: Multi-agent system (Context → Prompt → Review)
- **Sonnet+Context**: Claude Sonnet 4.5 with context injection
- **Sonnet Raw**: Claude Sonnet 4.5 baseline (no context)

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install anthropic

# Set environment variables in .env
ANTHROPIC_API_KEY=...
OPENROUTER_API_KEY=...
GEMINI_API_KEY=...
CEREBRAS_API_KEY=...
```

### Run Full Benchmark

```bash
# Run all 10 prompts
python benchmark/run_benchmark.py --prompts all

# Run specific prompts
python benchmark/run_benchmark.py --prompts "01_sharpe_ratio,02_websocket_server"

# Specify custom output directory
python benchmark/run_benchmark.py --prompts all --output-dir benchmark/results/my_run
```

### Generate Report

```bash
# After benchmark completes
python benchmark/analysis/report_generator.py benchmark/results/run_TIMESTAMP
```

## Benchmark Structure

### 10 Diverse Prompts

1. **01_sharpe_ratio** (Code Generation): Python financial calculation
2. **02_websocket_server** (Code Generation): Node.js WebSocket server
3. **03_binary_search_tree** (Code Generation): Rust data structure
4. **04_race_condition_fix** (Bug Fixing): Python threading bug
5. **05_sql_optimization** (Bug Fixing): SQL query optimization
6. **06_hft_architecture** (Architecture): High-frequency trading system design
7. **07_api_caching_strategy** (Architecture): Caching design for stock quotes
8. **08_fix_protocol_parser** (Code Explanation): FIX protocol walkthrough
9. **09_refactor_monolith** (Refactoring): Clean up 200-line function
10. **10_data_pipeline** (Multi-step): S&P 500 correlation analysis pipeline

### Evaluation Dimensions

Each solution scored 1-10 on:
- **Correctness**: Logic soundness, meets requirements
- **Completeness**: All requirements addressed, edge cases handled
- **Code Quality**: Readable, maintainable, idiomatic
- **Security**: No vulnerabilities, best practices
- **Clarity**: Well-documented, easy to understand

Judge: **o3-mini-high** via OpenRouter (advanced reasoning model)

## Output Structure

```
benchmark/results/run_TIMESTAMP/
├── summary.json                    # High-level metadata
├── report.md                       # Generated report
├── 01_sharpe_ratio/
│   ├── alo_output.txt
│   ├── alo_metadata.json
│   ├── sonnet_context_output.txt
│   ├── sonnet_context_metadata.json
│   ├── sonnet_raw_output.txt
│   ├── sonnet_raw_metadata.json
│   └── evaluation.json
├── 02_websocket_server/
│   └── ...
└── ...
```

## Key Metrics

- **Quality Score**: Overall 1-10 rating from judge
- **Cost**: USD spent on API calls
- **Time**: Elapsed seconds
- **Cost-Efficiency**: $ per quality point
- **Win Rate**: % of prompts where system won

## Adding New Prompts

Create a YAML file in `benchmark/prompts/`:

```yaml
id: "11_new_prompt"
category: "code_generation"
title: "Short Title"
prompt: |
  Full prompt text here...

expected_artifacts:
  - language: "python"
  - has_function: true

evaluation_focus:
  correctness: 0.35
  completeness: 0.25
  code_quality: 0.20
  security: 0.10
  clarity: 0.10
```

## Architecture Notes

- **ALO Runner**: Reuses existing `PromptOrchestrator` from main repo
- **Sonnet Runners**: Direct Anthropic API calls with/without context
- **Judge**: OpenRouter proxy to o3-mini-high
- **Fair Comparison**: Sonnet+Context receives same context ALO generates
- **Cost Tracking**: All API calls logged with token counts and costs

## Configuration

Edit `benchmark/config_benchmark.yaml`:

```yaml
judge:
  model: "openai/o3-mini-high"
  provider: "openrouter"
  temperature: 1

runs_per_prompt: 1  # Increase for variance analysis
```

## Troubleshooting

**API Key Errors**: Ensure all keys are set in `.env` file

**Import Errors**: Run from project root with `PYTHONPATH=.`

**Judge Parse Errors**: o3-mini may wrap JSON in markdown - parser handles this

**Out of Memory**: Large outputs cached in memory - reduce prompts or add streaming

## Future Enhancements

- [ ] Multiple runs per prompt for statistical significance
- [ ] Visualization charts (quality vs cost scatter plots)
- [ ] Human evaluation validation
- [ ] Additional systems (GPT-4o, Claude Opus)
- [ ] Automated code execution tests
- [ ] Prompt difficulty scoring
