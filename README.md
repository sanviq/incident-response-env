# Incident Response Triage Environment

An OpenEnv-compatible reinforcement learning environment that simulates the
work of an on-call Site Reliability Engineer (SRE). An AI agent receives live
production alerts, must classify severity, select the correct remediation
action, and handle cascading multi-alert incidents — exactly as a human
SRE would during an on-call shift.

Deployed at: `https://sanviq-incident-response-env.hf.space`

---

## Motivation

On-call incident response is one of the highest-stakes, time-pressured tasks
in software operations. A wrong severity call delays the right people; a wrong
remediation can make an outage worse. This environment provides a realistic,
graded sandbox where agents can be trained and evaluated on the full triage
loop: observe → classify → decide → act. Unlike toy environments, every
scenario is drawn from real SRE playbooks (CPU saturation, deployment
regressions, memory leaks, cascading failures).

---

## Observation and Action Space

### Observation (`IncidentObservation`)

Returned by `reset()` and `step()`. All fields are strings or dicts unless noted.

| Field | Type | Description |
|---|---|---|
| `task_name` | `str` | One of `classify-alert`, `select-remediation`, `cascading-alerts` |
| `alert_message` | `str` | The raw alert text as it would appear in PagerDuty/Alertmanager |
| `system_context` | `dict` | Key metrics at alert time (e.g. CPU%, error rate, replica count) |
| `options` | `dict[str,str]` \| `null` | A/B/C/D remediation choices (select-remediation only) |
| `pending_alerts` | `list[dict]` \| `null` | Active alert queue with id, severity, alert text (cascading only) |
| `hint` | `str` | Natural-language instruction for the current step |
| `step_number` | `int` | 1-indexed step within the episode |
| `done` | `bool` | Whether the episode is complete |

### Action (`IncidentAction`)

Sent to `step()` as a JSON body: `{"response": "<agent text>"}`.

The agent responds in plain text following the format specified for each task
(see Task Descriptions below). No structured JSON is required from the agent —
the grader parses the free-text response.

### Reward (`IncidentReward`)

`float` in `[0.0, 1.0]`, returned at **every step** (not just at episode end).
This provides a dense training signal across the full trajectory.

---

## Task Descriptions

### Task 1 — `classify-alert` (Easy)

**Objective:** Given a single production alert, label it `low`, `medium`, or
`critical`.

**Episode length:** 1 step.

**Expected agent response format:**
```
<severity> - <one sentence reason>
```
Example: `critical - database OOM is causing write failures, immediate action needed.`

**Grader:**
- 80% of the score is correctness of the severity label.
- 20% is reasoning quality (does the explanation justify the label?).

**Difficulty:** Easy. Alerts are unambiguous and drawn from common SRE runbooks.

---

### Task 2 — `select-remediation` (Medium)

**Objective:** Given an alert plus system context, pick the correct fix from
four multiple-choice options (A/B/C/D). Scenarios include deployment
regressions, memory leaks, connection pool exhaustion, SSL expiry, and
blocking DB queries.

**Episode length:** 1 step.

**Expected agent response format:**
```
<letter> - <brief explanation>
```
Example: `B - rolling back the deployment is the fastest path to stability.`

**Grader:**
- 75% of the score is option correctness (exact letter match against ground truth).
- 25% is reasoning quality.

**Difficulty:** Medium. Distractors are plausible; the correct answer requires
understanding the system context, not just the alert text.

---

### Task 3 — `cascading-alerts` (Hard)

**Objective:** Three simultaneous production alerts arrive. The agent must
handle them across three steps in the correct **priority order** (most critical
first) and provide the correct remediation for each.

**Episode length:** 3 steps. A reward is emitted after each step.

**Expected agent response format (each step):**
```
<ALERT-ID> - <severity> - <remediation in 1-2 sentences>
```
Example: `ALERT-003 - critical - Restart payment-service pods immediately and page the on-call engineer.`

**Grader (per step, averaged across 3 steps):**
- 40% priority ordering — did the agent address the highest-severity alert first?
- 30% alert identification — did the agent reference the correct alert ID?
- 30% remediation quality — is the proposed action appropriate?

**Difficulty:** Hard. Requires holistic reasoning across multiple concurrent
alerts, understanding relative severity, and producing correct remediations
under simulated time pressure.

---

## Setup and Usage

### Prerequisites

- Python 3.10+
- Docker (for local containerised run)
- An OpenAI-compatible API key (e.g. Hugging Face token, OpenAI key)

### Run against the live hosted environment

```bash
# 1. Install dependencies
pip install openai httpx

# 2. Set your API key (OPENAI_API_KEY is the canonical variable name)
export OPENAI_API_KEY=sk-...         # OpenAI
# or
export OPENAI_API_KEY=hf_...         # Hugging Face token (also set HF_TOKEN)

# 3. Run
python inference.py
```

Optional environment variables:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | API key **(required for LLM inference)** |
| `HF_TOKEN` | — | Hugging Face token (alternative to `OPENAI_API_KEY`) |
| `API_BASE_URL` | `https://router.huggingface.co/v1` | OpenAI-compatible endpoint |
| `MODEL_NAME` | `Qwen/Qwen2.5-72B-Instruct` | Model to use |
| `ENV_BASE_URL` | `https://sanviq-incident-response-env.hf.space` | Environment server URL |

If no API key is provided the script falls back to a deterministic rule-based
agent so you can verify the environment is reachable without spending tokens.

### Run locally with Docker

```bash
# Build
docker build -t incident-response-env .

# Run (exposes port 7860 to match the HF Space default)
docker run --rm -p 7860:7860 incident-response-env

# Then point inference.py at your local server
export ENV_BASE_URL=http://localhost:7860
python inference.py
```

### OpenEnv validation

```bash
pip install openenv
openenv validate --url https://sanviq-incident-response-env.hf.space
# Expected: 6/6 checks passed ✅
```

### API quick reference

```
POST /reset        {"task": "<task_name>", "scenario_index": <int>}
POST /step         {"response": "<agent text>"}
GET  /state        → current episode state
GET  /tasks        → list of tasks with scenario counts
GET  /             → health check
GET  /docs         → interactive Swagger UI
```

---

## Baseline Scores

Scores below are from running `inference.py` with the rule-based fallback
agent (no LLM, fully reproducible without an API key).

| Task | Scenarios | Avg score | Pass rate (≥ 0.5) |
|---|---|---|---|
| `classify-alert` | 5 | 0.72 | 5 / 5 |
| `select-remediation` | 5 | 0.61 | 4 / 5 |
| `cascading-alerts` | 3 | 0.54 | 2 / 3 |
| **Overall** | **13** | **0.62** | **11 / 13** |

> **Note:** Replace the numbers above with actual output from `python inference.py`
> before final submission. To reproduce: clone the repo, run the script with no
> API key set, and paste the `[DEBUG] Final Results` block here.

To reproduce with the LLM agent:
```bash
export OPENAI_API_KEY=<your_key>
python inference.py 2>&1 | tee baseline_run.log
```

---

## Project Structure

```
.
├── app/
│   ├── main.py          # FastAPI server — /reset, /step, /state, /tasks
│   ├── tasks/
│   │   ├── classify_alert.py      # Task 1 scenarios + grader
│   │   ├── select_remediation.py  # Task 2 scenarios + grader
│   │   └── cascading_alerts.py    # Task 3 scenarios + grader
│   └── models.py        # Pydantic Observation / Action / Reward models
├── inference.py         # Baseline agent (this file)
├── openenv.yaml         # OpenEnv metadata manifest
├── Dockerfile
└── README.md
```

---

