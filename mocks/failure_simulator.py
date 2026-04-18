import asyncio
import random
import logging

logger = logging.getLogger(__name__)

async def simulate_failure(tool_name, data):
    """
    Chaos Engineering Simulator for Production Reliability Evaluation.
    Injects latency, exceptions, timeouts, and malformed structures.
    """
    # 1. Baseline Network Jitter (simulate real API latency)
    delay = random.uniform(0.1, 1.5)
    await asyncio.sleep(delay)
    
    chance = random.random()
    
    # 2. Hard Timeout (15% chance - network drop)
    if chance < 0.15:
        logger.debug(f"[CHAOS] TIMEOUT for {tool_name}")
        await asyncio.sleep(1.0) # Delay then break
        raise asyncio.TimeoutError(f"Network Timeout on {tool_name} after 1.0s")
        
    # 3. HTTP Server Error (10% chance)
    if chance < 0.25:
        logger.debug(f"[CHAOS] 502 Bad Gateway for {tool_name}")
        raise ConnectionError(f"502 Bad Gateway: Upstream server for {tool_name} unavailable")
    
    # 4. Malformed Data Structure (15% chance - schema mismatch)
    if chance < 0.40:
        logger.debug(f"[CHAOS] MALFORMED DATA for {tool_name}")
        return {"corrupted": "unreadable_binary_data", "status_code": 200}
    
    # 5. Partial Data Loss (10% chance - missing keys)
    if chance < 0.50:
        logger.debug(f"[CHAOS] PARTIAL DATA for {tool_name}")
        if isinstance(data, dict) and data:
            partial_data = data.copy()
            # Randomly delete half the keys
            keys_to_remove = random.sample(list(partial_data.keys()), max(1, len(partial_data) // 2))
            for k in keys_to_remove:
                del partial_data[k]
            return partial_data

    # Return healthy data if chaos was evaded
    return data
