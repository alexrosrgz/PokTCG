"""Wraps optimizer invocation for the web UI."""

from __future__ import annotations

import time
from collections.abc import Callable

from poktcg.cards.card_db import get_card_db, reset_card_db
from poktcg.optimizer.archetypes import ARCHETYPE_BUILDERS, ARCHETYPE_NAMES, make_haymaker, make_raindance, make_damage_swap
from poktcg.optimizer.coevolution import CoevolutionConfig, CoevolutionOptimizer
from poktcg.optimizer.deck import Deck
from poktcg.optimizer.genetic import GeneticOptimizer, OptimizerConfig
from poktcg.optimizer.simulator import Simulator


DEPTH_PRESETS = {
    "quick": {"population_size": 20, "generations": 15, "games_per_eval": 15},
    "normal": {"population_size": 30, "generations": 30, "games_per_eval": 20},
    "deep": {"population_size": 50, "generations": 50, "games_per_eval": 30},
}

CARD_POOL_SETS = {
    "base": ["base1"],
    "base_jungle": ["base1", "base2"],
    "base_jungle_fossil": ["base1", "base2", "base3"],
    "all": ["base1", "base2", "base3", "basep"],
}


def _serialize_deck(deck: Deck) -> list[dict]:
    """Convert a deck to a JSON-friendly list of card entries."""
    db = get_card_db()
    result = []
    for cid, count in deck.cards.items():
        card = db.get(cid)
        entry = {
            "id": card.id,
            "name": card.name,
            "count": count,
            "supertype": card.supertype,
            "subtypes": card.subtypes,
            "hp": card.hp,
            "types": card.types,
            "set_id": card.set_id,
        }
        if card.is_pokemon:
            entry["attacks"] = [
                {"name": a.name, "cost": a.cost, "damage": a.damage}
                for a in card.attacks
            ]
            entry["weakness"] = [
                {"type": w.energy_type, "value": w.value}
                for w in card.weaknesses
            ]
            entry["resistance"] = [
                {"type": r.energy_type, "value": r.value}
                for r in card.resistances
            ]
            entry["retreat_cost"] = card.retreat_cost
        result.append(entry)
    return result


