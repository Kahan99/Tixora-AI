# Failure Modes & Resilience Strategies

This document outlines how the Agentic Support Resolver handles realistic engineering failures.

## 1. Tool Timeout

- **Trigger**: The `failure_simulator.py` injects timeout failures via delayed `asyncio.TimeoutError`.
- **Handling**:
  - The `tool_executor.py` catches `asyncio.TimeoutError`.
  - It performs a **3-retry attempt with exponential backoff** (0.5s -> 1s -> 2s).
  - If all retries fail, the ticket is moved to the **Dead Letter Queue (logs/dead_letter_queue.json)** and escalated with a reason.

## 2. Malformed Tool Response

- **Trigger**: The `failure_simulator.py` may return a dictionary with a `corrupted` payload or incomplete schema.
- **Handling**:
  - The `tool_executor.py` validates the response structure.
  - If the `corrupted` key is detected, it raises a `ValueError`.
  - This triggers the same retry-with-backoff logic as a timeout.
  - Prevents the ReAct loop from crashing due to unexpected data structures.

## 3. Confidence Below Threshold

- **Trigger**: After the ReAct loop finishes, `agent/confidence.py` computes a confidence score from the execution trace (or optional LLM scoring mode).
- **Handling**:
  - If the confidence score is **less than 0.7**, the system overrides the decision.
  - The `final_action` is automatically set to `Auto-escalated (Low confidence)`.
  - This ensures the agent "knows what it doesn't know" and prevents hallucinated or risky resolutions from being sent to customers.

## 4. Partial Data

- **Trigger**: 10% chance of random keys missing from the returned dictionary.
- **Handling**:
  - The ReAct loop is designed to be robust. If a key is missing, the agent records the partial data, reasons about the missing info, and may choose to call the tool again or search elsewhere.
