import asyncio
import random
import logging
import os

logger = logging.getLogger(__name__)

# Deterministic mode keeps chaos runs repeatable in test and CI.
DETERMINISTIC_MODE = os.getenv("DETERMINISTIC_MODE", "false").lower() == "true"
CHAOS_SEED = int(os.getenv("CHAOS_SEED", "42"))

# Seed the RNG when deterministic mode is enabled.
if DETERMINISTIC_MODE:
    random.seed(CHAOS_SEED)
    logger.debug(f"Chaos simulator running in DETERMINISTIC mode with seed={CHAOS_SEED}")

# Tracks call order so debug output is easy to follow.
_tool_call_counter = 0

async def simulate_failure(tool_name, data):
    """
    Simulate real upstream instability.
    Injects latency, timeouts, gateway failures, and malformed payloads so
    we can validate recovery logic under pressure.
    """
    global _tool_call_counter
    _tool_call_counter += 1
    
    # Baseline latency jitter.
    delay = random.uniform(0.1, 1.5) if not DETERMINISTIC_MODE else 0.2
    await asyncio.sleep(delay)
    
    chance = random.random()
    
    # Keep these traces in DEBUG so normal runs stay readable.
    logger.debug(f"[CHAOS] Tool call #{_tool_call_counter}: {tool_name} (chance={chance:.2f})")
    
    # Hard timeout.
    if chance < 0.15:
        logger.debug(f"[CHAOS] TIMEOUT for {tool_name}")
        await asyncio.sleep(1.0)
        raise asyncio.TimeoutError(f"Network Timeout on {tool_name} after 1.0s")
        
    # Gateway failure.
    elif chance < 0.25:
        logger.debug(f"[CHAOS] 502 Bad Gateway for {tool_name}")
        raise ConnectionError(f"502 Bad Gateway: Upstream server for {tool_name} unavailable")
    
    # Corrupted payload.
    elif chance < 0.40:
        logger.debug(f"[CHAOS] MALFORMED DATA for {tool_name}")
        return {"corrupted": "unreadable_binary_data", "status_code": 200}
    
    # Partial payload (missing keys).
    elif chance < 0.50:
        logger.debug(f"[CHAOS] PARTIAL DATA for {tool_name}")
        if isinstance(data, dict) and data:
            partial_data = data.copy()
            # Randomly remove half the keys.
            keys_to_remove = random.sample(
                list(partial_data.keys()),
                max(1, len(partial_data) // 2)
            )
            for k in keys_to_remove:
                del partial_data[k]
            return partial_data

    # Healthy response path.
    logger.debug(f"[CHAOS] Success - no injection for {tool_name}")
    return data

def reset_chaos_state():
    """Reset local chaos state before starting a new batch."""
    global _tool_call_counter
    _tool_call_counter = 0
    if DETERMINISTIC_MODE:
        random.seed(CHAOS_SEED)
