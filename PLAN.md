# PokTCG: Base-Fossil Format Engine & Deck Optimizer

## Context
**Goal:** Find the best possible deck in the Base-Fossil format (1999 Pokémon TCG rules) through automated simulation.

**Why:** No existing open-source engine covers this format. The closest options (RyuuPlay, TCG ONE) either lack Base-Fossil cards or have closed-source engines. We need to build a game engine that can play thousands of automated games, then use optimization to discover the strongest decks.

**Card Pool:** Base Set (102) + Jungle (64) + Fossil (62) + Promos 1-15 minus 11 (14) = **242 cards total**
- 203 Pokémon, 32 Trainers, 7 Energy types
- 71 simple damage-only attacks, ~207 unique effects to implement

**Card Data Source:** [PokemonTCG/pokemon-tcg-data](https://github.com/PokemonTCG/pokemon-tcg-data) — `base1.json`, `base2.json`, `base3.json`, `basep.json`
**Rules Source:** [jklaczpokemon.com](https://jklaczpokemon.com/pokemon-wotc-rules/), [Internet Archive WotC rulebook](https://archive.org/details/11_20230225)

---

## Decisions
- **Language:** Python (from scratch)
- **Priority:** Speed-to-result — minimize unnecessary abstractions, skip polish, get to the optimizer ASAP

## Tech Stack
- **Python 3.11+** (ML ecosystem, rapid prototyping, PyTorch MPS for future RL)
- **multiprocessing** for parallel simulation across M1 Pro cores
- **pytest** for minimal targeted tests (not exhaustive coverage)

---

## Project Structure

```
poktcg/
├── pyproject.toml
├── data/cards/                    # Raw JSON from pokemon-tcg-data
│   ├── base1.json, base2.json, base3.json, basep.json
├── src/poktcg/
│   ├── cards/
│   │   ├── card_db.py             # Load JSON, build card catalog
│   │   ├── effects.py             # Effect primitives & registry
│   │   ├── pokemon/               # Per-set card effect implementations
│   │   │   ├── base1.py, base2.py, base3.py, basep.py
│   │   ├── trainers.py            # All 32 trainer effects
│   │   └── energy.py              # Energy type definitions
│   ├── engine/
│   │   ├── state.py               # GameState, PlayerState, PokemonSlot
│   │   ├── actions.py             # Action types & legal action generation
│   │   ├── game.py                # Game loop, turn structure, effect propagation
│   │   ├── damage.py              # Damage calculation pipeline
│   │   └── rng.py                 # Seeded coin flips
│   ├── ai/
│   │   ├── player.py              # Abstract Player interface
│   │   ├── random_ai.py           # Random legal move player
│   │   ├── heuristic_ai.py        # Tactics-based AI
│   │   └── scoring.py             # State evaluation
│   └── optimizer/
│       ├── deck.py                # Deck representation & validation
│       ├── genetic.py             # Genetic algorithm optimizer
│       ├── simulator.py           # Parallel batch simulation
│       └── analysis.py            # Results & matchup reporting
├── tests/
└── scripts/
    ├── run_game.py
    ├── run_tournament.py
    └── run_optimizer.py
```

---

## Key 1999 Rules (Differences from Modern)
- Weakness = x2 damage (not +X)
- Resistance = -30
- Confusion self-damage (20) applies weakness/resistance
- Can retreat multiple times per turn
- No supporter limit — trainers can be played freely
- Winner of coin flip goes first AND can attack turn 1
- Mulligan gives opponent 2 extra cards (not 1)
- Pokemon Powers (not Abilities) — blocked by sleep/confusion/paralysis
- No stadium cards in this format

---

## Card Effect Implementation (3-Tier Hybrid)

### Tier 1: Auto-handled (~71 attacks)
Attacks with damage but no effect text. Engine handles automatically.

### Tier 2: Parameterized Primitives (~80 effects)
Common patterns mapped via config:
- `COIN_FLIP_BONUS_DAMAGE` — "Flip a coin. If heads, +X damage"
- `APPLY_STATUS_ON_FLIP` — "Flip a coin. If heads, defending is [status]"
- `SELF_DAMAGE` — "This attack does X to itself"
- `DISCARD_ENERGY` — "Discard N [type] energy"
- `MULTI_FLIP_DAMAGE` — "Flip N coins. X per heads"
- ~20-25 primitives total covering most patterns

### Tier 3: Custom Functions (~50-60 cards)
Bespoke Python for complex cards:
- Pokemon Powers: Alakazam (Damage Swap), Blastoise (Rain Dance), Mr. Mime (Invisible Wall), Muk (Toxic Gas), Venusaur (Energy Trans), Ditto (Transform), Gengar (Curse), Aerodactyl (Prehistoric Power)
- Complex trainers: Computer Search, Item Finder, Pokemon Breeder, Pokemon Trader, Scoop Up, Pokemon Center
- Complex attacks: Metronome, Amnesia, Transform, bench snipers

### Effect Propagation (Reducer Pattern from RyuuPlay)
All effects propagate through every card in play — cards can modify/block effects via before/after hooks. This handles interactions like Mr. Mime blocking damage >= 30 or Muk disabling all powers.

---

## Damage Pipeline
Order: Base damage → attack modifiers → PlusPower (+10 each) → Weakness (x2) → Resistance (-30) → Defender (-20 each) → minimum 0

---

## AI Strategy

### Level 1: Random AI (baseline for testing)
### Level 2: Heuristic Tactics AI (primary for simulation)
Priority-ordered decisions:
1. Play basics to bench
2. Evolve Pokemon
3. Attach energy (active priority)
4. Play draw trainers (Bill, Prof Oak)
5. Play disruption (Energy Removal, Gust of Wind)
6. Use Pokemon Powers
7. Play other trainers
8. Retreat if needed
9. Attack with best option
10. Pass

State scoring: prizes taken, HP remaining, bench size, energy advantage, hand size, opponent conditions.

### Level 3: 1-ply lookahead (for critical decisions)

---

## Deck Optimizer: Genetic Algorithm
- **Population:** 100 decks
- **Generations:** 200
- **Fitness:** Win rate over 50 games per evaluation
- **Selection:** Tournament selection, top 10% elite preservation
- **Crossover:** Combine Pokemon lines from one parent, trainers from another
- **Mutation:** Swap cards, adjust energy ratios, add/remove evolution lines
- **Repair:** Fix invalid decks (wrong count, no basics, >4 copies)
- **Seeding:** Initialize with known archetypes (Haymaker, Raindance, Damage Swap)

**Estimated runtime:** ~80-170 minutes for full optimization on M1 Pro (parallelized across 8 cores)

---

## Implementation Phases

### Phase 1: Foundation
**Goal:** Play a complete game between two hardcoded decks with Random AI.

1. Card database loader — parse 4 JSON files, build unified catalog
2. Core state model — GameState, PlayerState, PokemonSlot with fast clone()
3. Game loop — setup (shuffle, draw 7, mulligan, place actives, 6 prizes), turns, between-turns
4. Legal action generation
5. Damage pipeline (simple attacks only, with weakness/resistance)
6. Random AI
7. Win conditions (deck out, all KO'd, 6 prizes)

**Verify:** 1000 games run without crashes, all terminate, mirror matches ~50/50.

### Phase 2: Card Effects
**Goal:** All 242 cards functional.

8. Effect primitive library (~25 primitives)
9. Effect propagation system (before/after hooks)
10. Trainer card effects (all 32) — start with Bill, Prof Oak, Energy Removal, Gust of Wind, Computer Search
11. Pokemon Powers (~25 cards)
12. Complex attack effects (~60 remaining)
13. AI target selection for trainers/powers

**Verify:** Unit test each card. Cross-reference with TCG ONE Groovy implementations.

### Phase 3: Heuristic AI
**Goal:** AI that plays competently.

14. State scoring function
15. Tactics-based decision making
16. Trainer play intelligence
17. 1-ply lookahead for attack/retreat

**Verify:** Beats Random AI >90%. Known strong decks beat random decks >80%.

### Phase 4: Deck Optimizer
**Goal:** Discover the best deck.

18. Deck class with validation
19. Parallel simulator
20. Genetic algorithm
21. Seed with known archetypes
22. Analysis & matchup reporting

**Verify:** Optimizer rediscovers known archetypes (Haymaker, Raindance). Results converge.

### Phase 5: Polish & Meta Analysis
23. Performance profiling & optimization
24. Metagame simulation (optimizer vs its own best decks iteratively)
25. Game replay logs
26. Final "best deck" report with matchup tables

---

## Validation Checklist
- [ ] All 242 cards load from JSON correctly
- [ ] Games always terminate (no infinite loops)
- [ ] Mirror matches ~50% win rate
- [ ] Confusion self-damage applies weakness/resistance
- [ ] Multiple retreats per turn work
- [ ] Mulligan gives 2 cards
- [ ] Turn 1 attacks allowed
- [ ] Pokemon Powers blocked by sleep/confusion/paralysis
- [ ] Pokemon Breeder skips Stage 1
- [ ] Muk's Toxic Gas disables all powers
- [ ] Mr. Mime blocks damage >= 30
- [ ] Ditto copies defending Pokemon
- [ ] Heuristic AI beats Random AI >90%
- [ ] Optimizer converges on known strong archetypes

---

## Critical Files
- `src/poktcg/engine/state.py` — Core data model, must be fast to clone
- `src/poktcg/engine/game.py` — Game loop + effect propagation pipeline
- `src/poktcg/cards/effects.py` — Effect types, primitives, registry
- `src/poktcg/ai/heuristic_ai.py` — AI quality determines optimizer quality
- `src/poktcg/optimizer/genetic.py` — The optimization loop itself

## Reference Implementations
- [TCG ONE card DSL](https://github.com/axpendix/tcgone-engine-contrib) — Groovy implementations for card effects (cross-reference for correctness)
- [RyuuPlay](https://github.com/keeshii/ryuu-play) — TypeScript engine with effect reducer pattern and SimpleBot AI architecture
- [pret/poketcg](https://github.com/pret/poketcg) — Game Boy disassembly with original AI logic
