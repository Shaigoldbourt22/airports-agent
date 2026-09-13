# 7. The scoring formula

`rank_expansion_candidates` decides which airport most deserves a new
terminal. Four components, fixed weights, adding to 1:

| Component | Weight | Meaning |
|---|---|---|
| `load` | 0.35 | How hard the existing runways are already worked |
| `growth` | 0.25 | Are passenger numbers rising? |
| `catchment` | 0.25 | Is the metro area itself growing? |
| `spacing` | 0.15 | Does runway geometry cap arrivals in bad weather? |

**Why `load` is one number, not two.** It used to be two: passengers per
runway and peak departures per runway. But those correlate at r=0.92 — they
measure the same thing. Scoring both put half the weight on one signal while
pretending it was two. Now they are averaged into a single component.

**Why `catchment` earns its place.** It is the only component that does *not*
move with the others (r between −0.65 and +0.20). Passenger growth can be one
airline adding a seasonal route. Metro growth is whether people will still be
there in 2050. Population *level* is deliberately excluded: it tracks
passengers-per-runway at r=0.99, so it would add weight without information.

Three components are min-max normalised to 0–100 **inside the set you asked
about**. Ask about New England and the winner beats New England, not America.

Airports under 250,000 passengers are dropped — the percentages are noise.
Anything missing an input is listed separately with the reason, never silently
hidden.
