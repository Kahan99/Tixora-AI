# Tixora-AI: Autonomous Support Resolution Agent

![Status](https://img.shields.io/badge/Status-Hackathon%20Ready-success)
![Architecture](https://img.shields.io/badge/Architecture-Async%20ReAct-blue)
![Mode](https://img.shields.io/badge/Agent-Local%20Policy%20First-orange)

Tixora-AI is an autonomous support resolution agent for the Ksolves Agentic AI Hackathon 2026.

This is **not a chatbot**. It executes a bounded Think -> Act -> Observe loop with real tool actions, retry logic, escalation guardrails, and structured auditing.

---

## Architecture

The runtime pipeline is:

1. Ingest tickets from `data/tickets.json`
2. Classify each ticket (local deterministic classifier by default)
3. Run autonomous ReAct loop per ticket with tools:
   - Read tools: customer/order/product/knowledge base
   - Write tools: refund/reply/escalate
4. Enforce retry + backoff + malformed output checks in `tools/tool_executor.py`
5. Compute confidence score and auto-escalate when confidence is low
6. Persist full per-ticket trace to `logs/audit_log.json`

Tickets are processed concurrently using `asyncio.gather` with a configurable semaphore.

```mermaid
graph TD
    subgraph "Ingestion Layer"
        T[Batch Tickets JSON] --> M[main.py: asyncio.gather]
    end

    subgraph "Cognitive Layer (Per Ticket)"
        C[Classifier: Triage & Urgency]
        A["Agent Core (Local Policy Engine)"]
        S[Pydantic Schema Enforcer]

        M --> C
        C --> A
        A <-->|JSON Proposals| S
    end

    subgraph "Execution Layer"
        E["Tool Executor (Retry + Backoff)"]
        F["Chaos Simulator (Latency, 502, Timeout)"]

        S -->|Valid Actions| E
        E <--> F
        F <-->|Mock DBs| DB[(Orders / Customers / KB)]
    end

    subgraph "Governance Layer"
        G[Confidence Scorer]
        H[Escalation Guardian]
        L[Structured Audit Logger]

        A --> G
        G -->|>0.7| L
        G -->|<0.7 Override| H
        H --> L
    end
```

---

## Reliability Features

We didn't just build an agent; we built the hardened infrastructure required to run it in production.

1. Minimum tool depth: at least 3 tool calls per ticket before completion.
2. Async concurrency: tickets are processed in parallel with bounded concurrency.
3. Failure simulation: timeout, 502, malformed payload, and partial data are injected by `mocks/failure_simulator.py`.
4. Recovery strategy: tools are executed with retry + exponential backoff and validation.
5. Confidence guardrail: low-confidence outcomes trigger structured escalation.
6. Explainability: every step logs thought, action, params, observation, attempts, and status.

---

## Quick Start

1. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Run the system (single command):
   ```bash
   python main.py
   ```
   Default mode is fully local and does not require API keys.

Optional environment variables:

- `MAX_CONCURRENCY` (default `5`)
- `MAX_TICKETS` (default `0`, which means all tickets)
- `AGENT_MODE=llm` (optional, only when `groq` package and `GROQ_API_KEY` are available)

---

## Output and Demo

Run the audit viewer:

```bash
python demo_viewer.py
```

`logs/audit_log.json` contains full per-ticket execution traces, including:

- classification
- reasoning_chain (thought, action, observation, attempts)
- final decision
- confidence
- processing status and duration
