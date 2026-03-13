"""Heuristic AI: tactics-based decision making with priority ordering."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from poktcg.ai.player import BasePlayer
from poktcg.ai.scoring import score_state, evaluate_attack
from poktcg.cards.card_db import get_card_db
from poktcg.engine.state import GameState, SpecialCondition
from poktcg.engine.actions import Action, ActionType, _can_pay_energy

if TYPE_CHECKING:
    pass


class HeuristicAI(BasePlayer):
    """AI that follows a priority-ordered tactics list."""

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def choose_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        db = get_card_db()
        player_idx = state.active_player
        p = state.current_player
        opp = state.opponent

        # Group actions by type
        by_type: dict[ActionType, list[Action]] = {}
        for a in legal_actions:
            by_type.setdefault(a.type, []).append(a)

        # ---- TACTIC 1: Play basics to bench ----
        if ActionType.PLAY_BASIC in by_type and len(p.bench) < 3:
            basics = by_type[ActionType.PLAY_BASIC]
            # Prefer highest HP basics
            basics.sort(key=lambda a: db.get(a.card_id).hp, reverse=True)
            return basics[0]

        # ---- TACTIC 2: Evolve Pokemon ----
        if ActionType.EVOLVE in by_type:
            evolutions = by_type[ActionType.EVOLVE]
            # Prefer evolving active, then most damaged bench
            for evo in evolutions:
                if evo.target_slot == 0:
                    return evo
            return evolutions[0]

        # ---- TACTIC 3: Attach energy ----
        if ActionType.ATTACH_ENERGY in by_type:
            energy_actions = by_type[ActionType.ATTACH_ENERGY]
            best = self._choose_energy_target(state, energy_actions)
            if best:
                return best

        # ---- TACTIC 4: Play draw trainers (Bill, Prof Oak) ----
        if ActionType.PLAY_TRAINER in by_type:
            for a in by_type[ActionType.PLAY_TRAINER]:
                name = db.get(a.card_id).name
                if name == "Bill":
                    return a
            for a in by_type[ActionType.PLAY_TRAINER]:
                name = db.get(a.card_id).name
                if name == "Professor Oak" and len(p.hand) <= 3:
                    return a

        # ---- TACTIC 5: Play disruption trainers ----
        if ActionType.PLAY_TRAINER in by_type:
            for a in by_type[ActionType.PLAY_TRAINER]:
                name = db.get(a.card_id).name
                if name == "Energy Removal" and opp.active and opp.active.attached_energy:
                    return a
                if name == "Super Energy Removal":
                    # Only if we have spare energy
                    total_energy = sum(len(s.attached_energy) for s in p.all_pokemon_slots())
                    if total_energy > 2 and opp.active and opp.active.attached_energy:
                        return a
                if name == "Gust of Wind" and opp.bench:
                    # Pull in weakest bench Pokemon
                    return a

        # ---- TACTIC 6: Play other useful trainers ----
        if ActionType.PLAY_TRAINER in by_type:
            for a in by_type[ActionType.PLAY_TRAINER]:
                name = db.get(a.card_id).name
                if name == "PlusPower":
                    return a
                if name == "Defender" and p.active and p.active.damage > 0:
                    return a
                if name == "Switch" and p.active and p.active.conditions:
                    return a
                if name == "Full Heal" and p.active and p.active.conditions:
                    return a
                if name == "Potion" and p.active and p.active.damage >= 20:
                    return a
                if name == "Computer Search" and len(p.hand) >= 3:
                    return a
                if name == "Energy Search":
                    return a
                if name == "Energy Retrieval":
                    return a
                if name == "Pokémon Trader":
                    return a
                if name == "Pokémon Breeder":
                    return a
                if name == "Scoop Up" and p.active and p.active.damage >= 40 and p.bench:
                    return a
                if name == "Item Finder" and len(p.hand) >= 3:
                    return a

        # ---- TACTIC 7: Play remaining basics to bench ----
        if ActionType.PLAY_BASIC in by_type and len(p.bench) < 5:
            basics = by_type[ActionType.PLAY_BASIC]
            basics.sort(key=lambda a: db.get(a.card_id).hp, reverse=True)
            return basics[0]

        # ---- TACTIC 8: Retreat if needed ----
        if ActionType.RETREAT in by_type:
            retreat = self._should_retreat(state, by_type[ActionType.RETREAT])
            if retreat:
                return retreat

        # ---- TACTIC 9: Attack ----
        if ActionType.ATTACK in by_type:
            attacks = by_type[ActionType.ATTACK]
            best_attack = max(attacks, key=lambda a: evaluate_attack(state, player_idx, a.attack_index))
            if evaluate_attack(state, player_idx, best_attack.attack_index) > 0:
                return best_attack

        # ---- TACTIC 10: Play any remaining trainers ----
        if ActionType.PLAY_TRAINER in by_type:
            for a in by_type[ActionType.PLAY_TRAINER]:
                name = db.get(a.card_id).name
                if name not in ("Professor Oak",):  # Don't Prof Oak with big hand
                    return a

        # ---- TACTIC 11: Attack even with low value ----
        if ActionType.ATTACK in by_type:
            return by_type[ActionType.ATTACK][0]

        # ---- Default: Pass ----
        return Action(type=ActionType.PASS_TURN)

    def _choose_energy_target(self, state: GameState, energy_actions: list[Action]) -> Action | None:
        """Choose best energy attachment target."""
        db = get_card_db()
        p = state.current_player

        # Prefer attaching to active if it needs energy for attacks
        active_actions = [a for a in energy_actions if a.target_slot == 0]
        bench_actions = [a for a in energy_actions if a.target_slot > 0]

        if p.active and active_actions:
            active_card = db.get(p.active.card_id)
            for attack in active_card.attacks:
                if not _can_pay_energy(p.active, attack.cost, db):
                    # Active needs energy - find matching type
                    needed_types = set(attack.cost) - {"Colorless"}
                    for a in active_actions:
                        e_card = db.get(a.card_id)
                        e_type = e_card.name.replace(" Energy", "")
                        if e_type in needed_types or not needed_types:
                            return a
                    return active_actions[0]

        # If active is powered up, attach to bench
        if bench_actions:
            # Prefer bench Pokemon that need energy
            for a in bench_actions:
                slot_idx = a.target_slot - 1
                if slot_idx < len(p.bench):
                    slot = p.bench[slot_idx]
                    pokemon_card = db.get(slot.card_id)
                    if pokemon_card.attacks:
                        if not _can_pay_energy(slot, pokemon_card.attacks[0].cost, db):
                            return a

        # Default: attach to active
        if active_actions:
            return active_actions[0]
        if energy_actions:
            return energy_actions[0]
        return None

    def _should_retreat(self, state: GameState, retreat_actions: list[Action]) -> Action | None:
        """Decide whether to retreat and which bench to swap in."""
        db = get_card_db()
        p = state.current_player
        opp = state.opponent

        if not p.active:
            return None

        active_card = db.get(p.active.card_id)
        remaining_hp = active_card.hp - p.active.damage

        # Retreat if about to die and we have healthy bench
        should_retreat = False
        if remaining_hp <= 20 and p.bench:
            should_retreat = True

        # Retreat if paralyzed/asleep and no attacks possible
        if p.active.conditions & {SpecialCondition.PARALYZED, SpecialCondition.ASLEEP}:
            # Can't retreat while paralyzed actually
            pass

        # Retreat if active has no useful attacks (no energy)
        has_attack = False
        for attack in active_card.attacks:
            if _can_pay_energy(p.active, attack.cost, db):
                has_attack = True
                break
        if not has_attack and p.bench:
            # Check if any bench mon can attack
            for i, slot in enumerate(p.bench):
                bench_card = db.get(slot.card_id)
                for attack in bench_card.attacks:
                    if _can_pay_energy(slot, attack.cost, db):
                        should_retreat = True
                        break

        if should_retreat and retreat_actions:
            # Pick healthiest bench Pokemon that can attack
            best = None
            best_score = -1
            for a in retreat_actions:
                slot = p.bench[a.new_active]
                card = db.get(slot.card_id)
                s = card.hp - slot.damage
                # Bonus for being able to attack
                for attack in card.attacks:
                    if _can_pay_energy(slot, attack.cost, db):
                        s += 50
                        break
                if s > best_score:
                    best_score = s
                    best = a
            return best

        return None

    def choose_active(self, state: GameState, player_idx: int) -> int:
        """Choose best starting active Pokemon."""
        db = get_card_db()
        p = state.players[player_idx]

        basics = []
        for i, cid in enumerate(p.hand):
            card = db.get(cid)
            if card.is_pokemon and card.is_basic:
                # Score: HP + attack potential
                score = card.hp
                if card.attacks:
                    # Prefer Pokemon with low-cost attacks
                    min_cost = min(len(a.cost) for a in card.attacks)
                    score += (5 - min_cost) * 20
                    # Prefer high damage
                    max_dmg = max(a.base_damage for a in card.attacks)
                    score += max_dmg
                basics.append((i, score))

        if basics:
            basics.sort(key=lambda x: x[1], reverse=True)
            return basics[0][0]
        return 0

    def choose_bench(self, state: GameState, player_idx: int, basics_in_hand: list[int]) -> list[int]:
        """Bench all remaining basics."""
        return basics_in_hand[:5]

    def choose_new_active(self, state: GameState, player_idx: int) -> int:
        """Choose best bench Pokemon as new active."""
        db = get_card_db()
        p = state.players[player_idx]

        if not p.bench:
            return 0

        best_idx = 0
        best_score = -1
        for i, slot in enumerate(p.bench):
            card = db.get(slot.card_id)
            score = card.hp - slot.damage
            # Prefer Pokemon that can attack immediately
            for attack in card.attacks:
                if _can_pay_energy(slot, attack.cost, db):
                    score += 100 + attack.base_damage
                    break
            if score > best_score:
                best_score = score
                best_idx = i

        return best_idx
