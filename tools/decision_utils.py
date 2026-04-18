"""Shared decision helpers used across CLI, metrics, and UI."""


def is_escalated_decision(decision: str) -> bool:
    """Return True when a decision string indicates escalation."""
    return "escalat" in str(decision or "").lower()
