import asyncio
import json
import os
import time
from datetime import datetime
from agent.classifier import classify_ticket
from agent.react_loop import run_react_loop
from agent.confidence import get_confidence_score

async def process_ticket(ticket: dict):
    """
    Workflow for a single ticket.
    """
    ticket_id = ticket['ticket_id']
    start_time = time.time()
    
    # 1. Classify & Triage
    classification = await classify_ticket(ticket)
    
    # 2. ReAct Loop
    decision, history, confidence = await run_react_loop(ticket, classification)
    
    # 3. Final output & Logging
    # Note: Auto-escalation is handled inside run_react_loop prior to the final action
    result = {
        "ticket_id": ticket_id,
        "processed_at": datetime.utcnow().isoformat() + "Z",
        "classification": classification,
        "reasoning_chain": history,
        "decision": decision,
        "confidence": confidence,
        "duration": time.time() - start_time
    }
    
    return result

async def main():
    # Load tickets
    with open("data/tickets.json", "r") as f:
        tickets = json.load(f)
    
    print(f"Starting processing of {len(tickets)} tickets concurrently...")
    
    # Process all tickets in parallel
    tasks = [process_ticket(t) for t in tickets]
    results = await asyncio.gather(*tasks)
    
    # Save Audit Log
    os.makedirs("logs", exist_ok=True)
    with open("logs/audit_log.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Finished. Audit log saved to logs/audit_log.json")

if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("WARNING: GOOGLE_API_KEY not set. Agent will fail.")
    asyncio.run(main())
