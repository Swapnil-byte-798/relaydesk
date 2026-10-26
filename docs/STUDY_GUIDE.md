# Study RelayDesk from the first request to the commit

## Start with the business problem

A basic FAQ bot can explain a refund policy but cannot safely act on an order. RelayDesk gives a support workflow access to narrow tools, keeps policy in Python, and sends decisions with financial consequences to a person.

Imagine a shop with a receptionist, a shipping desk, and a returns desk. The receptionist sends each request to the right desk. The returns desk can prepare paperwork, but only the manager can approve it. That is the relationship between the router, specialists, and human-decision service.

## Follow one conversation

1. The CLI or FastAPI receives a message and request key for an existing ticket.
2. The service locks the workspace transition and checks whether that key already has a saved result.
3. The router identifies the topic and an order number supplied in customer conversation. Groq is optional; its plan is validated.
4. The selected specialist calls customer-scoped tools. The refund tool checks policy and can create an approval request.
5. The service writes the messages, ticket state, run result, and trace in one SQL transaction.
6. A human decision runs separately and rechecks the order before atomically recording the sandbox refund.

Read `service.py`, then `agents.py`, `tools.py`, `policy.py`, and `routing.py`. The HTTP layer in `api.py` does not duplicate business logic. This keeps the same behavior available through a CLI, tests, or a future integration.

## Concepts you should be able to explain

| Concept | In this project | Analogy |
| --- | --- | --- |
| Separation of concerns | HTTP and CLI call the same service. | The front counter changes; the shop's rules do not. |
| Tool authorization | Order queries require both workspace and customer. | Knowing a parcel number does not let you collect someone else's parcel. |
| Human approval | An agent prepares a request but cannot record the refund. | A cashier prepares the slip; a manager authorizes it. |
| Idempotency | A request key maps to one ticket/message hash and stored result. | Pressing a lift button again does not create another lift. |
| Atomic transaction | Approval, ledger, order, messages, and audit commit or roll back together. | A transfer must not debit one side while forgetting the other. |
| Unique constraint | One refund per workspace/order and per approval. | A numbered voucher can be redeemed once. |
| State machine | Open, waiting for approval, human inbox, and resolved are explicit states. | A case moves between labelled trays rather than disappearing into someone's memory. |
| Grounding | Replies use database results and curated articles. | The assistant reads the receipt instead of guessing the purchase. |
| Provider fallback | Invalid or failed model output produces labelled rules mode. | A receptionist uses the printed handbook when a computer is unavailable. |

## Why one model call?

Language interpretation benefits from an LLM. Checking whether a timestamp is within 30 days does not. RelayDesk asks the model for a small routing plan once, validates it, then performs tool execution and policy checks in Python. This reduces call count and prevents a fluent response from becoming authority to move money.

This is bounded specialist orchestration, not an autonomous agent loop. The specialist nodes are explicit Python workers. They are not independent models making an unlimited series of decisions. Be clear about that distinction in interviews.

## SQL and concurrency

Read the schema alongside the queries. Composite keys isolate fixture customer/order identifiers by workspace. Foreign keys prevent orphaned records, and indexes support customer lookups and queue reads. All external values go through SQL parameters.

The local adapter uses SQLite's `BEGIN IMMEDIATE`. The PostgreSQL adapter uses SQLAlchemy and row locks. Short state transitions are serialized within one sandbox workspace so concurrent duplicate requests cannot create separate actions. This is deliberately conservative; it is not a high-throughput design claim.

The model request currently happens inside that transaction and has an eight-second timeout. At production traffic, move interpretation outside the lock window, then use a durable queue or lease plus a transactional commit that revalidates state. Preserve the duplicate and policy tests while changing the execution model.

Two tickets can follow the same approval through a linking table. When the decision arrives, both tickets receive the update. Without that relationship, duplicate requests can leave one ticket permanently waiting even though the refund was decided elsewhere.

## How to discuss the tests

The unit suite checks account isolation, policy boundaries, concurrent retries, duplicate approvals, rollback on audit failure, handoff state, provider-output validation, API authorization, and request validation. PostgreSQL CI runs the core suite against a real database service. The 50-case evaluation checks scripted outcomes over synthetic store records.

Passing 50 cases proves those scenarios stayed correct. It does not prove general LLM accuracy, production reliability, Hindi fluency, or that 100% of customer cases will resolve. The live Groq path needs real-key evaluation before claiming model performance.

## Interview questions

1. Why can the model not execute a refund? Explain the tool boundary and separate human endpoint.
2. Why repeat the policy check at approval time? The order can age out or change between request and review.
3. Why use both an idempotency key and a unique order constraint? One protects request retries; the other protects the underlying business action across different requests.
4. What happens if audit logging fails during approval? The same transaction rolls back the ledger and order update; the test deliberately injects that failure.
5. Why can a fixture customer be selected in the API? This is a token-protected operator simulator. A public customer channel needs its own verified identity.
6. What would you change before real payments? Add a merchant adapter, payment-provider idempotency, independently authenticated reviewer roles, webhook reconciliation, retention rules, and operational monitoring.

## Honest resume wording

Built a Python customer-support workflow with order and refund specialists, customer-scoped SQL tools, human approval, idempotent requests, and atomic sandbox refund records. Exposed the same service through a CLI and FastAPI and checked scripted support scenarios plus SQLite/PostgreSQL integration tests.

Add live-model, cost, latency, and resolution metrics only after measuring them. Do not describe the sandbox ledger as an integration with a real payment processor.
