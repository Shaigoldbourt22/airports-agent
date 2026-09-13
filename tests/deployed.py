"""Ask the deployed agent a question over HTTP.

The golden tests run against a real deployment rather than an in-process
import, so they exercise the whole path: ingress, request validation, the
container's own database mount and its copy of the prompt. A prompt file left
out of the image, or an ETL column missing from the mounted database, fails
here and cannot fail in-process.

Set AGENT_URL to the deployment to test.
"""

import json
import os
import urllib.error
import urllib.request


class NotDeployed(RuntimeError):
    """AGENT_URL is unset, so there is nothing to test against."""


def base_url() -> str:
    url = os.environ.get("AGENT_URL")
    if not url:
        raise NotDeployed("AGENT_URL is not set")
    return url.rstrip("/")


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("AGENT_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def ask(question: str, timeout: int = 120) -> tuple[str, list]:
    """Return the reply and the tool trace for one question."""
    payload = json.dumps({"messages": [{"role": "user", "content": question}]})
    request = urllib.request.Request(
        f"{base_url()}/api/chat", data=payload.encode(), headers=_headers()
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise AssertionError(f"{exc.code} from {base_url()}: {detail}") from exc

    trace = body.get("trace")
    if trace is None:
        raise AssertionError(
            "The deployment did not return a tool trace. Set EXPOSE_TRACE=1 on "
            "the app under test so the figures in its answers can be checked."
        )
    return body["reply"], trace


def healthy(timeout: int = 15) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url()}/healthz", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False
