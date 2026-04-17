# Agentic AI Support Ticket Resolver - Hackathon 2026

A high-performance, resilient support ticket resolver built for the Ksolves Agentic AI Hackathon.

## Architecture
- **Classifier**: Triage tickets by urgency, category, and resolvability.
- **Custom ReAct Loop**: Reasoning-Action-Observation loop using Claude-3 Sonnet.
- **Concurrent Processing**: batch processes 20 tickets in parallel using `asyncio.gather`.
- **Mock Failure Simulation**: 60% combined failure rate in tools to test resilience.
- **Tool Executor**: Robust retries, exponential backoff, and Dead Letter Queue.

## Folder Structure
```text
├── main.py                  # Entry point
├── agent/
│   ├── react_loop.py        # Core reasoning
│   ├── classifier.py        # Triage logic
│   └── confidence.py        # Confidence scoring
├── tools/
│   ├── read_tools.py        # get_order, get_customer, etc.
│   ├── write_tools.py       # issue_refund, send_reply, etc.
│   └── tool_executor.py     # Retry + error handling
├── mocks/
│   ├── mock_data.py         # Mock DBs
│   └── failure_simulator.py # Simulated chaos
├── data/
│   └── tickets.json         # 20 mock tickets
├── logs/
│   └── audit_log.json       # Execution evidence
└── Dockerfile
```

## Setup & Run
1. Clone this repo.
2. Create a `.env` file with `ANTHROPIC_API_KEY`.
3. Install dependencies: `pip install -r requirements.txt`.
4. Run the resolver: `python main.py`.

## Resilience
Check [failure_modes.md](./failure_modes.md) for details on how we handle timeouts and corrupted data.
