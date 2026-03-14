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
4. **Web UI** — Browser-based interface to configure and run the optimizer with real-time progress streaming

## Quick start

### Web UI (recommended)

```bash
pip install -e ".[web]"
python -m poktcg.web
```

Open **http://localhost:8000** in your browser. From there you can:

1. **Pick starting archetypes** — check any combination of Haymaker, Raindance, and Damage Swap to seed the initial population (or none to start from scratch)
2. **Choose optimization mode**:
   - *Best overall deck* — coevolution with self-play and Hall of Fame
   - *Best counter to...* — genetic optimizer targeted against specific archetypes
3. **Set search depth**:
   - Quick (~1 min) — 20 pop, 15 generations, 15 games/eval
   - Normal (~3 min) — 30 pop, 30 generations, 20 games/eval
   - Deep (~8 min) — 50 pop, 50 generations, 30 games/eval
4. **Select card pool** — Base only, Base + Jungle, Base + Jungle + Fossil, or All (+ Promos)
5. **Click Run** and watch real-time progress: generation counter, progress bar, best/avg fitness

Results include:
- **Deck list** — card image thumbnails in a grid with count badges, grouped by Pokemon / Trainer / Energy
- **Simulation insights** — total games played, games/sec, total time, avg turns/game, and win condition breakdown (prizes taken, no Pokemon left, deck out)
- **Matchup table** — win rates vs seed archetypes (color-coded green/yellow/red)
- **Fitness chart** — best and average fitness over generations
- **Card frequency** — which cards appear across all top-3 decks

Time estimates assume multi-core execution. The app auto-detects your CPU cores and parallelizes game simulations accordingly.

### CLI

```bash
pip install -e .

# Run 100 test games
python3 scripts/run_game.py

# Run the genetic optimizer
python3 scripts/run_optimizer.py

# Run the coevolution optimizer
python3 scripts/run_optimizer.py --coevolution
```

## Project structure

```
src/poktcg/
├── cards/          # Card database, effects, trainer/attack implementations
├── engine/         # Game state, turn loop, damage pipeline, actions
├── ai/             # Random and heuristic AI players
├── optimizer/      # Genetic algorithm, coevolution, deck representation, archetypes
└── web/            # FastAPI app, optimization runner, single-page HTML UI
data/cards/         # Card data JSON (from PokemonTCG/pokemon-tcg-data)
scripts/            # Runnable CLI scripts
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

The **coevolution** mode adds self-play and a Hall of Fame — decks compete against each other and against historically strong decks, with a diversity bonus to avoid converging on a single strategy.

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
