import asyncio
import json
import os
import time
from datetime import datetime
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

load_dotenv()

from agent.classifier import classify_ticket
from agent.react_loop import run_react_loop

async def process_ticket(ticket: dict, ticket_semaphore: asyncio.Semaphore):
    """
    Workflow for a single ticket. Independent state guarantees thread-safety.
    Enforces a strict concurrency limit to respect Groq API Rate Limits.
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
            # Prevent individual ticket failures from crashing the entire batch
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
    # Load all tickets by default to satisfy hackathon validation requirements.
    max_tickets = int(os.getenv("MAX_TICKETS", "0"))
    with open("data/tickets.json", "r") as f:
        loaded = json.load(f)
        tickets = loaded[:max_tickets] if max_tickets > 0 else loaded
    
    print(f"Starting async processing of {len(tickets)} tickets...")
    start_time = time.time()
    
    # Process concurrently with a tunable cap.
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
    
    total_time = time.time() - start_time
    
    # Save Audit Log
    os.makedirs("logs", exist_ok=True)
    with open("logs/audit_log.json", "w") as f:
        json.dump(normalized_results, f, indent=2)

    success_count = len([r for r in normalized_results if r.get("status") == "success"])
    failed_count = len(normalized_results) - success_count
    
    print(f"Finished. Audit log saved to logs/audit_log.json")
    print(f"Summary: success={success_count}, failed={failed_count}, total={len(normalized_results)}, duration={total_time:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
