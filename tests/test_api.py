import importlib.util
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from relaydesk.config import Config, private_write
from relaydesk.database import Database
from relaydesk.service import SupportService

API_AVAILABLE = importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None


@unittest.skipUnless(API_AVAILABLE, "Install .[api,dev] for the FastAPI integration tests")
class ApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from relaydesk.api import create_app
        self.directory = tempfile.TemporaryDirectory()
        home = Path(self.directory.name)
        private_write(home / "operator.token", "test-operator-token")
        self.config = Config(home, f"sqlite:///{home / 'store.db'}")
        self.service = SupportService(Database(self.config.database_url))
        self.client = TestClient(create_app(self.config, self.service))
        self.client.__enter__()
        self.auth = {"Authorization": "Bearer test-operator-token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.directory.cleanup()

    def test_order_endpoints_require_operator(self):
        self.assertEqual(self.client.get("/store").status_code, 401)
        self.assertEqual(self.client.get("/store", headers={"Authorization": "Bearer wrong"}).status_code, 401)
        self.assertEqual(self.client.get("/store", headers=self.auth).status_code, 200)

    def test_message_and_human_decision_round_trip(self):
        ticket = self.client.post("/tickets", json={"customer_id": "maya"}, headers=self.auth).json()
        result = self.client.post(f"/tickets/{ticket['id']}/messages", json={"message": "Please refund RD-1043", "request_key": str(uuid4())}, headers=self.auth)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["status"], "waiting_approval")
        approval_id = result.json()["approval"]["id"]
        body = {"decision": "approved", "note": "Reviewed sandbox order"}
        self.assertEqual(self.client.post(f"/approvals/{approval_id}/decision", json=body).status_code, 401)
        approved = self.client.post(f"/approvals/{approval_id}/decision", json=body, headers=self.auth)
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["decided_by"], "authenticated-operator")

    def test_client_cannot_supply_another_workspace_or_reviewer(self):
        result = self.client.post("/tickets", json={"customer_id": "maya", "workspace": "someone-else"}, headers=self.auth)
        self.assertEqual(result.status_code, 422)
        result = self.client.post("/approvals/anything/decision", json={"decision": "approved", "actor": "admin"}, headers=self.auth)
        self.assertEqual(result.status_code, 422)

    def test_docs_are_generated_from_python_models(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/tickets/{ticket_id}/messages", schema["paths"])
        self.assertIn("HTTPBearer", schema["components"]["securitySchemes"])

    def test_validation_and_not_found(self):
        result = self.client.post("/tickets", json={"customer_id": "not-a-customer"}, headers=self.auth)
        self.assertEqual(result.status_code, 404)
        result = self.client.post("/tickets/missing/messages", json={"message": "", "request_key": "key"}, headers=self.auth)
        self.assertEqual(result.status_code, 422)


if __name__ == "__main__":
    unittest.main()
