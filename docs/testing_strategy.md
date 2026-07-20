# Testing Strategy

The suite covers deterministic poker rules, validated game states, draw and outs logic, exact
probability calculations, equity calculation, strategy math, persistence and schema migration,
training scenarios, export output, and Qt lifecycle behavior. Action-aware coverage includes
heads-up through ten-seat action order, legal policy distributions, profile behavior, players
behind, reopening, all-ins and side pots, net-EV accounting, cancellation, and the four named
acceptance scenarios.

Mathematical regressions directly exercise uncontested wins and heads-up win, loss, tie, and
fractional-equity settlement. Fixed-seed scenarios verify that response probabilities partition to
one, weighted branch EVs sum to total EV, effective stacks cap every action, rounded candidates are
unique, large wagers tighten sampled calling ranges, and weak hands do not inherit constant fold
probabilities. The documented `AD AH` on `7C 2D 9S` scenario records candidate-level response and
EV diagnostics instead of asserting only a final label.

Monte Carlo tests use fixed seeds for exact reproducibility and compare different seeds against
combined standard error. UI tests avoid fragile screen coordinates and validate startup through
the real application entry point with an automatic close timer.

Pytest-qt coverage also verifies Normal/Advanced disclosure and value preservation, required-card
focus, contextual help metadata, the Overview/Advanced result structure, hidden-answer training
submission through the real worker, searchable terminology, and full-hand versus street-only
reset behavior. Every analysis-starting test waits for worker destruction so no `QThread` survives
fixture teardown.

Focused UX regressions additionally cover canonical Bet/Raise/Call/all-in labels and exact chip
sizes, identical export candidate labels, titled Overview/Advanced blocks, the action-EV comparison,
the absence of the redundant Settings control, exclusive Training radios, Correct/Incorrect
feedback, repeated Training resets, card-picker scrolling and clearing, opponent-editor row height,
combo popup arrow state, and multi-field validation with per-control recovery.
Terminology coverage inspects the visible wrapping labels in both themes at the dialog's minimum
size, verifies that representative long terms are complete rather than elided, and keeps one card
per source entry through repeated searches, theme changes, resizes, and dialog reopen cycles.
