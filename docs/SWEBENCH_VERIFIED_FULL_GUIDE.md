# SWE-bench Verified: Complete Setup and Evaluation Guide

This guide takes you from zero to running a full evaluation on SWE-bench Verified with the Opus Meta-Orchestrator.

## Table of Contents

1. [Overview](#1-overview)
2. [Local Quick Test](#2-local-quick-test)
3. [Cloud Provider Selection](#3-cloud-provider-selection)
4. [Cloud Setup Instructions](#4-cloud-setup-instructions)
5. [Full Evaluation Process](#5-full-evaluation-process)
6. [Official Submission](#6-official-submission)
7. [Cost Estimation](#7-cost-estimation)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Overview

### What is SWE-bench Verified?

SWE-bench Verified is a curated subset of 500 software engineering issues that have been **human-validated** by OpenAI engineers. It's the gold standard for evaluating AI coding agents.

| Benchmark | Instances | Quality | Use Case |
|-----------|-----------|---------|----------|
| SWE-bench Full | ~2,294 | Mixed | Comprehensive testing |
| SWE-bench Lite | ~300 | Good | Quick iteration |
| **SWE-bench Verified** | **500** | **Human-verified** | **Leaderboard submission** |

### Your System: Opus Meta-Orchestrator

Your orchestrator now has two modes:
- `run()` - Self-contained code generation (EvalPlus benchmarks)
- `run_swebench()` - File editing mode (SWE-bench)

With integrated learners:
- **CompoundingLearner**: v26 with 340+ patterns
- **ModelSelectionLearner**: 300+ tasks, 11 routing rules

---

## 2. Local Quick Test

Before investing in cloud infrastructure, validate locally.

### Step 1: Quick Sanity Test (1 instance)

```bash
cd /Users/macbook2024/Library/CloudStorage/Dropbox/AAA\ Backup/A\ Working/Via2

# Test on a single instance
python benchmark/run_swebench_opus.py \
    --variant opus-optimized \
    --dataset verified \
    --num 1 \
    --verbose
```

### Step 2: Small Batch Test (5 instances)

```bash
python benchmark/run_swebench_opus.py \
    --variant opus-optimized \
    --dataset verified \
    --num 5
```

### Step 3: Compare Learners vs No Learners

```bash
python benchmark/run_swebench_opus.py \
    --variant opus-optimized \
    --dataset verified \
    --num 5 \
    --compare
```

### Expected Output

```
================================================================================
Instance: django__django-12345
Repo: django/django
Variant: opus-optimized (learners=ON)
================================================================================
  Creating workspace for django__django-12345...
  Checking out abc12345...
  Running Opus Meta-Orchestrator (SWE-bench Mode)...
    CompoundingLearner: v26
    ModelSelectionLearner: 300 tasks, 11 rules
  Complete - 45.2s - $0.0834
    Files modified: 1
    Patch size: 423 chars
```

---

## 3. Cloud Provider Selection

### Why Cloud?

Running SWE-bench Verified locally on your M4 Max is possible but has limitations:
1. **Time**: 500 instances × ~60s each = ~8 hours minimum
2. **Disk**: Each repo clone uses 100MB-2GB
3. **Docker**: Official evaluation requires Docker containers
4. **ARM Issues**: Some dependencies don't work on Apple Silicon

### Recommended: Modal (Best for SWE-bench)

**Why Modal?**
- Official SWE-bench team uses Modal
- `sb-cli` tool integrates directly
- Pay-per-use (no idle costs)
- Pre-built SWE-bench containers
- No Docker setup required

**Pricing**: ~$0.10-0.30 per instance evaluation

### Alternative: AWS EC2

**When to use AWS:**
- Need persistent storage
- Running multiple benchmarks
- Want more control

**Recommended Instance**: `c6i.4xlarge` (16 vCPU, 32GB RAM)
- Cost: ~$0.68/hour
- Full run: ~8 hours = ~$6

### Alternative: Google Cloud (GCE)

**Recommended Instance**: `n2-standard-16` (16 vCPU, 64GB RAM)
- Cost: ~$0.78/hour
- Full run: ~8 hours = ~$7

### Comparison Table

| Provider | Setup Time | Cost (500 instances) | Ease of Use | Official Support |
|----------|------------|---------------------|-------------|------------------|
| **Modal** | 10 min | ~$50-150 | Easiest | Yes (sb-cli) |
| AWS EC2 | 30 min | ~$6 + API costs | Medium | No |
| GCE | 30 min | ~$7 + API costs | Medium | No |
| Local (M4 Max) | 0 min | API costs only | Hardest | No |

**Recommendation**: Start with Modal for official evaluation, use local for development.

---

## 4. Cloud Setup Instructions

### Option A: Modal (Recommended)

#### Step 1: Install Modal CLI

```bash
pip install modal
```

#### Step 2: Create Modal Account

1. Go to https://modal.com
2. Sign up (free tier includes $30 credits)
3. Run authentication:

```bash
modal setup
```

#### Step 3: Install sb-cli

```bash
pip install swebench
```

#### Step 4: Run Evaluation on Modal

```bash
# Generate predictions locally first
python benchmark/run_swebench_opus.py \
    --variant opus-optimized \
    --dataset verified \
    --num 500 \
    --output predictions_opus_verified.jsonl

# Then evaluate with official harness on Modal
python -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Verified \
    --predictions_path predictions_opus_verified.jsonl \
    --max_workers 16 \
    --run_id opus_verified_run1
```

---

### Option B: AWS EC2 Setup

#### Step 1: Launch EC2 Instance

```bash
# Using AWS CLI (or use console)
aws ec2 run-instances \
    --image-id ami-0c7217cdde317cfec \  # Ubuntu 22.04
    --instance-type c6i.4xlarge \
    --key-name your-key-pair \
    --security-group-ids sg-xxxxxxxx \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":200}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=swebench-runner}]'
```

#### Step 2: SSH and Setup

```bash
ssh -i your-key.pem ubuntu@<instance-ip>

# Install dependencies
sudo apt update && sudo apt install -y docker.io python3-pip git
sudo usermod -aG docker ubuntu
newgrp docker

# Clone your repo
git clone https://github.com/your-repo/Via2.git
cd Via2

# Install Python dependencies
pip install -r requirements.txt
pip install swebench datasets

# Set environment variables
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export OPENROUTER_API_KEY="your-key"
export GEMINI_API_KEY="your-key"
export CEREBRAS_API_KEY="your-key"
```

#### Step 3: Run Evaluation

```bash
# Generate predictions
python benchmark/run_swebench_opus.py \
    --variant opus-optimized \
    --dataset verified \
    --num 500 \
    --output predictions.jsonl

# Run official evaluation
python -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Verified \
    --predictions_path predictions.jsonl \
    --max_workers 8 \
    --run_id opus_ec2_run
```

---

### Option C: Google Cloud Setup

#### Step 1: Create VM

```bash
gcloud compute instances create swebench-runner \
    --zone=us-central1-a \
    --machine-type=n2-standard-16 \
    --boot-disk-size=200GB \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud
```

#### Step 2: SSH and Setup

```bash
gcloud compute ssh swebench-runner --zone=us-central1-a

# Same setup steps as AWS...
```

---

## 5. Full Evaluation Process

### Phase 1: Generate Predictions (Your Orchestrator)

This runs YOUR code to generate patches:

```bash
# Full 500 instances
python benchmark/run_swebench_opus.py \
    --variant opus-optimized \
    --dataset verified \
    --output predictions_opus_verified_$(date +%Y%m%d).jsonl

# Monitor progress
tail -f predictions_opus_verified_*.jsonl | wc -l
```

**Expected time**: 8-12 hours for 500 instances
**Expected cost**: ~$50-100 in API calls

### Phase 2: Official Evaluation (Docker Harness)

This runs the OFFICIAL SWE-bench evaluation:

```bash
# Install evaluation harness
git clone https://github.com/princeton-nlp/SWE-bench.git
cd SWE-bench
pip install -e .

# Run evaluation
python -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Verified \
    --predictions_path ../predictions_opus_verified_*.jsonl \
    --max_workers 8 \
    --run_id opus_meta_orchestrator_v1

# Results will be in:
# - logs/run_evaluation/opus_meta_orchestrator_v1/
# - evaluation_results/
```

### Phase 3: Analyze Results

```bash
# View summary
python -c "
import json
from pathlib import Path

results_dir = Path('logs/run_evaluation/opus_meta_orchestrator_v1')
report = json.load(open(results_dir / 'report.json'))

print(f'Total: {report[\"total\"]}')
print(f'Resolved: {report[\"resolved\"]}')
print(f'Resolution Rate: {report[\"resolved\"] / report[\"total\"] * 100:.1f}%')
"
```

---

## 6. Official Submission

### Prepare Submission

1. **Collect artifacts**:
   - `predictions.jsonl` - Your model's patches
   - `report.json` - Evaluation results
   - `config.yaml` - Your configuration
   - Cost/time metrics

2. **Fork experiments repo**:
   ```bash
   git clone https://github.com/swe-bench/experiments
   cd experiments
   ```

3. **Create submission**:
   ```
   evaluation/
   └── verified/
       └── opus_meta_orchestrator/
           ├── predictions.jsonl
           ├── results.json
           └── README.md
   ```

4. **Submit PR**:
   - Title: "Add Opus Meta-Orchestrator results"
   - Include resolution rate, cost, and methodology

### Leaderboard

Results appear at: https://www.swebench.com

Current top performers (as of Nov 2024):
- Amazon Q Developer: ~38%
- Claude 3.5 Sonnet (Agentless): ~33%
- GPT-4o: ~28%

---

## 7. Cost Estimation

### API Costs (Prediction Generation)

| Model | Cost/1K tokens | Est. tokens/instance | Cost/instance |
|-------|---------------|---------------------|---------------|
| Gemini 2.5 Pro | $0.0025 in / $0.01 out | ~10K | ~$0.08 |
| Qwen3-235B | $0.001 in / $0.002 out | ~5K | ~$0.02 |
| GLM-4.6 | $0.002 in / $0.004 out | ~5K | ~$0.03 |

**Total for 500 instances**: ~$50-100

### Cloud Compute Costs

| Provider | Instance | Hours | Total |
|----------|----------|-------|-------|
| Modal | Serverless | N/A | ~$50-150 |
| AWS EC2 | c6i.4xlarge | 10 | ~$7 |
| GCE | n2-standard-16 | 10 | ~$8 |

### Total Budget

| Component | Low Est. | High Est. |
|-----------|----------|-----------|
| API calls | $50 | $150 |
| Cloud compute | $10 | $50 |
| **Total** | **$60** | **$200** |

---

## 8. Troubleshooting

### Common Issues

#### "No relevant files identified"
- The context model couldn't find files matching the issue
- **Fix**: Check if repo was cloned correctly, increase file listing limit

#### "Could not find original text in file"
- The edit pattern didn't match exactly
- **Fix**: Model needs to include more context in ORIGINAL block

#### Docker build failures
- Some repos have complex dependencies
- **Fix**: Use `--namespace ''` on ARM, or use cloud x86 instance

#### Rate limits
- Too many parallel API calls
- **Fix**: Reduce `--max_workers`, add delays

### Debug Mode

```bash
# Enable verbose logging
export ALO_LOG_LEVEL=DEBUG

# Run single instance with full output
python benchmark/run_swebench_opus.py \
    --variant opus-optimized \
    --dataset verified \
    --instances "django__django-12345" \
    --verbose
```

### Check Git Diff

```bash
# Manually inspect workspace
cd temp/swebench_repos/workspaces/django__django-12345
git diff
git status
```

---

## Quick Reference Commands

```bash
# Test 1 instance locally
python benchmark/run_swebench_opus.py --variant opus-optimized --dataset verified --num 1 --verbose

# Run 10 instances
python benchmark/run_swebench_opus.py --variant opus-optimized --dataset verified --num 10

# Full 500 instances
python benchmark/run_swebench_opus.py --variant opus-optimized --dataset verified

# Compare learners
python benchmark/run_swebench_opus.py --variant opus-optimized --dataset verified --num 10 --compare

# Run without learners
python benchmark/run_swebench_opus.py --variant opus-optimized --dataset verified --no-learners

# Official evaluation
python -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Verified \
    --predictions_path predictions.jsonl \
    --max_workers 8 \
    --run_id my_run
```

---

## Next Steps

1. **Run local quick test** (5 instances) to validate setup
2. **Create Modal account** and get $30 free credits
3. **Run pilot batch** (50 instances) on Modal
4. **Full run** (500 instances) once pilot succeeds
5. **Submit to leaderboard** with results

Good luck! The Opus Meta-Orchestrator with integrated learners should give you a competitive edge.
