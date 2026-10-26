# RelayDesk

Python support agents that can check an order, prepare a refund for human review, and hand a difficult case to a person with its conversation attached.

The first version runs against a clearly labelled store sandbox. Its tools read and write a real SQL database; refund approval records an internal sandbox ledger entry and never transfers money. No custom frontend is required.

## What it demonstrates

- A bounded router and separate order, refund, and technical-support specialists in readable Python.
- Customer-scoped order access, policy checks, a human approval gate, and transactional duplicate protection.
- Durable conversations, run traces, handoff summaries, and an explicit regression evaluation.
- Optional Groq interpretation with one model request per turn. Rules mode is clearly reported when no key is configured.
- A Python CLI plus an optional FastAPI service with automatically generated API documentation.

## Quick start

Python 3.11 or newer is required. The CLI and core tests use the standard library.

```bash
git clone https://github.com/Swapnil-byte-798/relaydesk.git
cd relaydesk
python -m relaydesk init
python -m relaydesk chat --customer maya
```

Try `Where is my order RD-1042?` or `Please refund RD-1043`. Use `python -m relaydesk approvals` to review requests and `python -m relaydesk approve APPROVAL_ID` to record a human decision in the sandbox.

For the optional REST API:

```bash
python -m pip install -e '.[api,dev]'
python -m relaydesk serve
```

Open `http://127.0.0.1:8013/docs`. All support endpoints require the local operator token. `python -m relaydesk token` displays it when you explicitly need to copy it into Swagger's Authorize dialog. Never paste it into a public ticket or commit it.

## Connect live language interpretation

Run `python -m relaydesk configure-groq`. The prompt hides your input and saves the key in a private, ignored local file. Alternatively set `GROQ_API_KEY` in the process environment. A configured provider is subject to its own limits and charges. The code does not fabricate a live-model result when no key is present.

## Verify

```bash
python -m unittest discover -s tests -v
python scripts/evaluate.py
```

The evaluation reports scripted sandbox outcomes in rules mode; it is not a measure of general language-model quality. The optional API and PostgreSQL adapter are also checked in GitHub Actions when their dependencies are available.

See [requirements](docs/PRD.md), [architecture](docs/ARCHITECTURE.md), [functional contracts](docs/FRD.md), [run instructions](docs/RUNBOOK.md), and [study notes](docs/STUDY_GUIDE.md). The stack follows the owner's resume: Python, SQL, PostgreSQL/SQLAlchemy, FastAPI, unit testing, Docker, GitHub, and LLM APIs. [AGENTS.md](AGENTS.md) records that project constraint.
