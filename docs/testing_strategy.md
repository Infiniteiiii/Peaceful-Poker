# Testing Strategy

The suite covers deterministic poker rules, validated game states, draw and outs logic, exact
probability calculations, equity calculation, strategy math, persistence and schema migration,
training scenarios, export output, and Qt lifecycle behavior. Action-aware coverage includes
heads-up through ten-seat action order, legal policy distributions, profile behavior, players
behind, reopening, all-ins and side pots, net-EV accounting, cancellation, and the four named
acceptance scenarios.

Monte Carlo tests use fixed seeds for exact reproducibility and compare different seeds against
combined standard error. UI tests avoid fragile screen coordinates and validate startup through
the real application entry point with an automatic close timer.
