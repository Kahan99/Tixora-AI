import asyncio
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from agent.classifier import classify_ticket
from agent.react_loop import run_react_loop
from agent.confidence import get_confidence_score

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
                "error": str(e),
                "status": "failed",
                "duration": time.time() - start_time
            }

async def main():
    # Load tickets (Limiting to 5 for Hackathon Demo due to Groq 30 RPM Free Tier limits)
    with open("data/tickets.json", "r") as f:
        tickets = json.load(f)[:5]
    
    print(f"Starting async processing of {len(tickets)} tickets...")
    start_time = time.time()
    
    # Process tickets with strict concurrency to survive free-tier limit of 30 RPM
    ticket_semaphore = asyncio.Semaphore(2)
    tasks = [process_ticket(t, ticket_semaphore) for t in tickets]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    total_time = time.time() - start_time
    
    # Save Audit Log
    os.makedirs("logs", exist_ok=True)
    with open("logs/audit_log.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Finished. Audit log saved to logs/audit_log.json")

if __name__ == "__main__":
    if not os.getenv("GROQ_API_KEY"):
        print("WARNING: GROQ_API_KEY not set. Agent will fail.")
    asyncio.run(main())
