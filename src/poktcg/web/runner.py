"""Wraps optimizer invocation for the web UI."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from itertools import combinations
from pathlib import Path

from poktcg.cards.card_db import get_card_db, reset_card_db
from poktcg.optimizer.archetypes import ARCHETYPE_BUILDERS, ARCHETYPE_NAMES
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

SAVED_DECKS_FILE = Path(__file__).parent.parent.parent.parent / "data" / "decks" / "saved_decks.json"


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


def _load_saved_decks() -> dict:
    try:
        if SAVED_DECKS_FILE.exists():
            return json.loads(SAVED_DECKS_FILE.read_text())
    except Exception:
        pass
    return {}


def _deck_from_saved_data(raw_deck) -> Deck:
    cards_list = raw_deck.get("cards", raw_deck) if isinstance(raw_deck, dict) else raw_deck
    if not isinstance(cards_list, list):
        raise ValueError("Deck must contain a cards list")

    cards: dict[str, int] = {}
    for entry in cards_list:
        if not isinstance(entry, dict):
            raise ValueError("Deck card entries must be objects")
        card_id = entry.get("id")
        count = entry.get("count")
        if not card_id or not isinstance(count, int):
            raise ValueError("Deck card entries must include id and integer count")
        if count <= 0:
            continue
        cards[card_id] = cards.get(card_id, 0) + count

    return Deck(cards=cards)


def _unique_names(names: list[str]) -> list[str]:
    unique = []
    seen = set()
    for name in names:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def _load_valid_saved_decks(names: list[str], saved_decks_data: dict) -> list[tuple[str, Deck]]:
    loaded = []
    for name in names:
        if name not in saved_decks_data:
            raise ValueError(f"Unknown saved deck: {name}")

        try:
            deck = _deck_from_saved_data(saved_decks_data[name])
        except Exception as exc:
            raise ValueError(f"Saved deck '{name}' has an invalid format") from exc

        valid, err = deck.validate()
        if not valid:
            raise ValueError(f"Saved deck '{name}' is invalid: {err}")

        loaded.append((name, deck))
    return loaded


def _build_matchup_label(pairing: dict) -> str:
    return f"{pairing['deck_a']} vs {pairing['deck_b']}"


def _format_matchup_highlight(pairing: dict | None, kind: str) -> dict | None:
    if not pairing:
        return None

    gap_pct = abs(pairing["win_rate_a"] - 0.5) * 100
    if kind == "closest":
        detail = f"{gap_pct:.1f} pt gap"
    elif kind == "lopsided":
        detail = f"{gap_pct:.1f} pt gap"
    else:
        detail = f"{pairing['avg_turns']:.1f} turns avg"

    return {
        "label": _build_matchup_label(pairing),
        "detail": detail,
    }


def _serialize_battle_matrix(participants: list[str], pairings: list[dict]) -> dict:
    lookup: dict[tuple[str, str], float] = {}
    for pairing in pairings:
        a = pairing["deck_a"]
        b = pairing["deck_b"]
        lookup[(a, b)] = pairing["win_rate_a"]
        lookup[(b, a)] = round(1 - pairing["win_rate_a"], 4)

    rows = []
    for row_name in participants:
        values = []
        for col_name in participants:
            if row_name == col_name:
                values.append(None)
            else:
                values.append(lookup.get((row_name, col_name)))
        rows.append({"name": row_name, "values": values})

    return {"headers": participants, "rows": rows}


def run_battleground(
    mode: str,
    rounds: int,
    deck_names: list[str],
    primary_deck: str | None,
    opponent_names: list[str],
    progress_callback: Callable[[str, dict], None],
    num_workers: int = 1,
    saved_decks_data: dict | None = None,
) -> dict:
    """Run saved decks against each other and return aggregate results."""
    try:
        rounds = int(rounds)
    except (TypeError, ValueError) as exc:
        raise ValueError("Rounds must be an integer") from exc

    if rounds < 1:
        raise ValueError("Rounds must be at least 1")
    if mode not in {"all_vs_all", "one_vs_all"}:
        raise ValueError("Invalid battleground mode")

    reset_card_db()
    db = get_card_db(sets=CARD_POOL_SETS["all"])
    progress_callback("status", {"message": f"Loaded {len(db)} cards for Battleground"})

    saved_decks_data = saved_decks_data if saved_decks_data is not None else _load_saved_decks()
    if not saved_decks_data:
        raise ValueError("No saved decks found")

    participants: list[str]
    matchups: list[tuple[str, Deck, str, Deck]]

    if mode == "all_vs_all":
        participants = _unique_names(deck_names)
        if len(participants) < 2:
            raise ValueError("All vs All requires at least 2 selected decks")
        loaded = _load_valid_saved_decks(participants, saved_decks_data)
        deck_by_name = {name: deck for name, deck in loaded}
        matchups = [
            (a_name, deck_by_name[a_name], b_name, deck_by_name[b_name])
            for a_name, b_name in combinations(participants, 2)
        ]
    else:
        if not primary_deck:
            raise ValueError("One vs All requires a primary deck")
        participants = [primary_deck]
        opponents = [name for name in _unique_names(opponent_names) if name != primary_deck]
        if not opponents:
            raise ValueError("One vs All requires at least 1 opponent deck")
        participants.extend(opponents)
        loaded = _load_valid_saved_decks(participants, saved_decks_data)
        deck_by_name = {name: deck for name, deck in loaded}
        matchups = [
            (primary_deck, deck_by_name[primary_deck], opp_name, deck_by_name[opp_name])
            for opp_name in opponents
        ]

    total_matchups = len(matchups)
    total_games = total_matchups * rounds
    progress_callback(
        "status",
        {
            "message": (
                f"Running Battleground with {len(participants)} decks, "
                f"{total_matchups} matchups, {total_games} total games"
            )
        },
    )

    standings_map = {
        name: {"name": name, "wins": 0, "losses": 0, "games": 0, "total_turns": 0}
        for name in participants
    }
    pairings = []
    aggregate_win_conditions: dict[str, int] = {}
    sim = Simulator(num_workers=num_workers)

    started_at = time.time()
    for matchup_index, (deck_a_name, deck_a, deck_b_name, deck_b) in enumerate(matchups, start=1):
        result = sim.evaluate_matchup(
            deck_a,
            deck_b,
            num_games=rounds,
            base_seed=matchup_index * 10000,
        )

        pairing = {
            "deck_a": deck_a_name,
            "deck_b": deck_b_name,
            "wins_a": result.wins,
            "wins_b": result.losses,
            "games": result.total,
            "win_rate_a": round(result.win_rate, 4),
            "avg_turns": round(result.avg_turns, 2),
            "win_conditions": dict(result.reason_counts or {}),
        }
        pairings.append(pairing)

        standings_map[deck_a_name]["wins"] += result.wins
        standings_map[deck_a_name]["losses"] += result.losses
        standings_map[deck_a_name]["games"] += result.total
        standings_map[deck_a_name]["total_turns"] += result.total_turns

        standings_map[deck_b_name]["wins"] += result.losses
        standings_map[deck_b_name]["losses"] += result.wins
        standings_map[deck_b_name]["games"] += result.total
        standings_map[deck_b_name]["total_turns"] += result.total_turns

        for reason, count in (result.reason_counts or {}).items():
            aggregate_win_conditions[reason] = aggregate_win_conditions.get(reason, 0) + count

        progress_callback(
            "progress",
            {
                "completed_matchups": matchup_index,
                "total_matchups": total_matchups,
                "completed_games": matchup_index * rounds,
                "total_games": total_games,
                "current_matchup": f"{deck_a_name} vs {deck_b_name}",
            },
        )
        progress_callback(
            "status",
            {
                "message": (
                    f"Completed {deck_a_name} vs {deck_b_name}: "
                    f"{result.wins}-{result.losses}"
                )
            },
        )

    total_time_sec = time.time() - started_at

    standings = []
    for entry in standings_map.values():
        games_played = max(1, entry["games"])
        standings.append(
            {
                "name": entry["name"],
                "wins": entry["wins"],
                "losses": entry["losses"],
                "games": entry["games"],
                "win_rate": round(entry["wins"] / games_played, 4),
                "avg_turns": round(entry["total_turns"] / games_played, 2),
            }
        )

    standings.sort(key=lambda row: (-row["win_rate"], -row["wins"], row["name"]))
    for rank, row in enumerate(standings, start=1):
        row["rank"] = rank

    closest_pairing = min(pairings, key=lambda row: abs(row["win_rate_a"] - 0.5), default=None)
    lopsided_pairing = max(pairings, key=lambda row: abs(row["win_rate_a"] - 0.5), default=None)
    longest_pairing = max(pairings, key=lambda row: row["avg_turns"], default=None)

    insights = {
        "best_performing_deck": standings[0]["name"] if standings else "",
        "weakest_deck": standings[-1]["name"] if standings else "",
        "total_decks": len(participants),
        "total_matchups": total_matchups,
        "total_games": total_games,
        "total_time_sec": round(total_time_sec, 1),
        "games_per_sec": round(total_games / max(0.01, total_time_sec), 1),
        "avg_turns_per_game": round(sim.total_turns_played / max(1, total_games), 1),
        "closest_matchup": _format_matchup_highlight(closest_pairing, "closest"),
        "most_lopsided_matchup": _format_matchup_highlight(lopsided_pairing, "lopsided"),
        "longest_matchup": _format_matchup_highlight(longest_pairing, "longest"),
        "win_conditions": aggregate_win_conditions,
    }

    matrix = _serialize_battle_matrix(participants, pairings) if mode == "all_vs_all" else None

    return {
        "mode": mode,
        "rounds": rounds,
        "participants": participants,
        "standings": standings,
        "pairings": pairings,
        "matrix": matrix,
        "insights": insights,
    }


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
    
    custom_decks = _load_saved_decks()

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
                deck = _deck_from_saved_data(custom_decks[key])
                valid, err = deck.validate()
                if valid:
                    seed_decks.append(deck)
                    seed_names.append(key)
                else:
                    progress_callback("status", {"message": f"Ignoring custom deck '{key}' (invalid: {err})"})
            except Exception:
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
