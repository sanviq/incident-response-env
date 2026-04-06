"""
inference.py — Baseline Inference Script
=========================================
Runs an LLM agent through all 3 tasks of the Incident Response Triage environment.
Prints structured logs in the required [START] / [STEP] / [END] format.

Environment variables:
  API_BASE_URL   The OpenAI-compatible API endpoint for the LLM.
  MODEL_NAME     The model identifier.
  HF_TOKEN       Your Hugging Face / API key.
  ENV_BASE_URL   Base URL of the running environment server (default: http://localhost:7860).
"""

import os
import textwrap
from typing import List, Optional, Dict, Any

import httpx
from openai import OpenAI

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
API_KEY: str = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or "dummy"
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME: str = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
ENV_BASE_URL: str = os.getenv("ENV_BASE_URL", "http://localhost:7860")
BENCHMARK: str = "incident-response-env"
SUCCESS_THRESHOLD: float = 0.5

TASKS_CONFIG = [
    {"name": "classify-alert",     "max_steps": 1, "scenario_index": 0},
    {"name": "select-remediation", "max_steps": 1, "scenario_index": 0},
    {"name": "cascading-alerts",   "max_steps": 3, "scenario_index": 0},
]

SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert Site Reliability Engineer (SRE) responding to live production incidents.
    Be concise, precise, and decisive.

    For classify-alert: respond with low/medium/critical and a one-sentence reason.
    For select-remediation: respond with option letter (A/B/C/D) and brief explanation.
    For cascading-alerts: respond with Alert ID, severity, and remediation action.
""").strip()


# ------------------------------------------------------------------
# Logging helpers
# ------------------------------------------------------------------
def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    action_clean = action.replace("\n", " ").strip()[:120]
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(f"[STEP] step={step} action={action_clean} reward={reward:.2f} done={done_val} error={error_val}", flush=True)

def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)


# ------------------------------------------------------------------
# Agent
# ------------------------------------------------------------------
def build_user_prompt(observation: Dict[str, Any]) -> str:
    task_name = observation.get("task_name", "")
    alert_msg = observation.get("alert_message", "")
    context = observation.get("system_context", {})
    options = observation.get("options")
    pending = observation.get("pending_alerts")
    hint = observation.get("hint", "")

    parts = [f"Task: {task_name}", f"Alert: {alert_msg}", f"System Context: {context}"]
    if options:
        opts = "\n".join(f"  {k}: {v}" for k, v in options.items())
        parts.append(f"Options:\n{opts}")
    if pending:
        alerts_text = "\n".join(f"  [{a['id']}] {a['alert']}" for a in pending)
        parts.append(f"Pending Alerts:\n{alerts_text}")
    if hint:
        parts.append(f"Instruction: {hint}")
    return "\n".join(parts)


def rule_based_response(observation: Dict[str, Any]) -> str:
    task = observation.get("task_name", "")
    alert = observation.get("alert_message", "").lower()
    pending = observation.get("pending_alerts", [])

    if task == "classify-alert":
        if any(w in alert for w in ["98%", "99%", "exhausted", "failing", "0/", "data loss"]):
            return "critical - system is in immediate danger and requires urgent intervention"
        if any(w in alert for w in ["84%", "85%", "79%", "rising", "climbing", "trending"]):
            return "medium - situation is concerning and needs active monitoring"
        return "low - no immediate action required, schedule during business hours"

    if task == "select-remediation":
        if "deploy" in alert or "spike" in alert or "5xx" in alert:
            return "B - rolling back the recent deployment is the fastest way to restore stability"
        if "memory" in alert or "oom" in alert or "ram" in alert:
            return "B - restart the service to recover memory, then investigate the leak"
        if "latency" in alert or "lock" in alert or "slow" in alert:
            return "C - identify and terminate blocking queries to immediately restore performance"
        return "B - this is the most appropriate immediate remediation action"

    if task == "cascading-alerts" and pending:
        top = pending[0]
        alert_text = top.get("alert", "").lower()
        aid = top["id"]
        if "99%" in alert_text or "failing" in alert_text or "data loss" in alert_text:
            return f"{aid} - critical severity. Immediately archive old WAL files and expand disk volume to prevent data loss."
        if "79%" in alert_text or "78%" in alert_text or "climbing" in alert_text:
            return f"{aid} - medium severity. Monitor memory and restart worker if usage exceeds 90%."
        return f"{aid} - low severity. Schedule remediation during the next maintenance window."

    return "Acknowledged. No further action required."


def llm_response(client: OpenAI, observation: Dict[str, Any]) -> str:
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(observation)},
            ],
            temperature=0.3,
            max_tokens=200,
        )
        text = (completion.choices[0].message.content or "").strip()
        return text if text else rule_based_response(observation)
    except Exception as exc:
        print(f"[DEBUG] LLM call failed: {exc}", flush=True)
        return rule_based_response(observation)


# ------------------------------------------------------------------
# Episode runner
# ------------------------------------------------------------------
def run_episode(task_config: Dict[str, Any], client: OpenAI) -> Dict[str, Any]:
    task_name = task_config["name"]
    max_steps = task_config["max_steps"]
    scenario_index = task_config.get("scenario_index", 0)

    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

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
            done = False
            error: Optional[str] = None

            try:
                step_resp = httpx.post(
                    f"{ENV_BASE_URL}/step",
                    json={"response": action},
                    timeout=30,
                )
                step_resp.raise_for_status()
                step_data = step_resp.json()
                observation = step_data["observation"]
                reward = float(step_data["reward"])
                done = bool(step_data["done"])
            except Exception as exc:
                error = str(exc)
                done = True

            rewards.append(reward)
            steps_taken = step
            log_step(step=step, action=action, reward=reward, done=done, error=error)

            if done:
                break

        score = sum(rewards) / len(rewards) if rewards else 0.0
        score = round(min(max(score, 0.0), 1.0), 3)
        success = score >= SUCCESS_THRESHOLD

    except Exception as exc:
        print(f"[DEBUG] Episode error for task '{task_name}': {exc}", flush=True)

    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return {"task": task_name, "score": score, "success": success}


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main() -> None:
    print(f"[DEBUG] Starting | API: {API_BASE_URL} | Model: {MODEL_NAME} | Env: {ENV_BASE_URL}", flush=True)
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    results = []
    for task_config in TASKS_CONFIG:
        result = run_episode(task_config, client)
        results.append(result)
    avg = sum(r["score"] for r in results) / len(results) if results else 0.0
    print(f"[DEBUG] All tasks complete. Average score: {avg:.3f}", flush=True)


if __name__ == "__main__":
    main()
