# Action-Aware Methodology

## Equity And EV Are Different

Raw showdown equity is hero's fractional pot share if every included opponent continues to the
river. Action-aware expected value estimates chips won or lost after opponents may fold, call,
raise, or move all-in. Peaceful Poker displays both and never labels EV as equity.

## Clockwise State

Seats record dealt/folded/all-in state, stack, street and total contribution, profile, range,
previous actions, and whether action remains. Preflop begins left of the big blind except heads-up,
where the button/small blind acts first. Postflop begins left of the button. Folded and all-in seats
are skipped. A raise reopens clockwise action for eligible players below the new contribution.

## Bounded Policy Sampling

For every candidate and iteration, the simulator removes known cards, samples legal private cards
from entered/profile ranges, applies hero's action, and samples each response from legal policy
weights. The policy classifies current hand/draw strength and adjusts for profile, bet size, board,
position, stack depth, opponents, and prior aggression. Calls/raises update contributions and pot;
all-ins cannot exceed stack; folders leave showdown.

Checked-to candidates are Check, 25%, 33%, 50%, 66%, 75%, 100%, and 150% pot, plus a distinct
effective-stack all-in. Candidate amounts are rounded, capped, and deduplicated. Facing a bet,
raise-to amounts remain distinct from additional chips invested.

For each candidate, the response policy measures the outstanding wager against the pot before that
wager. It then combines nonlinear size pressure with the sampled holding's current strength,
profile, pot odds, stack-to-pot ratio, position, street, board texture, number of opponents, and
prior aggression. A stack-capped all-in response is weighted as a call rather than receiving a
fixed continuation bonus. This makes each candidate select its own calling and raising range from
the legal, card-removed base range.

Fast mode allows one opponent raise and detailed mode two, with a finite action-depth guard. After
the current-street policy sequence, future cards complete to showdown under a simplified legal
continuation assumption. This intentionally avoids pretending to solve an exhaustive multi-street
game tree.

## Net EV Convention

Previous hero contributions are sunk. Each iteration records chips returned to hero minus new chips
invested from the present decision. Folding is zero future EV. If every opponent folds to a new bet,
the bet returns to hero and net profit is the pre-action current pot. Split showdowns credit the
fractional winner share.

Candidate reports include standard error and a normal-approximation 95% confidence interval.
Overlapping top-action uncertainty is called out. Results are estimates under configured behavior
assumptions, not exact predictions of real opponents.

For a heads-up matched bet \(B\) into a pre-action pot \(P\), called-branch net EV is:

```math
EV_{\text{called}} = e(P+B) - (1-e)B = e(P+2B)-B.
```

An uncontested bet wins \(P\), regardless of the uncalled wager size. Diagnostics report fold,
call, and raise probabilities as an exhaustive partition, call-conditional and raise-conditional
equity, conditional branch EV, weighted branch contributions, and their total. Called equity is
computed only from unraised call showdowns; it is not raw equity reused under a new label.

This remains a one-action policy approximation. After the bounded current-street sequence, the
remaining board runs to showdown without a full later-street betting tree. Large flop and turn
sizings are flagged because future value, later folds, redraws, and range changes can materially
alter their true value.
