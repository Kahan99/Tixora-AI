import asyncio
import random
import logging

logger = logging.getLogger(__name__)

async def simulate_failure(tool_name, data):
    """
    Randomly applies failure modes to tool responses.
    - 30% Timeout
    - 20% Malformed (missing keys)
    - 10% Partial data (random fields removed)
    """
    chance = random.random()
    
    if chance < 0.30:
        logger.warning(f"Simulating TIMEOUT for {tool_name}")
        await asyncio.sleep(10)
        raise asyncio.TimeoutError(f"Tool {tool_name} timed out")
    
    if chance < 0.50: # 0.30 to 0.50 is 20%
        logger.warning(f"Simulating MALFORMED DATA for {tool_name}")
        return {"corrupted": "data", "status": "unknown"} # Malformed response
    
    if chance < 0.60: # 0.50 to 0.60 is 10%
        logger.warning(f"Simulating PARTIAL DATA for {tool_name}")
        if isinstance(data, dict):
            keys = list(data.keys())
            if keys:
                partial_data = data.copy()
                # Remove one random key to make it partial
                key_to_remove = random.choice(keys)
                del partial_data[key_to_remove]
                return partial_data
        return data

    return data
