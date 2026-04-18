import json
import os
import sys


REQUIRED_TOP_LEVEL_FIELDS = {
    "ticket_id",
    "classification",
    "reasoning_chain",
    "decision",
    "confidence",
    "status",
}

REQUIRED_STEP_FIELDS = {"thought", "action", "observation"}


def _load_audit(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audit file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Audit file must contain a list of ticket results")

    return data


def _check(data):
    findings = []

    if not data:
        findings.append("Audit log is empty")
        return findings

    for idx, ticket in enumerate(data):
        missing_top = [k for k in REQUIRED_TOP_LEVEL_FIELDS if k not in ticket]
        if missing_top:
            findings.append(f"Ticket index {idx} missing top-level fields: {missing_top}")

        chain = ticket.get("reasoning_chain", [])
        if not isinstance(chain, list):
            findings.append(f"Ticket {ticket.get('ticket_id', idx)} reasoning_chain is not a list")
            continue

        if len(chain) < 3:
            findings.append(f"Ticket {ticket.get('ticket_id', idx)} has fewer than 3 reasoning steps")

        for step_idx, step in enumerate(chain):
            missing_step = [k for k in REQUIRED_STEP_FIELDS if k not in step]
            if missing_step:
                findings.append(
                    f"Ticket {ticket.get('ticket_id', idx)} step {step_idx + 1} missing step fields: {missing_step}"
                )

        if "confidence" in ticket and not isinstance(ticket.get("confidence"), (int, float)):
            findings.append(f"Ticket {ticket.get('ticket_id', idx)} confidence is not numeric")

    return findings


def main():
    audit_path = sys.argv[1] if len(sys.argv) > 1 else "logs/audit_log.json"

    try:
        data = _load_audit(audit_path)
    except Exception as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)

    findings = _check(data)
    escalated = sum(1 for t in data if "escalat" in str(t.get("decision", "")).lower())
    successful = sum(1 for t in data if t.get("status") == "success")

    print(f"tickets={len(data)} success={successful} escalated={escalated}")

    if findings:
        print("FAIL")
        for issue in findings:
            print(f"- {issue}")
        sys.exit(1)

    print("PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
