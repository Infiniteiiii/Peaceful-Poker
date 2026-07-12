# Peaceful Poker

Peaceful Poker is an educational No-Limit Texas Hold'em desktop application built with Python and PySide6. It analyzes a user-entered hand, evaluates the current made hand and draws, estimates showdown equity, models possible opponent responses, and compares legal decisions using transparent probability and expected-value calculations.

The project is designed to make the reasoning visible. It is not an online poker client, real-money gambling service, live-game assistant, GTO solver, or guarantee of profitable play. Every result depends on the cards, pot, stacks, action order, opponent ranges, and behavioural assumptions entered by the user.

---

## Table of Contents

1. [Core Features](#core-features)
2. [Analysis Pipeline](#analysis-pipeline)
3. [Mathematical Model](#mathematical-model)
   - [Deck State and Combinatorics](#deck-state-and-combinatorics)
   - [Five-Card Hand Ordering](#five-card-hand-ordering)
   - [Best Five Cards From Seven](#best-five-cards-from-seven)
   - [Draws, Outs, and Overlap](#draws-outs-and-overlap)
   - [Exact Runout Probabilities](#exact-runout-probabilities)
   - [Final-Hand Distributions](#final-hand-distributions)
4. [Showdown Equity](#showdown-equity)
   - [Pot-Share Definition](#pot-share-definition)
   - [Exact Enumeration](#exact-enumeration)
   - [Multiway State-Space Growth](#multiway-state-space-growth)
5. [Opponent Ranges and Card Removal](#opponent-ranges-and-card-removal)
6. [Monte Carlo Simulation](#monte-carlo-simulation)
   - [Estimator](#estimator)
   - [Variance and Standard Error](#variance-and-standard-error)
   - [Confidence Intervals](#confidence-intervals)
   - [Convergence Rate](#convergence-rate)
   - [Sampling Error Versus Model Error](#sampling-error-versus-model-error)
7. [Action-Aware Opponent Modelling](#action-aware-opponent-modelling)
   - [Action Order](#action-order)
   - [Policy Distributions](#policy-distributions)
   - [Conditional Equity](#conditional-equity)
   - [Fold Equity](#fold-equity)
8. [Pot Odds and Expected Value](#pot-odds-and-expected-value)
   - [Break-Even Equity](#break-even-equity)
   - [Call EV](#call-ev)
   - [Bet EV](#bet-ev)
   - [General Action EV](#general-action-ev)
   - [Uncertainty in EV](#uncertainty-in-ev)
9. [Worked Example](#worked-example)
10. [Recommendation System](#recommendation-system)
11. [Architecture](#architecture)
12. [Install and Run](#install-and-run)
13. [Tests and Builds](#tests-and-builds)
14. [Saved Data and Documentation](#saved-data-and-documentation)
15. [Limitations](#limitations)
16. [Troubleshooting](#troubleshooting)
17. [Educational Disclaimer](#educational-disclaimer)

---

## Core Features

- Validated 52-card model with duplicate prevention
- Five-card and seven-card hand evaluation with kicker and split-pot handling
- Preflop, flop, turn, and river analysis
- Draw detection and deduplicated apparent outs
- Exact runout probabilities where the state space is practical
- Seeded Monte Carlo simulation for larger and multiway states
- Opponent range presets and card-removal filtering
- Seat, action-order, folded-player, and all-in modelling
- Action-aware fold, call, raise, and all-in simulation
- Pot odds, required equity, simplified EV, and action EV
- Cancellable background analysis with stale-result protection
- Training scenarios, save/load, Markdown export, and JSON export
- Light and dark themes
- PyInstaller one-folder Windows build
- Headless GitHub Actions testing on supported Python versions

---

## Analysis Pipeline

A complete analysis proceeds through the following stages:

1. Validate the cards, street, stack, pot, and action state.
2. Remove every known card from the deck.
3. Evaluate the hero's current best five-card hand.
4. Classify the board and identify available draws.
5. Build a deduplicated set of apparent outs.
6. Enumerate or sample legal future boards and opponent holdings.
7. Calculate raw showdown equity.
8. Generate the hero's legal actions and candidate sizes.
9. Simulate opponents in correct action order.
10. Estimate the net chip value of each candidate action.
11. Present the recommendation together with assumptions and uncertainty.

The poker engine is independent of the PySide6 interface. The interface constructs a validated game state, sends it to the analysis service, and displays the returned result.

---

# Mathematical Model

## Deck State and Combinatorics

Texas Hold'em uses a 52-card deck. Let:

- \(K\) be the number of known cards
- \(U = 52-K\) be the number of unseen cards
- \(n\) be the number of future board cards still to come
- \(m\) be the number of unknown opponents

The number of ways to choose \(r\) unordered objects from \(N\) is the binomial coefficient:

```math
\binom{N}{r}
=
\frac{N!}{r!(N-r)!}.
```

Before the flop, only the hero's two cards are known, so one unknown opponent can hold:

```math
\binom{50}{2}
=
1{,}225
```

different two-card combinations.

On the river, the hero's two cards and all five board cards are known. One unknown opponent can then hold:

```math
\binom{45}{2}
=
990
```

different combinations before range filtering.

### Ordered versus unordered runouts

On the flop, 47 cards remain and two community cards are still to come.

If only the final five-card board matters, turn and river can be treated as an unordered pair:

```math
\binom{47}{2}
=
1{,}081.
```

If the order of the streets matters, there are:

```math
47 \times 46
=
2{,}162
```

ordered turn-river sequences.

Peaceful Poker can use unordered runouts for final-hand distributions because the final seven-card set is unchanged by swapping the turn and river. A street-by-street betting model must preserve the order because an opponent may react differently on the turn than on the river.

---

## Five-Card Hand Ordering

Hands are ranked from strongest to weakest:

| Rank | Category |
|---:|---|
| 1 | Straight Flush |
| 2 | Four of a Kind |
| 3 | Full House |
| 4 | Flush |
| 5 | Straight |
| 6 | Three of a Kind |
| 7 | Two Pair |
| 8 | One Pair |
| 9 | High Card |

A Royal Flush is an ace-high straight flush and can be displayed separately without requiring a distinct mathematical category.

Each evaluated hand is represented by:

1. A category rank
2. A lexicographically ordered tie-break tuple

For example:

```text
A♠ A♦ K♣ 9♥ 4♠
```

can be represented conceptually as:

```text
Category: One Pair
Tie break: (Ace, King, Nine, Four)
```

The comparison first checks the category. If the categories match, it compares the tuple from left to right.

Examples:

- **One pair:** pair rank, then three kickers
- **Two pair:** higher pair, lower pair, kicker
- **Three of a kind:** trip rank, then two kickers
- **Straight:** highest straight card
- **Flush:** all five cards from highest to lowest
- **Full house:** trip rank, then pair rank
- **Four of a kind:** quad rank, then kicker

The wheel \(A\text{-}2\text{-}3\text{-}4\text{-}5\) is assigned a high card of five, so it correctly loses to every six-high or better straight.

---

## Best Five Cards From Seven

At showdown, a player chooses the strongest five-card subset from two hole cards and five community cards. The number of five-card subsets is:

```math
\binom{7}{5}
=
\frac{7!}{5!2!}
=
21.
```

The evaluator scores all 21 subsets and keeps the maximum.

This correctly handles hands that use:

- both hole cards
- exactly one hole card
- no hole cards

Example:

```text
Hero:  A♣ 2♦
Board: K♠ K♥ Q♠ Q♦ J♣
```

The best hand is:

```text
K-K-Q-Q-A
```

Only the ace from the hero's hand is used.

If the board is:

```text
A♠ K♠ Q♠ J♠ 10♠
```

the board itself is the best hand for every active player, so the pot is split.

---

## Draws, Outs, and Overlap

An **out** is an unseen card that improves the hero's final hand according to a defined criterion.

Common structures include:

- open-ended straight draws
- gutshot and double-gutshot straight draws
- flush draws
- backdoor straight or flush draws
- pair-to-two-pair improvements
- pair-to-trips improvements
- two-pair-to-full-house improvements
- set-to-full-house or quads improvements
- combination draws

### Straight-draw examples

For:

```text
6-7-8-9
```

a five or ten completes a straight. If every relevant card is unseen, the apparent-out count is:

```math
4 + 4 = 8.
```

For:

```text
6-7-9-10
```

only an eight completes the straight:

```math
4
```

apparent outs.

### Flush-draw example

A suit contains 13 cards. If four cards of that suit are visible between the hero's hand and board, then:

```math
13-4=9
```

cards of that suit remain unseen.

### Overlapping outs

Out sets cannot always be added directly. Let \(A\) be the straight-completing cards and \(B\) the flush-completing cards. The number of unique cards is:

```math
|A \cup B|
=
|A|+|B|-|A \cap B|.
```

A card such as the jack of spades may complete both a straight and a flush, but it is still one physical card. The application avoids double counting by storing actual card identities and taking their set union.

### Apparent outs versus clean outs

Peaceful Poker uses the term **apparent outs** because an improving card does not necessarily produce a winning hand.

Examples:

- A flush card may complete a higher opponent flush.
- A paired river may improve the hero to two pair while giving an opponent a full house.
- A straight card may create a higher straight for part of the opponent's range.
- An overcard may make top pair but also improve an opponent to two pair.

The probability of improving and the probability of winning are therefore different quantities.

---

## Exact Runout Probabilities

Suppose there are \(U\) unseen cards, \(o\) apparent outs, and \(n\) cards still to come.

The exact number of hits among the next \(n\) cards follows a hypergeometric distribution:

```math
P(X=k)
=
\frac{
\binom{o}{k}
\binom{U-o}{n-k}
}{
\binom{U}{n}
}.
```

This model is appropriate because cards are drawn **without replacement**.

### One card to come

On the turn, six cards are known, leaving \(U=46\) possible river cards. With \(o\) apparent outs:

```math
P(\text{hit on river})
=
\frac{o}{46}.
```

For nine apparent flush outs:

```math
P(\text{flush card on river})
=
\frac{9}{46}
\approx 0.1957
=
19.57\%.
```

### Two cards to come

On the flop, five cards are known, leaving \(U=47\). The probability of missing all \(o\) outs on both remaining streets is:

```math
P(\text{miss both})
=
\frac{
\binom{47-o}{2}
}{
\binom{47}{2}
}.
```

The same expression can be written sequentially:

```math
P(\text{miss both})
=
\frac{47-o}{47}
\cdot
\frac{46-o}{46}.
```

Therefore:

```math
P(\text{hit at least once})
=
1-
\frac{47-o}{47}
\cdot
\frac{46-o}{46}.
```

For nine apparent flush outs:

```math
P(\text{hit by river})
=
1-
\frac{38}{47}
\cdot
\frac{37}{46}
\approx 0.3497
=
34.97\%.
```

The familiar “rule of four and two” is only a mental approximation. Exact enumeration or the hypergeometric formula is preferred when the software has access to the full state.

---

## Final-Hand Distributions

Rather than counting only named outs, Peaceful Poker can evaluate the completed hand for every legal runout.

Let \(\mathcal{B}\) be the set of legal future boards and let \(H(b)\) be the final hand category produced by runout \(b\). For category \(c\):

```math
P(H=c)
=
\frac{
|\{b \in \mathcal{B}:H(b)=c\}|
}{
|\mathcal{B}|
}.
```

Because final hand categories are mutually exclusive, their probabilities should sum to one:

```math
\sum_c P(H=c)=1.
```

An “at least” probability is the sum of all categories at or above a threshold. For example:

```math
P(\text{at least a straight})
=
P(\text{straight})
+
P(\text{flush})
+
P(\text{full house})
+
P(\text{quads})
+
P(\text{straight flush}).
```

This final-state approach is more reliable than raw out counting because it automatically handles overlapping improvements and situations where a nominal out produces a stronger category than expected.

---

# Showdown Equity

## Pot-Share Definition

Showdown equity is the expected fraction of the pot awarded to the hero if all players included in the showdown model continue to the end.

For simulation or exact state \(i\), define the hero's pot share \(S_i\) as:

```math
S_i
=
\begin{cases}
1, & \text{hero wins outright},\\
1/t_i, & \text{hero ties with } t_i-1 \text{ other winners},\\
0, & \text{hero loses}.
\end{cases}
```

The equity over \(N\) equally weighted states is:

```math
E
=
\frac{1}{N}
\sum_{i=1}^{N} S_i.
```

In a heads-up game this reduces to:

```math
E
=
P(\text{win})
+
\frac{1}{2}P(\text{tie}).
```

In a multiway game, a three-way tie contributes \(1/3\), a four-way tie contributes \(1/4\), and so on. Equity can therefore differ from both raw win percentage and raw tie percentage.

---

## Exact Enumeration

Exact enumeration visits every legal state in the selected state space.

For a completed river board against one unrestricted opponent:

1. Remove the hero's cards and board.
2. Generate all \(\binom{45}{2}=990\) opponent holdings.
3. Filter combinations excluded by the opponent range.
4. Evaluate the hero and opponent.
5. Record the hero's pot share.
6. Average the shares.

If the surviving range is \(\mathcal{R}\), unweighted exact equity is:

```math
E
=
\frac{1}{|\mathcal{R}|}
\sum_{h \in \mathcal{R}} S(h).
```

The current range presets behave as filters rather than solver-derived frequency weights. Every surviving legal combination is therefore treated uniformly unless a future model explicitly supplies weights.

Exact enumeration has no Monte Carlo sampling error. It can still be wrong as a model of a real player if the selected range is inaccurate.

---

## Multiway State-Space Growth

State spaces grow rapidly as opponents and unknown board cards are added.

If opponents are labelled by seat, a rough count for \(m\) unrestricted opponents and an unordered \(n\)-card future board is:

```math
\left[
\prod_{j=0}^{m-1}
\binom{U-2j}{2}
\right]
\binom{U-2m}{n}.
```

This expression enforces card removal by reducing the available deck after each opponent is assigned two cards.

For two labelled opponents on a completed board:

```math
\binom{45}{2}
\binom{43}{2}
=
990 \times 903
=
893{,}970
```

joint assignments exist before range filtering.

For a preflop six-player hand, the combination of five opponent holdings and a five-card board is vastly larger. This combinatorial explosion is why exact enumeration is reserved for practical cases and Monte Carlo simulation is used elsewhere.

---

# Opponent Ranges and Card Removal

A range is a set of possible two-card combinations.

Supported notation includes forms such as:

```text
AA
AKs
AQo
99+
ATs+
22-88
```

where:

- `s` means suited
- `o` means offsuit
- `+` extends through stronger holdings according to the parser's ordering
- `22-88` represents a pair interval

## Combination counts

Before blockers:

- A specific pocket pair has \(\binom{4}{2}=6\) combinations.
- A specific suited non-pair hand has 4 combinations.
- A specific offsuit non-pair hand has \(4 \times 3=12\) combinations.
- A non-pair hand with no suit restriction has \(4 \times 4=16\) combinations.

For example:

```math
|\text{AKs}|=4,
\qquad
|\text{AKo}|=12,
\qquad
|\text{AK}|=16.
```

## Blockers

Known cards remove combinations from the range.

If the hero holds \(A\spadesuit K\spadesuit\), the opponent cannot hold either card. The suited `AKs` combinations fall from four to three because \(A\spadesuit K\spadesuit\) is blocked.

Blockers affect more than the number of hands. They change the relative frequency of value hands, draws, and bluffs inside a surviving range. The engine therefore filters concrete combinations after removing all known cards rather than applying only a percentage adjustment.

---

# Monte Carlo Simulation

Monte Carlo simulation estimates a quantity by repeatedly sampling legal hidden states.

One trial can include:

1. Sampling non-overlapping opponent holdings from their ranges
2. Sampling future board cards without replacement
3. Evaluating each remaining player's best hand
4. Simulating legal opponent actions
5. Updating pot and stack contributions
6. Recording hero pot share or net chip return

Tests use fixed random seeds for reproducibility. Normal interactive runs may use varying seeds.

---

## Estimator

For showdown equity, let \(S_i\in[0,1]\) be the hero's pot share in trial \(i\). The Monte Carlo estimator is:

```math
\widehat{E}_N
=
\frac{1}{N}
\sum_{i=1}^{N} S_i.
```

For a pure win probability, define an indicator:

```math
W_i
=
\begin{cases}
1, & \text{hero wins outright in trial }i,\\
0, & \text{otherwise}.
\end{cases}
```

Then:

```math
\widehat{p}_{\text{win}}
=
\frac{1}{N}
\sum_{i=1}^{N} W_i.
```

The same indicator construction estimates fold, call, raise, showdown, and all-in frequencies.

---

## Variance and Standard Error

The sample variance of the observed pot shares is:

```math
s^2
=
\frac{1}{N-1}
\sum_{i=1}^{N}
\left(S_i-\widehat{E}_N\right)^2.
```

The estimated standard error of the equity mean is:

```math
SE(\widehat{E}_N)
=
\frac{s}{\sqrt{N}}.
```

For a binary probability with estimated value \(\widehat{p}\), the familiar approximation is:

```math
SE(\widehat{p})
\approx
\sqrt{
\frac{
\widehat{p}(1-\widehat{p})
}{
N
}
}.
```

Pot-share equity is not always binary because ties contribute fractions, so the sample-variance formula is more general.

---

## Confidence Intervals

For a sufficiently large sample, an approximate 95% confidence interval for the mean is:

```math
\widehat{E}_N
\pm
1.96\,
SE(\widehat{E}_N).
```

Example: suppose the estimated win probability is 40% after 10,000 independent trials.

```math
SE
\approx
\sqrt{
\frac{0.4(1-0.4)}{10{,}000}
}
\approx
0.00490.
```

The approximate interval is:

```math
0.40
\pm
1.96(0.00490)
=
0.40
\pm
0.0096.
```

That is approximately:

```text
39.04% to 40.96%
```

This does not mean there is a literal 95% probability that one fixed interval contains the true value. The repeated-sampling interpretation is that the method produces intervals covering the target about 95% of the time under its assumptions.

Normal intervals are approximate and can be less reliable for small samples or probabilities near zero or one.

---

## Convergence Rate

Monte Carlo standard error decreases proportionally to:

```math
\frac{1}{\sqrt{N}}.
```

Therefore:

- multiplying the simulation count by 4 approximately halves the standard error
- multiplying it by 9 approximately divides the standard error by 3
- doubling the number of simulations does **not** halve the error

A conservative concentration result for bounded outcomes \(S_i\in[0,1]\) is Hoeffding's inequality:

```math
P\left(
\left|
\widehat{E}_N-E
\right|
\ge \varepsilon
\right)
\le
2e^{-2N\varepsilon^2}.
```

Solving for \(N\), a sufficient sample size for error at most \(\varepsilon\) with failure probability at most \(\delta\) is:

```math
N
\ge
\frac{
\ln(2/\delta)
}{
2\varepsilon^2
}.
```

This bound is deliberately conservative, but it shows why very precise Monte Carlo estimates require many samples.

---

## Sampling Error Versus Model Error

Two different uncertainties must be separated.

### Sampling error

Sampling error comes from using a finite number of random trials. It can be reduced by increasing \(N\), and it is summarized by standard errors or confidence intervals.

### Model error

Model error comes from assumptions such as:

- an inaccurate opponent range
- an inappropriate opponent profile
- simplified fold, call, and raise frequencies
- a bounded action tree
- excluded future betting
- omitted rake
- unmodelled opponent adaptation

Increasing the simulation count does not correct model error.

An exact calculation under the wrong range is exactly wrong for that assumed model. More Monte Carlo trials only estimate the chosen model more precisely.

---

# Action-Aware Opponent Modelling

Raw showdown equity assumes the included players reach showdown. Real decisions occur before that outcome is known.

A player behind the hero may fold, call, raise, or move all-in. The action-aware model treats those responses as random variables and estimates the value of the hero's decision under the selected opponent profiles.

---

## Action Order

Peaceful Poker tracks:

- button position
- small blind and big blind
- current actor
- folded players
- all-in players
- players who have already acted
- players still eligible to act

In a standard multiway hand:

- preflop action begins to the left of the big blind
- postflop action begins with the first active player to the left of the button

In heads-up play:

- the button posts the small blind
- the button acts first preflop
- the big blind acts first postflop

Folded and all-in players are skipped when selecting the next player able to act.

---

## Policy Distributions

For opponent \(j\), the model produces a probability distribution over the legal action set \(\mathcal{A}_j\):

```math
\sum_{a \in \mathcal{A}_j}
P_j(a \mid x)
=
1,
```

where \(x\) represents the simulated state.

When facing a bet, the action set may contain:

```math
\mathcal{A}_j
=
\{
\text{fold},
\text{call},
\text{raise},
\text{all-in}
\}.
```

The rule-based probabilities may depend on:

- sampled opponent cards
- made-hand and draw strength
- selected opponent profile
- range
- board texture
- pot and call amount
- bet size relative to the pot
- stack-to-pot ratio
- seat position
- number of active opponents
- prior aggression

Illegal actions receive no probability mass.

The supported profiles are educational abstractions such as Tight Passive, Loose Passive, Tight Aggressive, Loose Aggressive, Calling Station, Nit, Maniac, and Unknown/Balanced. They are not empirically calibrated population models.

---

## Conditional Equity

Equity conditional on being called differs from unconditional showdown equity.

Let \(C_i\) indicate that at least one opponent continues against the hero's bet in trial \(i\). Then conditional equity can be estimated by:

```math
\widehat{E}_{\text{called}}
=
\frac{
\sum_{i=1}^{N} C_i S_i
}{
\sum_{i=1}^{N} C_i
}.
```

This value is often lower than unconditional equity because weak opposing hands fold more frequently while stronger hands continue.

The action-aware output can distinguish:

- raw showdown equity
- probability everyone folds
- probability exactly one opponent continues
- probability multiple opponents continue
- probability of facing a raise
- probability of reaching showdown
- equity conditional on continuation

These quantities answer different questions and should not be merged into a single “adjusted equity” number.

---

## Fold Equity

Let \(F\) be the event that every opponent folds to the hero's bet. The fold-equity probability is:

```math
P(F).
```

Under an unrealistic independence assumption with opponent fold probabilities \(f_1,\ldots,f_m\), it would be:

```math
P(F)
=
\prod_{j=1}^{m} f_j.
```

The simulator does not need to rely on that simplification. It samples responses sequentially in action order, allowing later decisions to depend on the updated state and earlier responses.

---

# Pot Odds and Expected Value

## Break-Even Equity

Let:

- \(P\) be the current pot, including the opponent's current bet
- \(C\) be the additional amount the hero must call

The final pot after the hero calls is:

```math
P_{\text{final}}
=
P+C.
```

The break-even equity is:

```math
E_{\text{break-even}}
=
\frac{C}{P+C}.
```

Example:

```text
Current pot: 140
Amount to call: 40
```

Then:

```math
E_{\text{break-even}}
=
\frac{40}{140+40}
=
\frac{40}{180}
\approx
22.22\%.
```

The opponent's current bet is already part of \(P\), so it must not be added a second time.

---

## Call EV

From the current decision point:

- winning produces net profit \(P\)
- losing costs \(C\)
- ties are already represented through fractional equity

With equity \(E\):

```math
EV_{\text{call}}
=
E P
-
(1-E)C.
```

An equivalent form is:

```math
EV_{\text{call}}
=
E(P+C)-C.
```

Setting call EV equal to zero gives the same break-even threshold:

```math
0
=
E(P+C)-C
\quad\Longrightarrow\quad
E
=
\frac{C}{P+C}.
```

Example with 35% equity:

```math
EV_{\text{call}}
=
0.35(140)
-
0.65(40)
=
49-26
=
23.
```

Under the simplified one-decision model, the call is worth an average of positive 23 chips relative to folding.

From the present decision point:

```math
EV_{\text{fold}}=0.
```

Earlier contributions are sunk costs and are not counted again.

---

## Bet EV

For a simplified heads-up bet of size \(B\), let:

- \(F\) be the probability the opponent folds
- \(E_c\) be hero equity conditional on being called
- \(P\) be the pot before the hero bets

If a call matches the bet, the simplified EV is:

```math
EV_{\text{bet}}
=
F P
+
(1-F)
\left[
E_c(P+B)
-
(1-E_c)B
\right].
```

The bracketed term can also be written:

```math
E_c(P+2B)-B.
```

The first term, \(FP\), is the value of winning the existing pot immediately. The hero's own bet is returned when everyone folds, so it is not counted as additional profit.

This compact formula is useful for explanation, but the full action-aware simulator uses actual stack caps, callers, raises, and multiway pot shares rather than assuming one caller and one fixed response.

---

## General Action EV

For hero action \(a\), let \(Z\) represent all uncertain future information:

- opponent cards
- board runout
- folds
- calls
- raises
- all-ins
- final pot
- showdown result

The theoretical value is:

```math
EV(a)
=
\mathbb{E}[R(a,Z)],
```

where \(R(a,Z)\) is the hero's net chip return measured from the current decision.

Monte Carlo estimates this with:

```math
\widehat{EV}_N(a)
=
\frac{1}{N}
\sum_{i=1}^{N}
R_i(a).
```

The return convention is:

```math
R_i(a)
=
\text{chips returned to hero}
-
\text{additional chips invested after the decision}.
```

This convention keeps previous contributions as sunk costs and allows every legal action to be compared from the same decision point.

---

## Uncertainty in EV

EV outcomes may vary much more than win indicators because one trial can win a small pot while another loses an entire effective stack.

For returns \(R_1,\ldots,R_N\), the sample mean is:

```math
\overline{R}
=
\frac{1}{N}
\sum_{i=1}^{N}R_i.
```

The sample variance is:

```math
s_R^2
=
\frac{1}{N-1}
\sum_{i=1}^{N}
(R_i-\overline{R})^2.
```

The estimated standard error is:

```math
SE(\overline{R})
=
\frac{s_R}{\sqrt{N}}.
```

An approximate 95% interval is:

```math
\overline{R}
\pm
1.96
\frac{s_R}{\sqrt{N}}.
```

If two actions have estimated EVs that are close relative to their standard errors, the statistical evidence is weak. The recommendation should describe the decision as close rather than implying false precision.

A useful comparison quantity is the EV difference:

```math
\Delta_{a,b}
=
EV(a)-EV(b).
```

The sign of \(\Delta_{a,b}\) identifies the preferred action under the model, while its uncertainty indicates how stable that ranking is.

---

# Worked Example

Consider:

```text
Players:        6
Hero position:  Button
Hero cards:     A♠ K♠
Flop:           Q♠ 10♦ 4♠
Current pot:    140
Amount to call: 40
Hero stack:     900
Effective stack: 620
```

## Current hand and draws

The hero currently has ace-high, plus:

- nut flush draw
- gutshot Broadway draw
- two overcards against some holdings
- combination-draw potential

Any remaining spade completes an ace-high flush. Any jack completes \(A\text{-}K\text{-}Q\text{-}J\text{-}10\).

The jack of spades belongs to both sets, so a naive count of \(9+4=13\) double counts it. The number of unique apparent outs is:

```math
9+4-1=12.
```

This does not mean every one of the 12 cards guarantees a win.

## Approximate improvement probability

With 12 unique apparent outs and two cards to come:

```math
P(\text{hit at least once})
=
1-
\frac{35}{47}
\cdot
\frac{34}{46}
\approx
44.96\%.
```

This is an improvement probability, not showdown equity.

## Pot odds

```math
E_{\text{break-even}}
=
\frac{40}{140+40}
\approx
22.22\%.
```

If the hero's estimated equity against the relevant continuing range is well above 22.22%, a call can be profitable under the simplified call model.

## Why players behind matter

Suppose two players remain to act after the hero. They may fold, call, or raise. Their decisions affect:

- the probability of reaching showdown
- the number of opponents at showdown
- the final pot size
- the hero's additional investment
- the probability of facing a raise
- conditional equity against the continuing range

Raw equity and action EV must therefore remain separate.

---

# Recommendation System

The recommendation layer compares only legal actions.

Possible actions include:

- check
- fold
- call
- small, medium, or large bet
- small, medium, or large raise
- all-in

The model considers:

- raw showdown equity
- required equity and pot odds
- simplified call EV
- action-aware EV
- all-fold probability
- continuation and raise probabilities
- equity conditional on continuation
- current hand and draw strength
- board texture
- position and action order
- stack-to-pot ratio
- opponent ranges and profiles
- simulation uncertainty

Recommendations are intentionally qualified. A suitable conclusion is:

> Calling has the highest estimated value under the entered ranges and opponent profiles.

The application should not claim that one action is certainly correct in the real game.

---

# Architecture

```text
src/poker_trainer/
├── engine/       Hand evaluation, draws, ranges, exact probability, and simulation
├── models/       Cards, game state, players, results, and recommendations
├── resources/    Themes, configuration, profiles, and artwork
├── services/     Analysis orchestration, persistence, exports, settings, and logging
├── strategy/     Legal actions, pot odds, sizing, EV, and recommendation rules
├── training/     Practice-scenario generation
├── ui/           PySide6 interface and cancellable worker integration
└── utils/        Shared support utilities
```

Long calculations run in a worker thread so the interface remains responsive. Worker completion stops and cleans up the worker thread without closing the application. Closing the window requests cancellation and waits for active work to finish safely.

Saved hands use a versioned JSON schema, while analysis reports can be exported as Markdown or JSON.

---

# Install and Run

## Windows

```powershell
git clone https://github.com/Infiniteiiii/Peaceful_Poker.git
cd Peaceful_Poker

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev,build]"
python -m poker_trainer
```

The installed command also launches the app:

```powershell
peaceful-poker
```

## macOS or Linux

```bash
git clone https://github.com/Infiniteiiii/Peaceful_Poker.git
cd Peaceful_Poker

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m poker_trainer
```

The Windows `.exe` does not run natively on macOS. macOS users should run the Python source or create a separate macOS build on a Mac.

## Valid board lengths

| Street | Community cards |
|---|---:|
| Preflop | 0 |
| Flop | 3 |
| Turn | 4 |
| River | 5 |

`Current pot` includes all chips already in the middle, including the opponent's current bet, but excludes the hero's pending call.

---

# Tests and Builds

Run all quality checks from the repository root:

```powershell
python -m pytest -p no:cacheprovider
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pip check
```

GitHub Actions runs the test suite on supported Python versions with Qt configured for headless testing.

Build the Windows one-folder release:

```powershell
.\scripts\build_windows.ps1
```

Output:

```text
dist\Peaceful Poker\Peaceful Poker.exe
```

Distribute the complete `dist\Peaceful Poker` folder, not only the executable.

Run source and packaged verification with:

```powershell
.\scripts\verify.ps1
```

---

# Saved Data and Documentation

Windows application data is stored under:

```text
%LOCALAPPDATA%\Peaceful Poker
```

On macOS it is normally stored under a location similar to:

```text
~/Library/Application Support/Peaceful Poker
```

Additional documentation:

- `CHANGELOG.md`
- `docs/action_aware_methodology.md`
- `docs/architecture.md`
- `docs/equity_and_strategy.md`
- `docs/release_checklist.md`
- `docs/save_schema.md`
- `docs/testing_plan.md`
- `docs/testing_strategy.md`

---

# Limitations

- Peaceful Poker is not a GTO solver.
- Opponent profiles are rule-based assumptions, not calibrated predictions.
- Range presets are simplified combination filters rather than solver frequency tables.
- Apparent outs are not guaranteed clean.
- Exact enumeration removes sampling error but not incorrect assumptions.
- Monte Carlo confidence intervals describe sampling uncertainty, not total model uncertainty.
- Basic call EV excludes future betting, rake, implied odds, reverse implied odds, tournament utility, and opponent adaptation.
- Action-aware simulation uses a bounded policy model rather than an exhaustive multi-street game tree.
- Real opponents can behave differently from their selected profile.
- No finite model can know hidden cards or future human decisions with certainty.

---

# Troubleshooting

## `pyproject.toml` not found

Run installation commands from the repository root:

```powershell
Test-Path .\pyproject.toml
```

The result should be `True`.

## Application does not open

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip check
python -X faulthandler -m poker_trainer
```

## Analysis is slow

Use a lower simulation preset. Action-aware analysis evaluates multiple candidate actions and is therefore more expensive than one raw-equity estimate.

## OneDrive pytest cache warning

```powershell
python -m pytest -p no:cacheprovider
```

## Windows build fails

```powershell
python -m pip install -e ".[dev,build]"
python -m pip check
.\scripts\build_windows.ps1
```

---

# Educational Disclaimer

Peaceful Poker provides probability estimates and educational decision guidance under simplified mathematical and behavioural assumptions.

A positive expected value is a long-run average under the model. It does not guarantee that an individual hand will win, and a recommendation does not guarantee profit.

Users are responsible for following applicable laws, platform rules, and responsible-gaming practices.
