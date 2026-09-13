# 9. The agent loop

`app/agent.py` is the bit that talks to Gemini. It is a loop, and it is
short.

1. Turn the chat history into Gemini's format. Attachments become inline
   base64 blobs alongside the text.
2. Send it, with the system prompt and the eight tool declarations.
3. Look at the reply. Did the model ask for tool calls?
   - **No** → that is the answer. Done.
   - **Yes** → run each tool, append the model's request *and* the results to
     the conversation, and go back to step 2.
4. Stop after 6 rounds.

Automatic function calling is deliberately switched off. Running the loop
ourselves means we can time each call, log it, and record a **trace** — one
entry per tool call with its arguments and result. The tests use that trace to
check every number in the answer actually came from a tool.

Failures are sorted into types the API layer can respond to sensibly:
`ModelUnavailable` (no API key), `RateLimited` (quota), `ContentBlocked`
(safety filter). Anything else bubbles up as an upstream error.

Two edge cases get special handling. If the loop hits 6 rounds it gives up
politely and suggests asking a narrower question. If Gemini returns an empty
body — usually a safety block or an exhausted token budget, which arrives as a
normal response, not an exception — that is logged and reported, not silently
shown as blank.
