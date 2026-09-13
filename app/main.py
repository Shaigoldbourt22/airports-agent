import base64
import binascii
import json
import logging
import os
import secrets
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from app import agent, sessions, telemetry

load_dotenv()
telemetry.configure()

STATIC_DIR = Path(__file__).parent.parent / "static"

app = FastAPI(title="Airport Investment Intelligence Agent")


ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "application/pdf",
    "text/plain",
    "text/csv",
}

MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024

# Comma-separated Google addresses permitted to use the agent.
# Empty means no allowlist, so anyone the auth proxy lets through may sign in.
ALLOWED_USERS = {
    email.strip().lower()
    for email in os.getenv("ALLOWED_USERS", "").split(",")
    if email.strip()
}


class Attachment(BaseModel):
    name: str = Field(max_length=200)
    mime_type: str
    data: str = Field(description="base64-encoded file contents")

    @field_validator("mime_type")
    @classmethod
    def check_mime_type(cls, value: str) -> str:
        if value not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported file type: {value}")
        return value

    @field_validator("data")
    @classmethod
    def check_size(cls, value: str) -> str:
        try:
            raw = base64.b64decode(value, validate=True)
        except binascii.Error as exc:
            raise ValueError("Attachment is not valid base64") from exc
        if len(raw) > MAX_ATTACHMENT_BYTES:
            raise ValueError("Attachment exceeds 8 MB limit")
        return value


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=40000)
    attachments: list[Attachment] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def check_user_length(self) -> "Message":
        # Replayed assistant turns carry whole tables, so only the typed
        # question is held to the short limit.
        if self.role == "user" and len(self.content) > 4000:
            raise ValueError("Question exceeds 4000 characters")
        return self


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=40)
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    # Present only where EXPOSE_TRACE is set, which the evaluation deployment
    # does so tests can check that every figure came from a tool. Production
    # leaves it unset: the trace exposes query internals to end users.
    trace: list[dict] | None = None


EXPOSE_TRACE = os.environ.get("EXPOSE_TRACE") == "1"
EVAL_TOKEN = os.environ.get("EVAL_TOKEN", "")


class SessionSummary(BaseModel):
    id: str
    title: str
    updated: str


class StoredMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    file_names: list[str] = Field(default_factory=list)


def current_user(request: Request) -> str:
    """Identity from the Container Apps auth proxy, or 'local' when running locally."""
    principal = request.headers.get("x-ms-client-principal")
    if principal:
        try:
            claims = json.loads(base64.b64decode(principal))["claims"]
            for claim in claims:
                if claim["typ"].endswith("emailaddress") or claim["typ"] == "email":
                    return claim["val"]
        except (ValueError, KeyError, binascii.Error):
            pass
    return request.headers.get("x-ms-client-principal-name") or "local"


def authorised_user(request: Request) -> str:
    """Identify the caller and refuse anyone outside the allowlist.

    A deployment with EVAL_TOKEN set has no sign-in in front of it, so the
    token is the only thing standing between it and the open internet. It
    replaces the allowlist rather than adding to it, because automated runs
    have no Google identity to present. Production leaves EVAL_TOKEN unset.
    """
    if EVAL_TOKEN:
        header = request.headers.get("authorization", "")
        offered = header.removeprefix("Bearer ").strip()
        if not secrets.compare_digest(offered, EVAL_TOKEN):
            telemetry.event("eval_token_rejected", level=logging.WARNING, status=401)
            raise HTTPException(status_code=401, detail="Invalid evaluation token")
        return "evaluation"

    user = current_user(request)
    if ALLOWED_USERS and user.lower() not in ALLOWED_USERS:
        telemetry.event("access_denied", level=logging.WARNING, user=user, status=403)
        raise HTTPException(status_code=403, detail="This account is not authorised")
    return user


@app.get("/api/sessions", response_model=list[SessionSummary])
def get_sessions(request: Request) -> list[dict]:
    return sessions.list_sessions(authorised_user(request))


@app.get("/api/sessions/{session_id}", response_model=list[StoredMessage])
def get_session(session_id: str, request: Request) -> list[dict]:
    return sessions.get_messages(authorised_user(request), session_id)


@app.delete("/api/sessions/{session_id}", status_code=204)
def remove_session(session_id: str, request: Request) -> None:
    sessions.delete_session(authorised_user(request), session_id)


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    user = authorised_user(http_request)
    session_id = request.session_id
    trace: list | None = [] if EXPOSE_TRACE else None
    try:
        text = agent.reply([m.model_dump() for m in request.messages], trace=trace)
    except agent.ModelUnavailable as exc:
        telemetry.event("chat_failed", level=logging.ERROR, reason="not_configured",
                        session_id=session_id, status=503)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except agent.RateLimited as exc:
        telemetry.event("chat_failed", level=logging.WARNING, reason="rate_limited",
                        session_id=session_id, status=429)
        raise HTTPException(
            status_code=429, detail="Model quota exhausted, try again shortly"
        ) from exc
    except agent.ContentBlocked as exc:
        telemetry.event("chat_failed", level=logging.WARNING, reason="content_blocked",
                        session_id=session_id, status=422)
        raise HTTPException(
            status_code=422, detail="The request was blocked by content filters"
        ) from exc
    except Exception as exc:  # upstream model or network failure
        telemetry.event("chat_failed", level=logging.ERROR, reason="upstream_error",
                        error_type=type(exc).__name__, error=str(exc)[:300],
                        session_id=session_id, status=502)
        raise HTTPException(status_code=502, detail="Model request failed") from exc

    last = request.messages[-1]
    session_id = request.session_id or sessions.create_session(user, last.content)
    sessions.add_messages(
        user,
        session_id,
        [
            {
                "role": "user",
                "content": last.content,
                "file_names": [a.name for a in last.attachments],
            },
            {"role": "assistant", "content": text},
        ],
    )
    telemetry.event("chat_ok", session_id=session_id, turns=len(request.messages),
                    reply_chars=len(text))
    return ChatResponse(reply=text, session_id=session_id, trace=trace)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
