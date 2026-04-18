# Failure Modes and Recovery Behavior

This document explains how Tixora-AI handles common failure scenarios in production-style runs.

## 1. Tool Timeout

- Trigger: upstream call stalls long enough to raise `asyncio.TimeoutError`.
- Where handled: `tools/tool_executor.py`.
- Recovery: automatic retries with exponential backoff (`0.5s -> 1s -> 2s`).
- Result: if retries still fail, the call is marked fatal and routed through normal escalation/DLQ flow.

## 2. Corrupted Response Payload

- Trigger: payload shape is invalid (for example, corrupted fields).
- Where handled: `tools/tool_executor.py` validation checks.
- Recovery: raises `ValueError`, then retries using the same backoff strategy.
- Result: successful retry continues processing; repeated failure is treated as tool exhaustion.

## 3. Low Confidence Decision

- Trigger: final confidence score falls below `0.7`.
- Where handled: `agent/confidence.py` and `agent/react_loop.py`.
- Recovery: auto-resolution is overridden and the ticket is escalated with context.
- Result: risky automation is avoided, and a human specialist takes over.

## 4. Partial Data Response

- Trigger: response is structurally valid but missing expected keys.
- Where handled: `tools/tool_executor.py`.
- Recovery: logged as a soft issue; execution continues with available context.
- Result: pipeline stays live, and confidence penalties may later trigger escalation.

## 5. Tool Exhaustion and Dead Letter Queue

- Trigger: all retry attempts fail for a tool call.
- Where handled: `tools/tool_executor.py` + `agent/react_loop.py`.
- Recovery: ticket step is marked as fatal and written to `logs/dead_letter_queue.json`.
- Result: one failing ticket doesn't stop the whole batch.

## Summary Table

| Scenario          | Primary Handler          | Outcome                            |
| :---------------- | :----------------------- | :--------------------------------- |
| Timeout           | `tools/tool_executor.py` | Retry with exponential backoff     |
| Corrupted payload | `tools/tool_executor.py` | Validation failure + retry         |
| Low confidence    | `agent/confidence.py`    | Forced escalation                  |
| Partial data      | `tools/tool_executor.py` | Continue with warnings             |
| Tool exhaustion   | `agent/react_loop.py`    | DLQ capture and batch continuation |
