import io
import json
from urllib.error import URLError
import unittest

from relaydesk.routing import GroqRouter, validate_plan


class ProviderTests(unittest.TestCase):
    def plan(self, **changes):
        return {"intent": "order", "order_id": "RD-1042", "sentiment": "neutral", "reason": "Check order", "query": "Where is RD-1042?", **changes}

    def test_live_provider_contract_uses_one_validated_request(self):
        requests = []
        def transport(request, timeout):
            requests.append(request)
            payload = {"choices": [{"message": {"content": json.dumps(self.plan())}}], "usage": {"prompt_tokens": 120, "completion_tokens": 35}}
            return io.BytesIO(json.dumps(payload).encode())
        result = GroqRouter("test-key-not-a-real-credential", transport=transport).route("Where is RD-1042?", [])
        self.assertEqual(result.mode, "groq")
        self.assertEqual(len(requests), 1)
        self.assertEqual(result.input_tokens, 120)
        self.assertEqual(result.output_tokens, 35)
        self.assertEqual(json.loads(requests[0].data)["response_format"], {"type": "json_object"})

    def test_provider_failure_falls_back_without_leaking_error(self):
        def transport(*args, **kwargs):
            raise URLError("sensitive provider details")
        result = GroqRouter("test-key-not-a-real-credential", transport=transport).route("Where is RD-1042?", [])
        self.assertEqual(result.mode, "fallback")
        self.assertEqual(result.llm_calls, 1)
        self.assertNotIn("sensitive", repr(result))

    def test_invented_order_number_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_plan(self.plan(order_id="RD-2042"), "Where is RD-1042?", [])

    def test_arbitrary_tool_field_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_plan(self.plan(tool="execute_refund"), "Where is RD-1042?", [])

    def test_malformed_provider_output_falls_back(self):
        result = GroqRouter("test-key-not-a-real-credential", transport=lambda *a, **k: io.BytesIO(b'{"choices": []}')).route("Please refund RD-1043", [])
        self.assertEqual(result.mode, "fallback")
        self.assertEqual(result.plan.intent, "refund")

    def test_human_request_does_not_spend_a_model_call(self):
        def forbidden(*args, **kwargs):
            self.fail("Human request should not call provider")
        result = GroqRouter("test-key-not-a-real-credential", transport=forbidden).route("I need a human", [])
        self.assertEqual(result.llm_calls, 0)
        self.assertEqual(result.plan.intent, "complaint")


if __name__ == "__main__":
    unittest.main()
