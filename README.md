# Peaceful Poker

Peaceful Poker is an educational No-Limit Texas Hold’em desktop application built with Python and PySide6. It allows users to enter a poker situation, analyze the current hand, estimate showdown equity, examine possible improvements, and compare legal decisions using transparent probability and expected-value calculations.

The application can analyze:

* Hero hole cards
* Flop, turn, and river cards
* Number of players
* Table position and action order
* Pot size and amount to call
* Hero and effective stack sizes
* Opponent ranges
* Opponent playing profiles
* Players who have folded, called, raised, or remain behind the hero
* Raw showdown equity
* Action-aware expected value
* Pot odds
* Draws and apparent outs
* Final-hand probabilities
* Recommended legal actions

Peaceful Poker is intended as a learning and analysis tool. It is not an online poker client, real-money gambling service, live-game automation tool, screen reader, GTO solver, or promise of profitable play.

Its results depend on the accuracy of the entered game state and the assumptions selected for unknown opponents.

---

# Table of Contents

1. [Main Features](#main-features)
2. [How the Application Works](#how-the-application-works)
3. [Poker Hand Evaluation](#poker-hand-evaluation)
4. [Best Five Cards From Seven](#best-five-cards-from-seven)
5. [Draws and Outs](#draws-and-outs)
6. [Exact Improvement Probabilities](#exact-improvement-probabilities)
7. [Showdown Equity](#showdown-equity)
8. [Exact Enumeration](#exact-enumeration)
9. [Monte Carlo Simulation](#monte-carlo-simulation)
10. [Split Pots and Pot-Share Equity](#split-pots-and-pot-share-equity)
11. [Opponent Ranges](#opponent-ranges)
12. [Action Order and Players Behind](#action-order-and-players-behind)
13. [Action-Aware Opponent Modelling](#action-aware-opponent-modelling)
14. [Pot Odds](#pot-odds)
15. [Expected Value](#expected-value)
16. [Recommendation System](#recommendation-system)
17. [Confidence and Statistical Uncertainty](#confidence-and-statistical-uncertainty)
18. [Example Analysis](#example-analysis)
19. [Application Architecture](#application-architecture)
20. [Background Workers and Cancellation](#background-workers-and-cancellation)
21. [Saving, Loading, and Exports](#saving-loading-and-exports)
22. [Training Mode](#training-mode)
23. [Requirements](#requirements)
24. [Installation on Windows](#installation-on-windows)
25. [Installation on macOS or Linux](#installation-on-macos-or-linux)
26. [Launching the Application](#launching-the-application)
27. [Running Tests and Quality Checks](#running-tests-and-quality-checks)
28. [Building the Windows Application](#building-the-windows-application)
29. [Saved Data Location](#saved-data-location)
30. [Project Structure](#project-structure)
31. [Design Decisions and Limitations](#design-decisions-and-limitations)
32. [Troubleshooting](#troubleshooting)
33. [Documentation](#documentation)

---

# Main Features

## Poker analysis

* Validated 52-card deck
* Duplicate-card prevention
* Five-card and seven-card hand evaluator
* Correct kicker and tie-break handling
* Ace-high and ace-low straight handling
* Board-only hands
* Split pots
* Current made-hand identification
* Best five-card display
* Hero-card usage identification

## Probability analysis

* Exact flop, turn, and river improvement probabilities
* Exact hand-category distributions
* Probability of finishing with at least a given hand strength
* Draw detection
* Apparent unique outs
* Exact showdown enumeration where practical
* Seeded Monte Carlo simulation for larger state spaces
* Fractional pot-share equity

## Decision analysis

* Legal-action detection
* Pot odds
* Required break-even equity
* Simplified call expected value
* Action-aware expected value
* Opponent fold, call, and raise modelling
* Player-position and action-order modelling
* Suggested bet and raise sizes
* Qualified educational recommendations

## Desktop application

* PySide6 graphical interface
* Light and dark themes
* Cancellable background analysis
* Safe worker-thread cleanup
* Stale-result protection
* Save and load
* Markdown and JSON export
* Training scenarios
* Versioned data schema
* Original SVG, PNG, and ICO artwork
* Windows PyInstaller release

---

# How the Application Works

A Peaceful Poker analysis moves through several independent stages.

1. The entered cards and betting information are validated.
2. Known cards are removed from the deck.
3. The current made hand is evaluated.
4. The community board is classified.
5. Draws and apparent outs are identified.
6. Future board runouts are enumerated or simulated.
7. Raw showdown equity is calculated.
8. Legal hero actions are generated.
9. Opponents who remain to act are modelled.
10. The expected value of each legal hero action is estimated.
11. The highest-value action is presented with assumptions and warnings.

These stages are separated in the codebase. The graphical interface does not perform poker calculations directly.

---

# Poker Hand Evaluation

Texas Hold’em hands are ranked from strongest to weakest:

| Rank | Hand            |
| ---: | --------------- |
|    1 | Straight Flush  |
|    2 | Four of a Kind  |
|    3 | Full House      |
|    4 | Flush           |
|    5 | Straight        |
|    6 | Three of a Kind |
|    7 | Two Pair        |
|    8 | One Pair        |
|    9 | High Card       |

A Royal Flush is represented internally as an ace-high straight flush but displayed separately for clarity.

Each evaluated hand contains two important pieces of information:

1. A hand category
2. A tie-break tuple

For example, consider:

```text
A♠ A♦ K♣ 9♥ 4♠
```

This is represented conceptually as:

```text
Category: One Pair
Tie breakers: (Ace, King, Nine, Four)
```

Another pair of aces can therefore be compared by checking the kickers in descending order.

## Tie-breaking rules

### One pair

Compare:

1. Pair rank
2. Highest kicker
3. Second kicker
4. Third kicker

### Two pair

Compare:

1. Higher pair
2. Lower pair
3. Kicker

### Three of a kind

Compare:

1. Trip rank
2. Highest kicker
3. Second kicker

### Straight

Compare the highest card in the straight.

The wheel:

```text
A-2-3-4-5
```

is treated as a five-high straight, not an ace-high straight.

### Flush

Compare all five cards from highest to lowest.

### Full house

Compare:

1. Three-of-a-kind rank
2. Pair rank

### Four of a kind

Compare:

1. Four-of-a-kind rank
2. Kicker

This creates a consistent ordering that can be used for hero hands, opponent hands, exact enumeration, Monte Carlo simulation, and split-pot detection.

---

# Best Five Cards From Seven

A Texas Hold’em player may use any five cards from:

* Two hole cards
* Five community cards

The player does not have to use both private cards.

With seven total cards, the number of five-card combinations is:

$$
\binom{7}{5}
============

# \frac{7!}{5!2!}

21
$$

The evaluator examines all 21 combinations and selects the strongest result.

This correctly handles cases where the best hand uses:

* Both hero cards
* One hero card
* No hero cards

For example:

```text
Hero: A♣ 2♦
Board: K♠ K♥ Q♠ Q♦ J♣
```

The best hand is:

```text
K-K-Q-Q-A
```

Only the ace from the hero’s hand is used.

If the board were:

```text
A♠ K♠ Q♠ J♠ 10♠
```

every player would have the same board-only Royal Flush.

---

# Draws and Outs

An **out** is an unseen card that may improve a player’s hand.

Peaceful Poker detects structures such as:

* Flush draws
* Backdoor flush draws
* Open-ended straight draws
* Gutshot straight draws
* Double-gutshot straight draws
* Backdoor straight possibilities
* Overcards
* Pair-to-two-pair improvements
* Pair-to-trips improvements
* Two-pair-to-full-house improvements
* Set-to-full-house improvements
* Set-to-quads improvements
* Combination draws

## Open-ended straight draw

Consider:

```text
6-7-8-9
```

Either a five or ten completes a straight.

Assuming all eight cards are unseen:

```text
4 fives + 4 tens = 8 apparent outs
```

## Gutshot straight draw

Consider:

```text
6-7-9-10
```

Only an eight completes the straight:

```text
4 eights = 4 apparent outs
```

## Flush draw

If the hero has four cards of one suit among their hole cards and board, there are normally:

```text
13 cards in a suit − 4 visible cards = 9 apparent flush outs
```

## Overlapping outs

Outs cannot simply be added when one card completes multiple draws.

For example, one card might complete both a straight and a flush. It is still only one physical card and must be counted once.

Peaceful Poker stores the actual unseen card objects associated with each draw and then creates a deduplicated collection.

## Apparent outs versus clean outs

The application intentionally describes these as **apparent outs**.

An apparent out improves the hero’s hand, but it may not guarantee the winning hand.

For example:

* A flush card may give an opponent a higher flush.
* A paired river may complete the hero’s two pair but give an opponent a full house.
* A straight-completing card may also complete a higher straight.
* A card that gives the hero top pair may complete an opponent’s two pair.

Determining whether an out is truly clean requires detailed opponent-range and action assumptions.

---

# Exact Improvement Probabilities

When future community cards remain, Peaceful Poker can enumerate every valid runout.

## Turn to river

After the hero’s two cards and four board cards are known, there are:

```text
52 − 6 = 46 unseen cards
```

Therefore, there are 46 possible river cards before accounting for any additional known opponent cards.

If a draw has $o$ apparent outs, the probability of completing it on the river is:

$$
P(\text{hit}) = \frac{o}{46}
$$

For nine flush outs:

$$
P(\text{flush on river})
========================

\frac{9}{46}
\approx 19.57%
$$

## Flop to river

After two hole cards and three flop cards are known, 47 cards remain.

The number of unordered turn-and-river combinations is:

$$
\binom{47}{2}
=============

# \frac{47 \times 46}{2}

1081
$$

Peaceful Poker can enumerate all 1,081 runouts for hand-improvement analysis.

## Hitting at least one out over two cards

If there are $o$ outs and 47 unseen cards on the flop, the probability of missing both the turn and river is:

$$
P(\text{miss both})
===================

\frac{47-o}{47}
\times
\frac{46-o}{46}
$$

Therefore:

$$
P(\text{hit by river})
======================

## 1

\frac{47-o}{47}
\times
\frac{46-o}{46}
$$

For nine apparent flush outs:

$$
P(\text{hit by river})
======================

## 1

\frac{38}{47}
\times
\frac{37}{46}
\approx 34.97%
$$

The exact hand-category engine is more complete than this shortcut because it evaluates the final poker hand for every runout rather than assuming every apparent out produces the desired final result.

---

# Showdown Equity

Showdown equity estimates the hero’s share of the pot if all included players continue until the cards are revealed.

It is not the same as the probability of winning outright because tied pots must be divided.

A simplified heads-up measure is:

$$
\text{Equity}
=============

P(\text{win})
+
\frac{1}{2}P(\text{tie})
$$

For multiway hands, the hero receives the appropriate fraction of each tied pot.

For example:

* Full win: $1$
* Two-player split: $\frac{1}{2}$
* Three-player split: $\frac{1}{3}$
* Four-player split: $\frac{1}{4}$

The general estimated equity is:

$$
\text{Equity}
=============

\frac{
\sum_{i=1}^{N}
\text{Hero pot share in simulation }i
}{
N
}
$$

This is why raw tie percentage and total equity are displayed separately.

---

# Exact Enumeration

Exact enumeration evaluates every legal outcome in a finite state space.

For a completed board against one unknown opponent, the number of opponent two-card combinations is:

$$
\binom{45}{2}
=============

990
$$

because seven cards are known:

* Hero’s two cards
* Five board cards

The exact river evaluator can:

1. Remove all known cards.
2. Generate every legal opponent holding.
3. Evaluate the hero.
4. Evaluate the opponent.
5. Compare the hands.
6. Count wins, losses, and ties.

Exact enumeration produces no sampling error, but it becomes expensive as more players and unknown board cards are introduced.

For several opponents, the number of assignments grows rapidly because opponent hands must be disjoint.

For two opponents on a completed board, an approximate unfiltered assignment count is:

$$
\binom{45}{2}
\times
\binom{43}{2}
$$

The order and symmetry of opponent seats must also be considered depending on how the state is represented.

Because this grows quickly, Peaceful Poker uses exact enumeration only when the state space is practical.

---

# Monte Carlo Simulation

Monte Carlo simulation estimates results by repeatedly sampling legal hidden cards and future boards.

A single simulation performs the following steps:

1. Remove all known cards.
2. Sample legal opponent holdings from their ranges.
3. Complete any unknown community cards.
4. Evaluate every remaining player.
5. Determine all winners.
6. Award the hero their full or fractional pot share.
7. Record the result.

After $N$ simulations:

$$
\hat{p}_{\text{win}}
====================

\frac{\text{wins}}{N}
$$

$$
\hat{p}_{\text{tie}}
====================

\frac{\text{ties}}{N}
$$

$$
\hat{p}_{\text{loss}}
=====================

\frac{\text{losses}}{N}
$$

The approximate equity is the average hero pot share across the simulations.

## Why Monte Carlo is used

A full preflop multiway enumeration would require evaluating an extremely large number of:

* Opponent hole-card assignments
* Five-card board runouts
* Range combinations
* Fold, call, and raise paths

Monte Carlo sampling allows the application to estimate these results in a practical amount of time.

## Simulation presets

The application may expose presets such as:

| Mode          | Typical purpose           |
| ------------- | ------------------------- |
| Quick         | Fast interactive estimate |
| Standard      | Normal analysis           |
| Accurate      | More stable comparison    |
| Very Accurate | Slower detailed analysis  |

Higher simulation counts reduce random variation but increase computation time.

## Deterministic seeds

Tests use deterministic seeds.

Given the same:

* Game state
* Opponent ranges
* Simulation count
* Random seed

the simulator should return the same result.

This makes regression tests repeatable while normal application analysis may use varying seeds.

---

# Split Pots and Pot-Share Equity

Suppose the board itself produces the best possible five-card hand for every remaining player.

If three players reach showdown, each receives:

$$
\frac{1}{3}
$$

of the pot.

The simulation therefore records:

```text
Hero pot share = 0.3333...
```

rather than incorrectly counting the result as either a full win or full loss.

This matters because two situations can have the same tie percentage but different equity if different numbers of players share the pot.

---

# Opponent Ranges

An opponent range is a collection of hole-card combinations the opponent may hold.

Peaceful Poker includes simplified presets such as:

* Any two cards
* Loose
* Standard
* Tight
* Premium

It also supports a documented subset of common range notation.

## Pocket pairs

```text
AA
99+
22-88
```

Meanings:

* `AA`: pocket aces only
* `99+`: pocket nines through pocket aces
* `22-88`: pocket pairs from twos through eights

## Suited hands

```text
AKs
ATs+
```

The `s` means suited.

`ATs+` represents suited ace-ten and stronger suited ace-high combinations according to the range parser’s documented ordering.

## Offsuit hands

```text
AQo
KQo
```

The `o` means offsuit.

## Card removal

Ranges are filtered after known cards are removed.

For example, if the hero holds:

```text
A♠ K♠
```

then no opponent combination may contain either `A♠` or `K♠`.

This effect is often called **card removal** or **blocking**.

The application does not treat range notation as a guarantee that a real opponent holds those cards. It defines the set from which hidden cards are sampled.

---

# Action Order and Players Behind

Raw showdown equity is insufficient when players remain to act.

For example:

* One opponent bets.
* Hero considers calling.
* Two players remain behind the hero.

Those later players may:

* Fold
* Call
* Raise
* Move all-in

They should not automatically be included in the final showdown.

Peaceful Poker models seat order and player state, including:

* Button
* Small blind
* Big blind
* Hero position
* Current player to act
* Folded players
* All-in players
* Players who have already acted
* Players who remain eligible to act

## Preflop action

In a normal multiway hand, preflop action begins to the left of the big blind.

## Postflop action

Postflop action begins with the first active player to the left of the button.

## Heads-up exception

Heads-up blind and action order differ from ordinary multiway play:

* The button posts the small blind.
* The button acts first preflop.
* The big blind acts first postflop.

Folded and all-in players are skipped when identifying the next player who can act.

---

# Action-Aware Opponent Modelling

The action-aware simulator estimates how opponents might react to a hero decision.

This result is separate from raw showdown equity.

## Opponent profiles

Example profiles include:

* Unknown or Balanced
* Tight Passive
* Loose Passive
* Tight Aggressive
* Loose Aggressive
* Calling Station
* Nit
* Maniac

These profiles affect estimated:

* Fold frequency
* Call frequency
* Raise frequency
* Bluff frequency
* Value threshold
* Response to bet sizing
* Response to board texture
* Response to previous aggression

These are simplified educational models, not exact descriptions of real players.

## Opponent action probabilities

For each opponent, the policy engine produces probabilities over only legal actions.

When facing a bet:

$$
P(\text{fold})
+
P(\text{call})
+
P(\text{raise})
+
P(\text{all-in})
================

1
$$

Actions that are illegal in the current state receive probability zero or are excluded entirely.

The probabilities may depend on:

* Sampled opponent cards
* Current made hand
* Draw strength
* Board texture
* Pot size
* Call amount
* Bet size relative to the pot
* Stack-to-pot ratio
* Position
* Number of opponents
* Previous aggression
* Opponent profile

A strong hand should therefore continue more frequently than complete air.

A larger bet should generally produce more folds than a smaller bet, all else equal.

A loose-aggressive opponent should generally continue and raise more frequently than a tight-passive opponent.

## Action-aware simulation process

For each candidate hero action, one simulation can:

1. Sample legal opponent cards.
2. Apply the hero’s action.
3. Move through remaining players in action order.
4. Sample a legal response for each opponent.
5. Remove folded players.
6. Add calls and raises to the pot.
7. Cap contributions by remaining stacks.
8. Handle all-in players.
9. Reopen action after a legal raise where supported.
10. Award the pot immediately if everyone folds.
11. Complete the board if a showdown remains possible.
12. Evaluate the remaining players.
13. Record the hero’s net result.

This process is repeated for every legal hero action.

---

# Pot Odds

Pot odds compare the price of calling with the pot that can be won.

Peaceful Poker defines:

```text
Current pot
```

as all chips already in the middle, including an opponent’s current bet, but excluding the hero’s pending call.

Therefore:

$$
\text{Final pot after calling}
==============================

\text{Current pot}
+
\text{Amount to call}
$$

Required break-even equity is:

$$
\text{Required equity}
======================

\frac{
\text{Amount to call}
}{
\text{Current pot} + \text{Amount to call}
}
$$

## Example

Suppose:

```text
Current pot: 140
Amount to call: 40
```

Then:

$$
\text{Final pot after calling}
==============================

# 140 + 40

180
$$

$$
\text{Required equity}
======================

\frac{40}{180}
\approx 0.2222
==============

22.22%
$$

If the hero’s estimated equity is significantly above 22.22%, calling may be profitable under the simplified assumptions.

The opponent’s current bet must not be added again because it is already part of the current pot.

---

# Expected Value

Expected value estimates the average chip result of repeatedly taking the same action in equivalent situations.

## Simplified call EV

Using Peaceful Poker’s current-pot definition:

$$
EV_{\text{call}}
================

## E \times P

(1-E)\times C
$$

where:

* $E$ is hero equity
* $P$ is the current pot
* $C$ is the call amount

For example:

```text
Equity: 35%
Current pot: 140
Call amount: 40
```

Then:

$$
EV_{\text{call}}
================

## 0.35(140)

0.65(40)
$$

$$
EV_{\text{call}}
================

# 49 - 26

23
$$

Under this simplified model, the call has an expected value of positive 23 chips.

This calculation excludes:

* Future betting
* Rake
* Implied odds
* Reverse implied odds
* Range errors
* Opponent adaptation
* Tournament value
* Risk preferences

## Fold EV

From the current decision point:

$$
EV_{\text{fold}} = 0
$$

Previous chips placed into the pot are already sunk and are not counted again.

## Immediate fold win

If the hero bets and every opponent folds:

$$
\text{Net result}
=================

\text{Current pot}
$$

The hero’s newly placed bet returns with the pot and should not be counted as additional profit.

## General action-aware EV

For a candidate action $a$:

$$
EV(a)
=====

\sum_{s \in S}
P(s \mid a)
\times
R(s,a)
$$

where:

* $S$ is the set of sampled future scenarios
* $P(s \mid a)$ is the probability of scenario $s$ after action $a$
* $R(s,a)$ is the hero’s net result in that scenario

Monte Carlo estimates this as:

$$
\widehat{EV}(a)
===============

\frac{1}{N}
\sum_{i=1}^{N}
R_i(a)
$$

The application compares the estimated EV of each legal hero action.

---

# Recommendation System

The recommendation system is transparent and rule-based.

It does not claim to produce a game-theory-optimal solution.

It considers available information such as:

* Legal actions
* Raw showdown equity
* Required equity
* Pot odds
* Simplified call EV
* Action-aware EV
* Probability all opponents fold
* Probability one opponent continues
* Probability multiple opponents continue
* Probability of facing a raise
* Conditional equity when called
* Hand category
* Draw strength
* Board texture
* Position
* Number of opponents
* Stack depth
* Opponent range
* Opponent profiles
* Statistical uncertainty

Possible results include:

When no bet is faced:

* Check
* Bet small
* Bet medium
* Bet large
* All-in

When facing a bet:

* Fold
* Call
* Raise small
* Raise medium
* Raise large
* All-in

The application filters illegal or duplicate sizing choices.

Recommendations use qualified wording because the model cannot know an opponent’s actual cards or future actions.

A suitable explanation is:

> Based on the entered information and current opponent assumptions, calling has the highest estimated value.

The application should not claim:

> Calling is definitely correct.

---

# Confidence and Statistical Uncertainty

Monte Carlo estimates vary because they are based on random samples.

For a binary probability estimate $\hat{p}$ from $N$ independent samples, an approximate standard error is:

$$
SE
==

\sqrt{
\frac{
\hat{p}(1-\hat{p})
}{
N
}
}
$$

An approximate 95% confidence interval is:

$$
\hat{p}
\pm
1.96SE
$$

For example, if:

```text
Estimated win probability: 40%
Simulations: 10,000
```

then:

$$
SE
==

\sqrt{
\frac{0.4(0.6)}{10000}
}
\approx 0.00490
$$

The approximate 95% interval is:

$$
0.40
\pm
1.96(0.00490)
$$

$$
0.40
\pm
0.0096
$$

or approximately:

```text
39.04% to 40.96%
```

Action-aware EV is more complicated because each outcome can produce a different chip result rather than a simple win or loss.

For simulated returns $R_1,\dots,R_N$:

$$
\overline{R}
============

\frac{1}{N}
\sum_{i=1}^{N}R_i
$$

The sample standard deviation is:

$$
s
=

\sqrt{
\frac{
\sum_{i=1}^{N}(R_i-\overline{R})^2
}{
N-1
}
}
$$

The estimated standard error of mean EV is:

$$
SE_{\text{EV}}
==============

\frac{s}{\sqrt{N}}
$$

When two actions have EV estimates that are very close relative to their uncertainty, Peaceful Poker should describe the decision as close rather than present false precision.

---

# Example Analysis

Consider:

```text
Players: 6
Hero position: Button
Hero cards: A♠ K♠
Flop: Q♠ 10♦ 4♠
Current pot: 140
Amount to call: 40
Hero stack: 900
Effective stack: 620
```

## Current hand

The hero currently has:

```text
Ace-high
```

## Draws

The hero has:

* Nut flush draw
* Gutshot straight draw
* Two overcards to some opponent holdings
* Combination-draw potential

A jack completes Broadway:

```text
A-K-Q-J-10
```

A spade completes the ace-high flush, although the jack of spades overlaps with both the straight and flush draw and must only be counted once as a physical out.

## Pot odds

$$
\text{Required equity}
======================

# \frac{40}{140+40}

\frac{40}{180}
\approx 22.22%
$$

## Raw equity

The showdown-equity simulator estimates how often the hero wins or splits if the included opponents continue.

## Players behind

If players remain after the hero, they may fold, call, or raise. Their possible responses affect:

* The chance of reaching showdown
* The number of showdown opponents
* Final pot size
* Hero investment
* Risk of facing a raise
* Expected value of calling or raising

The action-aware model therefore evaluates these decisions separately from raw equity.

---

# Application Architecture

The project separates mathematical logic, data representation, services, and user-interface code.

```text
src/poker_trainer/
├── engine/
├── models/
├── resources/
├── services/
├── strategy/
├── training/
├── ui/
└── utils/
```

## Engine

Contains pure poker calculations such as:

* Hand evaluation
* Board analysis
* Draw detection
* Outs calculation
* Exact runout probabilities
* Range parsing
* Exact equity
* Monte Carlo equity
* Action-aware policy simulation

The engine does not depend on PySide6.

## Models

Contains structured data such as:

* Card
* Deck
* Evaluated hand
* Game state
* Player state
* Betting state
* Equity result
* Draw result
* Probability result
* Recommendation
* Action-aware result

Models provide typed boundaries between different parts of the application.

## Strategy

Contains:

* Legal-action generation
* Pot-odds calculations
* Expected-value calculations
* Bet and raise sizing
* Recommendation thresholds
* Educational explanation generation

## Services

Contains orchestration and application-level operations such as:

* Running a complete analysis
* Loading settings
* Saving hands
* Migrating save schemas
* Exporting reports
* Logging
* Resolving user-data directories

## UI

Contains the PySide6 interface:

* Main window
* Card selector
* Table and player-state editor
* Results panels
* Settings
* Help
* Background workers

The UI submits structured game states to the service layer and displays structured results.

## Resources

Contains packaged:

* Themes
* Configuration
* Recommendation thresholds
* Opponent profiles
* Application artwork

`resource_path.py` allows the same files to be found when running:

* From source
* As an installed Python package
* Inside a PyInstaller bundle

---

# Background Workers and Cancellation

Long calculations run outside the Qt user-interface thread.

Without this separation, a 25,000-iteration simulation would freeze the window.

The application uses a worker-thread structure conceptually similar to:

```text
Main UI thread
    |
    | creates validated analysis request
    v
Worker thread
    |
    | performs exact or Monte Carlo calculation
    | emits progress
    | checks cancellation
    v
Main UI thread
    |
    | receives structured result
    | updates interface
```

Important lifecycle rules include:

* Worker completion stops the worker thread, not the entire application.
* The main window remains open after analysis.
* Closing the window requests cancellation.
* The application waits for active workers to stop safely.
* Stale analysis results cannot overwrite a newer game state.
* Worker code does not directly modify Qt widgets.

---

# Saving, Loading, and Exports

Saved hands use versioned JSON.

A saved state may include:

* Schema version
* Game type
* Hero cards
* Board cards
* Player count
* Player positions
* Folded and all-in states
* Betting values
* Stacks
* Opponent profiles
* Opponent ranges
* Simulation settings
* Notes
* Optional analysis summary

Versioning allows the application to migrate older save files when new fields are added.

The loader rejects:

* Invalid JSON
* Unsupported future versions
* Duplicate cards
* Invalid street lengths
* Missing required fields
* Impossible action states
* Negative betting values

Exports are available in readable Markdown and structured JSON.

---

# Training Mode

Training mode generates poker situations and asks the user to choose an action before seeing the analysis.

A training cycle can:

1. Generate a valid scenario.
2. Display cards, positions, stacks, and betting information.
3. Hide the recommendation.
4. Present legal decisions.
5. Record the user’s choice.
6. Run the real analysis engine.
7. Compare the user’s action with the model.
8. Explain the important factors.
9. Track local session results.

Scenarios may include:

* Hero last to act
* One player behind
* Several players behind
* Tight opponents
* Loose-aggressive opponents
* Short stacks
* Prior callers
* Draw-heavy boards
* Clear value hands
* Close decisions

Training mode uses the same engine as the main analyzer rather than separate placeholder logic.

---

# Requirements

## Source version

* Python 3.12 or newer
* PySide6
* A supported Windows, macOS, or Linux desktop environment

## Packaged Windows build

* Windows 10 or newer
* No separate Python installation required

The project is developed using a newer Python release while preserving Python 3.12 syntax and configuration.

---

# Installation on Windows

Open PowerShell in the repository root.

The repository root is the folder containing:

```text
pyproject.toml
README.md
src
tests
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install the application and development tools:

```powershell
python -m pip install -e ".[dev,build]"
```

Verify dependencies:

```powershell
python -m pip check
```

---

# Installation on macOS or Linux

Clone the repository:

```bash
git clone https://github.com/Infiniteiiii/Peaceful_Poker.git
cd Peaceful_Poker
```

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Launch:

```bash
python -m poker_trainer
```

The Windows `.exe` cannot run natively on macOS. macOS users should run the source version or build a separate macOS application on a Mac.

---

# Launching the Application

Both commands open the same application:

```powershell
python -m poker_trainer
```

or:

```powershell
peaceful-poker
```

## Entering a hand

The hero must have exactly two private cards.

Valid board lengths are:

| Street  | Board cards |
| ------- | ----------: |
| Preflop |           0 |
| Flop    |           3 |
| Turn    |           4 |
| River   |           5 |

One-card and two-card board states are rejected because they cannot occur in normal Hold’em progression.

Used cards are disabled in the card selector.

## Betting inputs

`Current pot` includes all chips already in the middle, including the opponent’s current bet, but excludes the hero’s pending call.

`Amount to call` is the additional amount the hero must contribute to continue.

## Controls

* **Analyze:** Runs the selected calculation.
* **Cancel:** Requests cancellation of a running simulation.
* **Clear street:** Removes the latest entered board street.
* **New hand:** Clears the hand and stale results.
* **Save:** Saves the current state.
* **Load:** Loads a saved state.
* **Export:** Writes a Markdown or JSON analysis report.
* **Settings:** Changes themes and analysis preferences.
* **Training:** Opens educational practice scenarios.

---

# Running Tests and Quality Checks

Activate the virtual environment first.

Run the test suite:

```powershell
python -m pytest
```

For a cache-independent test run:

```powershell
python -m pytest -p no:cacheprovider
```

Check formatting:

```powershell
python -m ruff format --check .
```

Run lint checks:

```powershell
python -m ruff check .
```

Run strict type checking:

```powershell
python -m mypy src
```

Check installed dependencies:

```powershell
python -m pip check
```

GitHub Actions runs the quality suite on supported Python versions with Qt configured for headless UI testing.

---

# Building the Windows Application

The build script:

1. Installs development and build dependencies.
2. Runs tests.
3. Runs Ruff.
4. Runs Mypy.
5. Runs dependency checks.
6. Removes old build output.
7. Invokes PyInstaller.
8. Confirms the executable exists.

Run:

```powershell
.\scripts\build_windows.ps1
```

Release output:

```text
dist\Peaceful Poker\Peaceful Poker.exe
```

Because this is a one-folder PyInstaller build, distribute the complete:

```text
dist\Peaceful Poker
```

folder or compress that folder into a ZIP.

Do not distribute only the `.exe` if supporting files are placed beside it.

Run full source and packaged verification with:

```powershell
.\scripts\verify.ps1
```

---

# Saved Data Location

On Windows:

```text
%LOCALAPPDATA%\Peaceful Poker
```

This directory contains application data such as:

* Settings
* Logs
* Saved hands
* Default exports

If `LOCALAPPDATA` is unavailable, the application attempts to use `APPDATA` and then the user’s home directory.

On macOS, application data will normally be stored under a location similar to:

```text
~/Library/Application Support/Peaceful Poker
```

The application never writes user saves into the installed PyInstaller bundle.

---

# Project Structure

```text
Peaceful_Poker/
├── .github/
│   └── workflows/
│       └── quality.yml
├── data/
├── docs/
│   ├── action_aware_methodology.md
│   ├── architecture.md
│   ├── equity_and_strategy.md
│   ├── release_checklist.md
│   ├── save_schema.md
│   ├── testing_plan.md
│   └── testing_strategy.md
├── packaging/
│   └── windows_version_info.txt
├── scripts/
│   ├── benchmark_action_aware.py
│   ├── benchmark_probabilities.py
│   ├── benchmark_simulation.py
│   ├── build_windows.ps1
│   ├── generate_icon.py
│   └── verify.ps1
├── src/
│   └── poker_trainer/
│       ├── engine/
│       ├── models/
│       ├── resources/
│       ├── services/
│       ├── strategy/
│       ├── training/
│       ├── ui/
│       └── utils/
├── tests/
│   └── unit/
├── CHANGELOG.md
├── Peaceful Poker.spec
├── pyproject.toml
└── README.md
```

---

# Design Decisions and Limitations

## The application is not a GTO solver

A full game-theory-optimal solver requires:

* Complete range-versus-range strategy trees
* Mixed strategies
* Bet-size abstraction
* Counterfactual values
* Repeated regret minimization or another solver method
* Large amounts of computation

Peaceful Poker instead uses understandable rule-based opponent policies and Monte Carlo estimates.

## Opponent profiles are assumptions

A real opponent may behave very differently from their selected profile.

Action-aware results should be interpreted as:

> Estimated results under the chosen opponent assumptions.

They should not be interpreted as exact predictions.

## Ranges are simplified

Range presets are filtered collections of legal hands.

They are not necessarily weighted by the frequency with which a strong player would choose each combination.

## Apparent outs are not guaranteed clean

A card can improve the hero without producing the winning hand.

## Simplified EV excludes future effects

Basic call EV excludes:

* Rake
* Future betting
* Implied odds
* Reverse implied odds
* Tournament utility
* Opponent adaptation

The action-aware simulator models more future decisions, but it still uses a bounded and simplified action tree.

## Multiway poker is computationally expensive

Every additional opponent increases:

* Hidden-card combinations
* Action paths
* Possible ranges
* Showdown comparisons

The application uses Monte Carlo simulation to keep these cases practical.

## Exact results and simulated results differ

Exact enumeration has no sampling error but may be expensive.

Monte Carlo simulation is faster for large state spaces but contains statistical uncertainty.

## Poker remains a game of incomplete information

No application can know unknown cards or future human decisions with certainty.

---

# Troubleshooting

## The install command says there is no `pyproject.toml`

You are in the wrong folder.

Move to the repository root:

```powershell
cd "C:\path\to\Peaceful_Poker"
```

Confirm:

```powershell
Test-Path .\pyproject.toml
```

It should return:

```text
True
```

## The application immediately closes

Activate the correct virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Launch with:

```powershell
python -m poker_trainer
```

Capture errors with:

```powershell
python -X faulthandler -m poker_trainer
```

Ensure no smoke-test environment variable is active.

## The application starts analyzing automatically

Open settings and disable automatic analysis.

Automatic analysis should only run when:

* It is explicitly enabled
* The entered state is valid

## A card is rejected

Use card codes such as:

```text
AS
KH
TD
10D
2C
```

Do not enter duplicate known cards.

## A range is rejected

Use a supported preset or notation form such as:

```text
AA
AKs
AQo
99+
ATs+
22-88
```

## Analysis feels slow

Use a lower simulation preset.

Action-aware analysis evaluates several candidate hero actions, so it can require more simulations than raw showdown equity.

## A GitHub Actions UI test crashes

Confirm the workflow contains:

```yaml
env:
  QT_QPA_PLATFORM: offscreen
  PYTHONFAULTHANDLER: "1"
```

Ensure UI tests:

* Use `pytest-qt`
* Register windows with `qtbot.addWidget`
* Wait for worker completion
* Do not create multiple `QApplication` instances
* Do not finish while a `QThread` is running

## Pytest produces a OneDrive cache warning

Use:

```powershell
python -m pytest -p no:cacheprovider
```

This disables only pytest’s cache provider and does not skip tests.

## The Windows build fails

Confirm:

```powershell
python --version
python -m pip install -e ".[dev,build]"
python -m pip check
```

Then rerun:

```powershell
.\scripts\build_windows.ps1
```

## A Mac user cannot open the `.exe`

Windows executables do not run natively on macOS.

The Mac user should clone the repository and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m poker_trainer
```

---

# Documentation

Additional technical details are available in:

* `CHANGELOG.md`
* `docs/action_aware_methodology.md`
* `docs/architecture.md`
* `docs/equity_and_strategy.md`
* `docs/release_checklist.md`
* `docs/save_schema.md`
* `docs/testing_plan.md`
* `docs/testing_strategy.md`

---

# Educational Disclaimer

Peaceful Poker provides probability estimates and educational decision guidance based on simplified mathematical and behavioural assumptions.

Poker outcomes contain randomness, incomplete information, opponent adaptation, and strategic complexity. A positive estimated expected value does not guarantee that an individual hand will win, and a model recommendation does not guarantee long-term profit.

Users are responsible for following all applicable laws, platform rules, and responsible-gaming practices.
