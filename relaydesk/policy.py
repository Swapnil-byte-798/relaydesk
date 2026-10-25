"""Refund policy is code, not a language-model instruction."""

from datetime import datetime, timedelta, timezone

POLICY_VERSION = "refunds-2026-10-v1"
REFUND_WINDOW = timedelta(days=30)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def refund_policy(order: dict, now: datetime) -> dict:
    try:
        delivered = datetime.fromisoformat(order.get("delivered_at") or "")
        age = now - delivered
        in_window = timedelta(0) <= age <= REFUND_WINDOW
    except (TypeError, ValueError):
        in_window = False
    amount = order.get("amount_paise")
    checks = [
        {"label": "Order delivered", "passed": order.get("status") == "delivered"},
        {"label": "Within 30 days of delivery", "passed": in_window},
        {"label": "Valid full-order amount", "passed": isinstance(amount, int) and not isinstance(amount, bool) and amount > 0},
    ]
    return {"version": POLICY_VERSION, "eligible": all(check["passed"] for check in checks),
            "checks": checks, "human_approval_required": True}


def money(paise: int) -> str:
    return f"INR {paise / 100:,.2f}"
