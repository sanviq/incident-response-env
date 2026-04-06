from typing import Dict, Any, List

from models import AlertObservation, StepResult, ResetResult, StateResult, IncidentAction
from tasks import get_task_info, get_task_scenario, list_tasks, TASKS
from graders import grade_classify_alert, grade_select_remediation, grade_cascading_alerts


class IncidentResponseEnv:
    """
    OpenEnv-compatible environment simulating production incident response.

    Three tasks of increasing difficulty:
      - classify-alert      (easy)   : classify alert severity
      - select-remediation  (medium) : pick the correct fix from 4 options
      - cascading-alerts    (hard)   : prioritise and resolve 3 simultaneous alerts
    """

    def __init__(self) -> None:
        self.task_name: str = "classify-alert"
        self.step_number: int = 0
        self.max_steps: int = 1
        self.done: bool = False
        self.cumulative_reward: float = 0.0
        self.scenario: Dict[str, Any] = {}
        self.scenario_index: int = 0
        self.handled_alerts: List[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self, task_name: str = "classify-alert", scenario_index: int = 0) -> ResetResult:
        if task_name not in TASKS:
            raise ValueError(f"Unknown task '{task_name}'. Valid: {list_tasks()}")

        self.task_name = task_name
        self.scenario_index = scenario_index
        self.step_number = 0
        self.done = False
        self.cumulative_reward = 0.0
        self.handled_alerts = []

        task_info = get_task_info(task_name)
        self.max_steps = task_info["max_steps"]
        self.scenario = get_task_scenario(task_name, scenario_index)

        return ResetResult(
            observation=self._build_observation(),
            state=self._get_state_dict(),
        )

    def step(self, action: IncidentAction) -> StepResult:
        if self.done:
            raise RuntimeError("Episode finished. Call reset() to begin a new episode.")

        self.step_number += 1

        reward = self._compute_reward(action.response)
        self.cumulative_reward = round(self.cumulative_reward + reward, 3)

        # Track which alerts have been addressed for cascading task
        if self.task_name == "cascading-alerts":
            for alert in self.scenario["alerts"]:
                aid = alert["id"]
                if aid.upper() in action.response.upper() and aid not in self.handled_alerts:
                    self.handled_alerts.append(aid)

        self.done = self.step_number >= self.max_steps

        return StepResult(
            observation=self._build_observation(),
            reward=reward,
            done=self.done,
            info={
                "step": self.step_number,
                "max_steps": self.max_steps,
                "cumulative_reward": self.cumulative_reward,
                "task": self.task_name,
            },
        )

    def state(self) -> StateResult:
        return StateResult(
            task_name=self.task_name,
            step_number=self.step_number,
            done=self.done,
            cumulative_reward=self.cumulative_reward,
            max_steps=self.max_steps,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_reward(self, response: str) -> float:
        if self.task_name == "classify-alert":
            return grade_classify_alert(response, self.scenario)
        if self.task_name == "select-remediation":
            return grade_select_remediation(response, self.scenario)
        if self.task_name == "cascading-alerts":
            return grade_cascading_alerts(
                response, self.step_number, self.scenario, self.handled_alerts
            )
        return 0.0

    def _build_observation(self) -> AlertObservation:
        task_info = get_task_info(self.task_name)

        if self.task_name == "classify-alert":
            return AlertObservation(
                task_name=self.task_name,
                step_number=self.step_number,
                alert_message=self.scenario["alert"],
                system_context=self.scenario["context"],
                task_description=task_info["description"],
                hint="Respond with: low, medium, or critical — and briefly explain why.",
            )

        if self.task_name == "select-remediation":
            return AlertObservation(
                task_name=self.task_name,
                step_number=self.step_number,
                alert_message=self.scenario["alert"],
                system_context=self.scenario["context"],
                options=self.scenario["options"],
                task_description=task_info["description"],
                hint="Respond with the option letter (A/B/C/D) and your reasoning.",
            )

        if self.task_name == "cascading-alerts":
            remaining = [
                a for a in self.scenario["alerts"]
                if a["id"] not in self.handled_alerts
            ]
            return AlertObservation(
                task_name=self.task_name,
                step_number=self.step_number,
                alert_message=(
                    f"You have {len(remaining)} alert(s) remaining. "
                    "Handle the highest-priority one now."
                ),
                system_context={
                    "total_alerts": 3,
                    "handled_count": len(self.handled_alerts),
                    "remaining_count": len(remaining),
                },
                pending_alerts=remaining,
                task_description=task_info["description"],
                hint=(
                    "Respond with: ALERT ID, severity (low/medium/critical), "
                    "and your remediation action."
                ),
            )

        # fallback
        return AlertObservation(
            task_name=self.task_name,
            step_number=self.step_number,
            alert_message="Unknown task.",
            system_context={},
            task_description="",
        )

    def _get_state_dict(self) -> Dict[str, Any]:
        return {
            "task_name": self.task_name,
            "step_number": self.step_number,
            "max_steps": self.max_steps,
            "done": self.done,
            "cumulative_reward": self.cumulative_reward,
            "scenario_index": self.scenario_index,
        }
