from mocks.mock_data import MOCK_ORDERS
from mocks.failure_simulator import simulate_failure

async def check_refund_eligibility(order_id: str):
    """Check whether this order can be refunded under policy."""
    order = MOCK_ORDERS.get(order_id)
    if not order:
        return await simulate_failure("check_refund_eligibility", {"eligible": False, "reason": "Order not found"})
    
    # Mock policy: only delivered orders are eligible.
    eligible = order["status"] == "delivered"
    reason = "Order delivered and within timeframe" if eligible else "Order not yet delivered"
    
    return await simulate_failure("check_refund_eligibility", {"eligible": eligible, "reason": reason})

async def issue_refund(order_id: str, amount: float):
    """Issue a refund for an eligible order."""
    # Refunds are irreversible. Guard the call with a final eligibility check.
    order = MOCK_ORDERS.get(order_id)
    if not order or order.get("status") != "delivered":
        return await simulate_failure("issue_refund", {
            "status": "failed", 
            "error": "Guard failed: order not eligible for refund or does not exist."
        })
    
    # Return a successful transaction payload in the mock environment.
    return await simulate_failure("issue_refund", {"status": "success", "order_id": order_id, "refunded_amount": amount})

async def send_reply(ticket_id: str, message: str):
    """Send the customer-facing message once the decision is finalized."""
    return await simulate_failure("send_reply", {"status": "sent", "ticket_id": ticket_id})

async def escalate(ticket_id: str, summary: str, priority: str):
    """Route a ticket to a human specialist with context and priority."""
    return await simulate_failure("escalate", {"status": "escalated", "ticket_id": ticket_id, "priority": priority})
