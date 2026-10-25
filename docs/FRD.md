# Functional contracts

| Function | Contract |
| --- | --- |
| Initialize | Create schema and seed known store fixtures exactly once per workspace. |
| Create ticket | Require a known customer in the configured workspace. |
| Send message | Require a known ticket, bounded text, and a request key; persist the resulting conversation and trace atomically. |
| Read order | Match workspace and ticket customer; use an order number explicitly mentioned in customer history. |
| Request refund | Check policy, create one request per workspace/order, and report its state. |
| Human decision | Recheck eligibility and atomically update approval, ledger, order, and audit records. |
| Handoff | Store the reason and latest conversation context; stop automated resolution while awaiting the person. |
| Human reply | Append an operator message and optionally close the handoff. |
| Provider setup | Accept a hidden local key prompt or environment variable; never include keys in logs, traces, source, or responses. |

Validation errors return 400, missing authentication 401, unknown scoped records 404, and state/idempotency conflicts 409 in the optional API. Provider timeouts or invalid outputs fall back to explicitly reported rules mode.
