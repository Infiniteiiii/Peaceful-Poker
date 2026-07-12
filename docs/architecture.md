# Architecture

The project keeps poker logic independent from the graphical interface.

Current layers:

- `models`: immutable card, deck, and evaluated-hand data structures.
- `engine`: pure poker calculation functions.
- `ui`: PySide6 presentation code, added gradually after engine verification.

The evaluator is custom and compares hands using category strength followed by
category-specific tie-break values.
