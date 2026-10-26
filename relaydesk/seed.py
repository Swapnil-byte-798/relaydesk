"""Synthetic store fixtures for repeatable support scenarios."""

from datetime import datetime, timedelta
from .database import Session


def seed_workspace(session: Session, workspace: str, now: datetime) -> None:
    session.execute("INSERT INTO workspaces(id, created_at) VALUES (:id, :at) ON CONFLICT (id) DO NOTHING",
                    {"id": workspace, "at": now.isoformat()})
    session.execute("""INSERT INTO ticket_approvals(workspace_id, ticket_id, approval_id)
        SELECT workspace_id, ticket_id, id FROM approvals WHERE workspace_id=:workspace
        ON CONFLICT (ticket_id, approval_id) DO NOTHING""", {"workspace": workspace})
    customers = [("maya", "Maya Rao", "maya@example.test"), ("rohan", "Rohan Shah", "rohan@example.test")]
    for customer_id, name, email in customers:
        session.execute("""INSERT INTO customers(workspace_id, id, name, email)
            VALUES (:workspace, :id, :name, :email) ON CONFLICT (workspace_id, id) DO NOTHING""",
                        {"workspace": workspace, "id": customer_id, "name": name, "email": email})
    orders = [
        ("RD-1042", "maya", "Everyday backpack", 329900, "shipped", None, 2, "DEMO-TRACK-1042"),
        ("RD-1043", "maya", "Wireless headphones", 249900, "delivered", 5, None, None),
        ("RD-1044", "maya", "Desk lamp", 159900, "delivered", 45, None, None),
        ("RD-1045", "maya", "Mechanical keyboard", 399900, "processing", None, 4, None),
        ("RD-1046", "maya", "Travel organiser", 199900, "cancelled", None, None, None),
        ("RD-2042", "rohan", "Studio speaker", 599900, "delivered", 3, None, None),
        ("RD-2043", "rohan", "USB-C hub", 129900, "shipped", None, 1, "DEMO-TRACK-2043"),
    ]
    for order_id, customer, item, amount, status, days_ago, eta_days, tracking in orders:
        session.execute("""INSERT INTO orders
            (workspace_id, id, customer_id, item, amount_paise, status, delivered_at, estimated_at, tracking)
            VALUES (:workspace, :id, :customer, :item, :amount, :status, :delivered, :estimated, :tracking)
            ON CONFLICT (workspace_id, id) DO NOTHING""", {
                "workspace": workspace, "id": order_id, "customer": customer, "item": item,
                "amount": amount, "status": status,
                "delivered": (now - timedelta(days=days_ago)).isoformat() if days_ago is not None else None,
                "estimated": (now + timedelta(days=eta_days)).isoformat() if eta_days is not None else None,
                "tracking": tracking,
            })
