import json
import os
import sys

# Simple color formatting for the terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_audit_log(ticket_id=None):
    log_path = "logs/audit_log.json"
    
    if not os.path.exists(log_path):
        print(f"{Colors.FAIL}Error: {log_path} not found. Run main.py first!{Colors.ENDC}")
        return

    with open(log_path, "r") as f:
        try:
            logs = json.load(f)
        except json.JSONDecodeError:
            print(f"{Colors.FAIL}Error: Log file is corrupted.{Colors.ENDC}")
            return

    # Filter logs if specific ticket is requested
    if ticket_id:
        logs = [log for log in logs if log.get("ticket_id") == ticket_id]
        if not logs:
            print(f"{Colors.FAIL}Error: Ticket {ticket_id} not found in logs.{Colors.ENDC}")
            return

    print(f"\n{Colors.HEADER}{Colors.BOLD}--- TIXORA-AI: AGENTIC SUPPORT EVALUATION LOGS ---{Colors.ENDC}\n")
    print(f"Total Tickets Processed: {len(logs)}\n")

    for ticket in logs:
        print(f"{Colors.BOLD}{Colors.BLUE}Ticket ID: {ticket.get('ticket_id')}{Colors.ENDC} | Status: {ticket.get('status')}")
        print(f"Confidence Score: {Colors.CYAN}{ticket.get('confidence', 'N/A')}{Colors.ENDC}")
        print(f"Final Decision: {Colors.GREEN}{ticket.get('decision')}{Colors.ENDC}\n")
        
        reasoning = ticket.get("reasoning_chain", [])
        
        if not reasoning:
            print(f"  {Colors.WARNING}No reasoning chain found (did it crash?){Colors.ENDC}")
            print(f"  Error: {ticket.get('error')}\n")
            print("-" * 60)
            continue
            
        print(f"  {Colors.BOLD}ReAct Execution Details:{Colors.ENDC}")
        for step in reasoning:
            step_num = step.get('step', '?')
            action = step.get('action', 'N/A')
            thought = step.get('thought', 'N/A')
            obs = step.get('observation', 'N/A')
            
            # Show retry resilience dynamically
            attempts = step.get('attempts', [])
            retries_str = f" ({len(attempts)} attempts - Recovery Used!)" if len(attempts) > 1 else ""
            
            print(f"  {Colors.BOLD}Step {step_num}:{Colors.ENDC}")
            print(f"    {Colors.CYAN}THOUGHT:{Colors.ENDC} {thought}")
            print(f"    {Colors.WARNING}ACTION:{Colors.ENDC} {action} {retries_str}")
            print(f"    {Colors.GREEN}OBS:{Colors.ENDC} {obs}")

            status = step.get("status", "N/A")
            print(f"    {Colors.BLUE}STATUS:{Colors.ENDC} {status}\n")

        print("-" * 60 + "\n")

if __name__ == "__main__":
    target_ticket = sys.argv[1] if len(sys.argv) > 1 else None
    print_audit_log(target_ticket)
