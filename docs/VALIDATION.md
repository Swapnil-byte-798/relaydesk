# Validation scope

The repository checks three different layers:

| Layer | What is checked |
| --- | --- |
| Python service | Customer isolation, refund policy, pending approval, transaction rollback, duplicate requests, concurrent decisions, handoff state, and durable results. |
| FastAPI | Operator authentication, request validation, generated API schema, and a complete refund-request/human-decision round trip. |
| PostgreSQL | The core service suite against a real PostgreSQL service in GitHub Actions. |
| Docker | Container build and HTTP health check in GitHub Actions. |
| Scripted conversations | Fifty synthetic support conversations checked against explicit status, intent, source, approval, and isolation expectations. |
| Groq contract | Simulated HTTP transport verifies request formatting, response validation, timeout/failure handling, and the one-request budget without a real key. |

`evaluations/report.json` contains the deterministic rules-mode evaluation results. Its recorded result is 50/50 scripted cases. That is a regression result over these fixtures, not a general support-resolution rate or live-model accuracy score.

The standard-library suite can run in a minimal environment. FastAPI tests are explicitly skipped when the optional FastAPI/HTTPX dependencies are absent; the GitHub Python jobs install those dependencies and run the full suite. The PostgreSQL job sets its own test database URL. No production database is used.

Live Groq evaluation remains separate and has not been claimed as completed without a user-supplied key. Store fixtures are synthetic. No real refund, merchant integration, load test, third-party customer identity flow, or production service-level objective has been validated.
