import asyncio
import random
import logging
import os

logger = logging.getLogger(__name__)

# Deterministic mode for reproducible testing
DETERMINISTIC_MODE = os.getenv("DETERMINISTIC_MODE", "false").lower() == "true"
CHAOS_SEED = int(os.getenv("CHAOS_SEED", "42"))

# Initialize seeded random generator for chaos simulation
if DETERMINISTIC_MODE:
    random.seed(CHAOS_SEED)
    logger.debug(f"Chaos simulator running in DETERMINISTIC mode with seed={CHAOS_SEED}")

# Tool-specific failure patterns (deterministic or random)
_tool_call_counter = 0

async def simulate_failure(tool_name, data):
    """
    Chaos Engineering Simulator for Production Reliability Evaluation.
    Injects latency, exceptions, timeouts, and malformed structures.
    
    In DETERMINISTIC mode, uses seeded randomness for reproducible results.
    In normal mode, uses full randomness for realistic chaos.
    """
    global _tool_call_counter
    _tool_call_counter += 1
    
    # 1. Baseline Network Jitter (simulate real API latency)
    delay = random.uniform(0.1, 1.5) if not DETERMINISTIC_MODE else 0.2
    await asyncio.sleep(delay)
    
    chance = random.random()
    
    # Log chaos injection at DEBUG level (won't clutter normal output)
    logger.debug(f"[CHAOS] Tool call #{_tool_call_counter}: {tool_name} (chance={chance:.2f})")
    
    # 2. Hard Timeout (15% chance - network drop)
    if chance < 0.15:
        logger.debug(f"[CHAOS] TIMEOUT for {tool_name}")
        await asyncio.sleep(1.0)  # Delay then break
        raise asyncio.TimeoutError(f"Network Timeout on {tool_name} after 1.0s")
        
    # 3. HTTP Server Error (10% chance)
    elif chance < 0.25:
        logger.debug(f"[CHAOS] 502 Bad Gateway for {tool_name}")
        raise ConnectionError(f"502 Bad Gateway: Upstream server for {tool_name} unavailable")
    
    # 4. Malformed Data Structure (15% chance - schema mismatch)
    elif chance < 0.40:
        logger.debug(f"[CHAOS] MALFORMED DATA for {tool_name}")
        return {"corrupted": "unreadable_binary_data", "status_code": 200}
    
    # 5. Partial Data Loss (10% chance - missing keys)
    elif chance < 0.50:
        logger.debug(f"[CHAOS] PARTIAL DATA for {tool_name}")
        if isinstance(data, dict) and data:
            partial_data = data.copy()
            # Randomly delete half the keys
            keys_to_remove = random.sample(
                list(partial_data.keys()),
                max(1, len(partial_data) // 2)
            )
            for k in keys_to_remove:
                del partial_data[k]
            return partial_data

    # Return healthy data if chaos was evaded
    logger.debug(f"[CHAOS] Success - no injection for {tool_name}")
    return data

def reset_chaos_state():
    """Reset chaos simulator state (useful for testing multiple batches)."""
    global _tool_call_counter
    _tool_call_counter = 0
    if DETERMINISTIC_MODE:
        random.seed(CHAOS_SEED)
