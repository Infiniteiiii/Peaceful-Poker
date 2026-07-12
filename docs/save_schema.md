# Save Schema

Peaceful Poker 1.1 writes JSON documents with `schema_version` set to `2`.

The original hand fields remain: game type, player count, hero and community cards, hero position,
pot/call/stacks/blinds/ante, previous action, simulation count, range, notes, and optional summary.

Schema 2 adds `table_state` with button, blind, hero, current-actor, street, and per-seat data:

- seat and position
- hero/dealt/folded/all-in flags
- remaining stack and current/total contributions
- profile and range
- previous actions
- eligibility and already-acted status

The loader accepts valid schema 1 documents, creates a clockwise table from the saved player count
and hero position, assigns Unknown/Balanced opponents, and records that the source schema was 1.
The next save writes schema 2. Invalid JSON, future versions, duplicate cards, illegal table
references, negative stacks/contributions, folded-and-all-in players, and malformed action states
are rejected.
