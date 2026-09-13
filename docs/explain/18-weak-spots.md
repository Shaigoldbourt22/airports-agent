# 18. Weak spots

Know these before someone else points them out.

**We score terminals without terminal data.** The whole tool is about terminal
expansion, and there is no free dataset for gate counts or floor area. Runways
stand in. An airport can be runway-rich and gate-poor, and this scoring will
not see it.

**The weights are a judgement call.** 0.35 / 0.25 / 0.25 / 0.15 is defensible,
not derived. Nothing was fitted to an outcome, because there is no labelled
"this expansion paid off" dataset. Change the weights and the ranking moves.

**No cost side.** The score says where demand and constraint are highest. It
says nothing about what building there would cost, or what FAA grant money is
available. That is half of any real investment decision.

**Small samples.** Ask about New England and you are normalising across six
airports. Min-max on six points is fragile; one outlier redefines the scale.

**Single replica.** SQLite on an SMB share only works because exactly one
process writes. Scale out and it breaks.

**The judge is a model.** The golden gate is non-deterministic. That is why
the deterministic tests exist separately and run first.

**Twelve months of flights.** Enough to see seasonality once. Not enough to
separate a trend from a good year.

**US carriers only.** BTS cannot see foreign airlines at US airports.
