"""Card database: loads JSON card data and provides lookup."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Attack:
    name: str
    cost: list[str]  # e.g. ["Fire", "Fire", "Colorless"]
    damage: str  # e.g. "30", "20+", "10×", ""
    text: str  # effect description, empty for simple attacks

    @property
    def base_damage(self) -> int:
        """Parse numeric damage, ignoring +/× modifiers."""
        s = self.damage.strip().rstrip("+×x")
        if not s:
            return 0
        try:
            return int(s)
        except ValueError:
            return 0

    @property
    def has_effect(self) -> bool:
        return bool(self.text.strip())


@dataclass
class Ability:
    name: str
    text: str
    ability_type: str  # "Pokémon Power"


@dataclass
class WeaknessResistance:
    energy_type: str
    value: str  # "×2" or "-30"


@dataclass
class CardData:
    id: str  # e.g. "base1-1"
    name: str
    supertype: str  # "Pokémon", "Trainer", "Energy"
    subtypes: list[str]  # ["Basic"], ["Stage 1"], ["Stage 2"], etc.
    hp: int
    types: list[str]  # ["Fire"], ["Water", "Psychic"], etc.
    evolves_from: str
    attacks: list[Attack]
    abilities: list[Ability]
    weaknesses: list[WeaknessResistance]
    resistances: list[WeaknessResistance]
    retreat_cost: int  # number of colorless energy
    set_id: str  # "base1", "base2", "base3", "basep"
    number: str  # card number in set

    @property
    def is_pokemon(self) -> bool:
        return self.supertype == "Pokémon"

    @property
    def is_trainer(self) -> bool:
        return self.supertype == "Trainer"

    @property
    def is_energy(self) -> bool:
        return self.supertype == "Energy"

    @property
    def is_basic(self) -> bool:
        return "Basic" in self.subtypes

    @property
    def is_stage1(self) -> bool:
        return "Stage 1" in self.subtypes

    @property
    def is_stage2(self) -> bool:
        return "Stage 2" in self.subtypes

    @property
    def is_basic_energy(self) -> bool:
        return self.is_energy and "Basic" in self.subtypes


# Trainer cards store their rules/text differently
@dataclass
class TrainerData:
    rules: list[str]  # The effect text


def _parse_card(raw: dict, set_id: str) -> CardData:
    attacks = []
    for a in raw.get("attacks", []):
        attacks.append(Attack(
            name=a["name"],
            cost=a.get("cost", []),
            damage=a.get("damage", ""),
            text=a.get("text", ""),
        ))

    abilities = []
    for a in raw.get("abilities", []):
        abilities.append(Ability(
            name=a["name"],
            text=a.get("text", ""),
            ability_type=a.get("type", "Pokémon Power"),
        ))

    weaknesses = []
    for w in raw.get("weaknesses", []):
        weaknesses.append(WeaknessResistance(
            energy_type=w["type"],
            value=w["value"],
        ))

    resistances = []
    for r in raw.get("resistances", []):
        resistances.append(WeaknessResistance(
            energy_type=r["type"],
            value=r["value"],
        ))

    retreat_cost = raw.get("convertedRetreatCost", 0)
    hp = int(raw["hp"]) if raw.get("hp") else 0

    return CardData(
        id=raw["id"],
        name=raw["name"],
        supertype=raw["supertype"],
        subtypes=raw.get("subtypes", []),
        hp=hp,
        types=raw.get("types", []),
        evolves_from=raw.get("evolvesFrom", ""),
        attacks=attacks,
        abilities=abilities,
        weaknesses=weaknesses,
        resistances=resistances,
        retreat_cost=retreat_cost,
        set_id=set_id,
        number=raw.get("number", ""),
    )


class CardDB:
    """Singleton-ish card database for the Base-Fossil format."""

    def __init__(self):
        self.cards: dict[str, CardData] = {}
        self._trainer_rules: dict[str, list[str]] = {}

    def load(self, data_dir: str | Path, sets: list[str] | None = None) -> None:
        data_dir = Path(data_dir)
        all_set_files = {
            "base1": "base1.json",
            "base2": "base2.json",
            "base3": "base3.json",
            "basep": "basep.json",
        }
        set_files = {k: v for k, v in all_set_files.items()
                     if sets is None or k in sets}
        for set_id, filename in set_files.items():
            filepath = data_dir / filename
            with open(filepath) as f:
                raw_cards = json.load(f)

            for raw in raw_cards:
                # Filter promos: only 1-15 minus 11
                if set_id == "basep":
                    num = raw.get("number", "")
                    if not num.isdigit():
                        continue
                    n = int(num)
                    if n < 1 or n > 15 or n == 11:
                        continue

                card = _parse_card(raw, set_id)
                self.cards[card.id] = card

                # Store trainer rules separately
                if card.is_trainer and "rules" in raw:
                    self._trainer_rules[card.id] = raw["rules"]

    def get(self, card_id: str) -> CardData:
        return self.cards[card_id]

    def get_trainer_rules(self, card_id: str) -> list[str]:
        return self._trainer_rules.get(card_id, [])

    def all_pokemon(self) -> list[CardData]:
        return [c for c in self.cards.values() if c.is_pokemon]

    def all_trainers(self) -> list[CardData]:
        return [c for c in self.cards.values() if c.is_trainer]

    def all_energy(self) -> list[CardData]:
        return [c for c in self.cards.values() if c.is_energy]

    def all_basic_pokemon(self) -> list[CardData]:
        return [c for c in self.cards.values() if c.is_pokemon and c.is_basic]

    def find_by_name(self, name: str) -> list[CardData]:
        return [c for c in self.cards.values() if c.name == name]

    def __len__(self) -> int:
        return len(self.cards)


# Global instance
_db: CardDB | None = None


def get_card_db(sets: list[str] | None = None) -> CardDB:
    global _db
    if _db is None:
        _db = CardDB()
        # Try to find data directory relative to project root
        for candidate in [
            Path(__file__).parent.parent.parent.parent / "data" / "cards",
            Path("data/cards"),
        ]:
            if candidate.exists():
                _db.load(candidate, sets=sets)
                break
    return _db


def reset_card_db() -> None:
    """Clear the global CardDB so a fresh one can be loaded with different sets."""
    global _db
    _db = None
