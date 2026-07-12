# Save Schema

Saved hands are JSON documents with `schema_version` set to `1`.

Required fields include:

- `game_type`
- `active_players`
- `hero_cards`
- `community_cards`
- `hero_position`
- `pot_size`
- `amount_to_call`
- `hero_stack`
- `effective_stack`
- `small_blind`
- `big_blind`
- `ante`
- `requested_simulation_count`
- `opponent_range`

The loader rejects invalid JSON, unsupported future schema versions, missing
required fields, and duplicate card states through the normal `GameState`
validation path.