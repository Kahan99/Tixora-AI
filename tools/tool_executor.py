import asyncio
import logging
import time
import json
import os

logger = logging.getLogger(__name__)

async def execute_tool(tool_func, **kwargs):
    """
    Executes a tool with 3 retries and exponential backoff.
    """
    max_retries = 3
    base_delay = 0.5
    attempts = []

    for attempt in range(1, max_retries + 1):
        start_time = time.time()
        try:
            # Check for partial/malformed data simulations (mocked in the simulator)
            result = await tool_func(**kwargs)
            
            # Basic validation: if result is malformed or missing key keys (simulated failure)
            if isinstance(result, dict) and "corrupted" in result:
                raise ValueError("Malformed response received")

            log_entry = {
                "attempt": attempt,
                "status": "success",
                "duration": time.time() - start_time
            }
            attempts.append(log_entry)
            return result, attempts

        except (asyncio.TimeoutError, ValueError, Exception) as e:
            logger.warning(f"Attempt {attempt} failed for {tool_func.__name__}: {str(e)}")
            log_entry = {
                "attempt": attempt,
                "status": "failed",
                "error": str(e),
                "duration": time.time() - start_time
            }
            attempts.append(log_entry)
            
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
            else:
                # All retries failed
                return None, attempts

def log_to_dlq(ticket_id, reason, history):
    """Logs failed ticket to Dead Letter Queue."""
    dlq_path = "logs/dead_letter_queue.json"
    entry = {
        "ticket_id": ticket_id,
        "failed_at": time.asctime(),
        "reason": reason,
        "tool_history": history
    }
    
    # Simple append to JSON list
    data = []
    if os.path.exists(dlq_path):
        with open(dlq_path, "r") as f:
            try:
                data = json.load(f)
            except:
                data = []
    
    data.append(entry)
    with open(dlq_path, "w") as f:
        json.dump(data, f, indent=2)
