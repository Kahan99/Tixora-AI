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
            
            # --- ADVANCED VALIDATION STAGE ---
            if tool_func.__name__ == "search_knowledge_base":
                if not isinstance(result, (dict, list)):
                    raise ValueError(f"CRITICAL: search_knowledge_base returned invalid type: {type(result)}")
            elif not isinstance(result, dict):
                raise ValueError(f"CRITICAL: Tool returned non-dict type: {type(result)}")
            
            if isinstance(result, dict):
                if "corrupted" in result or result.get("status_code") == 500:
                    raise ValueError("CRITICAL: Upstream API returned corrupted schema")

            # Partial data is recoverable for this agent; keep it as a soft signal.
            if isinstance(result, dict):
                missing_keys = []
                if tool_func.__name__ == "get_order" and "status" not in result and "error" not in result:
                    missing_keys.append("status")
                if tool_func.__name__ == "get_customer" and "tier" not in result and "error" not in result:
                    missing_keys.append("tier")
                if missing_keys:
                    logger.debug("Partial data from %s missing keys: %s", tool_func.__name__, ", ".join(missing_keys))

            log_entry = {
                "attempt": attempt,
                "status": "success",
                "duration": time.time() - start_time
            }
            attempts.append(log_entry)
            return result, attempts

        except (asyncio.TimeoutError, ValueError, Exception) as e:
            if attempt < max_retries:
                logger.debug(f"Attempt {attempt} failed for {tool_func.__name__}: {str(e)}")
            else:
                logger.warning(f"Tool {tool_func.__name__} failed after {max_retries} attempts: {str(e)}")
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
