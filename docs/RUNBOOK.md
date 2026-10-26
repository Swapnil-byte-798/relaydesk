# Run RelayDesk

## Local Python

From the repository root:

```bash
python -m relaydesk init
python -m relaydesk chat --customer maya
```

This uses only the standard library and creates a local synthetic store. Start with `Where is my order RD-1042?`, then try `Please refund RD-1043`. The answer includes the agent, execution mode, and whether human review is required. Type `/quit` to leave the chat.

Use a second terminal for operator actions:

```bash
python -m relaydesk approvals
python -m relaydesk approve APPROVAL_ID --note "Reviewed the sandbox order"
python -m relaydesk handoffs
python -m relaydesk inspect TICKET_ID
python -m relaydesk reply TICKET_ID "I have reviewed your case." --resolve
```

Substitute the IDs printed by the listing commands. An approval records a sandbox ledger entry. It does not contact a bank or payment processor. A repeated identical approval returns the saved decision; a conflicting final decision is refused.

## Optional FastAPI service

```bash
python -m pip install -e '.[api,dev]'
python -m relaydesk serve
```

The service listens on `127.0.0.1:8013`. Open `/docs` on that origin for generated Swagger documentation. Run `python -m relaydesk token` only when you need to copy the operator token into Authorize. The token is never included in normal logs or support results. The operator can simulate either fixture customer; this is not a publicly authenticated customer chat endpoint.

Swagger flow: create a ticket with customer `maya`, send a message to that ticket with a new request key, inspect its approval ID, then call the human-decision endpoint. Reuse the same request key only to retry the same ticket and message. A retry returns the original response snapshot; fetch the ticket for its current approval state.

## Groq

```bash
python -m relaydesk configure-groq
```

The hidden-input prompt verifies the key against Groq's models endpoint and saves it under the ignored application data directory. On POSIX systems, the secret file uses mode 0600. Alternatively set `GROQ_API_KEY` in the environment. Keys remain local to the process or host; they are never part of the repository.

When configured, normal turns can make one live interpretation request. Explicit human requests and obvious unsafe instructions skip the provider. If the provider times out or returns an invalid plan, the response reports `fallback`. Without a key, the response reports `rules`, with zero model calls. Live-provider correctness must be evaluated separately from the included offline suite.

## PostgreSQL and Docker

For a locally managed PostgreSQL database, install `.[postgres]` and set `RELAYDESK_DATABASE_URL` to a `postgresql+psycopg://` URL. Credentials containing reserved URL characters must be URL-encoded. Local CLI-only use can remain on SQLite.

For Docker Compose, create an ignored `.env` containing a random hex `POSTGRES_PASSWORD`. A hex password avoids URL-encoding issues. Docker Compose reads `.env`; the Python CLI itself does not automatically load it.

```bash
docker compose up --build -d
docker compose exec app python -m relaydesk token
docker compose exec app python -m relaydesk configure-groq
```

Open `http://127.0.0.1:8013/docs`. Database and local secret files live in named volumes. Stop the services with `docker compose down`; keep the volumes to preserve your data. The API is bound to the host's loopback interface by default.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Rules mode | No Groq key is configured for this process or application data directory. |
| Fallback mode | Verify the provider key, configured model, network access, and provider rate limits. Raw provider errors are intentionally not returned. |
| 401 from API | Copy the current operator token from the same environment running the service. |
| Request-key conflict | Retry with the exact original payload, or use a new key for a new message. |
| Refund decision rejected | Recheck delivery age, order status, full-order amount, and an existing final decision. |
| Cannot import FastAPI | Install `.[api]`; the CLI still works without that extra. |
| PostgreSQL driver missing | Install `.[postgres]` in the environment that runs the application. |

Run tests with `python -m unittest discover -s tests -v` or `python -m pytest -q`. Run the 50 scripted cases with `python scripts/evaluate.py`. Tests containing a fake provider transport verify the HTTP contract without spending model calls.
