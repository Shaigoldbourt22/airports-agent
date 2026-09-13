# 1. The big picture

Imagine you work at a firm that buys and upgrades airports. You want to know
which US airport is most worth spending money on. That takes digging through
government spreadsheets for hours.

This project is a chat box that answers that question in seconds.

You type a question. A language model (Gemini) reads it, picks the right
lookup function, gets real numbers back from a database, and writes an answer
in plain English.

The important rule: **the model never does maths and never remembers numbers.**
It only decides what to look up and how to explain it. Every figure comes from
SQL. If you ask the same question twice, the numbers are identical.

The flow:

```
You type a question
  -> the browser sends it to FastAPI
  -> FastAPI hands it to the agent
  -> the agent asks Gemini
  -> Gemini says "call rank_expansion_candidates for New England"
  -> the tool runs SQL against airports.db
  -> the numbers go back to Gemini
  -> Gemini writes the answer
  -> you read it
```

The database is not built live. A scheduled job rebuilds it monthly from
public sources, so answers are fast and a government website going down
cannot break the demo.
