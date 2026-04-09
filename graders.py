import re
from typing import Dict, Any, List


def _extract_severity(response: str) -> str | None:
    """
    Extract the agent's intended severity from the response.
    Looks for the FIRST standalone severity word to avoid false positives
    (e.g. 'medium - not critical yet' should return 'medium').
    """
    # Try pattern: starts with severity or "severity: X"
    response_lower = response.lower().strip()
    patterns = [
        r"^(critical|medium|low)\b",                    # starts with severity
        r"severity[:\s]+(critical|medium|low)\b",       # "severity: critical"
        r"\bclassif\w*[:\s]+(critical|medium|low)\b",  # "classification: medium"
        r"\bis\s+(critical|medium|low)\b",              # "is critical"
    ]
    for pattern in patterns:
        m = re.search(pattern, response_lower)
        if m:
            return m.group(1)

    # Fallback: find FIRST occurrence of any severity word
    for word in re.findall(r"\b(critical|medium|low)\b", response_lower):
        return word

    return None


def grade_classify_alert(response: str, scenario: Dict[str, Any]) -> float:
    """
    Grade classify-alert task using weighted metrics:
    - Accuracy (80%)  : correct severity label
    - Quality  (20%)  : reasoning word count
    """
    severity_scores: Dict[str, float] = scenario["severity_scores"]
    detected = _extract_severity(response)
    accuracy_score = severity_scores.get(detected, 0.0) if detected else 0.0

    word_count = len(response.split())
    quality_score = min(1.0, word_count / 15.0)

    final = accuracy_score * 0.8 + quality_score * 0.2
    return round(min(max(final, 0.01), 0.99), 3)


def grade_select_remediation(response: str, scenario: Dict[str, Any]) -> float:
    """
    Grade select-remediation task using weighted metrics:
    - Option correctness (75%) : correct letter chosen
    - Reasoning quality  (25%) : explanation length
    """
    response_upper = response.upper()
    option_scores: Dict[str, float] = scenario["option_scores"]

    detected_option = None
    patterns = [
        r"option\s+([ABCD])\b",
        r"\boption([ABCD])\b",
        r"\b([ABCD])\.\s",
        r"answer[:\s]+([ABCD])\b",
        r"choose\s+([ABCD])\b",
        r"select\s+([ABCD])\b",
        r"go\s+with\s+([ABCD])\b",
        r"^([ABCD])\b",            # starts with letter
        r"\b([ABCD])\s+[-–]",      # "B - restart..."
    ]
    for pattern in patterns:
        m = re.search(pattern, response_upper)
        if m:
            detected_option = m.group(1)
            break

    option_score = option_scores.get(detected_option, 0.0) if detected_option else 0.0
    reasoning_score = min(1.0, len(response.split()) / 25.0)

    final = option_score * 0.75 + reasoning_score * 0.25
    return round(min(max(final, 0.01), 0.99), 3)


def grade_cascading_alerts(
    response: str,
    step: int,
    scenario: Dict[str, Any],
    handled_alerts: List[str],
) -> float:
    """
    Grade cascading-alerts per step using weighted metrics:
    - Priority correctness  (40%) : right alert handled at this step
    - Alert identification  (30%) : valid alert ID referenced
    - Remediation quality   (30%) : response detail
    """
    response_upper = response.upper()
    correct_priority: List[str] = scenario["correct_priority_order"]
    alert_ids = [a["id"] for a in scenario["alerts"]]

    expected_id = correct_priority[step - 1] if step <= len(correct_priority) else None

    detected_id = None
    for aid in alert_ids:
        if aid.upper() in response_upper:
            detected_id = aid
            break

    if detected_id == expected_id:
        priority_score = 0.99
    elif detected_id in correct_priority:
        priority_score = 0.4  # valid alert, wrong order
    else:
        priority_score = 0.05

    identification_score = 0.99 if detected_id else 0.01
    remediation_score = min(1.0, len(response.split()) / 30.0)

    final = (
        priority_score * 0.4
        + identification_score * 0.3
        + remediation_score * 0.3
    )
    return round(min(max(final, 0.01), 0.99), 3)
