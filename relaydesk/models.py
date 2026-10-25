from dataclasses import asdict, dataclass
from typing import Literal

Intent = Literal["order", "refund", "technical", "complaint", "unknown"]


class SupportError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Plan:
    intent: Intent
    order_id: str | None
    sentiment: str = "neutral"
    reason: str = ""
    query: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RoutingResult:
    plan: Plan
    mode: str = "rules"
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Outcome:
    reply: str
    status: str
    intent: str
    failed_attempts: int = 0
    order: dict | None = None
    approval: dict | None = None
    sources: list[dict] | None = None

    def to_dict(self) -> dict:
        return asdict(self)
