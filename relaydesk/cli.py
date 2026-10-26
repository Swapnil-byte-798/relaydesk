"""A Python-only operator interface; no authored HTML, CSS, or JavaScript."""

import argparse
from getpass import getpass
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from .config import Config, private_write
from .models import SupportError


def print_json(value):
    print(json.dumps(value, indent=2, ensure_ascii=False))


def configure_groq(config: Config):
    key = getpass("Paste Groq API key (input hidden): ").strip()
    if not key.startswith("gsk_") or len(key) < 20:
        raise SupportError("That does not look like a Groq API key; nothing was saved.")
    request = Request("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"})
    try:
        with urlopen(request, timeout=8) as response:
            if response.status != 200:
                raise SupportError("Groq did not accept the key; nothing was saved.")
    except (HTTPError, URLError, TimeoutError, OSError):
        raise SupportError("Could not verify the key with Groq. Check the key and network; nothing was saved.") from None
    private_write(config.home / "groq.key", key)
    print("Groq key verified and saved privately. It will not be printed or committed.")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="relaydesk", description="Python support agents for a synthetic store; no real payments.")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ["init", "status", "tickets", "approvals", "handoffs", "token", "configure-groq"]:
        commands.add_parser(name)
    chat = commands.add_parser("chat")
    chat.add_argument("--customer", default="maya")
    chat.add_argument("--ticket")
    ask = commands.add_parser("ask")
    ask.add_argument("message")
    ask.add_argument("--customer", default="maya")
    ask.add_argument("--ticket")
    ask.add_argument("--request-key")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("ticket_id")
    for name in ["approve", "reject"]:
        decision = commands.add_parser(name)
        decision.add_argument("approval_id")
        decision.add_argument("--note", default="")
    reply = commands.add_parser("reply")
    reply.add_argument("ticket_id")
    reply.add_argument("message")
    reply.add_argument("--resolve", action="store_true")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8013)
    return root


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    config = Config.from_env()
    try:
        if args.command == "configure-groq":
            configure_groq(config)
            return 0
        if args.command == "serve":
            try:
                import uvicorn
                from .api import create_app
            except ImportError:
                raise SupportError("Install the API extra first: python -m pip install -e '.[api]'") from None
            uvicorn.run(create_app(config), host="127.0.0.1", port=args.port)
            return 0
        service = config.service()
        try:
            service.initialize()
            config.ensure_token()
            if args.command == "init":
                print("RelayDesk initialized. Synthetic store only; no real payments.")
                print("Customers: maya, rohan. Try: python -m relaydesk chat --customer maya")
            elif args.command == "token":
                # This command is intentionally explicit. No other output includes the token.
                print(config.api_token())
            elif args.command in {"status", "tickets", "approvals", "handoffs"}:
                snapshot = service.snapshot()
                if args.command == "status":
                    print_json({"sandbox": True, "provider": "groq configured" if config.api_key() else "rules (no live model)", "usage": snapshot["usage"], "ticket_count": len(snapshot["tickets"]), "pending_approvals": sum(a["status"] == "pending" for a in snapshot["approvals"]), "human_inbox": len(snapshot["handoffs"])})
                else:
                    print_json(snapshot[args.command])
            elif args.command == "inspect":
                print_json(service.ticket_detail(args.ticket_id))
            elif args.command in {"approve", "reject"}:
                print_json(service.decide_refund(args.approval_id, "approved" if args.command == "approve" else "rejected", "local-operator", args.note))
            elif args.command == "reply":
                print_json(service.human_reply(args.ticket_id, args.message, args.resolve))
            elif args.command == "ask":
                ticket = {"id": args.ticket} if args.ticket else service.create_ticket(args.customer)
                print_json(service.send_message(ticket["id"], args.message, args.request_key or str(uuid4())))
            elif args.command == "chat":
                ticket = {"id": args.ticket} if args.ticket else service.create_ticket(args.customer)
                print(f"RelayDesk sandbox | ticket {ticket['id']} | type /quit to leave")
                while True:
                    try:
                        message = input("You: ").strip()
                    except EOFError:
                        break
                    if message in {"/quit", "/exit"}:
                        break
                    if not message:
                        continue
                    result = service.send_message(ticket["id"], message, str(uuid4()))
                    print(f"\nRelayDesk [{result['intent']} / {result['mode']}]: {result['reply']}")
                    print(f"Status: {result['status']} | Model calls: {result['llm_calls']}\n")
        finally:
            service.database.close()
        return 0
    except (SupportError, ValueError) as exc:
        print(f"RelayDesk: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nRelayDesk stopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
