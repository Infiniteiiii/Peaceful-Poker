# Testing Strategy

The suite covers deterministic poker rules, validated game states, draw and outs
logic, exact probability calculations, equity calculation, strategy math,
persistence, training scenarios, export output, and a Qt startup smoke test.

Monte Carlo tests use fixed seeds for reproducibility. UI tests avoid fragile
screen coordinates and validate startup through the real application entry point
with an automatic close timer.