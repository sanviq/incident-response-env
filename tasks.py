"""
tasks.py — Scenario definitions for the Incident Response Triage Environment
==============================================================================
Each task has multiple scenarios. Graders expect these keys per scenario:

classify-alert:
  alert, context, severity_scores

select-remediation:
  alert, context, options, option_scores

cascading-alerts:
  alerts (list of {id, alert, severity}), correct_priority_order
"""

from typing import Any, Dict, List

# ──────────────────────────────────────────────────────────────────────────────
#  Task metadata
# ──────────────────────────────────────────────────────────────────────────────

TASKS: Dict[str, Any] = {
    "classify-alert": {
        "difficulty": "easy",
        "max_steps": 1,
        "description": (
            "You are an on-call SRE. Classify the incoming alert as low, medium, or critical. "
            "Respond with the severity label and a brief justification."
        ),
    },
    "select-remediation": {
        "difficulty": "medium",
        "max_steps": 1,
        "description": (
            "You are an on-call SRE. Given the alert and system context, choose the best "
            "remediation action from options A, B, C, or D."
        ),
    },
    "cascading-alerts": {
        "difficulty": "hard",
        "max_steps": 3,
        "description": (
            "You are an on-call SRE. Three alerts have fired simultaneously. "
            "Handle them one at a time, starting with the highest-priority alert. "
            "Each step: state the Alert ID, its severity, and your remediation action."
        ),
    },
}

# ──────────────────────────────────────────────────────────────────────────────
#  Classify-Alert Scenarios  (5 scenarios)
# ──────────────────────────────────────────────────────────────────────────────

CLASSIFY_SCENARIOS: List[Dict[str, Any]] = [
    # 0 — CPU critical on payment server
    {
        "alert": (
            "CPU at 98% on prod-payment-server-01 for 10 minutes. "
            "Payment API p99 latency has tripled. Transactions timing out."
        ),
        "context": {
            "server": "prod-payment-server-01",
            "metric": "cpu_percent",
            "value": 98,
            "duration_mins": 10,
            "service": "payment-api",
            "environment": "production",
            "p99_latency_ms": 4800,
        },
        "severity_scores": {"critical": 1.0, "medium": 0.15, "low": 0.0},
    },
    # 1 — Disk trending medium on log server
    {
        "alert": (
            "Disk usage at 76% on log-aggregator-02. "
            "Trending up ~3%/hour over the last 4 hours."
        ),
        "context": {
            "server": "log-aggregator-02",
            "metric": "disk_percent",
            "value": 76,
            "trend": "increasing",
            "rate_per_hour": "3%",
            "environment": "production",
            "estimated_full_hours": 8,
        },
        "severity_scores": {"medium": 1.0, "critical": 0.25, "low": 0.1},
    },
    # 2 — Memory low on dev box
    {
        "alert": (
            "Memory usage at 52% on dev-sandbox-03. "
            "No anomalies. Stable for 48 hours."
        ),
        "context": {
            "server": "dev-sandbox-03",
            "metric": "memory_percent",
            "value": 52,
            "environment": "development",
            "trend": "stable",
            "uptime_hours": 48,
        },
        "severity_scores": {"low": 1.0, "medium": 0.35, "critical": 0.0},
    },
    # 3 — Database disk full, imminent data loss
    {
        "alert": (
            "PostgreSQL WAL disk at 99% on prod-db-primary. "
            "Write-ahead log writes will fail if disk fills. Data loss risk imminent."
        ),
        "context": {
            "server": "prod-db-primary",
            "metric": "wal_disk_percent",
            "value": 99,
            "database": "postgres-prod",
            "environment": "production",
            "risk": "data_loss",
            "estimated_fill_mins": 4,
        },
        "severity_scores": {"critical": 1.0, "medium": 0.05, "low": 0.0},
    },
    # 4 — Staging CPU elevated but non-critical
    {
        "alert": (
            "CPU at 84% on staging-api-server-01. "
            "Load test running as expected. No production impact."
        ),
        "context": {
            "server": "staging-api-server-01",
            "metric": "cpu_percent",
            "value": 84,
            "environment": "staging",
            "cause": "scheduled_load_test",
            "production_impact": False,
        },
        "severity_scores": {"low": 1.0, "medium": 0.45, "critical": 0.0},
    },
]

