# Product requirements

RelayDesk gives a support operator a reliable way to answer routine questions and control actions that affect an order. The first release simulates the customer side of an online store in a private operator session. It does not claim to be a production merchant integration.

## Acceptance criteria

1. A customer can ask about an order using its number; only orders in that customer account can be returned.
2. The refund specialist checks delivered status, a 30-day window, and the full order amount before creating a request.
3. A separate human action approves or rejects the request. Approval and ledger updates are atomic and duplicate-safe.
4. An explicit human request, serious complaint, unsafe instruction, or two unsuccessful attempts creates a handoff with the transcript.
5. Technical answers cite curated knowledge articles instead of making up store policy.
6. A request key is bound to its ticket and message. A retry returns the saved result; a changed payload fails.
7. A 50-conversation evaluation has explicit expected outcomes and reports actual pass/fail results.
8. The application uses Python and SQL, a Python CLI, and optional generated FastAPI documentation. It requires no custom frontend code.

## Boundaries

Store records are synthetic sandbox fixtures. Refunds are internal ledger entries, not payments. A public customer channel, payment-provider integration, independently authenticated reviewer roles, long-running queues, automatic crash recovery, and multilingual reply generation are future work.

## Measures

Report policy violations, cross-customer disclosures, duplicate refunds, evaluation pass rate, model calls per turn, and handoff reasons. Keep rules-mode results separate from live-provider evaluations. Do not publish unmeasured resolution, latency, or cost claims.
