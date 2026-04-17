# Mock databases for the support system
MOCK_CUSTOMERS = {
    f"user{i}@example.com": {
        "customer_id": f"CUST-{5000+i}",
        "name": f"Customer {i}",
        "email": f"user{i}@example.com",
        "tier": "gold" if i % 3 == 0 else "silver",
        "phone": f"+1-555-010{i:02d}"
    } for i in range(1, 100)
}

MOCK_ORDERS = {
    f"ORD-{2000+i}": {
        "order_id": f"ORD-{2000+i}",
        "customer_id": f"CUST-{5000+i}",
        "status": "delivered" if i % 2 == 0 else "shipped",
        "items": [{"product_id": f"PROD-{3000+i}", "quantity": 1, "price": 49.99}],
        "total_amount": 49.99,
        "delivery_date": "2026-04-10"
    } for i in range(1, 100)
}

MOCK_PRODUCTS = {
    f"PROD-{3000+i}": {
        "product_id": f"PROD-{3000+i}",
        "name": f"Gizmo Tool {i}",
        "description": "High-quality gizmo tool for general use.",
        "warranty_period": "12 months",
        "stock_status": "in_stock"
    } for i in range(1, 100)
}

MOCK_KB = [
    {"id": "KB-001", "title": "Refund Policy", "content": "Refunds are processed within 5-7 business days for items returned within 30 days in original condition."},
    {"id": "KB-002", "title": "Shipping Delays", "content": "Due to high demand, some orders may experience a 2-3 day delay in shipping."},
    {"id": "KB-003", "title": "Warranty Information", "content": "All mechanical products come with a 1-year limited warranty against manufacturing defects."},
    {"id": "KB-004", "title": "Order Tracking", "content": "You can track your order using the link provided in your shipping confirmation email."}
]
