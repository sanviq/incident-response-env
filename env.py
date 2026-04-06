"""
Incident Response Triage - OpenEnv Environment
================================================
A real-world RL environment where an AI agent acts as an on-call SRE,
receiving system alerts and making triage + remediation decisions.

Tasks:
  - classify-alert     (easy)   : Classify alert severity
  - select-remediation (medium) : Pick correct fix from options
  - cascading-alerts   (hard)   : Handle 3 simultaneous alerts
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ─────────────────────────────────────────────
#  Typed Models (required by OpenEnv spec)
# ─────────────────────────────────────────────

class IncidentObservation(BaseModel):
    task: str
    step: int
    scenario_id: str
    message: str
    system_context: Dict[str, Any]
    available_actions: List[str]
    instructions: str


class IncidentAction(BaseModel):
    action: str


class StepResult(BaseModel):
    observation: IncidentObservation
    reward: float
    done: bool
    info: Dict[str, Any]


class ResetResult(BaseModel):
    observation: IncidentObservation


class EnvState(BaseModel):
    task: str
    step: int
    scenario_index: int
    done: bool
    rewards: List[float]
    actions_taken: List[str]


# ─────────────────────────────────────────────
#  Scenario Data (fixed → deterministic graders)
# ─────────────────────────────────────────────

CLASSIFY_SCENARIOS = [
    {
        "id": "cls_001",
        "message": "CPU utilization at 97% on prod-api-server for the last 8 minutes. Payment API response times degrading.",
        "context": {
            "server": "prod-api-server",
            "metric": "cpu_percent",
            "value": 97,
            "duration_mins": 8,
            "service": "payment-api",
            "environment": "production",
        },
        "correct": "critical",
        # Weighted: correct gets 1.0, adjacent gets partial, opposite gets 0.0
        "weights": {"critical": 1.0, "medium": 0.2, "low": 0.0},
    },
    {
        "id": "cls_002",
        "message": "Disk usage at 78% on log-aggregator-01. Trending upward over last 6 hours at ~2%/hour.",
        "context": {
            "server": "log-aggregator-01",
            "metric": "disk_percent",
            "value": 78,
            "trend": "increasing",
            "rate_per_hour": "2%",
        },
        "correct": "medium",
        "weights": {"medium": 1.0, "critical": 0.3, "low": 0.1},
    },
    {
        "id": "cls_003",
        "message": "Memory usage at 55% on dev-testing-02. No anomalies detected. Stable for last 24h.",
        "context": {
            "server": "dev-testing-02",
            "metric": "memory_percent",
            "value": 55,
            "environment": "development",
            "trend": "stable",
        },
        "correct": "low",
        "weights": {"low": 1.0, "medium": 0.4, "critical": 0.0},
    },
]

REMEDIATION_SCENARIOS = [
    {
        "id": "rem_001",
        "message": "ALERT: Database connection pool exhausted on prod-db-01. User-API error rate spiked to 45%.",
        "context": {
            "service": "user-api",
            "error_type": "connection_pool_exhausted",
            "error_rate": "45%",
            "current_pool_size": 100,
            "active_connections": 100,
            "database": "postgres-prod",
        },
        "options": {
            "A": "Restart the database server immediately",
            "B": "Increase connection pool size to 200 and restart the user-api service",
            "C": "Enable rate limiting on the API to reduce incoming traffic",
            "D": "Wait 15 minutes and monitor if it self-resolves",
        },
        "correct": "B",
        "partial": {"C": 0.4},
    },
    {
        "id": "rem_002",
        "message": "ALERT: Memory leak in recommendation-service. Heap growing 50MB/hour. Current: 7.2GB / 8GB max.",
        "context": {
            "service": "recommendation-service",
            "issue": "memory_leak",
            "current_heap_gb": 7.2,
            "max_heap_gb": 8.0,
            "growth_rate": "50MB/hour",
            "estimated_oom_mins": 16,
        },
        "options": {
            "A": "Rolling restart of recommendation-service pods to reclaim memory",
            "B": "Increase max heap size to 16GB immediately",
            "C": "Kill the service immediately to prevent cascade failure",
            "D": "Enable GC logging and wait for automatic cleanup",
        },
        "correct": "A",
        "partial": {"B": 0.3},
    },
    {
        "id": "rem_003",
        "message": "ALERT: SSL certificate for api.company.com expires in 2 hours. Auto-renewal failed (DNS challenge error).",
        "context": {
            "domain": "api.company.com",
            "cert_expiry_hours": 2,
            "affected_services": ["mobile-app", "web-frontend", "partner-api"],
            "auto_renewal_status": "failed - DNS challenge error",
        },
        "options": {
            "A": "Manually renew certificate using certbot with DNS challenge fix",
            "B": "Switch all services to HTTP temporarily until cert renews",
            "C": "Enable HTTP bypass in nginx config for all services",
            "D": "Contact SSL provider support and wait for their response",
        },
        "correct": "A",
        "partial": {"D": 0.1},
    },
]

CASCADE_SCENARIO = {
    "id": "cas_001",
    "alerts": [
        {
            "id": "alert_A",
            "message": "Payment service returning 503 errors. 80% of checkout transactions are failing.",
            "hint": "Direct customer revenue impact",
        },
        {
            "id": "alert_B",
            "message": "Internal metrics dashboard is down. Engineers cannot view system metrics.",
            "hint": "Internal tooling only, no customer impact",
        },
        {
            "id": "alert_C",
            "message": "Database replica lag at 45 seconds on read replicas. Some reads returning stale data.",
            "hint": "Degraded reads, but primary writes still work",
        },
    ],
    # Correct priority: payment outage > db lag > internal dashboard
    "correct_priority": ["alert_A", "alert_C", "alert_B"],
    "remediation_keywords": {
        "alert_A": ["restart", "payment", "503", "pod", "service", "deploy"],
        "alert_B": ["restart", "dashboard", "metric"],
        "alert_C": ["replica", "lag", "replication", "promote", "investigate"],
    },
}


# ─────────────────────────────────────────────
#  Environment
# ─────────────────────────────────────────────

class IncidentResponseEnv:
    """
    OpenEnv-compatible Incident Response Triage environment.
    All graders are deterministic (same input → same score).
    """

    TASKS = ["classify-alert", "select-remediation", "cascading-alerts"]
    MAX_STEPS = {
        "classify-alert": 3,
        "select-remediation": 3,
        "cascading-alerts": 1,
    }

    def __init__(self) -> None:
        self._task: str = "classify-alert"
        self._step: int = 0
        self._scenario_idx: int = 0
        self._done: bool = False
        self._rewards: List[float] = []
        self._actions_taken: List[str] = []

    # ── Public API ────────────────────────────

    def reset(self, task: str = "classify-alert") -> ResetResult:
        if task not in self.TASKS:
            raise ValueError(f"Unknown task '{task}'. Valid: {self.TASKS}")
        self._task = task
        self._step = 0
        self._scenario_idx = 0
        self._done = False
        self._rewards = []
        self._actions_taken = []
        return ResetResult(observation=self._build_obs())

    def step(self, action: IncidentAction) -> StepResult:
        if self._done:
            raise RuntimeError("Episode is done. Call reset() first.")

        self._step += 1
        self._actions_taken.append(action.action)

        reward, info = self._grade(action.action)
        self._rewards.append(reward)

        # Advance scenario index
        if self._task in ("classify-alert", "select-remediation"):
            self._scenario_idx += 1
            scenarios = (
                CLASSIFY_SCENARIOS
                if self._task == "classify-alert"
                else REMEDIATION_SCENARIOS
            )
            done = self._scenario_idx >= len(scenarios)
        else:
            done = True  # cascading-alerts is single-step

        self._done = done
        return StepResult(
            observation=self._build_obs(),
            reward=round(reward, 4),
            done=done,
            info=info,
        )

    def state(self) -> EnvState:
        return EnvState(
            task=self._task,
            step=self._step,
            scenario_index=self._scenario_idx,
            done=self._done,
            rewards=list(self._rewards),
            actions_taken=list(self._actions_taken),
        )

    # ── Observation Builder ───────────────────

    def _build_obs(self) -> IncidentObservation:
        if self._done:
            return IncidentObservation(
                task=self._task,
                step=self._step,
                scenario_id="episode_complete",
                message="Episode complete.",
                system_context={"total_reward": sum(self._rewards)},
                available_actions=[],
                instructions="Episode finished. See rewards.",
            )

        if self._task == "classify-alert":
            s = CLASSIFY_SCENARIOS[self._scenario_idx]
            return IncidentObservation(
                task=self._task,
                step=self._step,
                scenario_id=s["id"],
                message=s["message"],
                system_context=s["context"],
                available_actions=["low", "medium", "critical"],
                instructions=(
                    "Classify the alert severity. "
                    "Reply with EXACTLY one word: low, medium, or critical"
                ),
            )

        elif self._task == "select-remediation":
            s = REMEDIATION_SCENARIOS[self._scenario_idx]
            return IncidentObservation(
                task=self._task,
                step=self._step,
                scenario_id=s["id"],
                message=s["message"],
                system_context={**s["context"], "options": s["options"]},
                available_actions=["A", "B", "C", "D"],
                instructions=(
                    "Select the best remediation action. "
                    "Reply with EXACTLY one letter: A, B, C, or D"
                ),
            )

        else:  # cascading-alerts
            alerts = CASCADE_SCENARIO["alerts"]
            return IncidentObservation(
                task=self._task,
                step=self._step,
                scenario_id=CASCADE_SCENARIO["id"],
                message="MULTIPLE SIMULTANEOUS ALERTS — Triage required.",
                system_context={"alerts": alerts},
                available_actions=[],
                instructions=(
                    "You have 3 simultaneous production alerts. "
                    "Respond with a JSON object only:\n"
                    '{"priority": ["alert_A","alert_B","alert_C"], '
                    '"remediations": {"alert_A": "action", "alert_B": "action", "alert_C": "action"}}\n'
                    "Priority list must be ordered most-critical → least-critical."
                ),
            )

    # ── Graders (deterministic) ───────────────

    def _grade(self, action: str) -> tuple[float, Dict[str, Any]]:
        if self._task == "classify-alert":
            return self._grade_classify(action)
        elif self._task == "select-remediation":
            return self._grade_remediation(action)
        else:
            return self._grade_cascading(action)

    def _grade_classify(self, action: str) -> tuple[float, Dict[str, Any]]:
        """
        Weighted scoring:
          - Correct severity       → 1.0
          - Adjacent severity      → 0.2–0.4
          - Completely wrong       → 0.0
        """
        s = CLASSIFY_SCENARIOS[self._scenario_idx]
        clean = action.strip().lower().split()[0] if action.strip() else ""
        score = s["weights"].get(clean, 0.0)
        return score, {
            "scenario": s["id"],
            "correct_answer": s["correct"],
            "your_answer": clean,
            "score": score,
        }

    def _grade_remediation(self, action: str) -> tuple[float, Dict[str, Any]]:
        """
        Scoring:
          - Best remediation       → 1.0
          - Reasonable but subopt  → 0.3–0.4
          - Wrong / dangerous      → 0.0
        """
        s = REMEDIATION_SCENARIOS[self._scenario_idx]
        clean = action.strip().upper()[:1]  # take first letter only

        if clean == s["correct"]:
            score, result = 1.0, "correct"
        elif clean in s.get("partial", {}):
            score, result = s["partial"][clean], "partial"
        else:
            score, result = 0.0, "incorrect"

        return score, {
            "scenario": s["id"],
            "correct_answer": s["correct"],
            "your_answer": clean,
            "result": result,
            "score": score,
        }

    def _grade_cascading(self, action: str) -> tuple[float, Dict[str, Any]]:
        """
        Weighted score:
          40% → Priority ordering correctness
          60% → Remediation quality (keyword matching vs expert answer)
        """
        s = CASCADE_SCENARIO
        correct_priority = s["correct_priority"]
        keywords = s["remediation_keywords"]

        # Parse action
        try:
            parsed = json.loads(action)
        except (json.JSONDecodeError, ValueError):
            parsed = {}

        priority: List[str] = parsed.get("priority", [])
        remediations: Dict[str, str] = parsed.get("remediations", {})

        # 1) Priority score (40%)
        priority_score = 0.0
        weights = [0.5, 0.3, 0.2]  # 1st most important, then 2nd, then 3rd
        for i, (pos_weight, correct_id) in enumerate(zip(weights, correct_priority)):
            if i < len(priority) and priority[i] == correct_id:
                priority_score += pos_weight

        # 2) Remediation score (60%) — keyword matching
        remediation_score = 0.0
        for alert_id, kws in keywords.items():
            text = remediations.get(alert_id, "").lower()
            if text:
                hits = sum(1 for kw in kws if kw in text)
                alert_score = min(hits / max(len(kws) * 0.5, 1), 1.0)
                remediation_score += alert_score / len(keywords)

        final = round(min(max(0.4 * priority_score + 0.6 * remediation_score, 0.0), 1.0), 4)

        return final, {
            "scenario": s["id"],
            "priority_score": round(priority_score, 4),
            "remediation_score": round(remediation_score, 4),
            "final_score": final,
            "correct_priority": correct_priority,
            "your_priority": priority,
        }
