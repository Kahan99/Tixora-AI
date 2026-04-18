import os
import logging

logger = logging.getLogger(__name__)

# Optional Groq client; deterministic scoring remains available.
try:
    from groq import AsyncGroq, RateLimitError
except ImportError:
    AsyncGroq = None
    RateLimitError = Exception

client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", "")) if AsyncGroq and os.environ.get("GROQ_API_KEY") else None
MODEL_NAME = "llama-3.3-70b-versatile"


def _local_confidence(reasoning_chain: list, final_decision: str) -> float:
    steps = len(reasoning_chain)
    successful_actions = len([s for s in reasoning_chain if s.get("status") in {"success", "completed"}])
    failures = len([s for s in reasoning_chain if s.get("status") in {"failed", "fatal_failure"}])
    escalated = "escalat" in str(final_decision).lower()

    score = 0.35 + min(steps, 6) * 0.07 + successful_actions * 0.08 - failures * 0.12
    if escalated:
        score = min(score + 0.1, 0.9)

    return round(max(0.0, min(score, 0.98)), 2)

async def get_confidence_score(ticket: dict, reasoning_chain: list, final_decision: str) -> float:
    """
    Score how confident we are in the final resolution.
    Low-confidence outcomes are escalated so risky decisions don't ship automatically.
    """
    history_summary = "\n".join([f"Step {s.get('step', '?')}: {s.get('action', 'thought')} -> {s.get('status', 'N/A')}" for s in reasoning_chain])

    if os.getenv("AGENT_MODE", "local").lower() != "llm" or client is None:
        return _local_confidence(reasoning_chain, final_decision)
    
    prompt = f"""
    Evaluate the following support ticket resolution process.
    
    Ticket: {ticket['subject']}
    Reasoning Chain:
    {history_summary}
    
    Final Decision: {final_decision}
    
    Output a strictly valid JSON response containing a single key "score" with a numeric value between 0.0 and 1.0 that this resolution is correct, safe, and followed a logical chain. Example: {{"score": 0.85}}
    """
    
    import asyncio
    
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
            
    return _local_confidence(reasoning_chain, final_decision)
