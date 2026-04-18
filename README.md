# Tixora-AI

![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)
![Architecture](https://img.shields.io/badge/Architecture-Async%20ReAct-blue)
![Mode](https://img.shields.io/badge/Mode-Local%20Policy%20First-orange)

Tixora-AI is an Autonomous Support Resolution Agent designed for ShopWave as part of the Ksolves Agentic AI Hackathon 2026. It reads customer support tickets and automates the resolution process using a robust, deterministic Think → Act → Observe ReAct loop. By classifying tickets by category, urgency, and resolvability, it autonomously utilizes a suite of tools to fetch customer data, query the knowledge base, check refund eligibilities, and issue refunds or escalations. The agent uniquely operates with a dual-engine architecture: a primary robust local fallback policy engine requiring zero API keys, and an optionally configurable, high-performance LLM (Groq) reasoning engine.

## Architecture

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

## Reliability Features

1. **Deterministic ReAct Loop**: Implements a robust `Think → Act → Observe` loop ensuring continuous structured progression per ticket.
2. **Concurrent Execution**: Leverages `asyncio.gather()` alongside a configurable Semaphore to intelligently process all tickets in parallel without resource starvation.
3. **Resilient Tool Executor**: Every tool execution request goes through a dedicated executor wrapper that natively supports 3 automatic retries paired with exponential backoff (0.5s → 1s → 2s).
4. **Chaos Engineering Resilience**: Ships with an embedded `failure_simulator` explicitly verifying system robustness against 15% timeouts, 10% 502 Bad Gateway errors, 15% malformed shapes, and 10% partial data streams.
5. **Dead Letter Queue (DLQ)**: Implements asynchronous DLQ capture pushing critically failed tool interactions to isolated logs preventing entire pipeline crashes.
6. **Guardian Overrides**: Post-loop confidence scoring evaluates the ReAct session. Any resolution pathway generating a confidence string below `0.7` is overridden with an autonomous escalation hook.

## Quick Start
1. Clone the repository
   ```bash
   git clone https://github.com/Kahan99/Tixora-AI.git
   ```
2. Navigate into the project directory
   ```bash
   cd Tixora-AI
   ```
3. Create a virtual environment
   ```bash
   python -m venv venv
   ```
4. Activate the virtual environment
   ```bash
   # On Windows
   .\venv\Scripts\activate
   
   # On Mac/Linux
   source venv/bin/activate
   ```
5. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
6. Duplicate environment variables template (Optional — not needed for fully local mode)
   ```bash
   cp .env.example .env
   ```
7. Run the agent natively!
   ```bash
   python main.py
   ```

## Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | Optional: Your Groq API key to unlock the LLM reasoning features | `""` |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `MAX_CONCURRENCY` | Maximum number of concurrent async routines processing tickets | `5` |
| `MAX_TICKETS`| Limit the number of tickets to ingest (`0` ingests all available)| `0` |
| `AGENT_MODE` | Specifies backend reasoning engine ("`local`" or "`llm`") | `local` |

## Output & Demo

Optional startup arguments let you specify custom data, while additional utilities preview and audit system behaviors: 
```bash
# Process Custom Manual Tickets
python main.py data/manual_test_tickets.json

# View Live Auditing Trace in Terminal
python demo_viewer.py

# Launch the Streamlit Monitoring UI Dashboard
streamlit run ui/app.py 

# Execute the local mock Compliance Checks
python tools/compliance_check.py 
```

## Docker Run

You can seamlessly execute the entire environment locally using Docker:
```bash
docker compose -f docker-compose.yml up -d --build
```

## File Structure

```text
Tixora-AI/
├── main.py                     # Entry point, asyncio orchestrator
├── .env.example                # Environment variable template
├── Dockerfile                  # Containerization instructions
├── docker-compose.yml          # Docker composition framework
├── demo_viewer.py              # Pretty-prints audit log to terminal
├── agent/
│   ├── classifier.py           # Local heuristics + optional Groq classifier
│   ├── confidence.py           # Confidence scoring (local + optional Groq)
│   ├── react_loop.py           # Core Think→Act→Observe execution loop
│   └── schemas.py              # Pydantic state/model definition rules
├── data/
│   ├── manual_test_tickets.json # Extra test tickets inputs
│   └── tickets.json            # Base 20 mock support tickets inputs
├── logs/
│   ├── audit_log.json          # Post-execution tracing output
│   └── dead_letter_queue.json  # Post-execution critically failed processes 
├── mocks/
│   ├── failure_simulator.py    # Chaos engineering injector parameters
│   └── mock_data.py            # In-memory mock DB (customers, orders, etc.)
├── tools/
│   ├── compliance_check.py     # Validates audit log against hackathon rules
│   ├── read_tools.py           # get_customer, get_order, get_product, etc.
│   ├── tool_executor.py        # Retry + backoff + schema validation + DLQ
│   └── write_tools.py          # check_refund_eligibility, issue_refund, etc.
└── ui/
    └── app.py                  # Streamlit monitoring dashboard GUI
```

## Hackathon Compliance Highlights

Designed strategically to comfortably accommodate and explicitly satisfy all strict Ksolves Agentic AI Hackathon 2026 rubric requirements:

*   **Strict Multi-Tool Invocations**: At least `3` specific tool calls per ticket are inherently guaranteed recursively by the underlying loop inside `react_loop.py`.
*   **Performance Maximization**: All 20 base dataset tickets are successfully ingested and executed in full parallel operation powered natively efficiently via native `asyncio.gather`.
*   **Chaos Resilient Pipeline**: Provides incredibly graceful failure handling integrating a hard 3-retry attempt maximum enhanced dynamically via exponential backoff paired with a Dead Letter Queue strategy.
*   **Holistic Execution Auditing**: Every system decision is safely logged sequentially including internal `thought`, exact `action` payload, dynamic `params`, target `observation`, executed `attempts`, and specific terminal `status`.
*   **Human-In-The-Loop Overrides**: An autonomous safety confidence guardrail executes hard auto-escalations automatically intercepting instances where resulting confidence scores land `< 0.7`.
*   **Production Secure Best-Practices**: Retains absolutely zero hardcoded API keys by referencing explicitly off standardized `.env` architecture.
*   **True Zero-Shot Redundancy**: Configures out-of-the-box natively operating in a fully local environment processing completely accurately using zero API Keys inherently.
