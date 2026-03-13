"""Deck representation and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from poktcg.cards.card_db import get_card_db


@dataclass
class Deck:
    cards: dict[str, int]  # card_id -> count

    def to_list(self) -> list[str]:
        """Convert to flat list of card IDs."""
        result = []
        for card_id, count in self.cards.items():
            result.extend([card_id] * count)
        return result

    @classmethod
    def from_list(cls, card_list: list[str]) -> "Deck":
        cards = {}
        for cid in card_list:
            cards[cid] = cards.get(cid, 0) + 1
        return cls(cards=cards)

    def total_cards(self) -> int:
        return sum(self.cards.values())

    def validate(self) -> tuple[bool, str]:
        """Check if deck is valid. Returns (is_valid, error_message)."""
        db = get_card_db()
        total = self.total_cards()

        if total != 60:
            return False, f"Deck has {total} cards (need 60)"

        # Check per-card limits
        for card_id, count in self.cards.items():
            card = db.get(card_id)
            if card.is_energy and card.is_basic_energy:
                continue  # No limit on basic energy
            if count > 4:
                return False, f"{card.name} has {count} copies (max 4)"

        # Must contain at least 1 basic Pokemon
        has_basic = False
        for card_id in self.cards:
            card = db.get(card_id)
            if card.is_pokemon and card.is_basic:
                has_basic = True
                break
        if not has_basic:
            return False, "No basic Pokémon in deck"

        return True, ""

    def pokemon_count(self) -> int:
        db = get_card_db()
        return sum(n for cid, n in self.cards.items() if db.get(cid).is_pokemon)

    def trainer_count(self) -> int:
        db = get_card_db()
        return sum(n for cid, n in self.cards.items() if db.get(cid).is_trainer)

    def energy_count(self) -> int:
        db = get_card_db()
        return sum(n for cid, n in self.cards.items() if db.get(cid).is_energy)

    def summary(self) -> str:
        db = get_card_db()
        lines = []
        lines.append(f"Deck ({self.total_cards()} cards: {self.pokemon_count()}P / {self.trainer_count()}T / {self.energy_count()}E)")

        # Group by type
        pokemon = [(db.get(cid), n) for cid, n in self.cards.items() if db.get(cid).is_pokemon]
        trainers = [(db.get(cid), n) for cid, n in self.cards.items() if db.get(cid).is_trainer]
        energy = [(db.get(cid), n) for cid, n in self.cards.items() if db.get(cid).is_energy]

        lines.append("Pokemon:")
        for card, n in sorted(pokemon, key=lambda x: x[0].name):
            lines.append(f"  {n}x {card.name} ({card.hp}HP {'/'.join(card.types)})")

        lines.append("Trainers:")
        for card, n in sorted(trainers, key=lambda x: x[0].name):
            lines.append(f"  {n}x {card.name}")

        lines.append("Energy:")
        for card, n in sorted(energy, key=lambda x: x[0].name):
            lines.append(f"  {n}x {card.name}")

        return "\n".join(lines)

    def clone(self) -> "Deck":
        return Deck(cards=dict(self.cards))
