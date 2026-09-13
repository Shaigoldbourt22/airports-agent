"""The four golden questions, end to end.

Each case is checked three ways:
  1. the model called the tool the answer must be grounded in,
  2. every figure in the answer appears in that tool's output,
  3. a second Gemini call grades the answer against a rubric.

Check 2 is the one that catches hallucination. The judge cannot verify numbers
because it has no database, so the numbers are matched against the recorded
tool results directly and only the reasoning is left to the judge.

Each question is asked once per module and the three checks share the result,
which keeps the suite to one API call per case plus one judge call.

These call the API, so they are marked llm and excluded from the default run.
"""

import re

import pytest

from app import agent
from tests.conftest import GOLDEN
from tests.judge import grade

pytestmark = [
    pytest.mark.llm,
    pytest.mark.usefixtures("require_db", "require_model"),
]

CASES = [pytest.param(case, id=case["id"]) for case in GOLDEN]

# Values a model may legitimately state without a tool: the long-haul threshold,
# years, months, small counts used in prose ("4 runways", "top 5"), and the
# regulatory constants written into the system prompt.
IGNORE = re.compile(r"^(19|20)\d\d$|^\d{1,2}$")
FROM_PROMPT = set(re.findall(r"\d[\d,]*\.?\d*", agent.SYSTEM_INSTRUCTION))


def _clean(number: str) -> str:
    return number.strip(" .,")


def _numbers(text: str) -> set[str]:
    """Numbers a reader would take as factual claims."""
    found = (_clean(n) for n in re.findall(r"\d[\d,]*\.?\d*", text))
    return {n for n in found if n and not IGNORE.match(n)} - FROM_PROMPT


def _tool_numbers(payload) -> set[str]:
    """Every number a tool returned, in the shapes a model might print them."""
    out: set[str] = set()

    def add(number: float) -> None:
        """Record one value in the forms an answer might use.

        Signs are dropped because a model writes a fall as "down 3.4%" as often
        as "-3.4%", and the sign is prose, not a separate claim.
        """
        number = abs(number)
        out.add(str(number))
        if float(number).is_integer():
            whole = int(number)
            out.update({str(whole), f"{whole:,}"})
        for places in (1, 2, 3, 4):
            out.add(str(round(number, places)))
            out.add(f"{round(number, places):,}")

    def walk(value):
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, bool) or value is None:
            return
        elif isinstance(value, (int, float)):
            add(value)
            # Ratios are usually printed as percentages.
            add(value * 100)
            # Large counts may be abbreviated: 1,125,651,105 -> 1.13B
            for size in (1e9, 1e6, 1e3):
                if abs(value) >= size:
                    add(value / size)
        elif isinstance(value, str):
            out.update(re.findall(r"\d[\d,]*\.?\d*", value))

    walk(payload)
    return {_clean(n) for n in out}


@pytest.fixture(scope="module")
def answers():
    """Ask each golden question once and reuse the result across the checks."""
    out = {}
    for case in GOLDEN:
        trace: list = []
        text = agent.reply(
            [{"role": "user", "content": case["question"]}], trace=trace
        )
        out[case["id"]] = (text, trace)
    return out


@pytest.mark.parametrize("case", CASES)
def test_calls_the_required_tools(case, answers):
    _, trace = answers[case["id"]]
    used = [step["tool"] for step in trace]
    missing = set(case["must_call"]) - set(used)
    assert not missing, f"expected {case['must_call']}, model called {used or 'nothing'}"


@pytest.mark.parametrize("case", CASES)
def test_every_figure_comes_from_a_tool(case, answers):
    answer, trace = answers[case["id"]]
    grounded: set[str] = set()
    for step in trace:
        grounded |= _tool_numbers(step["result"])
    invented = _numbers(answer) - grounded
    assert not invented, f"figures not found in any tool result: {sorted(invented)}"


@pytest.mark.parametrize("case", CASES)
def test_reasoning_meets_the_rubric(case, answers):
    answer, _ = answers[case["id"]]
    verdict = grade(case["question"], answer, case["rubric"])
    assert verdict["passed"], (
        f"{verdict['reason']}\nmissed: {verdict['failed_points']}\n\n{answer}"
    )
