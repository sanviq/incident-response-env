from typing import Dict, Any, List

TASKS: Dict[str, Any] = {
    "classify-alert": {
        "difficulty": "easy",
        "max_steps": 1,
        "description": (
            "You are an on-call SRE. A system alert has come in. "
            "Classify it as 'low', 'medium', or 'critical' severity and explain your reasoning briefly."
        ),
        "scenarios": [
            {
                "alert": "CPU usage has been at 98% for 12 minutes on production payment server prod-pay-01.",
                "context": {
                    "server": "prod-pay-01",
                    "service": "payment-api",
                    "cpu_percent": 98,
                    "duration_minutes": 12,
                    "environment": "production",
                },
                "correct_severity": "critical",
                "severity_scores": {"critical": 1.0, "medium": 0.3, "low": 0.0},
            },
            {
                "alert": "Disk usage at 65% on the log archival server log-archive-02.",
                "context": {
                    "server": "log-archive-02",
                    "service": "log-archiver",
                    "disk_percent": 65,
                    "environment": "non-production",
                },
                "correct_severity": "low",
                "severity_scores": {"low": 1.0, "medium": 0.4, "critical": 0.0},
            },
            {
                "alert": "Memory usage at 84% and rising on API gateway gw-01. No OOM errors yet.",
                "context": {
                    "server": "gw-01",
                    "service": "api-gateway",
                    "memory_percent": 84,
                    "trend": "increasing",
                    "oom_errors": False,
                },
                "correct_severity": "medium",
                "severity_scores": {"medium": 1.0, "critical": 0.5, "low": 0.1},
            },
            {
                "alert": "Production database connection pool exhausted: 0/200 connections available. Queries timing out.",
                "context": {
                    "server": "db-prod-01",
                    "service": "postgresql",
                    "connections_available": 0,
                    "connections_max": 200,
                    "queries_timing_out": True,
                },
                "correct_severity": "critical",
                "severity_scores": {"critical": 1.0, "medium": 0.2, "low": 0.0},
            },
            {
                "alert": "SSL certificate for staging.example.com expires in 40 days.",
                "context": {
                    "server": "staging-web",
                    "service": "nginx",
                    "days_remaining": 40,
                    "environment": "staging",
                },
                "correct_severity": "low",
                "severity_scores": {"low": 1.0, "medium": 0.5, "critical": 0.0},
            },
        ],
    },

    "select-remediation": {
        "difficulty": "medium",
        "max_steps": 1,
        "description": (
            "You are an on-call SRE. Given a system alert and context, select the best immediate "
            "remediation action. Respond with the option letter (A, B, C, or D) and a brief justification."
        ),
        "scenarios": [
            {
                "alert": (
                    "Out of memory error on web server web-02. "
                    "Node.js app is consuming 7.9 GB of 8 GB RAM. Response times are degraded."
                ),
                "context": {
                    "server": "web-02",
                    "service": "node-app",
                    "memory_used_gb": 7.9,
                    "memory_total_gb": 8.0,
                    "uptime_hours": 68,
                    "recent_deploy": False,
                },
                "options": {
                    "A": "Upgrade the server instance to one with more RAM immediately",
                    "B": "Restart the Node.js service to free memory, then investigate the memory leak",
                    "C": "Kill the highest memory-consuming process without restarting",
                    "D": "Reduce the number of worker threads in the application config",
                },
                "correct_option": "B",
                "option_scores": {"B": 1.0, "D": 0.4, "C": 0.2, "A": 0.1},
            },
            {
                "alert": (
                    "5xx error rate spiked to 45% on the checkout service. "
                    "Started 8 minutes after a new deployment."
                ),
                "context": {
                    "service": "checkout-api",
                    "error_rate_pct": 45,
                    "recent_deployment": True,
                    "deployment_age_minutes": 12,
                    "traffic_normal": True,
                },
                "options": {
                    "A": "Scale up checkout service instances to handle the load",
                    "B": "Roll back the deployment made 12 minutes ago",
                    "C": "Flush the application cache and CDN",
                    "D": "Restart the downstream payment microservice",
                },
                "correct_option": "B",
                "option_scores": {"B": 1.0, "A": 0.3, "C": 0.2, "D": 0.1},
            },
            {
                "alert": (
                    "Database query latency spiked from 15 ms to 3200 ms. "
                    "Active connections: 480/500. 47 queries waiting on locks."
                ),
                "context": {
                    "service": "postgresql",
                    "avg_latency_ms": 3200,
                    "baseline_ms": 15,
                    "active_connections": 480,
                    "max_connections": 500,
                    "locks_waiting": 47,
                },
                "options": {
                    "A": "Restart the PostgreSQL service immediately",
                    "B": "Increase max_connections in postgresql.conf and reload",
                    "C": "Identify and terminate the long-running blocking queries",
                    "D": "Add a read replica to distribute the load",
                },
                "correct_option": "C",
                "option_scores": {"C": 1.0, "B": 0.3, "D": 0.2, "A": 0.0},
            },
        ],
    },

    "cascading-alerts": {
        "difficulty": "hard",
        "max_steps": 3,
        "description": (
            "You are an on-call SRE facing 3 simultaneous production alerts. "
            "Handle them one at a time, highest priority first. "
            "Each response must include: the Alert ID, the severity (low/medium/critical), "
            "and your remediation action."
        ),
        "scenarios": [
            {
                "alerts": [
                    {
                        "id": "ALERT-001",
                        "alert": "SSL certificate for api.prod.example.com expires in 28 days.",
                        "context": {
                            "service": "nginx",
                            "environment": "production",
                            "days_remaining": 28,
                        },
                        "correct_severity": "low",
                    },
                    {
                        "id": "ALERT-002",
                        "alert": (
                            "Production database disk usage at 99.1%. "
                            "Write operations are failing. Risk of data loss."
                        ),
                        "context": {
                            "service": "postgresql",
                            "disk_percent": 99.1,
                            "writes_failing": True,
                            "data_loss_risk": True,
                        },
                        "correct_severity": "critical",
                    },
                    {
                        "id": "ALERT-003",
                        "alert": "Background job worker memory at 79% and climbing. No job failures yet.",
                        "context": {
                            "service": "celery-worker",
                            "memory_percent": 79,
                            "trend": "increasing",
                            "job_failures": False,
                        },
                        "correct_severity": "medium",
                    },
                ],
                "correct_priority_order": ["ALERT-002", "ALERT-003", "ALERT-001"],
            },
        ],
    },
}


def get_task_info(task_name: str) -> Dict[str, Any]:
    return TASKS[task_name]


def get_task_scenario(task_name: str, scenario_index: int = 0) -> Dict[str, Any]:
    scenarios = TASKS[task_name]["scenarios"]
    return scenarios[scenario_index % len(scenarios)]


def list_tasks() -> List[str]:
    return list(TASKS.keys())
