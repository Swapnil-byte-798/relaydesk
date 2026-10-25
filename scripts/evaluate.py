"""Run the 50-case deterministic sandbox regression; never calls a live LLM."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from relaydesk.database import Database
from relaydesk.routing import RuleRouter
from relaydesk.service import SupportService


def evaluate() -> dict:
    scenarios = json.loads((ROOT / "evaluations/scenarios.json").read_text())
    results = []
    fixed_now = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as directory:
        database = Database(f"sqlite:///{directory}/evaluation.db")
        for scenario in scenarios:
            service = SupportService(database, scenario["id"], RuleRouter(), clock=lambda: fixed_now)
            service.initialize()
            ticket = service.create_ticket(scenario.get("customer", "maya"))
            for message in scenario["messages"]:
                result = service.send_message(ticket["id"], message, str(uuid4()))
            snapshot = service.snapshot()
            checks = {"status": result["status"] == scenario["status"], "intent": result["intent"] == scenario["intent"],
                      "no_autonomous_refund": not snapshot["refunds"], "no_model_calls": snapshot["usage"]["llm_calls"] == 0}
            if scenario.get("no_order"):
                checks["customer_isolation"] = result["order"] is None
            if "order_status" in scenario:
                checks["order_status"] = bool(result["order"]) and result["order"]["status"] == scenario["order_status"]
            if "approval_count" in scenario:
                checks["approval_count"] = len(snapshot["approvals"]) == scenario["approval_count"]
            if "source" in scenario:
                checks["source"] = scenario["source"] in [source["id"] for source in (result["sources"] or [])]
            results.append({"id": scenario["id"], "passed": all(checks.values()), "checks": checks,
                            "actual_status": result["status"], "actual_intent": result["intent"]})
        database.close()
    return {"mode": "rules", "dataset": "50 synthetic scripted conversations", "live_llm_evaluated": False,
            "cases": len(results), "passed": sum(result["passed"] for result in results),
            "failed": sum(not result["passed"] for result in results), "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = evaluate()
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Rules-mode regression: {report['passed']}/{report['cases']} passed; {report['failed']} failed; live LLM evaluated: no")
    for result in report["results"]:
        if not result["passed"]:
            print(json.dumps(result))
    raise SystemExit(1 if report["failed"] else 0)
