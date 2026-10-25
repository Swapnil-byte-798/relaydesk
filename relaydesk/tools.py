"""Tools available to specialists. Approval is deliberately absent from this API."""

from datetime import datetime
import json
from uuid import uuid4

from .database import Session
from .policy import refund_policy


class SupportTools:
    def __init__(self, session: Session, workspace: str, ticket: dict, now: datetime):
        self.session = session
        self.workspace = workspace
        self.ticket = ticket
        self.now = now

    def get_order(self, order_id: str) -> dict | None:
        return self.session.one(self.session.lock("""SELECT * FROM orders
            WHERE workspace_id=:workspace AND id=:id AND customer_id=:customer"""),
            {"workspace": self.workspace, "id": order_id, "customer": self.ticket["customer_id"]})

    def request_refund(self, order: dict, reason: str) -> tuple[dict | None, dict]:
        # Keep the boundary correct even if a new specialist calls it incorrectly.
        scoped_order = self.get_order(order["id"])
        if scoped_order is None:
            raise ValueError("Order is outside the ticket's customer account")
        existing = self.session.one("SELECT * FROM approvals WHERE workspace_id=:workspace AND order_id=:order",
                                    {"workspace": self.workspace, "order": scoped_order["id"]})
        policy = refund_policy(scoped_order, self.now)
        if existing is not None:
            return existing, policy
        if not policy["eligible"]:
            return None, policy
        approval = {
            "id": str(uuid4()), "workspace_id": self.workspace, "ticket_id": self.ticket["id"],
            "customer_id": self.ticket["customer_id"], "order_id": scoped_order["id"],
            "amount_paise": scoped_order["amount_paise"], "status": "pending", "reason": reason[:1000],
            "policy_json": json.dumps(policy), "created_at": self.now.isoformat(),
            "decided_at": None, "decided_by": None, "decision_note": None,
        }
        self.session.execute("""INSERT INTO approvals
            (id, workspace_id, ticket_id, customer_id, order_id, amount_paise, status, reason, policy_json, created_at)
            VALUES (:id, :workspace_id, :ticket_id, :customer_id, :order_id, :amount_paise, :status, :reason, :policy_json, :created_at)""", approval)
        return approval, policy
