---
title: Incident Response Env
emoji: 🚨
colorFrom: red
colorTo: orange
sdk: docker
pinned: false
tags:
  - openenv
---

# 🚨 Incident Response Triage Environment

A real-world OpenEnv environment where an AI agent acts as an on-call **Site Reliability Engineer (SRE)**, triaging live production system alerts. Built for the Meta x HuggingFace OpenEnv Hackathon.

## Why This Exists

Every major tech company (Google, Meta, Netflix) has SRE teams who must classify alerts, choose remediations, and handle cascading failures under pressure. This environment trains AI agents to perform these tasks with human-level judgment — a genuine real-world need.

## Tasks

| Task | Difficulty | Steps | Description |
|------|-----------|-------|-------------|
| `classify-alert` | Easy | 1 | Classify a single system alert as low / medium / critical severity |
| `select-remediation` | Medium | 1 | Pick the correct remediation action (A/B/C/D) for a given alert |
| `cascading-alerts` | Hard | 3 | Prioritise and resolve 3 simultaneous production alerts in order of severity |

## Observation Space

```json
{
  "task_name": "string — current task name",
  "step_number": "int — current step",
  "alert_message": "string — the system alert",
  "system_context": "object — server name, metrics, environment",
  "options": "object (optional) — A/B/C/D choices for select-remediation",
  "pending_alerts": "array (optional) — unresolved alerts for cascading task",
  "task_description": "string — agent instructions",
  "hint": "string — response format guidance"
}
```

## Action Space

```json
{
  "response": "string — agent free-text answer to the alert"
}
```

## Reward Functions

All rewards are normalised to **[0.0, 1.0]** and are fully **deterministic**.

| Task | Metric | Weight |
|------|--------|--------|
| classify-alert | Severity accuracy | 80% |
| classify-alert | Reasoning quality | 20% |
| select-remediation | Option correctness | 75% |
| select-remediation | Reasoning quality | 25% |
| cascading-alerts | Priority correctness | 40% |
| cascading-alerts | Alert identification | 30% |
| cascading-alerts | Remediation quality | 30% |

## Baseline Scores

| Task | Score |
|------|-------|
| classify-alert | 0.72 |
| select-remediation | 0.65 |
| cascading-alerts | 0.58 |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/metadata` | Environment info |
| GET | `/schema` | Action/observation/state schemas |
| GET | `/state` | Current episode state |
| GET | `/tasks` | List all tasks |
| POST | `/reset` | Start a new episode |
| POST | `/step` | Send an action |
| POST | `/mcp` | MCP JSON-RPC endpoint |

## Usage

```bash
# Start a new episode
curl -X POST https://sanviq-incident-response-env.hf.space/reset \
  -H "Content-Type: application/json" \
  -d '{"task": "classify-alert", "scenario_index": 0}'

# Take a step
curl -X POST https://sanviq-incident-response-env.hf.space/step \
  -H "Content-Type: application/json" \
  -d '{"response": "critical - CPU at 98% on production server requires immediate action"}'

# Check state
curl https://sanviq-incident-response-env.hf.space/state
```

## Run Locally

```bash
git clone https://huggingface.co/spaces/sanviq/incident-response-env
cd incident-response-env
pip install -r requirements.txt
python server.py
```

## Project Structure

```
├── server.py         # FastAPI server (OpenEnv API)
├── environment.py    # Core step/reset/state logic
├── tasks.py          # Task & scenario definitions
├── graders.py        # Reward/grading functions
├── models.py         # Pydantic typed models
├── inference.py      # Baseline inference script
├── openenv.yaml      # OpenEnv spec
├── Dockerfile        # Container config
├── requirements.txt  # Dependencies
└── README.md         # This file
```