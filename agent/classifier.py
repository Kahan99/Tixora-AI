import json
import logging
from groq import AsyncGroq
import os
from agent.schemas import TicketClassification

logger = logging.getLogger(__name__)

# Initialize Groq
client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY", ""))

# Groq Mixtral or LLaMa-3 Models are ideal for reasoning
MODEL_NAME = "llama-3.3-70b-versatile"

async def classify_ticket(ticket: dict) -> dict:
    """
    Classifies a ticket into categories, urgency, and resolvability using Groq and Pydantic validation.
    """
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
            
    return {
        "category": "other",
        "urgency": "medium",
        "resolvability": "escalate",
        "error": "Failed after max retries due to rate limits or API errors."
    }
