from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class IncidentAction(BaseModel):
    response: str


class AlertObservation(BaseModel):
    task_name: str
    step_number: int
    alert_message: str
    system_context: Dict[str, Any]
    options: Optional[Dict[str, str]] = None
    pending_alerts: Optional[List[Dict[str, Any]]] = None
    task_description: str
    hint: Optional[str] = None


class StepResult(BaseModel):
    observation: AlertObservation
    reward: float
    done: bool
    info: Dict[str, Any]


class ResetResult(BaseModel):
    observation: AlertObservation
    state: Dict[str, Any]


class StateResult(BaseModel):
    task_name: str
    step_number: int
    done: bool
    cumulative_reward: float
    max_steps: int