# ──────────────────────────────────────────────────────────────────────────────
#  Select-Remediation Scenarios  (5 scenarios)
# ──────────────────────────────────────────────────────────────────────────────

REMEDIATION_SCENARIOS: List[Dict[str, Any]] = [
    # 0 — DB connection pool exhausted
    {
        "alert": (
            "Database connection pool exhausted on prod-db-01. "
            "User-API error rate spiked to 45%."
        ),
        "context": {
            "service": "user-api",
            "error_type": "connection_pool_exhausted",
            "error_rate_pct": 45,
            "current_pool_size": 100,
            "active_connections": 100,
            "database": "postgres-prod",
            "environment": "production",
        },
        "options": {
            "A": "Restart the database server immediately",
            "B": "Increase connection pool size to 200 and restart the user-api service",
            "C": "Enable rate limiting on the API to reduce incoming traffic",
            "D": "Wait 15 minutes and monitor if it self-resolves",
        },
        "option_scores": {"A": 0.05, "B": 1.0, "C": 0.4, "D": 0.0},
    },
    # 1 — Memory leak approaching OOM
    {
        "alert": (
            "Memory leak in recommendation-service. "
            "Heap growing 50 MB/hour. Current: 7.2 GB / 8 GB max. OOM in ~16 minutes."
        ),
        "context": {
            "service": "recommendation-service",
            "issue": "memory_leak",
            "current_heap_gb": 7.2,
            "max_heap_gb": 8.0,
            "growth_rate_mb_per_hour": 50,
            "estimated_oom_mins": 16,
            "environment": "production",
        },
        "options": {
            "A": "Rolling restart of recommendation-service pods to reclaim memory",
            "B": "Increase max heap size to 16 GB immediately",
            "C": "Kill the service immediately to prevent cascade failure",
            "D": "Enable GC logging and wait for automatic cleanup",
        },
        "option_scores": {"A": 1.0, "B": 0.3, "C": 0.1, "D": 0.0},
    },
    # 2 — SSL cert expiring in 2 hours
    {
        "alert": (
            "SSL certificate for api.company.com expires in 2 hours. "
            "Auto-renewal failed (DNS challenge error)."
        ),
        "context": {
            "domain": "api.company.com",
            "cert_expiry_hours": 2,
            "affected_services": ["mobile-app", "web-frontend", "partner-api"],
            "auto_renewal_status": "failed - DNS challenge error",
            "environment": "production",
        },
        "options": {
            "A": "Manually renew certificate using certbot with DNS challenge fix",
            "B": "Switch all services to HTTP temporarily until cert renews",
            "C": "Enable HTTP bypass in nginx config for all services",
            "D": "Contact SSL provider support and wait for their response",
        },
        "option_scores": {"A": 1.0, "B": 0.0, "C": 0.0, "D": 0.1},
    },
    # 3 — Deployment causing 5xx errors
    {
        "alert": (
            "5xx error rate on checkout-service spiked to 22% immediately after v2.4.1 deployment. "
            "Deployment completed 8 minutes ago."
        ),
        "context": {
            "service": "checkout-service",
            "error_rate_pct": 22,
            "deployment_version": "v2.4.1",
            "mins_since_deploy": 8,
            "previous_version": "v2.4.0",
            "environment": "production",
            "rollback_available": True,
        },
        "options": {
            "A": "Scale up checkout-service pods from 4 to 8 to handle load",
            "B": "Roll back to v2.4.0 immediately",
            "C": "Restart all checkout-service pods without rollback",
            "D": "Increase DB connection timeout values in config",
        },
        "option_scores": {"A": 0.1, "B": 1.0, "C": 0.2, "D": 0.0},
    },
    # 4 — Postgres blocking queries causing latency
    {
        "alert": (
            "Database query latency p99 at 12s on prod-db-primary. "
            "3 long-running queries have held locks for >20 minutes."
        ),
        "context": {
            "database": "prod-db-primary",
            "p99_latency_secs": 12,
            "blocking_queries": 3,
            "lock_duration_mins": 20,
            "affected_services": ["user-api", "order-service"],
            "environment": "production",
        },
        "options": {
            "A": "Restart the PostgreSQL service to clear all locks",
            "B": "Increase max_connections and reload Postgres config",
            "C": "Identify and pg_terminate_backend() the blocking query PIDs",
            "D": "Add a database index on the most-queried column",
        },
        "option_scores": {"A": 0.1, "B": 0.0, "C": 1.0, "D": 0.0},
    },
]

