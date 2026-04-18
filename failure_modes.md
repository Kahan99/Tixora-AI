# Failure Modes & Reliability Architecture

This document dictates explicitly how Tixora-AI implements its production-grade reliability design. The system handles external dependency failures, degraded network states, and unexpected API responses gracefully without crashing the core agent loop.

The failures documented below are actively tested during runtime via an embedded chaos engineering simulator (`mocks/failure_simulator.py`) alongside strict schema-bound executor wrappers.

---

## 1. Tool Timeout

*   **Trigger**: A simulated network disruption where upstream services stall. Injected by `mocks/failure_simulator.py` which induces a 15% chance of triggering an `asyncio.TimeoutError` (and introduces random baseline jitter of 0.1s to 1.5s).
*   **Detection**: The `tools/tool_executor.py` wrapper specifically catches `asyncio.TimeoutError` during execution try/except blocks.
*   **Handling**: The executor aggressively retries the call up to 3 total times implementing exponential backoff intervals: `0.5s → 1s → 2s`.
*   **Outcome**: If the retry succeeds, processing continues unhindered. If all 3 attempts time out, the system triggers Complete Tool Exhaustion (Scenario 5).
*   **Code Location**: `tools/tool_executor.py`, `mocks/failure_simulator.py`

---

## 2. Malformed Tool Response (Corrupted Schema)

*   **Trigger**: Upstream service responds successfully (Status 200) but payloads contain corrupted binary strings or schema mismatches. Injected by `mocks/failure_simulator.py` with a 15% chance returning: `{"corrupted": "unreadable_binary_data", "status_code": 200}`.
*   **Detection**: `tools/tool_executor.py` explicitly searches the result for the literal `"corrupted"` key, and enforces downstream type validation (expecting proper dict or list structures mapping to Pydantic definitions).
*   **Handling**: Detects the corruption and explicitly raises a `ValueError`, immediately triggering the standard retry sequence with exponential backoff (`0.5s → 1s → 2s`).
*   **Outcome**: Similar to timeouts, if a clean payload is fetched on a retry, processing resumes safely. Otherwise, it is exhausted and sent to the DLQ.
*   **Code Location**: `tools/tool_executor.py`, `mocks/failure_simulator.py`

---

## 3. Confidence Below Threshold (< 0.7)

*   **Trigger**: The agent formulates a resolution plan, but the internal trajectory was heavily penalized (multiple failed steps, excessive looping overhead).
*   **Detection**: After the core ReAct loop finishes its progression, the governance layer executes a fixed formula calculating confidence from 0.0 to 1.0: `0.35 + (steps × 0.07) + (successes × 0.08) - (failures × 0.12)`. It caps at 0.98. The system flags if this score is `< 0.7`.
*   **Handling**: Tixora-AI completely overrides its own final decision. It resets the state to `"auto_escalated_low_confidence"` overriding any local action proposal enforcing extreme safety.
*   **Outcome**: The ticket is actively escalated alongside a structured summary to a human support agent instead of trusting unconfident automation.
*   **Code Location**: `agent/confidence.py`

---

## 4. Partial Data Response (Missing Keys)

*   **Trigger**: The upstream database or API returns disjointed data. Injected by `mocks/failure_simulator.py` which induces a 10% chance of randomly deleting exactly half the keys from an otherwise valid response dictionary.
*   **Detection**: Tracked passively by `tools/tool_executor.py` which registers and flags missing required payload keys natively without fully failing dict-parsing.
*   **Handling**: Unlike corruption, partial data is treated as a soft warning. It gets written out to logs cleanly (preventing a crash) and passes whatever data was scraped back to the agent core.
*   **Outcome**: The cognitive agent dynamically receives partial states. It attempts to reason with whatever data is left over. While the loop does not crash, the failure to lookup complete data penalizes the confidence score eventually triggering an escalation later.
*   **Code Location**: `tools/tool_executor.py`, `mocks/failure_simulator.py`

---

## 5. Complete Tool Exhaustion / Dead Letter Queue

*   **Trigger**: An external tool consistently fails every single one of its 3 allocated retry attempts whether via an unresponsive 502 Bad Gateway, Timeout, or unending corruption errors.
*   **Detection**: `tools/tool_executor.py` exhausts its while loop and safely returns a fatal `None` object explicitly to the cognitive loop.
*   **Handling**: Once caught by `agent/react_loop.py`, the state is permanently assigned `status="fatal_failure"`. It forcefully executes the `log_to_dlq()` function writing the `ticket_id`, `failed_at` timestamp, underlying `reason`, and full `tool_history` string dump into `logs/dead_letter_queue.json`.
*   **Outcome**: The precise ticket step is abandoned cleanly into the Dead Letter Queue. The agent does NOT crash the entire ticket process; instead, it progresses other internal logic. Further, at the batch level (`main.py`), `asyncio.gather(return_exceptions=True)` ensures any actual unhandled exceptions are caught transforming gracefully to an isolated `status="failed"` state preserving the batch.
*   **Code Location**: `tools/tool_executor.py`, `agent/react_loop.py`, `main.py`


## Summary Overview

| Failure Scenario | Detection Trigger File | Outcome |
| :--- | :--- | :--- |
| **Tool Timeout** | `tool_executor.py` | Retries 3x w/ exponential backoff (0.5s → 1s → 2s) |
| **Malformed Tool Response (Schema)** | `tool_executor.py` | Raises ValueError and retries 3x w/ exponential backoff |
| **Confidence Below Threshold** | `confidence.py` | Escaped logic enforcing Human Agent Escalation overridden state |
| **Partial Data Response** | `tool_executor.py` | Logs soft warning, continues with partial data |
| **Tool Exhaustion / Dead Letter Queue** | `react_loop.py` | Logs directly to `dead_letter_queue.json`, isolated batch continuation preserved via `main.py` |
