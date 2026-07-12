# Equity And Strategy

Peaceful Poker separates raw poker calculation from betting advice.

## Equity

The equity engine reuses the custom seven-card evaluator for every player. It
uses exact enumeration when the state space is practical, including completed
river boards and heads-up turn states under the configured threshold. Larger or
multiway states use seeded Monte Carlo simulation.

Every iteration removes known hero cards, board cards, and any supplied known
opponent cards before dealing opponents and completing the board. Split pots are
credited as fractional pot share, so a three-way tie gives the hero one third of
an equity point for that outcome.

Opponent assumptions currently support random holdings, preset filtered ranges,
and a documented notation subset: pairs such as `AA`, suited and offsuit hands
such as `AKs` and `AQo`, pair-plus ranges such as `99+`, suited-plus ranges such
as `ATs+`, and pair intervals such as `22-88`.

## Pot Definition

Current pot means all chips already in the middle, including the opponent's
current bet, but excluding the hero's pending call.

```text
Final pot after calling = current pot + amount to call
Required equity = amount to call / final pot after calling
```

The simplified call EV is:

```text
Call EV = equity * current pot - (1 - equity) * amount to call
```

This excludes future betting, rake, implied odds, reverse implied odds, range
uncertainty, and opponent adaptation.

## Recommendations

Recommendations are transparent educational rules, not GTO strategy. The engine
considers legal actions, equity, pot odds, simplified EV, apparent outs, and the
entered betting state. Wording is intentionally qualified because no rule-based
trainer can guarantee a profitable decision.