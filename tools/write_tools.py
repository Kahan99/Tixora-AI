from mocks.mock_data import MOCK_ORDERS
from mocks.failure_simulator import simulate_failure
import asyncio

async def check_refund_eligibility(order_id: str):
    """Checks if an order is eligible for a refund."""
    order = MOCK_ORDERS.get(order_id)
    if not order:
        return await simulate_failure("check_refund_eligibility", {"eligible": False, "reason": "Order not found"})
    
    # Simple logic: only delivered orders within a mock timeframe are eligible
    eligible = order["status"] == "delivered"
    reason = "Order delivered and within timeframe" if eligible else "Order not yet delivered"
    
    return await simulate_failure("check_refund_eligibility", {"eligible": eligible, "reason": reason})

async def issue_refund(order_id: str, amount: float):
    """Issues a refund for a specific order."""
    # Mock successful refund
    return await simulate_failure("issue_refund", {"status": "success", "order_id": order_id, "refunded_amount": amount})

async def send_reply(ticket_id: str, message: str):
    """Sends a reply to the customer."""
    return await simulate_failure("send_reply", {"status": "sent", "ticket_id": ticket_id})

async def escalate(ticket_id: str, summary: str, priority: str):
    """Escalates the ticket to a human agent."""
    return await simulate_failure("escalate", {"status": "escalated", "ticket_id": ticket_id, "priority": priority})
