"""Effect system: primitives, registry, and effect execution.

Attack effects are registered as functions that take (game, player_idx, attack, base_damage)
and return the modified base_damage. They may also modify game state (apply status, etc).

Pokemon Powers are registered as hooks that the engine calls at appropriate times.
Trainer effects are registered as functions called when the trainer is played.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from poktcg.engine.game import Game
    from poktcg.engine.state import PokemonSlot

from poktcg.engine.state import SpecialCondition


# ============================================================
# Effect Registry
# ============================================================

# attack_id -> effect function
# Function signature: (game: Game, player_idx: int, attack_index: int, base_damage: int) -> int
_attack_effects: dict[str, Callable] = {}

# card_id -> trainer effect function
# Function signature: (game: Game, player_idx: int) -> bool (True if successfully played)
_trainer_effects: dict[str, Callable] = {}

# card_id -> power hooks dict
# Keys: "activate" (for activated powers), "passive" (for continuous),
#        "before_damage" (for damage modification), "on_damaged" (reactive)
_power_effects: dict[str, dict[str, Callable]] = {}


def register_attack(card_id: str, attack_index: int):
    """Decorator to register an attack effect."""
    key = f"{card_id}:{attack_index}"
    def decorator(fn):
        _attack_effects[key] = fn
        return fn
    return decorator


def register_trainer(card_id: str):
    """Decorator to register a trainer card effect."""
    def decorator(fn):
        _trainer_effects[card_id] = fn
        return fn
    return decorator


def register_trainer_by_name(name: str):
    """Register trainer by name (applies to all prints of same trainer)."""
    def decorator(fn):
        _trainer_effects[f"name:{name}"] = fn
        return fn
    return decorator


def register_power(card_id: str, hook_type: str = "activate"):
    """Register a Pokemon Power effect."""
    def decorator(fn):
        if card_id not in _power_effects:
            _power_effects[card_id] = {}
        _power_effects[card_id][hook_type] = fn
        return fn
    return decorator


def get_power_hooks_by_name(card_name: str, db) -> dict[str, Callable] | None:
    """Find power hooks by card name (for duplicate prints)."""
    for card_id, hooks in _power_effects.items():
        card = db.get(card_id)
        if card.name == card_name:
            return hooks
    return None


def get_attack_effect(card_id: str, attack_index: int) -> Optional[Callable]:
    key = f"{card_id}:{attack_index}"
    return _attack_effects.get(key)


def get_trainer_effect(card_id: str, card_name: str) -> Optional[Callable]:
    # Try specific card ID first, then by name
    return _trainer_effects.get(card_id) or _trainer_effects.get(f"name:{card_name}")


def get_power_hooks(card_id: str) -> Optional[dict[str, Callable]]:
    return _power_effects.get(card_id)


# ============================================================
# Common Effect Helpers
# ============================================================

def apply_status(game: "Game", target_player_idx: int, slot_idx: int, condition: SpecialCondition):
    """Apply a special condition to a Pokemon."""
    slot = game._get_slot(game.state.players[target_player_idx], slot_idx)
    if slot is None:
        return
    # Sleep, Confusion, and Paralysis are mutually exclusive
    if condition in (SpecialCondition.ASLEEP, SpecialCondition.CONFUSED, SpecialCondition.PARALYZED):
        slot.conditions.discard(SpecialCondition.ASLEEP)
        slot.conditions.discard(SpecialCondition.CONFUSED)
        slot.conditions.discard(SpecialCondition.PARALYZED)
    slot.conditions.add(condition)


def is_muk_active(game: "Game") -> bool:
    """Check if any Muk in play has Toxic Gas active (not asleep/confused/paralyzed)."""
    for p in game.state.players:
        for slot in p.all_pokemon_slots():
            card = game.db.get(slot.card_id)
            if card.name == "Muk":
                # Toxic Gas stops working if Muk is asleep/confused/paralyzed
                if not (slot.conditions & {SpecialCondition.ASLEEP, SpecialCondition.CONFUSED, SpecialCondition.PARALYZED}):
                    return True
    return False


def power_usable(game: "Game", slot: "PokemonSlot") -> bool:
    """Check if a Pokemon can use its power (not blocked by conditions or Muk)."""
    if is_muk_active(game):
        # Check if THIS card is Muk - Muk's own power is not blocked by itself
        card = game.db.get(slot.card_id)
        if card.name != "Muk":
            return False
    if slot.conditions & {SpecialCondition.ASLEEP, SpecialCondition.CONFUSED, SpecialCondition.PARALYZED}:
        return False
    return True


def discard_energy_from_slot(game: "Game", player_idx: int, slot: "PokemonSlot",
                              energy_type: str | None = None, count: int = 1) -> int:
    """Discard energy from a slot. Returns number actually discarded."""
    p = game.state.players[player_idx]
    discarded = 0
    for _ in range(count):
        if not slot.attached_energy:
            break
        if energy_type:
            # Find matching energy
            found = -1
            for i, eid in enumerate(slot.attached_energy):
                card = game.db.get(eid)
                if energy_type in card.name:
                    found = i
                    break
            if found >= 0:
                eid = slot.attached_energy.pop(found)
                p.discard.append(eid)
                discarded += 1
        else:
            # Discard any energy
            eid = slot.attached_energy.pop(0)
            p.discard.append(eid)
            discarded += 1
    return discarded


def count_energy_of_type(slot: "PokemonSlot", energy_type: str, db) -> int:
    """Count attached energy of a specific type."""
    count = 0
    for eid in slot.attached_energy:
        card = db.get(eid)
        if energy_type in card.name:
            count += 1
    return count
