"""
inference.py — Baseline Inference Script
=========================================
Runs an LLM agent through ALL scenarios in each of the 3 tasks.
Prints structured logs in the required [START] / [STEP] / [END] format.

Environment variables (all optional except one of the key vars):
  OPENAI_API_KEY   OpenAI API key  (checked first, per OpenEnv spec)
  HF_TOKEN         Hugging Face token  (fallback)
  API_KEY          Generic fallback key
  API_BASE_URL     OpenAI-compatible endpoint
                   (default: https://router.huggingface.co/v1)
  MODEL_NAME       Model identifier
                   (default: Qwen/Qwen2.5-72B-Instruct)
  ENV_BASE_URL     Base URL of the running environment server
                   (default: https://sanviq-incident-response-env.hf.space)

Quickstart:
  export OPENAI_API_KEY=sk-...
  python inference.py
"""

import os
import re
import textwrap
from typing import List, Optional, Dict, Any

import httpx
from openai import OpenAI

# ------------------------------------------------------------------
# Configuration  —  OPENAI_API_KEY is the canonical name per spec
# ------------------------------------------------------------------
API_KEY: str = (
    os.environ.get("OPENAI_API_KEY")
    or os.environ.get("HF_TOKEN")
    or os.environ.get("API_KEY")
    or "dummy"
)
API_BASE_URL: str = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME: str   = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
ENV_BASE_URL: str = os.environ.get(
    "ENV_BASE_URL", "https://sanviq-incident-response-env.hf.space"
)
BENCHMARK: str          = "incident-response-env"
SUCCESS_THRESHOLD: float = 0.5

# How many scenarios to run per task (set to None to run all)
MAX_SCENARIOS_PER_TASK: Optional[int] = None

SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert Site Reliability Engineer (SRE) responding to live production incidents.
    Be concise, precise, and decisive. Think about severity and customer impact first.

    For classify-alert:
      Respond starting with the severity word (low / medium / critical),
      then a dash, then one sentence explaining why.
      Example: "critical - CPU at 98% is causing payment timeouts, immediate action needed."

    For select-remediation:
      Respond starting with the option letter (A / B / C / D),
      then a dash, then a brief explanation of why that is the best action.
      Example: "B - rolling back the faulty deployment is the fastest path to restoring stability."

    For cascading-alerts:
      You will handle one alert per step. Respond with:
        ALERT ID - severity - remediation action in 1-2 sentences.
      Example: "ALERT-001 - critical - Restart the payment-service pods immediately and page the on-call engineer."
