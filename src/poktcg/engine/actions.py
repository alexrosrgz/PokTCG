"""Action types and legal action generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from poktcg.cards.card_db import CardDB, get_card_db
from poktcg.cards.effects import get_power_hooks, get_power_hooks_by_name, power_usable, is_muk_active
from poktcg.engine.state import GameState, PlayerState, PokemonSlot, SpecialCondition


class ActionType(Enum):
    PLAY_BASIC = "play_basic"
    EVOLVE = "evolve"
    ATTACH_ENERGY = "attach_energy"
    PLAY_TRAINER = "play_trainer"
    USE_POWER = "use_power"
    RETREAT = "retreat"
    ATTACK = "attack"
    PASS_TURN = "pass"


@dataclass
class Action:
    type: ActionType
    card_id: str = ""  # Card being played/used
    target_slot: int = -1  # 0 = active, 1-5 = bench positions
    attack_index: int = 0  # Which attack to use
    energy_to_discard: list[int] = field(default_factory=list)  # Indices into attached_energy
    new_active: int = -1  # Bench index for new active after retreat
    trainer_targets: list = field(default_factory=list)  # Flexible targets for trainer effects

    def __repr__(self) -> str:
        db = get_card_db()
        if self.type == ActionType.PASS_TURN:
            return "Pass"
        name = db.get(self.card_id).name if self.card_id and self.card_id in db.cards else self.card_id
        if self.type == ActionType.PLAY_BASIC:
            return f"Play {name} to bench"
        if self.type == ActionType.EVOLVE:
            return f"Evolve slot {self.target_slot} into {name}"
        if self.type == ActionType.ATTACH_ENERGY:
            return f"Attach {name} to slot {self.target_slot}"
        if self.type == ActionType.ATTACK:
            atk = db.get(self.card_id).attacks[self.attack_index]
            return f"Attack: {atk.name}"
        if self.type == ActionType.RETREAT:
            return f"Retreat, swap in bench[{self.new_active}]"
        if self.type == ActionType.PLAY_TRAINER:
            return f"Play trainer: {name}"
        if self.type == ActionType.USE_POWER:
            return f"Use power: {name}"
        return f"{self.type.value}: {name}"


def _can_pay_energy(slot: PokemonSlot, cost: list[str], db: CardDB) -> bool:
    """Check if slot has enough energy to pay an attack cost."""
    available = {}
    for eid in slot.attached_energy:
        card = db.get(eid)
        etype = card.name.replace(" Energy", "")
        available[etype] = available.get(etype, 0) + 1

    # First satisfy specific (non-Colorless) costs
    remaining = dict(available)
    colorless_needed = 0
    for c in cost:
        if c == "Colorless":
            colorless_needed += 1
        else:
            if remaining.get(c, 0) > 0:
                remaining[c] -= 1
            else:
                return False

    # Then check if remaining energy covers colorless
    total_remaining = sum(remaining.values())
    return total_remaining >= colorless_needed


def _can_pay_retreat(slot: PokemonSlot, db: CardDB) -> bool:
    """Check if slot has enough energy to pay retreat cost."""
    card = db.get(slot.card_id)
    return len(slot.attached_energy) >= card.retreat_cost


def power_usable_for_action(slot: PokemonSlot, state: GameState) -> bool:
    """Check if a Pokemon's power can be used as an action (not blocked, not already used if once-per-turn)."""
    if slot.conditions & {SpecialCondition.ASLEEP, SpecialCondition.CONFUSED, SpecialCondition.PARALYZED}:
        return False
    # Muk check is done via power_usable in the effect itself
    return True


def _is_aerodactyl_active(state: GameState, db: CardDB) -> bool:
    """Check if any Aerodactyl in play has Prehistoric Power active."""
    for p in state.players:
        for slot in p.all_pokemon_slots():
            card = db.get(slot.card_id)
            if card.name == "Aerodactyl":
                if not (slot.conditions & {SpecialCondition.ASLEEP, SpecialCondition.CONFUSED, SpecialCondition.PARALYZED}):
                    if not is_muk_active_state(state, db):
                        return True
    return False


def is_muk_active_state(state: GameState, db: CardDB) -> bool:
    """Check if Muk's Toxic Gas is active (state-only version, no Game needed)."""
    for p in state.players:
        for slot in p.all_pokemon_slots():
            card = db.get(slot.card_id)
            if card.name == "Muk":
                if not (slot.conditions & {SpecialCondition.ASLEEP, SpecialCondition.CONFUSED, SpecialCondition.PARALYZED}):
                    return True
    return False


