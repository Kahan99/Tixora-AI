from groq import AsyncGroq
import os
import logging

logger = logging.getLogger(__name__)

client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", ""))
MODEL_NAME = "llama-3.3-70b-versatile"

async def get_confidence_score(ticket: dict, reasoning_chain: list, final_decision: str) -> float:
    """
    Evaluates the confidence of the resolution based on the history using Groq.
    Returns a score between 0.0 and 1.0.
    """
    history_summary = "\n".join([f"Step {s.get('step', '?')}: {s.get('action', 'thought')} -> {s.get('status', 'N/A')}" for s in reasoning_chain])
    
    prompt = f"""
    Evaluate the following support ticket resolution process.
    
    Ticket: {ticket['subject']}
    Reasoning Chain:
    {history_summary}
    
    Final Decision: {final_decision}
    
    Output a strictly valid JSON response containing a single key "score" with a numeric value between 0.0 and 1.0 that this resolution is correct, safe, and followed a logical chain. Example: {{"score": 0.85}}
    """
    
    import asyncio
    from groq import RateLimitError
    
    max_retries = 5
    base_delay = 5.0
    
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            import json
            text = response.choices[0].message.content.strip()
            data = json.loads(text)
            return float(data.get("score", 0.5))
            
        except RateLimitError:
            logger.warning(f"Groq Rate Limit (429) in Confidence Scorer. Retrying in {base_delay * (2 ** attempt)}s...")
            await asyncio.sleep(base_delay * (2 ** attempt))
            
        except Exception as e:
            logger.error(f"Confidence scoring failed using Groq: {e}")
            break
            
    return 0.5 # Default middle confidence if scoring fails completely
