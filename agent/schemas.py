from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any, List

# Classification Schema
class TicketClassification(BaseModel):
    category: Literal["refund", "order_status", "product_info", "complaint", "other"]
    urgency: Literal["high", "medium", "low"]
    resolvability: Literal["auto", "escalate"]
    error: Optional[str] = None

# Tool Input Schemas
class GetCustomerInput(BaseModel):
    email: str

class GetOrderInput(BaseModel):
    order_id: str

class GetProductInput(BaseModel):
    product_id: str

class SearchKbInput(BaseModel):
    query: str

class CheckRefundInput(BaseModel):
    order_id: str

class IssueRefundInput(BaseModel):
    order_id: str
    amount: float

class SendReplyInput(BaseModel):
    ticket_id: str
    message: str

class EscalateInput(BaseModel):
    ticket_id: str
    summary: str
    priority: Literal["low", "medium", "high", "critical"]

# ReAct Loop Schemas
class ReActAction(BaseModel):
    thought: str = Field(description="Reasoning about the current state and what to do next.")
    action: Literal[
        "get_customer", "get_order", "get_product", "search_knowledge_base", 
        "check_refund_eligibility", "issue_refund", "send_reply", "escalate", 
        "final_answer"
    ] = Field(description="The tool to execute, or 'final_answer' if done.")
    params: Dict[str, Any] = Field(description="The parameters for the expected tool.")
