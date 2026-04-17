import json
import logging
import google.generativeai as genai
import os
from agent.schemas import TicketClassification

logger = logging.getLogger(__name__)

# Initialize Gemini
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))

# Use Gemini 1.5 Flash for triage (fast, cheap)
model = genai.GenerativeModel('gemini-1.5-flash')

async def classify_ticket(ticket: dict) -> dict:
    """
    Classifies a ticket into categories, urgency, and resolvability using Gemini and Pydantic validation.
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
    
    Return ONLY JSON. No markdown backticks, no explanations.
    """
    
    try:
        response = await model.generate_content_async(prompt)
        text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        
        # Validate with Pydantic
        validated = TicketClassification(**data)
        return validated.model_dump()
        
    except Exception as e:
        logger.error(f"Classification failed: {e}. Output was: {response.text if 'response' in locals() else 'None'}")
        return {
            "category": "other",
            "urgency": "medium",
            "resolvability": "escalate",
            "error": str(e)
        }
