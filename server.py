from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

from models import IncidentAction, ResetResult, StepResult, StateResult
from environment import IncidentResponseEnv
from tasks import list_tasks, TASKS

app = FastAPI(
    title="Incident Response Triage Environment",
    description="A real-world OpenEnv environment where an AI agent acts as an on-call SRE, triaging production incidents across three tasks of increasing difficulty.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env = IncidentResponseEnv()


class ResetRequest(BaseModel):
    task: Optional[str] = "classify-alert"
    scenario_index: Optional[int] = 0


@app.get("/")
def root():
    return {
        "name": "Incident Response Triage Environment",
        "version": "1.0.0",
        "tasks": list_tasks(),
        "status": "ready",
        "docs": "/docs",
    }


# ✅ FIXED: return "healthy" not "ok"
@app.get("/health")
def health():
    return {"status": "healthy"}


# ✅ NEW: /metadata endpoint
@app.get("/metadata")
def metadata():
    return {
        "name": "Incident Response Triage Environment",
        "description": (
            "A real-world OpenEnv environment simulating production incident response. "
            "An AI agent acts as an on-call SRE, classifying alerts, selecting remediations, "
            "and handling cascading failures across three tasks of increasing difficulty."
        ),
        "version": "1.0.0",
        "tasks": [
            {"name": name, "difficulty": info["difficulty"], "max_steps": info["max_steps"]}
            for name, info in TASKS.items()
        ],
    }


# ✅ NEW: /schema endpoint
@app.get("/schema")
def schema():
    return {
        "action": {
            "type": "object",
            "properties": {
                "response": {
                    "type": "string",
                    "description": "Agent free-text response to the alert",
                }
            },
            "required": ["response"],
        },
        "observation": {
            "type": "object",
            "properties": {
                "task_name": {"type": "string"},
                "step_number": {"type": "integer"},
                "alert_message": {"type": "string"},
                "system_context": {"type": "object"},
                "options": {"type": "object", "nullable": True},
                "pending_alerts": {"type": "array", "nullable": True},
                "task_description": {"type": "string"},
                "hint": {"type": "string", "nullable": True},
            },
        },
        "state": {
            "type": "object",
            "properties": {
                "task_name": {"type": "string"},
                "step_number": {"type": "integer"},
                "done": {"type": "boolean"},
                "cumulative_reward": {"type": "number"},
                "max_steps": {"type": "integer"},
            },
        },
    }


# ✅ NEW: /mcp endpoint (JSON-RPC)
@app.post("/mcp")
def mcp(request: dict = None):
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "name": "Incident Response Triage Environment",
            "version": "1.0.0",
            "capabilities": {
                "reset": True,
                "step": True,
                "state": True,
            },
        },
    }


@app.post("/reset", response_model=ResetResult)
def reset(request: ResetRequest = ResetRequest()):
    task = request.task or "classify-alert"
    if task not in TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task '{task}'. Valid tasks: {list_tasks()}",
        )
    result = env.reset(task_name=task, scenario_index=request.scenario_index or 0)
    return result


@app.post("/step", response_model=StepResult)
def step(action: IncidentAction):
    if env.done:
        raise HTTPException(
            status_code=400,
            detail="Episode is finished. Call POST /reset to start a new episode.",
        )
    try:
        result = env.step(action)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@app.get("/state", response_model=StateResult)
def state():
    return env.state()


@app.get("/tasks")
def get_tasks():
    return {
        "tasks": [
            {
                "name": name,
                "difficulty": info["difficulty"],
                "max_steps": info["max_steps"],
                "description": info["description"],
            }
            for name, info in TASKS.items()
        ]
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
