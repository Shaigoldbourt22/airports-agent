"""Gemini wrapper for the chat interface.

The model answers by calling the deterministic tools in app.tools; it turns the
results into prose but never produces a figure of its own.
"""

import base64
import logging
import os
from pathlib import Path

from google import genai
from google.genai import types

from app import telemetry, tools


class ModelUnavailable(RuntimeError):
    """Configuration is missing, so no request can be made."""


class RateLimited(RuntimeError):
    """Provider quota exhausted. Retryable."""


class ContentBlocked(RuntimeError):
    """The prompt or the response was refused by the safety filters."""


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system.md"
SYSTEM_INSTRUCTION = PROMPT_PATH.read_text(encoding="utf-8")

MAX_TOOL_TURNS = 6

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ModelUnavailable("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=api_key)
    return _client


def _to_contents(messages: list[dict]) -> list[types.Content]:
    contents = []
    for message in messages:
        parts = [types.Part(text=message["content"])]
        for attachment in message.get("attachments") or []:
            parts.append(
                types.Part(
                    inline_data=types.Blob(
                        mime_type=attachment["mime_type"],
                        data=base64.b64decode(attachment["data"]),
                    )
                )
            )
        contents.append(
            types.Content(
                role="model" if message["role"] == "assistant" else "user",
                parts=parts,
            )
        )
    return contents


def _classify(exc: Exception) -> Exception:
    """Map provider errors onto types the API layer can respond to sensibly."""
    text = f"{type(exc).__name__}: {exc}".lower()
    if "resource_exhausted" in text or "429" in text or "quota" in text:
        return RateLimited(str(exc))
    if "safety" in text or "blocked" in text or "prohibited" in text:
        return ContentBlocked(str(exc))
    return exc


def _call_tool(call: types.FunctionCall, record: list | None = None) -> types.Part:
    """Run one tool and wrap its result for the model. Errors go back as data."""
    args = dict(call.args or {})
    with telemetry.timed("tool_call", tool=call.name, args=sorted(args)):
        function = tools.REGISTRY.get(call.name)
        if function is None:
            result = {"error": f"Unknown tool {call.name}"}
        else:
            try:
                result = function(**args)
            except Exception as exc:
                result = {"error": f"{type(exc).__name__}: {exc}"}
    if record is not None:
        record.append({"tool": call.name, "args": args, "result": result})
    return types.Part.from_function_response(name=call.name, response={"result": result})


def _generate(model: str, contents: list[types.Content]):
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[types.Tool(function_declarations=[
            types.FunctionDeclaration.from_callable(client=_get_client(), callable=f)
            for f in tools.REGISTRY.values()
        ])],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    try:
        return _get_client().models.generate_content(
            model=model, contents=contents, config=config
        )
    except Exception as exc:
        raise _classify(exc) from exc


def reply(messages: list[dict], trace: list | None = None) -> str:
    """Return the assistant's reply, running any tools the model asks for.

    Pass trace to collect one {tool, args, result} entry per tool call, in
    order. The evaluation suite uses it to check that every figure in the
    answer came from a tool.
    """
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    attachments = sum(len(m.get("attachments") or []) for m in messages)
    contents = _to_contents(messages)

    with telemetry.timed("model_call", model=model, turns=len(messages),
                         attachments=attachments or None):
        for _ in range(MAX_TOOL_TURNS):
            response = _generate(model, contents)
            calls = response.function_calls
            if not calls:
                break
            contents.append(response.candidates[0].content)
            contents.append(types.Content(
                role="user", parts=[_call_tool(c, trace) for c in calls]
            ))
        else:
            telemetry.event("tool_loop_exhausted", level=logging.WARNING, model=model)
            return (
                "I could not finish this one: the lookups kept branching. "
                "Try asking about one airport or one comparison at a time."
            )

    text = response.text
    if not text:
        # An empty body is usually a safety block or an exhausted token budget,
        # and it arrives as a normal response rather than an exception.
        feedback = getattr(response, "prompt_feedback", None)
        reason = getattr(feedback, "block_reason", None)
        finish = None
        if getattr(response, "candidates", None):
            finish = getattr(response.candidates[0], "finish_reason", None)
        telemetry.event(
            "empty_response",
            level=logging.WARNING,
            model=model,
            block_reason=str(reason) if reason else None,
            finish_reason=str(finish) if finish else None,
        )
        if reason:
            raise ContentBlocked(f"Response blocked: {reason}")
        return "(no response)"
    return text
