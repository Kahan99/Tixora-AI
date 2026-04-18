import asyncio
import logging
import time
import json
import os

logger = logging.getLogger(__name__)

async def execute_tool(tool_func, **kwargs):
    """
    Run a tool call with automatic retries.
    We back off exponentially so we don't hammer an upstream service that's already struggling.
    """
    max_retries = 3
    base_delay = 0.5
    attempts = []
    # Check if verbose logging is enabled
    verbose_mode = os.getenv("AGENT_VERBOSE", "false").lower() == "true"

    for attempt in range(1, max_retries + 1):
        start_time = time.time()
        try:
            # Simulated upstream failures can return malformed or partial responses.
            result = await tool_func(**kwargs)
            
            # Validate payload shape before it reaches decision logic.
            if tool_func.__name__ == "search_knowledge_base":
                if not isinstance(result, (dict, list)):
                    raise ValueError(f"CRITICAL: search_knowledge_base returned invalid type: {type(result)}")
            elif not isinstance(result, dict):
                raise ValueError(f"CRITICAL: Tool returned non-dict type: {type(result)}")
            
            if isinstance(result, dict):
                if "corrupted" in result or result.get("status_code") == 500:
                    raise ValueError("CRITICAL: Upstream API returned corrupted schema")

            # Partial payloads are recoverable; log them and continue.
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
            error_msg = str(e)
            if attempt < max_retries:
                logger.debug(f"Attempt {attempt} failed for {tool_func.__name__}: {error_msg}")
            else:
                # Final failures are expected in chaos runs; keep noise out of stderr by default.
                log_level = logging.WARNING if verbose_mode else logging.DEBUG
                logger.log(log_level, f"Tool {tool_func.__name__} failed after {max_retries} attempts: {error_msg}")
            
            log_entry = {
                "attempt": attempt,
                "status": "failed",
                "error": error_msg,
                "duration": time.time() - start_time
            }
            attempts.append(log_entry)
            
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
            else:
                # Retries are exhausted. Caller decides whether to escalate or continue.
                return None, attempts

def log_to_dlq(ticket_id, reason, history):
    """Park a failed ticket in the dead letter queue for later investigation."""
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
