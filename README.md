---
title: Incident Response Env
emoji: 🚨
colorFrom: red
colorTo: orange
sdk: docker
pinned: false
tags:
  - openenv
---<<<<<<< HEAD
<<<<<<< HEAD
# 🚨 Incident Response Triage Environment

An OpenEnv environment where an AI agent acts as an on-call **Site Reliability Engineer (SRE)**, responding to real-world production system alerts.

---

## 🧠 Motivation

Incident response is one of the most high-stakes real-world tasks in tech. Every major company (Google, Meta, Netflix) has SRE teams who must classify alerts, choose remediations, and handle cascading failures — often at 3am. This environment trains AI agents to perform these tasks with human-level judgment.

---

## 🎯 Tasks

| Task | Difficulty | Steps | Description |
|------|-----------|-------|-------------|
| `classify-alert` | Easy | 1 | Classify a single alert as low / medium / critical |
| `select-remediation` | Medium | 1 | Pick the correct fix (A/B/C/D) for a given alert |
| `cascading-alerts` | Hard | 3 | Prioritise and resolve 3 simultaneous alerts |

---

## 👁️ Observation Space

```json
{
  "task_name": "string",
  "step_number": "int",
  "alert_message": "string — the system alert",
  "system_context": "object — server name, metrics, environment",
  "options": "object (optional) — A/B/C/D choices for select-remediation",
  "pending_alerts": "array (optional) — unresolved alerts for cascading task",
  "task_description": "string — agent instructions",
  "hint": "string — response format guidance"
}
```

## ⚡ Action Space

```json
{
  "response": "string — agent's free-text answer to the alert"
}
```

---

## 🏆 Reward Functions

### classify-alert (Easy)
- **Accuracy (80%)**: Correct severity label (critical/medium/low)
- **Quality (20%)**: Reasoning word count (penalises empty responses)

### select-remediation (Medium)
- **Option correctness (75%)**: Correct letter chosen (partial credit for adjacent options)
- **Reasoning quality (25%)**: Length and justification of explanation

### cascading-alerts (Hard)
- **Priority correctness (40%)**: Was the most critical alert handled first?
- **Alert identification (30%)**: Did the agent reference a valid alert ID?
- **Remediation quality (30%)**: Did the agent describe a concrete action?

All rewards are normalised to **[0.0, 1.0]** and are **deterministic**.

---

## 📊 Baseline Scores

| Task | Score |
|------|-------|
| classify-alert | 0.72 |
| select-remediation | 0.65 |
| cascading-alerts | 0.58 |

---

## 🚀 Setup & Usage

### Local

```bash
pip install -r requirements.txt
python server.py
```

The server runs on `http://localhost:7860`.

### Docker

```bash
docker build -t incident-response-env .
docker run -p 7860:7860 incident-response-env
```

### API

```bash
# Reset to a task
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task": "classify-alert", "scenario_index": 0}'

# Take a step
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"response": "critical - CPU at 98% on production server requires immediate action"}'

# Check state
curl http://localhost:7860/state
```

### Run Baseline Inference

```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="your-token-here"
export ENV_BASE_URL="http://localhost:7860"

python inference.py
```

---

## 📁 Project Structure

```
incident-response-env/
├── server.py         # FastAPI server (OpenEnv API)
├── environment.py    # Core environment logic
├── tasks.py          # Task & scenario definitions
├── graders.py        # Reward/grading functions
├── models.py         # Pydantic typed models
├── inference.py      # Baseline inference script
├── openenv.yaml      # OpenEnv spec
├── Dockerfile        # Container configuration
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

---

## 🏷️ Tags

`openenv` `incident-response` `sre` `real-world` `devops`
=======
## ✅ OpenEnv Spec Compliance
 
- ✅ `reset()` returns clean typed `ResetResult` with `IncidentObservation`
- ✅ `step()` returns `StepResult` with observation, reward, done, info
- ✅ `state()` returns `EnvState` with full episode metadata
- ✅ All models are Pydantic-typed
- ✅ Graders are deterministic (same input → same score, always)
- ✅ All rewards in [0.0, 1.0]
- ✅ Graders produce varying scores (not all same value)
- ✅ 3 tasks with easy → medium → hard difficulty progression
=======
---
title: Incident Response Env
emoji: 👀
colorFrom: purple
colorTo: green
sdk: docker
pinned: false
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
>>>>>>> 7122f408178f3ad1663bcb9684702c45cf646d6c
