# Tixora-AI Architecture

## 1. System Overview

Tixora-AI is ShopWave's autonomous support resolution service. It triages tickets, gathers evidence through tool calls, and either resolves safely or escalates with context.

## 2. Design Principles

- Local policy first: the core path runs without external AI dependencies.
- Bounded ReAct: decisions follow explicit branches and safety gates.
- Fail safe: low-confidence outcomes are escalated instead of auto-resolved.
- Full traceability: every ticket leaves a structured audit trail.

## 3. Runtime Layers

### Ingestion (`main.py`)

Loads a ticket batch from JSON, applies optional limits, and dispatches concurrent workers with `asyncio.gather` and a semaphore.

### Classification (`agent/classifier.py`)

Classifies category, urgency, and resolvability using local heuristics by default. Optional LLM mode is available via `AGENT_MODE=llm`.

### Resolution Loop (`agent/react_loop.py`)

Runs a bounded Think -> Act -> Observe sequence. Enforces policy gates, including refund eligibility checks before refund execution.

### Tool Execution (`tools/tool_executor.py`)

Wraps every tool call with retries, exponential backoff, payload validation, and DLQ handoff for unrecoverable failures.

### Tooling + Failure Simulation (`tools/`, `mocks/`)

Read and write tools simulate external systems. Failure simulation injects realistic timeouts and malformed responses to stress recovery logic.

### Confidence + Escalation (`agent/confidence.py`)

Calculates confidence from the reasoning chain. Scores below `0.7` trigger automatic escalation with full context.

### Audit + Metrics (`logs/`, `tools/metrics_collector.py`)

Persists per-ticket traces and summary metrics for operational visibility.

## 4. Typical Tool Flows

- Refund flow
  `get_customer -> get_order -> check_refund_eligibility -> issue_refund -> send_reply`

- Order status flow
  `get_customer -> get_order -> search_knowledge_base -> send_reply`

- Complaint flow
  `get_customer -> search_knowledge_base -> escalate -> send_reply`

## 5. Concurrency Model

Workers run asynchronously with `asyncio.gather(return_exceptions=True)`. The semaphore guard (`MAX_CONCURRENCY`) prevents overload while keeping throughput high.

## 6. Failure Handling

Transient failures are retried automatically. Hard failures are routed to the dead-letter queue so one ticket can't stall the whole batch.

## 7. Audit Log Shape

Each ticket record contains:

- `ticket_id`
- `classification`
- `reasoning_chain`
- `decision`
- `confidence`
- `status`
- `duration`

## 8. Operational Requirements

| Requirement                         | Implementation                                |
| :---------------------------------- | :-------------------------------------------- |
| Minimum 3 tool calls per ticket     | Enforced in `agent/react_loop.py`             |
| Parallel batch processing           | `main.py` with `asyncio.gather` + semaphore   |
| Graceful retry behavior             | `tools/tool_executor.py`                      |
| Explainable decision trail          | `logs/audit_log.json`                         |
| Automatic low-confidence escalation | `agent/confidence.py` + `agent/react_loop.py` |
