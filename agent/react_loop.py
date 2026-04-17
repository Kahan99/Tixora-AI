import json
import asyncio
import logging
import google.generativeai as genai
from pydantic import ValidationError
from google.api_core.exceptions import ResourceExhausted

from tools.read_tools import get_customer, get_order, get_product, search_knowledge_base
from tools.write_tools import check_refund_eligibility, issue_refund, send_reply, escalate
from tools.tool_executor import execute_tool, log_to_dlq
from agent.schemas import ReActAction
from agent.confidence import get_confidence_score

logger = logging.getLogger(__name__)

model = genai.GenerativeModel('gemini-1.5-flash')

# Global semaphore to prevent instantly blowing past the 15 RPM limit
gemini_semaphore = asyncio.Semaphore(15)

# Tool registry
TOOL_MAP = {
    "get_customer": get_customer,
    "get_order": get_order,
    "get_product": get_product,
    "search_knowledge_base": search_knowledge_base,
    "check_refund_eligibility": check_refund_eligibility,
    "issue_refund": issue_refund,
    "send_reply": send_reply,
    "escalate": escalate
}

async def _call_llm_with_retry(prompt: str) -> str:
    """Calls Gemini with rate limit (429) backoff."""
    max_retries = 5
    base_delay = 5.0 # Wait 5 seconds on rate limit

    for attempt in range(max_retries):
        async with gemini_semaphore:
            try:
                response = await model.generate_content_async(prompt)
                return response.text
            except ResourceExhausted:
                logger.warning(f"Gemini Rate Limit (429) hit. Retrying in {base_delay * (2 ** attempt)}s...")
                await asyncio.sleep(base_delay * (2 ** attempt))
            except Exception as e:
                logger.error(f"Gemini API Error: {e}")
                raise e
    raise TimeoutError("Exceeded max retries for LLM due to rate limits.")

