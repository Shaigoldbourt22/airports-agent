"""Grade a free-text answer against a rubric using Gemini.

The golden answers are prose, so an exact-match assertion would fail on
harmless rewording. Instead a second model call checks the answer against the
rubric and returns a structured verdict, which keeps the pass/fail decision
about substance rather than phrasing.

The judge sees no tools and no database. It only judges the text it is given.
"""

import json
import os

from google import genai
from google.genai import types

JUDGE_INSTRUCTION = (
    "You grade answers from an airport investment analysis assistant.\n"
    "Check the answer against each rubric point and be strict: a point is met "
    "only if the answer actually states it, not if it merely implies it.\n"
    "Judge substance, not wording or formatting. Different phrasing, ordering "
    "or extra detail is fine.\n"
    "Do not check numbers for correctness. You have no data; that is verified "
    "separately. Only check that the required claims are present."
)

SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    required=["passed", "failed_points", "reason"],
    properties={
        "passed": types.Schema(type=types.Type.BOOLEAN),
        "failed_points": types.Schema(
            type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)
        ),
        "reason": types.Schema(type=types.Type.STRING),
    },
)


def grade(question: str, answer: str, rubric: str) -> dict:
    """Return {passed, failed_points, reason} for one answer."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = (
        f"Question asked:\n{question}\n\n"
        f"Answer given:\n{answer}\n\n"
        f"Rubric, every point must be met:\n{rubric}"
    )
    response = client.models.generate_content(
        model=os.environ.get("JUDGE_MODEL", "gemini-2.5-flash"),
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=JUDGE_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=SCHEMA,
            temperature=0,
        ),
    )
    return json.loads(response.text)
