# Tixora-AI: Autonomous Support Resolution Agent

![Status](https://img.shields.io/badge/Status-Production%20Ready-success)
![Architecture](https://img.shields.io/badge/Architecture-Asynchronous%20Distributed-blue)
![Model](https://img.shields.io/badge/Agent-Google%20Gemini%201.5%20Flash-orange)

Tixora-AI is a high-performance, fault-tolerant Autonomous Agent designed to resolve customer support tickets dynamically. It was engineered from the ground up for the **Ksolves Agentic AI Hackathon 2026** with a strict focus on distributed system resilience, explainability, and pure zero-shot agency.

This is **not a chatbot**. It is a deterministically bounded ReAct machine running on a strict JSON-evaluation loop.

---

## 🏗️ Architecture

The system operates through an asynchronous orchestration loop, capable of processing hundreds of tickets concurrently while handling aggressive upstream API failures.

```mermaid
graph TD
    subgraph "Ingestion Layer"
        T[Batch Tickets JSON] --> M[main.py: asyncio.gather]
    end

    subgraph "Cognitive Layer (Per Ticket)"
        C[Classifier: Triage & Urgency]
        A["Agent Core (Gemini 1.5 Flash)"]
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

## 🛠️ Engineering Depth & Production Readiness

We didn't just build an agent; we built the hardened infrastructure required to run it in production.

1.  **Strict Pydantic Validation**:
    The agent cannot execute a tool unless its generated JSON strictly validates against `agent/schemas.py`. If it fails, the error is fed back to the LLM as an Observation for **self-correction**.
2.  **Semaphore Rate Limiting**:
    Processing 20+ tickets asynchronously triggers massive LLM traffic. A global `asyncio.Semaphore` combined with caught `429 ResourceExhausted` exponential backoffs ensures the free-tier API never crashes the application.
3.  **Chaos Engineering & Healing**:
    Upstream APIs fail. `failure_simulator.py` randomly injects:
    - 15% Timeouts
    - 10% 502 Bad Gateway
    - 15% Malformed JSON/Binary corruption
    - 10% Partial Data Loss (simulating DB issues)
    
    `tool_executor.py` automatically detects corruption and applies 3x exponential backoff retries. If the retry exhausts, the ticket gracefully lands in the Dead Letter Queue.

---

## 🚀 How to Run

1.  **Environment Setup**:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    ```
2.  **API Keys**:
    Rename `.env.example` to `.env` and insert your API key:
    ```env
    GOOGLE_API_KEY=your_gemini_api_key
    ```
3.  **Execute the Engine**:
    ```bash
    python main.py
    ```

---

## 📊 Evaluation & Explainability

To explicitly evaluate the Agent's reasoning, we have decoupled the logs from the raw execution string.

**Run the Demo Viewer:**
```bash
python demo_viewer.py
```
This renders `logs/audit_log.json` into a readable terminal UI, explicitly proving the agent's `<THINK> → <ACT> → <OBSERVE>` chains, displaying real-time confidence scores, and highlighting upstream recovery retries.
