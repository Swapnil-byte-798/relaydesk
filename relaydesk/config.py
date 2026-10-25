"""Local secrets use private files or process environment, never source code."""

from dataclasses import dataclass
import os
from pathlib import Path
import secrets

from .database import Database
from .routing import GroqRouter, RuleRouter
from .service import SupportService


def private_write(path: Path, value: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            descriptor = -1
            stream.write(value.strip() + "\n")
    finally:
        if descriptor >= 0:
            os.close(descriptor)


@dataclass(frozen=True)
class Config:
    home: Path
    database_url: str
    workspace: str = "local-store"
    model: str = "llama-3.3-70b-versatile"

    @classmethod
    def from_env(cls) -> "Config":
        home = Path(os.environ.get("RELAYDESK_HOME", ".relaydesk"))
        return cls(home, os.environ.get("RELAYDESK_DATABASE_URL", f"sqlite:///{home / 'relaydesk.db'}"),
                   os.environ.get("RELAYDESK_WORKSPACE", "local-store"),
                   os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"))

    def _read_secret(self, name: str) -> str:
        path = self.home / name
        return path.read_text().strip() if path.is_file() else ""

    def api_key(self) -> str:
        return os.environ.get("GROQ_API_KEY", "").strip() or self._read_secret("groq.key")

    def api_token(self) -> str:
        return os.environ.get("RELAYDESK_API_TOKEN", "").strip() or self._read_secret("operator.token")

    def ensure_token(self) -> None:
        if not self.api_token():
            private_write(self.home / "operator.token", secrets.token_urlsafe(32))

    def service(self) -> SupportService:
        key = self.api_key()
        router = GroqRouter(key, self.model) if key else RuleRouter()
        return SupportService(Database(self.database_url), self.workspace, router)
