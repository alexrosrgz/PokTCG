# PokTCG

A Pokemon TCG game engine and deck optimizer for the **Base-Fossil format** (1999 rules).

The goal: find the best possible deck through automated simulation.

## Format

**Base-Fossil** — the original 1999 competitive format:
- Base Set (102 cards)
- Jungle (64 cards)
- Fossil (62 cards)
- Promo cards 1-15 minus 11 (14 cards)
- **242 cards total**

## What it does

1. **Game Engine** — Plays full automated Pokemon TCG games using 1999 rules (weakness x2, resistance -30, unlimited trainers per turn, mulligans give 2 cards, etc.)
2. **AI Players** — Heuristic AI that plays competently (91.9% win rate vs random)
3. **Deck Optimizer** — Genetic algorithm that evolves decks over generations to find the strongest builds

## Quick start

```bash
# Run 100 test games
python3 scripts/run_game.py

# Run the deck optimizer
python3 scripts/run_optimizer.py
```

## Project structure

```
src/poktcg/
├── cards/          # Card database, effects, trainer/attack implementations
├── engine/         # Game state, turn loop, damage pipeline, actions
├── ai/             # Random and heuristic AI players
└── optimizer/      # Deck representation, genetic algorithm, simulation runner
data/cards/         # Card data JSON (from PokemonTCG/pokemon-tcg-data)
scripts/            # Runnable scripts
```

## Performance

- ~700-980 games/sec (single core, M1 Pro)
- 1000-game tournament in ~1-3 seconds
- Full 20-generation optimization in ~1 minute

## How the optimizer works

1. Starts with a population of decks (seeded with known archetypes like Haymaker, Raindance, Damage Swap)
2. Evaluates each deck by playing games against a field of opponents
3. Selects the best performers, crosses them over, mutates, and repeats
4. Converges on the strongest deck composition

## Card data

Card data sourced from [PokemonTCG/pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data) (JSON format with attacks, HP, weakness, resistance, effect text, etc.)

## 1999 Rules (key differences from modern)

- Weakness = x2 damage
- Resistance = -30
- No supporter limit — play unlimited trainers per turn
- Winner of coin flip goes first AND can attack turn 1
- Mulligan gives opponent 2 extra cards
- Confusion self-damage applies weakness/resistance
- Can retreat multiple times per turn
- Pokemon Powers blocked by sleep/confusion/paralysis