def run_optimization(
    archetypes: list[str],
    mode: str,
    counter_targets: list[str],
    depth: str,
    card_pool: str,
    progress_callback: Callable[[str, dict], None],
    num_workers: int = 1,
) -> dict:
    """Run the optimizer and return results.

    Args:
        archetypes: List of archetype keys to seed with
        mode: "coevolution" or "counter"
        counter_targets: Archetype keys to counter (for counter mode)
        depth: "quick", "normal", or "deep"
        card_pool: "base", "base_jungle", "base_jungle_fossil", or "all"
        progress_callback: Called with (event_type, data) for SSE streaming
        num_workers: Number of worker processes for simulation

    Returns:
        Dict with decks, matchups, fitness_history
    """
    # Set up card pool
    sets = CARD_POOL_SETS.get(card_pool, CARD_POOL_SETS["all"])
    reset_card_db()
    db = get_card_db(sets=sets)

    progress_callback("status", {"message": f"Loaded {len(db)} cards from {', '.join(sets)}"})
    
    import json
    from pathlib import Path
    custom_decks = {}
    try:
        saved_decks_file = Path(__file__).parent.parent.parent.parent / "data" / "decks" / "saved_decks.json"
        if saved_decks_file.exists():
            custom_decks = json.loads(saved_decks_file.read_text())
    except Exception:
        pass

    # Build seed decks
    seed_decks = []
    seed_names = []
    for key in archetypes:
        if key in ARCHETYPE_BUILDERS:
            try:
                deck = ARCHETYPE_BUILDERS[key]()
                valid, err = deck.validate()
                if valid:
                    seed_decks.append(deck)
                    seed_names.append(ARCHETYPE_NAMES[key])
            except (IndexError, KeyError):
                # Card not available in selected pool
                pass
        elif key in custom_decks:
            try:
                raw_deck = custom_decks[key]
                cards_list = raw_deck.get("cards", raw_deck) if isinstance(raw_deck, dict) else raw_deck
                cards = {c_data["id"]: c_data["count"] for c_data in cards_list}
                deck = Deck(cards=cards)
                valid, err = deck.validate()
                if valid:
                    seed_decks.append(deck)
                    seed_names.append(key)
                else:
                    progress_callback("status", {"message": f"Ignoring custom deck '{key}' (invalid: {err})"})
            except Exception as e:
                progress_callback("status", {"message": f"Ignoring custom deck '{key}' (format error/pool mismatch)"})
                pass

    if not seed_decks:
        progress_callback("status", {"message": "No valid seed decks; starting from scratch"})

    # Build config from depth preset
    preset = DEPTH_PRESETS.get(depth, DEPTH_PRESETS["normal"])

    fitness_history = []

    def on_progress(data: dict) -> None:
        event_type = data.pop("event", None)
        if event_type == "hof":
            progress_callback("hof", data)
        else:
            fitness_history.append({
                "gen": data["gen"],
                "best_fitness": data["best_fitness"],
                "avg_fitness": data["avg_fitness"],
            })
            progress_callback("generation", {
                "gen": data["gen"],
                "total": data["total"],
                "best_fitness": round(data["best_fitness"], 4),
                "avg_fitness": round(data["avg_fitness"], 4),
                "hof_size": data.get("hof_size", 0),
            })

    optimization_start = time.time()

    if mode == "counter" and counter_targets:
        # Use GeneticOptimizer against specific targets
        target_decks = []
        for key in counter_targets:
            if key in ARCHETYPE_BUILDERS:
                try:
                    deck = ARCHETYPE_BUILDERS[key]()
                    valid, _ = deck.validate()
                    if valid:
                        target_decks.append(deck)
                except (IndexError, KeyError):
                    pass

        if not target_decks:
            progress_callback("error", {"message": "No valid target decks for counter mode"})
            return {"error": "No valid target decks"}

        config = OptimizerConfig(
            population_size=preset["population_size"],
            generations=preset["generations"],
            games_per_eval=preset["games_per_eval"],
            mutation_rate=0.3,
            num_workers=num_workers,
        )
        optimizer = GeneticOptimizer(config=config, seed=42)
        progress_callback("status", {"message": "Running genetic optimizer (counter mode)..."})
        results = optimizer.run(
            seed_decks=seed_decks or None,
            opponent_decks=target_decks,
            verbose=False,
            on_progress=on_progress,
        )
    else:
        # Coevolution mode
        config = CoevolutionConfig(
            population_size=preset["population_size"],
            generations=preset["generations"],
            games_per_eval=preset["games_per_eval"],
            mutation_rate=0.3,
            elite_ratio=0.1,
            num_workers=num_workers,
            hof_size=10,
            hof_weight=0.4,
            hof_add_interval=3,
            games_per_hof_eval=preset["games_per_eval"],
            self_play_opponents=4,
            final_tournament_games=50,
            diversity_bonus=0.03,
            novelty_threshold=0.20,
        )
        optimizer = CoevolutionOptimizer(config=config, seed=42)
        progress_callback("status", {"message": "Running coevolution optimizer..."})
        results = optimizer.run(
            seed_decks=seed_decks or None,
            verbose=False,
            on_progress=on_progress,
        )

    optimization_elapsed = time.time() - optimization_start

    progress_callback("status", {"message": "Running matchup evaluation..."})

    # Serialize top 3 decks
    top_results = []
    for deck, fitness in results[:3]:
        top_results.append({
            "cards": _serialize_deck(deck),
            "fitness": round(fitness, 4),
            "total_cards": deck.total_cards(),
            "pokemon_count": deck.pokemon_count(),
            "trainer_count": deck.trainer_count(),
            "energy_count": deck.energy_count(),
        })

    # Matchup evaluation: best deck vs seed archetypes
    matchups = {}
    if seed_decks:
        sim = Simulator(num_workers=num_workers)
        best_deck = results[0][0]
        for name, seed_deck in zip(seed_names, seed_decks):
            result = sim.evaluate_matchup(best_deck, seed_deck, num_games=100)
            matchups[name] = round(result.win_rate, 4)

    # Card frequency across top 3 decks
    card_freq: dict[str, int] = {}
    for deck, _ in results[:3]:
        for cid in deck.cards:
            card_freq[cid] = card_freq.get(cid, 0) + 1

    # Cards appearing in all top 3
    common_cards = []
    for cid, freq in card_freq.items():
        if freq == min(3, len(results)):
            card = db.get(cid)
            common_cards.append({
                "id": card.id,
                "name": card.name,
                "supertype": card.supertype,
                "types": card.types,
                "frequency": freq,
            })

    # Gather simulation stats from the optimizer's simulator
    sim_stats = optimizer.sim
    total_games = sim_stats.total_games_played
    total_turns = sim_stats.total_turns_played
    reason_counts = dict(sim_stats.reason_counts)

    # Add games from matchup evaluation
    if seed_decks:
        total_games += sim.total_games_played
        total_turns += sim.total_turns_played
        for reason, count in sim.reason_counts.items():
            reason_counts[reason] = reason_counts.get(reason, 0) + count

    avg_turns = total_turns / max(1, total_games)
    games_per_sec = total_games / max(0.01, optimization_elapsed)

    # Build insights
    insights = {
        "total_games": total_games,
        "total_time_sec": round(optimization_elapsed, 1),
        "games_per_sec": round(games_per_sec, 1),
        "avg_turns_per_game": round(avg_turns, 1),
        "win_conditions": reason_counts,
    }

    return {
        "decks": top_results,
        "matchups": matchups,
        "fitness_history": fitness_history,
        "common_cards": common_cards,
        "insights": insights,
    }
