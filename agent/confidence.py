import google.generativeai as genai
import os
import logging

logger = logging.getLogger(__name__)

model = genai.GenerativeModel('gemini-1.5-flash')

async def get_confidence_score(ticket: dict, reasoning_chain: list, final_decision: str) -> float:
    """
    Evaluates the confidence of the resolution based on the history using Gemini.
    Returns a score between 0.0 and 1.0.
    """
    history_summary = "\n".join([f"Step {s.get('step', '?')}: {s.get('tool', 'thought')} -> {s.get('status', 'N/A')}" for s in reasoning_chain])
    
    prompt = f"""
    Evaluate the following support ticket resolution process.
    
    Ticket: {ticket['subject']}
    Reasoning Chain:
    {history_summary}
    
    Final Decision: {final_decision}
    
    Provide a confidence score between 0.0 and 1.0 that this resolution is correct, safe, and followed a logical chain.
    Return ONLY a single numeric value (e.g., 0.85). No other text.
    """
    
    try:
        response = await model.generate_content_async(prompt)
        score_text = response.text.strip()
        return float(score_text)
    except Exception as e:
        logger.error(f"Confidence scoring failed: {e}")
        return 0.5 # Default middle confidence if scoring fails
