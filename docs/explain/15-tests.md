# 15. Tests

Testing a language model is awkward: ask it the same thing twice and the
wording changes. So there are two layers, because they fail for different
reasons.

**Layer one: deterministic** (`tests/test_tools.py`). These run against a small
fixture database, need no API key, no network, and finish in a second. They
check the weights sum to 1, the score really equals the weighted components,
rankings come back ordered and bounded 0–100, filters exclude what they claim
to exclude, and unscored airports are reported with reasons. Run on every
push. Fail and nothing deploys.

**Layer two: golden questions** (`tests/golden.yaml`, `tests/test_golden.py`).
The four questions the agent exists to answer, asked over HTTP against a real
running deployment. Each answer gets three checks:

1. Did the model call the tool the answer must rest on?
2. Does every number in the prose appear in that tool's output?
3. Does a second Gemini call, given a rubric, judge the reasoning sound?

Check 2 is the hallucination catcher, and it is the clever one. The judge
model has no database, so it cannot verify figures — instead every number in
the text is matched against the recorded tool trace, in all the shapes a model
might print them (1,234 / 1234 / 1234.0). Years, tiny counts, and constants
already in the system prompt are excluded. Only the *reasoning* is left to the
judge.

Because they run over HTTP, they also prove the deployment is wired correctly.
