import asyncio
import json
import os
import time
import argparse
from datetime import datetime
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

load_dotenv()

from agent.classifier import classify_ticket
from agent.react_loop import run_react_loop
from tools.decision_utils import is_escalated_decision
from tools.metrics_collector import MetricsCollector

async def process_ticket(ticket: dict, ticket_semaphore: asyncio.Semaphore):
    """
    Process one ticket end-to-end.
    Each task runs with isolated state, and the semaphore keeps concurrency within safe limits.
    """
    async with ticket_semaphore:
        ticket_id = ticket.get('ticket_id', 'UNKNOWN')
        start_time = time.time()
        
        try:
            # 1. Classify & Triage
            classification = await classify_ticket(ticket)
            
            # 2. ReAct Loop
            decision, history, confidence = await run_react_loop(ticket, classification)
            
            # 3. Final output & Logging
            result = {
                "ticket_id": ticket_id,
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "classification": classification,
                "reasoning_chain": history,
                "decision": decision,
                "confidence": confidence,
                "duration": time.time() - start_time,
                "status": "success"
            }
            return result
            
        except Exception as e:
            # One bad ticket shouldn't take down the whole run. Capture it and move on.
            return {
                "ticket_id": ticket_id,
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "classification": {"category": "other", "urgency": "medium", "resolvability": "escalate"},
                "reasoning_chain": [],
                "decision": "failed_before_resolution",
                "confidence": 0.0,
                "error": str(e),
                "status": "failed",
                "duration": time.time() - start_time
            }

async def main():
    parser = argparse.ArgumentParser(description="Tixora-AI ticket processor")
    parser.add_argument("ticket_file", nargs="?", default="data/tickets.json")
    parser.add_argument("--deterministic", "-d", action="store_true")
    parser.add_argument("--seed", "-s", type=int, default=42)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    ticket_file = args.ticket_file
    deterministic = args.deterministic
    chaos_seed = args.seed
    verbose = args.verbose
    
    # Let operators toggle deterministic chaos and verbose logging from the CLI.
    if deterministic:
        os.environ["DETERMINISTIC_MODE"] = "true"
        os.environ["CHAOS_SEED"] = str(chaos_seed)
    if verbose:
        os.environ["AGENT_VERBOSE"] = "true"
    
    if not os.path.exists(ticket_file):
        print(f"Error: Ticket file {ticket_file} not found.")
        return

    # Load the ticket batch. Respect MAX_TICKETS when we want a quick subset run.
    max_tickets = int(os.getenv("MAX_TICKETS", "0"))
    with open(ticket_file, "r") as f:
        loaded = json.load(f)
        tickets = loaded[:max_tickets] if max_tickets > 0 else loaded
    
    print(f"--- Tixora-AI Orchestrator ---")
    if deterministic:
        print(f"(Running in DETERMINISTIC mode with seed={chaos_seed})")
    print(f"Processing {len(tickets)} tickets...")
    
    start_time = time.time()
    
    # Process tickets in parallel using asyncio with a configurable concurrency limit.
    max_concurrency = int(os.getenv("MAX_CONCURRENCY", "5"))
    ticket_semaphore = asyncio.Semaphore(max_concurrency)
    tasks = [process_ticket(t, ticket_semaphore) for t in tickets]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    normalized_results = []
    for item in results:
        if isinstance(item, Exception):
            normalized_results.append({
                "ticket_id": "UNKNOWN",
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "classification": {"category": "other", "urgency": "medium", "resolvability": "escalate"},
                "reasoning_chain": [],
                "decision": "gather_exception",
                "confidence": 0.0,
                "error": str(item),
                "status": "failed",
                "duration": 0.0
            })
        else:
            normalized_results.append(item)
    
    # Compute metrics
    metrics_collector = MetricsCollector()
    for result in normalized_results:
        classification = result.get("classification", {})
        category = classification.get("category", "other")
        metrics_collector.record_ticket(
            ticket_id=result.get("ticket_id", "unknown"),
            category=category,
            decision=result.get("decision", "unknown"),
            confidence=result.get("confidence", 0.0),
            reasoning_chain=result.get("reasoning_chain", []),
            duration=result.get("duration", 0.0)
        )
    
    # Write audit log
    audit_log_path = "logs/audit_log.json"
    os.makedirs(os.path.dirname(audit_log_path), exist_ok=True)
    with open(audit_log_path, "w") as f:
        json.dump(normalized_results, f, indent=2)
    
    # Export metrics
    metrics_collector.export_metrics()
    
    # Print summary
    total_duration = time.time() - start_time
    summary = metrics_collector.get_summary()
    
    success_count = len([r for r in normalized_results if not is_escalated_decision(r.get("decision", ""))])
    failed_count = len(normalized_results) - success_count
    
    print(f"Tixora-AI: Processing Finished. Audit log saved to {audit_log_path}")
    print(f"Final Report: success={success_count}, failed={failed_count}, total={len(normalized_results)}, duration={total_duration:.2f}s")
    
    if verbose:
        print("\nDetailed Metrics:")
        print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    asyncio.run(main())