# ──────────────────────────────────────────────────────────────────────────────
#  Cascading-Alert Scenarios  (3 full incident scenarios)
# ──────────────────────────────────────────────────────────────────────────────

CASCADE_SCENARIOS: List[Dict[str, Any]] = [
    # 0 — Payment outage + DB lag + internal dashboard
    {
        "alerts": [
            {
                "id": "ALERT-001",
                "alert": "Payment service returning 503 errors. 80% of checkout transactions failing.",
                "severity": "critical",
            },
            {
                "id": "ALERT-002",
                "alert": "Database read-replica lag at 45 seconds. Some reads returning stale data.",
                "severity": "medium",
            },
            {
                "id": "ALERT-003",
                "alert": "Internal metrics dashboard (Grafana) is down. No customer-facing impact.",
                "severity": "low",
            },
        ],
        # Payment outage > DB lag (affects reads) > internal tooling
        "correct_priority_order": ["ALERT-001", "ALERT-002", "ALERT-003"],
    },
    # 1 — Auth service down + high memory + cron job failure
    {
        "alerts": [
            {
                "id": "ALERT-A",
                "alert": "Auth service is returning 401 for all login attempts. Users cannot log in.",
                "severity": "critical",
            },
            {
                "id": "ALERT-B",
                "alert": "Nightly billing cron job failed silently. Invoices not sent for today.",
                "severity": "medium",
            },
            {
                "id": "ALERT-C",
                "alert": "Worker node memory at 88% on k8s-worker-04. No evictions yet.",
                "severity": "medium",
            },
        ],
        # Auth outage blocks all users > memory (could cascade) > billing (time-sensitive but async)
        "correct_priority_order": ["ALERT-A", "ALERT-C", "ALERT-B"],
    },
    # 2 — Kubernetes node down + cache miss storm + slow CDN
    {
        "alerts": [
            {
                "id": "INC-1",
                "alert": "Kubernetes node k8s-prod-node-07 is NotReady. 12 pods rescheduling.",
                "severity": "critical",
            },
            {
                "id": "INC-2",
                "alert": "Redis cache hit rate dropped to 8%. Services are hammering the database directly.",
                "severity": "critical",
            },
            {
                "id": "INC-3",
                "alert": "CDN edge cache miss rate elevated at 35%. Page load times up by 600ms.",
                "severity": "low",
            },
        ],
        # Node down causes pod rescheduling (infra layer) > cache miss storm (active DB risk) > CDN perf
        "correct_priority_order": ["INC-1", "INC-2", "INC-3"],
    },
]

# ──────────────────────────────────────────────────────────────────────────────
#  Public API used by environment.py
# ──────────────────────────────────────────────────────────────────────────────

def list_tasks() -> List[str]:
    return list(TASKS.keys())


def get_task_info(task_name: str) -> Dict[str, Any]:
    if task_name not in TASKS:
        raise ValueError(f"Unknown task: {task_name}")
    return TASKS[task_name]


def get_task_scenario(task_name: str, scenario_index: int) -> Dict[str, Any]:
    """Return scenario at index, clamped to available range."""
    if task_name == "classify-alert":
        pool = CLASSIFY_SCENARIOS
    elif task_name == "select-remediation":
        pool = REMEDIATION_SCENARIOS
    elif task_name == "cascading-alerts":
        pool = CASCADE_SCENARIOS
    else:
        raise ValueError(f"Unknown task: {task_name}")

    idx = scenario_index % len(pool)  # wrap around safely
    return pool[idx]


def scenario_count(task_name: str) -> int:
    """Return total number of scenarios for a task."""
    if task_name == "classify-alert":
        return len(CLASSIFY_SCENARIOS)
    elif task_name == "select-remediation":
        return len(REMEDIATION_SCENARIOS)
    elif task_name == "cascading-alerts":
        return len(CASCADE_SCENARIOS)
    return 0