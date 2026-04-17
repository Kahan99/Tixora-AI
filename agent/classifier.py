import json
import os
import logging
from agent.schemas import TicketClassification

logger = logging.getLogger(__name__)

# Optional Groq client; local fallback stays active when unavailable.
try:
    from groq import AsyncGroq, RateLimitError
except ImportError:
    AsyncGroq = None
    RateLimitError = Exception

client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", "")) if AsyncGroq and os.environ.get("GROQ_API_KEY") else None
MODEL_NAME = "llama-3.3-70b-versatile"


def _local_classify_ticket(ticket: dict) -> dict:
    text = f"{ticket.get('subject', '')} {ticket.get('body', '')}".lower()

    if "refund" in text or "damaged" in text or "return" in text:
        category = "refund"
    elif "where is my order" in text or "status" in text or "tracking" in text:
        category = "order_status"
    elif "warranty" in text or "product" in text or "spec" in text:
        category = "product_info"
    elif "disappointed" in text or "poor service" in text or "complaint" in text:
        category = "complaint"
    else:
        category = "other"

    tier = str(ticket.get("tier", "bronze")).lower()
    high_signal = any(k in text for k in ["urgent", "asap", "immediately", "angry", "escalate"])
    if tier == "gold" or high_signal:
        urgency = "high"
    elif tier == "silver":
        urgency = "medium"
    else:
        urgency = "low"

    resolvability = "escalate" if category in {"complaint", "other"} else "auto"
    return TicketClassification(category=category, urgency=urgency, resolvability=resolvability).model_dump()

async def classify_ticket(ticket: dict) -> dict:
    """
    Classifies a ticket into categories, urgency, and resolvability using Groq and Pydantic validation.
    """
    # Fast deterministic mode (default) avoids external dependency failures.
    if os.getenv("AGENT_MODE", "local").lower() != "llm" or client is None:
        return _local_classify_ticket(ticket)

    prompt = f"""
    Analyze the following support ticket and provide a classification in strictly valid JSON format.
    
    Ticket Details:
    Subject: {ticket['subject']}
    Body: {ticket['body']}
    Tier: {ticket['tier']}
    
    The response MUST be a JSON object with exactly the following schema:
    {{
      "category": "refund" | "order_status" | "product_info" | "complaint" | "other",
      "urgency": "high" | "medium" | "low",
      "resolvability": "auto" | "escalate"
    }}
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
            text = response.choices[0].message.content.strip()
            data = json.loads(text)
            
            # Validate with Pydantic
            validated = TicketClassification(**data)
            return validated.model_dump()
            
        except RateLimitError:
            logger.warning(f"Groq Rate Limit (429) in Classifier. Retrying in {base_delay * (2 ** attempt)}s...")
            await asyncio.sleep(base_delay * (2 ** attempt))
            
        except Exception as e:
            logger.error(f"Classification failed using Groq: {e}")
            break

    fallback = _local_classify_ticket(ticket)
    fallback["error"] = "Groq classification failed; local heuristic fallback used."
    return fallback
