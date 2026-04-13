from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from poktcg.cards.card_db import get_card_db, reset_card_db
from poktcg.optimizer.archetypes import make_damage_swap, make_haymaker
from poktcg.optimizer.simulator import MatchResult
from poktcg.web import runner


def _noop_progress(_event_type: str, _data: dict) -> None:
    pass


def _saved_payload(deck) -> dict:
    return {
        "fitness": None,
        "total_cards": deck.total_cards(),
        "pokemon_count": deck.pokemon_count(),
        "trainer_count": deck.trainer_count(),
        "energy_count": deck.energy_count(),
        "cards": runner._serialize_deck(deck),
    }


def _valid_saved_decks() -> dict:
    reset_card_db()
    get_card_db(sets=runner.CARD_POOL_SETS["all"])
    return {
        "Alpha": _saved_payload(make_haymaker()),
        "Beta": _saved_payload(make_damage_swap()),
    }


class FakeSimulator:
    def __init__(self, num_workers: int = 1):
        self.num_workers = num_workers
        self.total_games_played = 0
        self.total_turns_played = 0
        self.reason_counts: dict[str, int] = {}

    def evaluate_matchup(self, deck_a, deck_b, num_games: int = 50, base_seed: int = 0):
        wins = max(0, num_games - 1) if deck_a["name"] < deck_b["name"] else 1
        losses = num_games - wins
        total_turns = num_games * (10 + len(deck_a["name"]) + len(deck_b["name"]))
        reasons = {
            "all prizes taken": wins,
            "deck out": losses,
        }

        self.total_games_played += num_games
        self.total_turns_played += total_turns
        for reason, count in reasons.items():
            self.reason_counts[reason] = self.reason_counts.get(reason, 0) + count

        return MatchResult(
            wins=wins,
            losses=losses,
            draws=0,
            total_turns=total_turns,
            reason_counts=reasons,
        )


def test_run_battleground_rejects_all_vs_all_with_too_few_decks():
    saved_decks = _valid_saved_decks()

    with pytest.raises(ValueError, match="at least 2 selected decks"):
        runner.run_battleground(
            mode="all_vs_all",
            rounds=3,
            deck_names=["Alpha"],
            primary_deck=None,
            opponent_names=[],
            progress_callback=_noop_progress,
            num_workers=1,
            saved_decks_data=saved_decks,
        )


def test_run_battleground_rejects_unknown_saved_deck():
    saved_decks = _valid_saved_decks()

    with pytest.raises(ValueError, match="Unknown saved deck: Missing"):
        runner.run_battleground(
            mode="all_vs_all",
            rounds=3,
            deck_names=["Alpha", "Missing"],
            primary_deck=None,
            opponent_names=[],
            progress_callback=_noop_progress,
            num_workers=1,
            saved_decks_data=saved_decks,
        )


def test_run_battleground_rejects_invalid_rounds():
    saved_decks = _valid_saved_decks()

    with pytest.raises(ValueError, match="Rounds must be at least 1"):
        runner.run_battleground(
            mode="all_vs_all",
            rounds=0,
            deck_names=["Alpha", "Beta"],
            primary_deck=None,
            opponent_names=[],
            progress_callback=_noop_progress,
            num_workers=1,
            saved_decks_data=saved_decks,
        )


def test_run_battleground_all_vs_all_aggregates_results(monkeypatch):
    monkeypatch.setattr(
        runner,
        "_load_valid_saved_decks",
        lambda names, saved: [(name, {"name": name}) for name in names],
    )
    monkeypatch.setattr(runner, "Simulator", FakeSimulator)

    result = runner.run_battleground(
        mode="all_vs_all",
        rounds=3,
        deck_names=["Alpha", "Beta", "Gamma"],
        primary_deck=None,
        opponent_names=[],
        progress_callback=_noop_progress,
        num_workers=1,
        saved_decks_data={"Alpha": {}, "Beta": {}, "Gamma": {}},
    )

    assert result["participants"] == ["Alpha", "Beta", "Gamma"]
    assert len(result["pairings"]) == 3
    assert all(pairing["games"] == 3 for pairing in result["pairings"])
    assert result["matrix"] is not None
    assert len(result["matrix"]["rows"]) == 3
    assert result["standings"][0]["rank"] == 1
    assert result["win_conditions"]


def test_run_battleground_one_vs_all_aggregates_results(monkeypatch):
    monkeypatch.setattr(
        runner,
        "_load_valid_saved_decks",
        lambda names, saved: [(name, {"name": name}) for name in names],
    )
    monkeypatch.setattr(runner, "Simulator", FakeSimulator)

    result = runner.run_battleground(
        mode="one_vs_all",
        rounds=2,
        deck_names=[],
        primary_deck="Alpha",
        opponent_names=["Beta", "Gamma"],
        progress_callback=_noop_progress,
        num_workers=1,
        saved_decks_data={"Alpha": {}, "Beta": {}, "Gamma": {}},
    )

    assert result["participants"] == ["Alpha", "Beta", "Gamma"]
    assert len(result["pairings"]) == 2
    assert result["matrix"] is None

    alpha_row = next(row for row in result["standings"] if row["name"] == "Alpha")
    beta_row = next(row for row in result["standings"] if row["name"] == "Beta")
    gamma_row = next(row for row in result["standings"] if row["name"] == "Gamma")

    assert alpha_row["wins"] + alpha_row["losses"] == 4
    assert beta_row["wins"] + beta_row["losses"] == 2
    assert gamma_row["wins"] + gamma_row["losses"] == 2