async def run_react_loop(ticket: dict, classification: dict):
    """
    Core ReAct loop enforcing strict JSON agency.
    """
    ticket_id = ticket['ticket_id']
    history = []
    max_steps = 8
    tool_calls_count = 0
    
    system_prompt = f"""
    You are an Autonomous Support Agent (NOT a chatbot). Your goal is to resolve the user's issue using tools.
    You MUST output valid JSON and ONLY JSON. No pleasantries, no markdown blocks.

    Available Tools:
    - get_customer: params -> {{"email": str}}
    - get_order: params -> {{"order_id": str}}
    - get_product: params -> {{"product_id": str}}
    - search_knowledge_base: params -> {{"query": str}}
    - check_refund_eligibility: params -> {{"order_id": str}}
    - issue_refund: params -> {{"order_id": str, "amount": float}}
    - send_reply: params -> {{"ticket_id": str, "message": str}}
    - escalate: params -> {{"ticket_id": str, "summary": str, "priority": "low"|"medium"|"high"|"critical"}}
    
    Output JSON Schema:
    {{
        "thought": "your step-by-step reasoning",
        "action": "tool_name OR final_answer",
        "params": {{ "key": "value" }}
    }}
    
    Rules:
    1. If you are missing information to perform an action, use a tool to get it first.
    2. A minimum of 3 tool calls is expected before resolution for non-trivial tickets.
    3. If you decide to send a reply or escalate, that is usually a 'final_answer' action, but you still need to log the thought and set action to it. However, if you use the 'escalate' or 'send_reply' tool, you should subsequently output "final_answer".
    """

    # We will maintain conversation history manually for ReAct format
    context = f"Ticket ID: {ticket_id}\nSubject: {ticket['subject']}\nBody: {ticket['body']}\nClassification: {json.dumps(classification)}\n"
    
    conversation_str = system_prompt + "\n\nENVIRONMENT OBS:\n" + context

    for step in range(1, max_steps + 1):
        try:
            # We enforce a small sleep between steps broadly to help with RPM across 20 concurrent tasks
            await asyncio.sleep(2)
            
            content = await _call_llm_with_retry(conversation_str)
            content_clean = content.replace("```json", "").replace("```", "").strip()
            
            # Pydantic validation of Agent output
            try:
                action_data = json.loads(content_clean)
                validated_action = ReActAction(**action_data)
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"[{ticket_id}] Agent format error: {str(e)}")
                # Provide feedback to agent to self-correct
                conversation_str += f"\nAGENT OUTPUT: {content_clean}\nOBSERVATION: ERROR - Invalid JSON or Schema. Follow the schema strictly. Error details: {str(e)}\n"
                continue
            
            thought = validated_action.thought
            tool_name = validated_action.action
            kwargs = validated_action.params
            
            # Map tool name to its Pydantic input schema for strict validation
            from agent.schemas import (
                GetCustomerInput, GetOrderInput, GetProductInput, SearchKbInput,
                CheckRefundInput, IssueRefundInput, SendReplyInput, EscalateInput
            )
            SCHEMA_MAP = {
                "get_customer": GetCustomerInput,
                "get_order": GetOrderInput,
                "get_product": GetProductInput,
                "search_knowledge_base": SearchKbInput,
                "check_refund_eligibility": CheckRefundInput,
                "issue_refund": IssueRefundInput,
                "send_reply": SendReplyInput,
                "escalate": EscalateInput
            }
            
            if tool_name in SCHEMA_MAP:
                try:
                    # Validate the params against the specific tool schema
                    SCHEMA_MAP[tool_name](**kwargs)
                except ValidationError as e:
                    logger.warning(f"[{ticket_id}] Tool argument validation error: {e}")
                    conversation_str += f"\nAGENT OUTPUT: {content_clean}\nOBSERVATION: ERROR - Invalid tool parameters. Detailed error: {str(e)}\n"
                    continue
            
            if tool_name == "final_answer":
                if tool_calls_count < 3:
                    logger.warning(f"[{ticket_id}] Agent tried to answer early (calls: {tool_calls_count}). Rejecting.")
                    conversation_str += f"\nAGENT OUTPUT: {content_clean}\nOBSERVATION: ERROR - You MUST perform at least 3 tool calls to gather context before giving a final_answer. You have done {tool_calls_count}.\n"
                    continue
                
                # Check confidence before finalizing
                decision_str = json.dumps(kwargs) if kwargs else "Resolved"
                confidence = await get_confidence_score(ticket, history, decision_str)
                
                if confidence < 0.7:
                    logger.warning(f"[{ticket_id}] Low confidence ({confidence}). Auto-escalating.")
                    # Force escalation tool
                    history.append({
                        "step": step,
                        "thought": f"Agent proposed: {decision_str}. System Overridden: Low Confidence ({confidence}).",
                        "action": "escalate",
                        "params": {"ticket_id": ticket_id, "summary": "Auto-escalated by Confidence Guardian", "priority": "high"},
                        "status": "system_override"
                    })
                    await execute_tool(escalate, ticket_id=ticket_id, summary="Low Confidence Escalate", priority="high")
                    return "Auto-escalated (Low confidence)", history, confidence

                history.append({
                    "step": step,
                    "thought": thought,
                    "action": tool_name,
                    "params": kwargs,
                    "status": "completed"
                })
                return decision_str, history, confidence

            if tool_name in TOOL_MAP:
                result, attempts = await execute_tool(TOOL_MAP[tool_name], **kwargs)
                
                if result is None: # Exhausted max retries
                    history.append({
                        "step": step,
                        "thought": thought,
                        "action": tool_name,
                        "params": kwargs,
                        "observation": {"error": "Tool failed after all retries"},
                        "status": "fatal_failure"
                    })
                    log_to_dlq(ticket_id, f"Tool {tool_name} failed max retries", history)
                    return "failed_tool", history
                
                history.append({
                    "step": step,
                    "thought": thought,
                    "action": tool_name,
                    "params": kwargs,
                    "observation": result,
                    "status": "success",
                    "attempts": attempts
                })
                
                tool_calls_count += 1
                
                # Append to conversation string for next iteration
                conversation_str += f"\nAGENT OUTPUT: {content_clean}\nOBSERVATION: {json.dumps(result)}\n"
                
            else:
                conversation_str += f"\nAGENT OUTPUT: {content_clean}\nOBSERVATION: ERROR - Unknown tool '{tool_name}'\n"

        except Exception as e:
            logger.error(f"[{ticket_id}] Fatal Loop Error: {str(e)}")
            return f"fatal_error: {str(e)}", history, 0.0

    return "timeout_steps", history, 0.0
