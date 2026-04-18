from mocks.mock_data import MOCK_CUSTOMERS, MOCK_ORDERS, MOCK_PRODUCTS, MOCK_KB
from mocks.failure_simulator import simulate_failure

async def get_customer(email: str):
    """Retrieves customer details by email."""
    data = MOCK_CUSTOMERS.get(email, {"error": "Customer not found"})
    return await simulate_failure("get_customer", data)

async def get_order(order_id: str):
    """Retrieves order details by order ID."""
    data = MOCK_ORDERS.get(order_id, {"error": "Order not found"})
    return await simulate_failure("get_order", data)

async def get_product(product_id: str):
    """Retrieves product details by product ID."""
    data = MOCK_PRODUCTS.get(product_id, {"error": "Product not found"})
    return await simulate_failure("get_product", data)

async def search_knowledge_base(query: str):
    """Searches the knowledge base for relevant articles."""
    results = [item for item in MOCK_KB if query.lower() in item["title"].lower() or query.lower() in item["content"].lower()]
    return await simulate_failure("search_knowledge_base", results if results else {"error": "No matching articles"})
