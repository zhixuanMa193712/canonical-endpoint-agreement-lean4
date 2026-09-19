# Exp59 disjoint four-policy confirmation execution

The confirmation set was frozen after the 32-root pilot and before any
confirmation continuation probe. It contains 64 roots, balanced as 32 miniF2F
and 32 PutnamBench roots, and is disjoint from the pilot. The selection design,
selected-root ledger, and complete selection audit are protected by their
reported SHA-256 values.

All four policies, the 21-candidate panel, eight-probe panel, candidate order,
time budget, fresh-process requirement, and stopping rule are carried forward
unchanged. The primary efficiency test requires the one-sided 95% lower bound
for paired full-minus-effect-aware actual process calls to exceed zero. The
coverage test requires the one-sided 95% Wilson upper bound for roots solved by
full but not effect-aware to be at most 0.05.

Because the pilot produced zero full-policy proofs, the confirmation analysis
also reports a non-negotiable information flag indicating whether full solves
at least one confirmation root. Passing the registered numerical coverage rule
with zero full-policy successes is not described as informative preservation of
proof success. Strict canonical endpoint preservation is reported separately.
