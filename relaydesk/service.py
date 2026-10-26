"""Application transactions shared by the CLI and optional HTTP interface."""

from datetime import datetime
from hashlib import sha256
import json
from typing import Callable
from uuid import uuid4

from .agents import SupportWorkflow
from .database import Database, Session
from .models import SupportError
from .policy import money, refund_policy, utc_now
from .routing import Router, RuleRouter
from .seed import seed_workspace
from .tools import SupportTools


def checked_text(value: str, label: str, limit: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise SupportError(f"{label} must contain 1-{limit} characters.")
    return value.strip()


class SupportService:
    def __init__(self, database: Database, workspace: str = "local-store", router: Router | None = None,
                 clock: Callable[[], datetime] = utc_now):
        self.database = database
        self.workspace = checked_text(workspace, "Workspace", 100)
        self.router = router or RuleRouter()
        self.clock = clock

    def initialize(self) -> None:
        self.database.initialize()
        with self.database.transaction() as session:
            seed_workspace(session, self.workspace, self.clock())

    def _lock_workspace(self, session: Session) -> None:
        row = session.one(session.lock("SELECT id FROM workspaces WHERE id=:workspace"), {"workspace": self.workspace})
        if row is None:
            raise SupportError("Initialize the store first.", 409)

    def _ticket(self, session: Session, ticket_id: str) -> dict:
        ticket = session.one(session.lock("SELECT * FROM tickets WHERE workspace_id=:workspace AND id=:id"),
                             {"workspace": self.workspace, "id": ticket_id})
        if ticket is None:
            raise SupportError("Ticket not found.", 404)
        return ticket

    def _messages(self, session: Session, ticket_id: str) -> list[dict]:
        return session.all("SELECT role, content, created_at, sequence_no FROM messages WHERE workspace_id=:workspace AND ticket_id=:ticket ORDER BY sequence_no",
                           {"workspace": self.workspace, "ticket": ticket_id})

    def _pending_approval(self, session: Session, ticket_id: str) -> dict | None:
        return session.one("""SELECT a.id FROM approvals a JOIN ticket_approvals t ON t.approval_id=a.id
            AND t.workspace_id=a.workspace_id WHERE a.workspace_id=:workspace AND t.ticket_id=:ticket
            AND a.status='pending'""", {"workspace": self.workspace, "ticket": ticket_id})

    def _summary(self, session: Session, ticket: dict, status: str) -> str:
        recent = [message["content"] for message in self._messages(session, ticket["id"])
                  if message["role"] == "customer"][-4:]
        return (f"Customer {ticket['customer_id']}; intent {ticket['intent']}; status {status}. "
                "Latest requests: " + " | ".join(recent))[:3000]

    def _append(self, session: Session, ticket_id: str, role: str, content: str, at: str) -> None:
        sequence = session.one("SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next FROM messages WHERE workspace_id=:workspace AND ticket_id=:ticket",
                               {"workspace": self.workspace, "ticket": ticket_id})["next"]
        session.execute("""INSERT INTO messages(id, workspace_id, ticket_id, sequence_no, role, content, created_at)
            VALUES (:id, :workspace, :ticket, :sequence, :role, :content, :at)""", {
                "id": str(uuid4()), "workspace": self.workspace, "ticket": ticket_id,
                "sequence": sequence, "role": role, "content": content, "at": at,
            })

    def create_ticket(self, customer_id: str) -> dict:
        with self.database.transaction() as session:
            customer = session.one("SELECT * FROM customers WHERE workspace_id=:workspace AND id=:id",
                                   {"workspace": self.workspace, "id": customer_id})
            if customer is None:
                raise SupportError("Customer not found.", 404)
            ticket_id, at = str(uuid4()), self.clock().isoformat()
            session.execute("""INSERT INTO tickets(id, workspace_id, customer_id, title, created_at, updated_at)
                VALUES (:id, :workspace, :customer, :title, :at, :at)""", {
                    "id": ticket_id, "workspace": self.workspace, "customer": customer_id,
                    "title": f"Support for {customer['name']}", "at": at,
                })
            return self._ticket(session, ticket_id)

    def send_message(self, ticket_id: str, message: str, request_key: str) -> dict:
        message = checked_text(message, "Message")
        request_key = checked_text(request_key, "Request key", 100)
        input_hash = sha256(json.dumps([ticket_id, message], ensure_ascii=False).encode()).hexdigest()
        with self.database.transaction() as session:
            # Serializing a small sandbox workspace keeps duplicate keys safe across tickets too.
            self._lock_workspace(session)
            ticket = self._ticket(session, ticket_id)
            previous = session.one("SELECT * FROM runs WHERE workspace_id=:workspace AND request_key=:key",
                                   {"workspace": self.workspace, "key": request_key})
            if previous:
                if previous["input_hash"] != input_hash:
                    raise SupportError("This request key was already used for a different message or ticket.", 409)
                return json.loads(previous["response_json"])
            history = self._messages(session, ticket_id)
            now = self.clock()
            tools = SupportTools(session, self.workspace, ticket, now)
            outcome, routed, trace = SupportWorkflow(self.router).run(message, history, tools)
            pending = self._pending_approval(session, ticket_id)
            if pending and outcome.status != "needs_human":
                outcome.status = "waiting_approval"
            run_id, at = str(uuid4()), now.isoformat()
            result = {**outcome.to_dict(), "ticket_id": ticket_id, "run_id": run_id, "mode": routed.mode,
                      "llm_calls": routed.llm_calls, "input_tokens": routed.input_tokens,
                      "output_tokens": routed.output_tokens, "trace": trace}
            self._append(session, ticket_id, "customer", message, at)
            self._append(session, ticket_id, "assistant", outcome.reply, at)
            customer_messages = [entry["content"] for entry in history if entry["role"] == "customer"][-3:] + [message]
            summary = f"Customer {ticket['customer_id']}; intent {outcome.intent}; status {outcome.status}. Latest requests: " + " | ".join(customer_messages)
            session.execute("""UPDATE tickets SET title=:title, status=:status, intent=:intent,
                failed_attempts=:attempts, summary=:summary, updated_at=:at WHERE id=:ticket AND workspace_id=:workspace""", {
                    "title": message[:80] if not history else ticket["title"], "status": outcome.status,
                    "intent": outcome.intent, "attempts": outcome.failed_attempts, "summary": summary[:3000],
                    "at": at, "ticket": ticket_id, "workspace": self.workspace,
                })
            session.execute("""INSERT INTO runs
                (id, workspace_id, ticket_id, request_key, input_hash, response_json, mode, llm_calls, input_tokens, output_tokens, created_at)
                VALUES (:id, :workspace, :ticket, :key, :hash, :response, :mode, :calls, :input, :output, :at)""", {
                    "id": run_id, "workspace": self.workspace, "ticket": ticket_id, "key": request_key,
                    "hash": input_hash, "response": json.dumps(result), "mode": routed.mode,
                    "calls": routed.llm_calls, "input": routed.input_tokens, "output": routed.output_tokens, "at": at,
                })
            for event in trace:
                self._event(session, ticket_id, event["node"], event["detail"], at, run_id, event["step"], event["duration_ms"])
            return result

    def _event(self, session: Session, ticket: str, node: str, detail: str, at: str,
               run: str | None = None, step: int = 1, duration_ms: int = 0) -> None:
        session.execute("""INSERT INTO events(id, workspace_id, ticket_id, run_id, step, node, detail, duration_ms, created_at)
            VALUES (:id, :workspace, :ticket, :run, :step, :node, :detail, :duration, :at)""", {
                "id": str(uuid4()), "workspace": self.workspace, "ticket": ticket, "run": run,
                "step": step, "node": node, "detail": detail, "duration": duration_ms, "at": at,
            })

    def decide_refund(self, approval_id: str, decision: str, actor: str, note: str = "") -> dict:
        if decision not in {"approved", "rejected"}:
            raise SupportError("Decision must be approved or rejected.")
        actor = checked_text(actor, "Reviewer", 100)
        if not isinstance(note, str) or len(note) > 1000:
            raise SupportError("Decision note must be at most 1000 characters.")
        with self.database.transaction() as session:
            self._lock_workspace(session)
            approval = session.one(session.lock("SELECT * FROM approvals WHERE workspace_id=:workspace AND id=:id"),
                                   {"workspace": self.workspace, "id": approval_id})
            if approval is None:
                raise SupportError("Approval request not found.", 404)
            if approval["status"] != "pending":
                if approval["status"] == decision:
                    return approval
                raise SupportError("This request already has a different final decision.", 409)
            ticket = self._ticket(session, approval["ticket_id"])
            now = self.clock()
            order = SupportTools(session, self.workspace, ticket, now).get_order(approval["order_id"])
            if order is None:
                raise SupportError("The order no longer belongs to this customer.", 409)
            if decision == "approved":
                if not refund_policy(order, now)["eligible"] or approval["amount_paise"] != order["amount_paise"]:
                    raise SupportError("The order no longer satisfies the refund policy. Review manually.", 409)
                session.execute("""INSERT INTO refunds(id, workspace_id, approval_id, order_id, amount_paise, created_at)
                    VALUES (:id, :workspace, :approval, :order, :amount, :at)""", {
                        "id": str(uuid4()), "workspace": self.workspace, "approval": approval_id,
                        "order": order["id"], "amount": order["amount_paise"], "at": now.isoformat(),
                    })
                session.execute("UPDATE orders SET status='refunded' WHERE workspace_id=:workspace AND id=:id",
                                {"workspace": self.workspace, "id": order["id"]})
            at = now.isoformat()
            session.execute("""UPDATE approvals SET status=:status, decided_at=:at, decided_by=:actor, decision_note=:note
                WHERE workspace_id=:workspace AND id=:id AND status='pending'""", {
                    "status": decision, "at": at, "actor": actor, "note": note,
                    "workspace": self.workspace, "id": approval_id,
                })
            reply = (f"Human review: a sandbox refund of {money(order['amount_paise'])} has been recorded for {order['id']}. No real money was transferred."
                     if decision == "approved" else f"Human review: the refund request for {order['id']} was declined. No refund was recorded.")
            if note.strip():
                reply += " Reviewer note: " + note.strip()
            followers = session.all("SELECT ticket_id FROM ticket_approvals WHERE workspace_id=:workspace AND approval_id=:approval",
                                    {"workspace": self.workspace, "approval": approval_id})
            for follower in followers:
                related = self._ticket(session, follower["ticket_id"])
                self._append(session, related["id"], "human", reply, at)
                pending = self._pending_approval(session, related["id"])
                status = "needs_human" if related["status"] == "needs_human" else ("waiting_approval" if pending else "resolved")
                session.execute("UPDATE tickets SET status=:status, summary=:summary, updated_at=:at WHERE workspace_id=:workspace AND id=:id",
                                {"status": status, "summary": self._summary(session, related, status),
                                 "at": at, "workspace": self.workspace, "id": related["id"]})
                self._event(session, related["id"], "human:refund_decision", f"{decision} by {actor}; sandbox ledger only", at)
            return session.one("SELECT * FROM approvals WHERE workspace_id=:workspace AND id=:id",
                               {"workspace": self.workspace, "id": approval_id})

    def human_reply(self, ticket_id: str, message: str, resolve: bool = False) -> dict:
        message = checked_text(message, "Human reply")
        with self.database.transaction() as session:
            self._lock_workspace(session)
            ticket = self._ticket(session, ticket_id)
            if ticket["status"] != "needs_human":
                raise SupportError("This ticket is not in the human inbox.", 409)
            at = self.clock().isoformat()
            self._append(session, ticket_id, "human", message, at)
            pending = self._pending_approval(session, ticket_id)
            status = ("waiting_approval" if pending else "resolved") if resolve else "needs_human"
            session.execute("UPDATE tickets SET status=:status, summary=:summary, failed_attempts=0, updated_at=:at WHERE workspace_id=:workspace AND id=:id",
                            {"status": status, "summary": self._summary(session, ticket, status),
                             "at": at, "workspace": self.workspace, "id": ticket_id})
            self._event(session, ticket_id, "human:reply", "Operator replied" + (" and resolved the handoff" if resolve else ""), at)
            return self._ticket(session, ticket_id)

    def ticket_detail(self, ticket_id: str) -> dict:
        with self.database.transaction() as session:
            ticket = self._ticket(session, ticket_id)
            params = {"workspace": self.workspace, "ticket": ticket_id}
            return {**ticket, "messages": self._messages(session, ticket_id),
                    "approvals": session.all("""SELECT a.* FROM approvals a JOIN ticket_approvals t ON t.approval_id=a.id
                        AND t.workspace_id=a.workspace_id WHERE a.workspace_id=:workspace AND t.ticket_id=:ticket ORDER BY a.created_at""", params),
                    "events": session.all("SELECT * FROM events WHERE workspace_id=:workspace AND ticket_id=:ticket ORDER BY created_at, step", params)}

    def snapshot(self) -> dict:
        with self.database.transaction() as session:
            p = {"workspace": self.workspace}
            tickets = session.all("SELECT * FROM tickets WHERE workspace_id=:workspace ORDER BY updated_at DESC, id", p)
            usage = session.one("SELECT COUNT(*) AS turns, COALESCE(SUM(llm_calls),0) AS llm_calls, COALESCE(SUM(input_tokens),0) AS input_tokens, COALESCE(SUM(output_tokens),0) AS output_tokens FROM runs WHERE workspace_id=:workspace", p)
            return {"sandbox": True, "workspace": self.workspace,
                    "customers": session.all("SELECT id, name, email FROM customers WHERE workspace_id=:workspace ORDER BY id", p),
                    "orders": session.all("SELECT * FROM orders WHERE workspace_id=:workspace ORDER BY id", p),
                    "tickets": tickets,
                    "approvals": session.all("SELECT * FROM approvals WHERE workspace_id=:workspace ORDER BY created_at DESC", p),
                    "refunds": session.all("SELECT * FROM refunds WHERE workspace_id=:workspace ORDER BY created_at", p),
                    "handoffs": [ticket for ticket in tickets if ticket["status"] == "needs_human"],
                    "usage": usage}
