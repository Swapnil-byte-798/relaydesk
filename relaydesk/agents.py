"""Explicit specialist nodes with bounded tool access and grounded replies."""

from dataclasses import replace
from time import perf_counter
from .knowledge import search_knowledge
from .models import Outcome, Plan, RoutingResult
from .policy import money
from .routing import HUMAN_PATTERN, UNSAFE_PATTERN, Router, mentioned_order
from .tools import SupportTools


def unsuccessful(ticket: dict, intent: str, reply: str) -> Outcome:
    attempts = ticket["failed_attempts"] + 1
    if attempts >= 2:
        return Outcome("I have passed this case to the human support inbox with the conversation attached. "
                       "A person needs to review the details before we continue.", "needs_human", intent, attempts)
    return Outcome(reply, "open", intent, attempts)


class OrderAgent:
    def run(self, plan: Plan, tools: SupportTools, trace) -> Outcome:
        if not plan.order_id:
            return unsuccessful(tools.ticket, "order", "Please share your order number, such as RD-1042, so I can check this customer account.")
        order = tools.get_order(plan.order_id)
        trace("tool:get_order", "Customer-scoped order lookup completed")
        if order is None:
            return unsuccessful(tools.ticket, "order", "I could not find that order in this customer account. Please check the number or ask for a human review.")
        reply = f"Order {order['id']} ({order['item']}) is {order['status']}."
        if order["estimated_at"] and order["status"] in {"processing", "shipped"}:
            reply += f" Estimated delivery: {order['estimated_at'][:10]}."
        if order["tracking"] and order["status"] == "shipped":
            reply += f" Sandbox tracking reference: {order['tracking']}."
        if order["status"] == "refunded":
            reply += " A sandbox refund has been recorded; no real payment was made."
        return Outcome(reply, "resolved", "order", order=order)


class RefundAgent:
    def run(self, plan: Plan, tools: SupportTools, trace) -> Outcome:
        if not plan.order_id:
            return unsuccessful(tools.ticket, "refund", "Please share the order number you want reviewed for a refund.")
        order = tools.get_order(plan.order_id)
        trace("tool:get_order", "Customer-scoped refund order lookup completed")
        if order is None:
            return unsuccessful(tools.ticket, "refund", "I could not find that order in this customer account. Please check the number or request a human review.")
        approval, policy = tools.request_refund(order, plan.reason)
        trace("policy:refund", "Eligible for review" if policy["eligible"] else "Outside the automatic eligibility policy")
        if approval is None:
            failed = ", ".join(check["label"] for check in policy["checks"] if not check["passed"])
            return Outcome(f"Order {order['id']} is outside the automatic refund policy: {failed}. "
                           "I have not created a refund. You can ask for a human review.", "resolved", "refund", order=order)
        trace("tool:request_refund", f"Approval request status: {approval['status']}; no payment tool executed")
        if approval["status"] == "approved":
            reply = f"A sandbox refund of {money(approval['amount_paise'])} is already recorded for {order['id']}. No real money was transferred."
            status = "resolved"
        elif approval["status"] == "rejected":
            reply = f"A human reviewer declined the refund for {order['id']}. No refund was recorded. You can ask for a human review of the decision."
            status = "resolved"
        else:
            reply = f"I have prepared a refund request for {order['id']} for {money(approval['amount_paise'])}. "
            reply += "It is waiting for human approval. No refund has been recorded and no money has moved."
            status = "waiting_approval"
        return Outcome(reply, status, "refund", order=order, approval=approval)


class TechnicalAgent:
    def run(self, plan: Plan, tools: SupportTools, trace) -> Outcome:
        sources = search_knowledge(plan.query)
        trace("tool:search_knowledge", f"Retrieved {len(sources)} curated articles")
        if not sources:
            return unsuccessful(tools.ticket, "technical", "I do not have a matching support article. Please share the error message or ask for a human specialist.")
        reply = "\n\n".join(f"{source['body']}\nSource: {source['title']} [{source['id']}]" for source in sources)
        return Outcome(reply, "resolved", "technical", sources=sources)


class SupportWorkflow:
    def __init__(self, router: Router):
        self.router = router
        self.agents = {"order": OrderAgent(), "refund": RefundAgent(), "technical": TechnicalAgent()}

    def run(self, message: str, history: list[dict], tools: SupportTools) -> tuple[Outcome, RoutingResult, list[dict]]:
        events: list[dict] = []
        last = perf_counter()

        def trace(node: str, detail: str):
            nonlocal last
            at = perf_counter()
            events.append({"step": len(events) + 1, "node": node, "detail": detail,
                           "duration_ms": max(0, round((at - last) * 1000)), "created_at": tools.now.isoformat()})
            last = at

        if tools.ticket["status"] == "needs_human":
            result = RoutingResult(Plan("complaint", None, reason="Already in human inbox", query=message))
            trace("handoff", "Appended to the existing human support case")
            return Outcome("Your message is attached to the case in the human support inbox. A person will review it.",
                           "needs_human", "complaint", tools.ticket["failed_attempts"]), result, events

        # The non-model guard runs even when a custom router is injected.
        if HUMAN_PATTERN.search(message) or UNSAFE_PATTERN.search(message):
            result = RoutingResult(Plan("complaint", None, "angry", "Human review required", message))
        else:
            result = self.router.route(message, history)
        plan = replace(result.plan, order_id=mentioned_order(message, history))
        trace("router", f"Intent: {plan.intent}; mode: {result.mode}; model requests: {result.llm_calls}")

        if plan.intent == "complaint" or plan.sentiment == "angry":
            outcome = Outcome("I have passed this case to the human support inbox with your conversation attached. "
                              "A person should review it before any further action.", "needs_human", "complaint")
            trace("handoff", "Human review requested; automated tools stopped")
        elif plan.intent in self.agents:
            outcome = self.agents[plan.intent].run(plan, tools, trace)
            trace(f"agent:{plan.intent}", f"Outcome: {outcome.status}")
        else:
            outcome = unsuccessful(tools.ticket, "unknown", "I can help with an order, a refund request, or a technical issue. Please share a few details, or ask for a human.")
            trace("clarify", f"Unsuccessful attempts: {outcome.failed_attempts}")
        trace("finish", "Reply built from tools and policy; no autonomous financial action")
        return outcome, result, events