def _get_retreat_cost_with_dodrio(player: PlayerState, db: CardDB) -> int:
    """Get retreat cost factoring in Dodrio's Retreat Aid."""
    if not player.active:
        return 0
    card = db.get(player.active.card_id)
    cost = card.retreat_cost
    # Dodrio reduces retreat cost by 1 for each Dodrio on bench
    for slot in player.bench:
        bench_card = db.get(slot.card_id)
        if bench_card.name == "Dodrio":
            if not (slot.conditions & {SpecialCondition.ASLEEP, SpecialCondition.CONFUSED, SpecialCondition.PARALYZED}):
                cost -= 1
    return max(0, cost)


def get_legal_actions(state: GameState) -> list[Action]:
    """Generate all legal actions for the current player."""
    db = get_card_db()
    player = state.current_player
    actions = []

    # Always can pass
    actions.append(Action(type=ActionType.PASS_TURN))

    # Play basic Pokémon to bench (max 5 on bench)
    if len(player.bench) < 5:
        seen = set()
        for card_id in player.hand:
            card = db.get(card_id)
            if card.is_pokemon and card.is_basic and card_id not in seen:
                seen.add(card_id)
                actions.append(Action(
                    type=ActionType.PLAY_BASIC,
                    card_id=card_id,
                ))

    # Evolve Pokémon (can't evolve on turn played or turn 1)
    if state.turn > 1:
        seen_evolutions = set()
        for card_id in player.hand:
            card = db.get(card_id)
            if card.is_pokemon and (card.is_stage1 or card.is_stage2) and card.evolves_from:
                for slot_idx, slot in enumerate([player.active] + player.bench):
                    if slot is None:
                        continue
                    target_card = db.get(slot.card_id)
                    if target_card.name == card.evolves_from and slot.turn_evolved < state.turn and slot.turn_played < state.turn:
                        key = (card_id, slot_idx)
                        if key not in seen_evolutions:
                            seen_evolutions.add(key)
                            actions.append(Action(
                                type=ActionType.EVOLVE,
                                card_id=card_id,
                                target_slot=slot_idx,
                            ))

    # Attach energy (once per turn)
    if not player.energy_attached_this_turn:
        seen_energy = set()
        for card_id in player.hand:
            card = db.get(card_id)
            if card.is_energy and card.name not in seen_energy:
                seen_energy.add(card.name)
                all_slots = [player.active] + player.bench
                for slot_idx, slot in enumerate(all_slots):
                    if slot is not None:
                        actions.append(Action(
                            type=ActionType.ATTACH_ENERGY,
                            card_id=card_id,
                            target_slot=slot_idx,
                        ))

    # Play trainer cards (unlimited per turn in 1999 rules)
    seen_trainers = set()
    for card_id in player.hand:
        card = db.get(card_id)
        if card.is_trainer and card.name not in seen_trainers:
            seen_trainers.add(card.name)
            actions.append(Action(
                type=ActionType.PLAY_TRAINER,
                card_id=card_id,
            ))

    # Use Pokemon Powers
    for slot_idx, slot in enumerate([player.active] + player.bench):
        if slot is None:
            continue
        card = db.get(slot.card_id)
        hooks = get_power_hooks(slot.card_id)
        if not hooks:
            hooks = get_power_hooks_by_name(card.name, db)
        if hooks and "activate" in hooks:
            if power_usable_for_action(slot, state):
                actions.append(Action(
                    type=ActionType.USE_POWER,
                    card_id=slot.card_id,
                    target_slot=slot_idx,
                ))

    # Check for Aerodactyl: block evolution
    aerodactyl_active = _is_aerodactyl_active(state, db)
    if aerodactyl_active:
        actions = [a for a in actions if a.type != ActionType.EVOLVE]

    # Attack (ends turn)
    if player.active:
        active_card = db.get(player.active.card_id)
        # Can't attack if paralyzed
        if SpecialCondition.PARALYZED not in player.active.conditions:
            for i, attack in enumerate(active_card.attacks):
                if _can_pay_energy(player.active, attack.cost, db):
                    actions.append(Action(
                        type=ActionType.ATTACK,
                        card_id=player.active.card_id,
                        attack_index=i,
                    ))

    # Retreat (costs energy, need bench to swap with, Dodrio reduces cost)
    if player.active and player.bench:
        if SpecialCondition.PARALYZED not in player.active.conditions:
            adjusted_cost = _get_retreat_cost_with_dodrio(player, db)
            if len(player.active.attached_energy) >= adjusted_cost:
                for bench_idx in range(len(player.bench)):
                    actions.append(Action(
                        type=ActionType.RETREAT,
                        new_active=bench_idx,
                    ))

    return actions