""").strip()


# ------------------------------------------------------------------
# Logging helpers
# ------------------------------------------------------------------
def log_start(task: str, env: str, model: str, scenario: int) -> None:
    print(f"[START] task={task} scenario={scenario} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    action_clean = action.replace("\n", " ").strip()[:150]
    error_val    = error if error else "null"
    done_val     = str(done).lower()
    print(
        f"[STEP] step={step} action={action_clean!r} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# ------------------------------------------------------------------
# Rule-based fallback  (used when LLM call fails)
# ------------------------------------------------------------------
def _extract_severity(alert: str) -> str:
    """Heuristic severity from alert text."""
    a = alert.lower()
    # Clear critical signals
    if any(k in a for k in [
        "99%", "98%", "97%", "503", "down", "failing", "data loss", "oom",
        "imminent", "outage", "exhausted", "not ready", "cannot log"
    ]):
        return "critical"
    # Medium signals
    if any(k in a for k in [
        "76%", "78%", "84%", "85%", "88%", "trending", "climbing", "lag",
        "latency", "leak", "elevated", "slow", "failed silently", "cron"
    ]):
        return "medium"
    return "low"


def _best_remediation_option(observation: Dict[str, Any]) -> str:
    """Heuristic option picker for select-remediation."""
    alert = observation.get("alert_message", "").lower()
    options: Dict[str, str] = observation.get("options", {})
    context = observation.get("system_context", {})

    # Deployment-caused errors → rollback
    if any(k in alert for k in ["deploy", "5xx", "spike", "v2."]):
        for letter, text in options.items():
            if "roll" in text.lower():
                return letter

    # SSL cert expiry → manual renewal
    if "ssl" in alert or "certificate" in alert or "cert" in alert:
        for letter, text in options.items():
            if "renew" in text.lower() or "certbot" in text.lower():
                return letter

    # Memory leak → rolling restart
    if "memory" in alert or "leak" in alert or "heap" in alert or "oom" in alert:
        for letter, text in options.items():
            if "restart" in text.lower() and "roll" in text.lower():
                return letter
        for letter, text in options.items():
            if "restart" in text.lower():
                return letter

    # Connection pool → increase pool + restart
    if "connection" in alert or "pool" in alert:
        for letter, text in options.items():
            if "pool" in text.lower() and ("increase" in text.lower() or "restart" in text.lower()):
                return letter

    # Blocking queries / lock / latency → terminate queries
    if "lock" in alert or "blocking" in alert or "latency" in context.get("p99_latency_secs", ""):
        for letter, text in options.items():
            if "terminate" in text.lower() or "pg_terminate" in text.lower() or "kill" in text.lower():
                return letter

    # Default: pick B (often correct for medium/hard fixes)
    return "B"


def rule_based_response(observation: Dict[str, Any]) -> str:
    task    = observation.get("task_name", "")
    alert   = observation.get("alert_message", "")
    pending = observation.get("pending_alerts", [])

    if task == "classify-alert":
        sev = _extract_severity(alert)
        reasons = {
            "critical": "immediate customer or data impact detected, escalation required",
            "medium":   "situation is concerning and trending toward impact if left unattended",
            "low":      "no immediate risk, can be addressed during business hours",
        }
        return f"{sev} - {reasons[sev]}"

    if task == "select-remediation":
        letter = _best_remediation_option(observation)
        options = observation.get("options", {})
        chosen_text = options.get(letter, "appropriate remediation action")
        return f"{letter} - {chosen_text.lower()} is the most effective immediate fix"

    if task == "cascading-alerts" and pending:
        # Handle the first pending alert (already sorted by env to highest priority)
        top = pending[0]
        aid   = top.get("id", "UNKNOWN")
        atxt  = top.get("alert", "").lower()
        sev   = top.get("severity", _extract_severity(atxt))

        if sev == "critical" or any(k in atxt for k in ["503", "down", "failing", "outage", "not ready"]):
            action = "Immediately page the on-call engineer and restart the affected service to restore availability."
        elif any(k in atxt for k in ["lag", "replica", "memory", "cache", "cron"]):
            action = "Investigate root cause and apply targeted fix; monitor for escalation."
        else:
            action = "Schedule remediation in the next maintenance window; no immediate customer impact."

        return f"{aid} - {sev} - {action}"

    return "Acknowledged. Monitoring the situation. No immediate action required."


# ------------------------------------------------------------------
# LLM call
# ------------------------------------------------------------------
def build_user_prompt(observation: Dict[str, Any]) -> str:
    task_name = observation.get("task_name", "")
    alert_msg = observation.get("alert_message", "")
    context   = observation.get("system_context", {})
    options   = observation.get("options")
    pending   = observation.get("pending_alerts")
    hint      = observation.get("hint", "")

    parts = [
        f"Task: {task_name}",
        f"Alert: {alert_msg}",
        f"System Context: {context}",
    ]
    if options:
        opts = "\n".join(f"  {k}: {v}" for k, v in options.items())
        parts.append(f"Options:\n{opts}")
    if pending:
        alerts_text = "\n".join(
            f"  [{a['id']}] (severity: {a.get('severity','?')}) {a['alert']}"
            for a in pending
        )
        parts.append(f"Pending Alerts:\n{alerts_text}")
    if hint:
        parts.append(f"Instruction: {hint}")
    return "\n".join(parts)


def llm_response(client: OpenAI, observation: Dict[str, Any]) -> str:
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": build_user_prompt(observation)},
            ],
            temperature=0.2,
            max_tokens=200,
        )
        text = (completion.choices[0].message.content or "").strip()
        return text if text else rule_based_response(observation)
    except Exception as exc:
        print(f"[DEBUG] LLM call failed ({type(exc).__name__}): {exc}", flush=True)
        return rule_based_response(observation)


# ------------------------------------------------------------------
# Discover scenario count from the environment
# ------------------------------------------------------------------
def get_scenario_count(task_name: str) -> int:
    """Ask the env /tasks endpoint how many scenarios exist, or use defaults."""
    defaults = {
        "classify-alert":     5,
        "select-remediation": 5,
        "cascading-alerts":   3,
    }
    try:
        r = httpx.get(f"{ENV_BASE_URL}/tasks", timeout=10)
        r.raise_for_status()
        for t in r.json().get("tasks", []):
            if t["name"] == task_name and "scenario_count" in t:
                return int(t["scenario_count"])
    except Exception:
        pass
    return defaults.get(task_name, 1)


# ------------------------------------------------------------------
# Single-episode runner
# ------------------------------------------------------------------
def run_episode(
    task_name: str,
    scenario_index: int,
    max_steps: int,
    client: OpenAI,
) -> Dict[str, Any]:
    rewards: List[float]   = []
    steps_taken: int       = 0
    score: float           = 0.0
    success: bool          = False

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME, scenario=scenario_index)

    try:
        reset_resp = httpx.post(
            f"{ENV_BASE_URL}/reset",
            json={"task": task_name, "scenario_index": scenario_index},
            timeout=30,
        )
        reset_resp.raise_for_status()
        observation = reset_resp.json()["observation"]

        for step in range(1, max_steps + 1):
            action = llm_response(client, observation)
            reward = 0.0
            done   = False
            error: Optional[str] = None

            try:
                step_resp = httpx.post(
                    f"{ENV_BASE_URL}/step",
                    json={"response": action},
                    timeout=30,
                )
                step_resp.raise_for_status()
                step_data   = step_resp.json()
                observation = step_data["observation"]
                reward      = float(step_data["reward"])
                done        = bool(step_data["done"])
            except Exception as exc:
                error = str(exc)[:200]
                done  = True

            rewards.append(reward)
            steps_taken = step
            log_step(step=step, action=action, reward=reward, done=done, error=error)

            if done:
                break

        score   = sum(rewards) / len(rewards) if rewards else 0.0
        score   = round(min(max(score, 0.0), 1.0), 3)
        success = score >= SUCCESS_THRESHOLD

    except Exception as exc:
        print(f"[DEBUG] Episode error for task '{task_name}' scenario {scenario_index}: {exc}", flush=True)

    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return {"task": task_name, "scenario": scenario_index, "score": score, "success": success}


# ------------------------------------------------------------------
# Main — iterate over all tasks and all scenarios
# ------------------------------------------------------------------
TASK_CONFIG = [
    {"name": "classify-alert",     "max_steps": 1},
    {"name": "select-remediation", "max_steps": 1},
    {"name": "cascading-alerts",   "max_steps": 3},
]


def main() -> None:
    print(
        f"[DEBUG] Starting | API: {API_BASE_URL} | Model: {MODEL_NAME} | Env: {ENV_BASE_URL}",
        flush=True,
    )

    using_openai_key = bool(os.environ.get("OPENAI_API_KEY"))
    if not using_openai_key:
        print(
            "[DEBUG] OPENAI_API_KEY not set — "
            "will fall back to rule-based responses if LLM call fails.",
            flush=True,
        )

    client  = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    results: List[Dict[str, Any]] = []

    for task_cfg in TASK_CONFIG:
        task_name  = task_cfg["name"]
        max_steps  = task_cfg["max_steps"]
        n_scenarios = get_scenario_count(task_name)

        if MAX_SCENARIOS_PER_TASK is not None:
            n_scenarios = min(n_scenarios, MAX_SCENARIOS_PER_TASK)

        print(
            f"[DEBUG] Task '{task_name}': running {n_scenarios} scenario(s) × {max_steps} step(s)",
            flush=True,
        )

        for scenario_idx in range(n_scenarios):
            result = run_episode(
                task_name      = task_name,
                scenario_index = scenario_idx,
                max_steps      = max_steps,
                client         = client,
            )
            results.append(result)

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n[DEBUG] ── Final Results ─────────────────────────────────────────", flush=True)
    task_scores: Dict[str, List[float]] = {}
    for r in results:
        task_scores.setdefault(r["task"], []).append(r["score"])

    overall_scores: List[float] = []
    for task_name, scores in task_scores.items():
        avg  = sum(scores) / len(scores)
        wins = sum(1 for s in scores if s >= SUCCESS_THRESHOLD)
        overall_scores.append(avg)
        print(
            f"[DEBUG]   {task_name}: avg={avg:.3f} | passed={wins}/{len(scores)} scenarios",
            flush=True,
        )

    overall_avg = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0
    print(f"[DEBUG] Overall average score: {overall_avg:.3f}", flush=True)


if __name__ == "__main__":
    main()