"""Optional FastAPI transport. All business rules live in the Python service."""

from contextlib import asynccontextmanager
import secrets
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from .config import Config
from .models import SupportError
from .service import SupportService


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TicketInput(StrictInput):
    customer_id: str = Field(min_length=1, max_length=100)


class MessageInput(StrictInput):
    message: str = Field(min_length=1, max_length=2000)
    request_key: str = Field(min_length=1, max_length=100)


class DecisionInput(StrictInput):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=1000)


class ReplyInput(StrictInput):
    message: str = Field(min_length=1, max_length=2000)
    resolve: bool = False


def create_app(config: Config | None = None, service: SupportService | None = None) -> FastAPI:
    config = config or Config.from_env()
    service = service or config.service()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service.initialize()
        config.ensure_token()
        yield
        service.database.close()

    app = FastAPI(title="RelayDesk", version="0.1.0", lifespan=lifespan,
                  description="Python multi-agent support over a synthetic store. Refunds are sandbox ledger records; no real payments are processed.")
    bearer = HTTPBearer(auto_error=False)

    def operator(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        expected = config.api_token()
        if not expected:
            raise HTTPException(503, "Initialize the local operator token first.")
        if credentials is None or not secrets.compare_digest(credentials.credentials, expected):
            raise HTTPException(401, "A valid operator bearer token is required.", headers={"WWW-Authenticate": "Bearer"})
        return "authenticated-operator"

    @app.exception_handler(SupportError)
    async def support_error(request: Request, exc: SupportError):
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    @app.get("/health", tags=["Operations"])
    def health():
        return {"status": "ok", "sandbox": True}

    @app.get("/store", dependencies=[Depends(operator)], tags=["Support"])
    def store():
        return service.snapshot()

    @app.post("/tickets", dependencies=[Depends(operator)], tags=["Support"], status_code=201)
    def create_ticket(body: TicketInput):
        return service.create_ticket(body.customer_id)

    @app.get("/tickets/{ticket_id}", dependencies=[Depends(operator)], tags=["Support"])
    def ticket(ticket_id: str):
        return service.ticket_detail(ticket_id)

    @app.post("/tickets/{ticket_id}/messages", dependencies=[Depends(operator)], tags=["Support"])
    def message(ticket_id: str, body: MessageInput):
        return service.send_message(ticket_id, body.message, body.request_key)

    @app.post("/approvals/{approval_id}/decision", tags=["Human review"])
    def decide(approval_id: str, body: DecisionInput, reviewer: Annotated[str, Depends(operator)]):
        return service.decide_refund(approval_id, body.decision, reviewer, body.note)

    @app.post("/tickets/{ticket_id}/human-reply", dependencies=[Depends(operator)], tags=["Human review"])
    def reply(ticket_id: str, body: ReplyInput):
        return service.human_reply(ticket_id, body.message, body.resolve)

    return app
