"""Heuristic AI: tactics-based decision making with priority ordering."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from poktcg.ai.player import BasePlayer
from poktcg.ai.scoring import (
    score_state, evaluate_attack, estimate_damage, can_ko,
    score_gust_target, score_energy_removal_target,
)
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

        # ---- TACTIC 1: Play basics to bench (up to 3 early) ----
        if ActionType.PLAY_BASIC in by_type and len(p.bench) < 3:
            basics = by_type[ActionType.PLAY_BASIC]
            basics.sort(key=lambda a: db.get(a.card_id).hp, reverse=True)
            return basics[0]

        # ---- TACTIC 2: Evolve Pokemon ----
        if ActionType.EVOLVE in by_type:
            evolutions = by_type[ActionType.EVOLVE]
            # Prefer evolving active, then highest-stage evolutions
            for evo in evolutions:
                if evo.target_slot == 0:
                    return evo
            return evolutions[0]

        # ---- TACTIC 3: Use Pokemon Powers (before energy) ----
        if ActionType.USE_POWER in by_type:
            power_action = self._choose_power(state, by_type[ActionType.USE_POWER])
            if power_action:
                return power_action

        # ---- TACTIC 4: Attach energy ----
        if ActionType.ATTACH_ENERGY in by_type:
            best = self._choose_energy_target(state, by_type[ActionType.ATTACH_ENERGY])
            if best:
                return best

        # ---- TACTIC 5: Play draw trainers first (see hand before deciding) ----
        if ActionType.PLAY_TRAINER in by_type:
            draw_action = self._play_draw_trainers(state, by_type[ActionType.PLAY_TRAINER])
            if draw_action:
                return draw_action

        # ---- TACTIC 6: Play disruption trainers (smart targeting) ----
        if ActionType.PLAY_TRAINER in by_type:
            disrupt = self._play_disruption_trainers(state, by_type[ActionType.PLAY_TRAINER])
            if disrupt:
                return disrupt

        # ---- TACTIC 7: Play other useful trainers ----
        if ActionType.PLAY_TRAINER in by_type:
            other = self._play_other_trainers(state, by_type[ActionType.PLAY_TRAINER])
            if other:
                return other

        # ---- TACTIC 8: Play remaining basics to bench ----
        if ActionType.PLAY_BASIC in by_type and len(p.bench) < 5:
            basics = by_type[ActionType.PLAY_BASIC]
            basics.sort(key=lambda a: db.get(a.card_id).hp, reverse=True)
            return basics[0]

        # ---- TACTIC 9: Retreat if needed ----
        if ActionType.RETREAT in by_type:
            retreat = self._should_retreat(state, by_type.get(ActionType.RETREAT, []),
                                           by_type.get(ActionType.ATTACK, []))
            if retreat:
                return retreat

        # ---- TACTIC 10: Attack (pick best with lookahead) ----
        if ActionType.ATTACK in by_type:
            best_attack = self._choose_attack(state, by_type[ActionType.ATTACK])
            if best_attack:
                return best_attack

        # ---- TACTIC 11: Play any remaining trainers ----
        if ActionType.PLAY_TRAINER in by_type:
            for a in by_type[ActionType.PLAY_TRAINER]:
                name = db.get(a.card_id).name
                if name != "Professor Oak":  # Don't Prof Oak with big hand
                    return a

        # ---- TACTIC 12: Attack even with low value ----
        if ActionType.ATTACK in by_type:
            return by_type[ActionType.ATTACK][0]

        # ---- Default: Pass ----
        return Action(type=ActionType.PASS_TURN)

    # ================================================================
    # Draw trainers
    # ================================================================

    def _play_draw_trainers(self, state: GameState, trainer_actions: list[Action]) -> Action | None:
        db = get_card_db()
        p = state.current_player

        # Bill is always good
        for a in trainer_actions:
            if db.get(a.card_id).name == "Bill":
                return a

        # Computer Search: play early to find key cards
        for a in trainer_actions:
            if db.get(a.card_id).name == "Computer Search" and len(p.hand) >= 3:
                return a

        # Prof Oak only with small hand
        for a in trainer_actions:
            if db.get(a.card_id).name == "Professor Oak" and len(p.hand) <= 3:
                return a

        return None

    # ================================================================
    # Disruption trainers (smart targeting)
    # ================================================================

    def _play_disruption_trainers(self, state: GameState, trainer_actions: list[Action]) -> Action | None:
        db = get_card_db()
        p = state.current_player
        opp = state.opponent

        for a in trainer_actions:
            name = db.get(a.card_id).name

            # Energy Removal: target opponent's active if it would disable attacks
            if name == "Energy Removal" and opp.active and opp.active.attached_energy:
                return a

            # Super Energy Removal: only if we have spare energy and target is worth it
            if name == "Super Energy Removal":
                total_energy = sum(len(s.attached_energy) for s in p.all_pokemon_slots())
                if total_energy > 2 and opp.active and opp.active.attached_energy:
                    return a

            # Gust of Wind: always play if opponent has bench — targets are
            # evaluated by the trainer effect itself, we just decide to play it
            if name == "Gust of Wind" and opp.bench:
                return a

            # Lass: play when opponent has big hand
            if name == "Lass" and len(opp.hand) >= 5:
                return a

            # Impostor Professor Oak: play when opponent has small hand (they shuffle and draw 7)
            # Actually bad for us usually — skip unless they have 0-1 cards
            if name == "Impostor Professor Oak" and len(opp.hand) <= 1:
                return a

        return None

    def _evaluate_gust_targets(self, state: GameState) -> int | None:
        """Find the best Gust of Wind target. Returns bench index or None if not worth it."""
        player_idx = state.active_player
        opp = state.opponent

        if not opp.bench:
            return None

        best_score = 0
        best_idx = None

        for i, slot in enumerate(opp.bench):
            s = score_gust_target(state, player_idx, slot)
            if s > best_score:
                best_score = s
                best_idx = i

        # Only gust if the target is actually better than current active
        if opp.active and best_idx is not None:
            active_score = score_gust_target(state, player_idx, opp.active)
            if best_score > active_score + 50:  # Threshold to avoid wasteful gusts
                return best_idx

        return None

    # ================================================================
    # Other trainers
    # ================================================================

    def _play_other_trainers(self, state: GameState, trainer_actions: list[Action]) -> Action | None:
        db = get_card_db()
        p = state.current_player
        opp = state.opponent

        for a in trainer_actions:
            name = db.get(a.card_id).name

            # PlusPower: always play — free +10 damage (or +20 with weakness)
            if name == "PlusPower":
                return a

            # Switch: use if active has bad status or is stuck
            if name == "Switch" and p.active and p.bench:
                if p.active.conditions & {SpecialCondition.ASLEEP, SpecialCondition.CONFUSED, SpecialCondition.PARALYZED}:
                    return a

            if name == "Full Heal" and p.active and p.active.conditions:
                return a

            # Defender: use if active is damaged and opponent can attack
            if name == "Defender" and p.active and p.active.damage > 0:
                return a

            # Potion: heal if significant damage
            if name == "Potion" and p.active and p.active.damage >= 20:
                return a

            # Scoop Up: save a heavily damaged active
            if name == "Scoop Up" and p.active and p.bench:
                if p.active.damage >= 40:
                    return a

            if name == "Energy Search":
                return a
            if name == "Energy Retrieval":
                return a
            if name == "Pokémon Trader":
                return a
            if name == "Pokémon Breeder":
                return a
            if name == "Item Finder" and len(p.hand) >= 3:
                return a

        return None

    # ================================================================
    # Pokemon Powers
    # ================================================================

    def _choose_power(self, state: GameState, power_actions: list[Action]) -> Action | None:
        """Choose which Pokemon Power to use, if any."""
        db = get_card_db()
        p = state.current_player

        for a in power_actions:
            card = db.get(a.card_id)
            name = card.name

            # Blastoise: Rain Dance - attach Water Energy if available
            if name == "Blastoise":
                water_in_hand = [cid for cid in p.hand
                                 if db.get(cid).is_energy and "Water" in db.get(cid).name]
                if water_in_hand:
                    return a

            # Alakazam: Damage Swap - move damage away from active
            if name == "Alakazam":
                if p.active and p.active.damage > 0:
                    for s in p.bench:
                        remaining = db.get(s.card_id).hp - s.damage
                        if remaining > 10:
                            return a

            # Gengar: Curse - move damage to opponent's active
            if name == "Gengar":
                slot = self._find_slot(p, a.target_slot)
                if slot and not slot.used_power_this_turn:
                    opp = state.opponent
                    has_source = any(s.damage > 0 for s in opp.all_pokemon_slots())
                    if has_source:
                        return a

            # Vileplume: Heal
            if name == "Vileplume":
                slot = self._find_slot(p, a.target_slot)
                if slot and not slot.used_power_this_turn:
                    if any(s.damage > 0 for s in p.all_pokemon_slots()):
                        return a

            # Venusaur: Energy Trans
            if name == "Venusaur":
                return a

            # Dragonite: Step In - switch if active is weak
            if name == "Dragonite" and a.target_slot > 0:
                slot = self._find_slot(p, a.target_slot)
                if slot and not slot.used_power_this_turn:
                    if p.active:
                        active_hp = db.get(p.active.card_id).hp - p.active.damage
                        dragonite_hp = db.get(slot.card_id).hp - slot.damage
                        if dragonite_hp > active_hp and active_hp <= 30:
                            return a

            # Slowbro: Strange Behavior - absorb damage
            if name == "Slowbro":
                slot = self._find_slot(p, a.target_slot)
                if slot:
                    remaining = db.get(a.card_id).hp - slot.damage
                    if remaining > 10:
                        has_damaged = any(s.damage > 0 and s is not slot
                                          for s in p.all_pokemon_slots())
                        if has_damaged:
                            return a

        return None

    # ================================================================
    # Energy attachment
    # ================================================================

    def _choose_energy_target(self, state: GameState, energy_actions: list[Action]) -> Action | None:
        """Choose best energy attachment target."""
        db = get_card_db()
        p = state.current_player

        active_actions = [a for a in energy_actions if a.target_slot == 0]
        bench_actions = [a for a in energy_actions if a.target_slot > 0]

        # If active needs energy for an attack, prioritize it
        if p.active and active_actions:
            active_card = db.get(p.active.card_id)
            for attack in active_card.attacks:
                if not _can_pay_energy(p.active, attack.cost, db):
                    needed_types = set(attack.cost) - {"Colorless"}
                    for a in active_actions:
                        e_type = db.get(a.card_id).name.replace(" Energy", "")
                        if e_type in needed_types or not needed_types:
                            return a
                    return active_actions[0]

        # Bench: prefer Pokemon closest to being able to attack
        if bench_actions:
            best_action = None
            best_deficit = 999
            for a in bench_actions:
                slot_idx = a.target_slot - 1
                if slot_idx < len(p.bench):
                    slot = p.bench[slot_idx]
                    pokemon_card = db.get(slot.card_id)
                    e_type = db.get(a.card_id).name.replace(" Energy", "")
                    for attack in pokemon_card.attacks:
                        if not _can_pay_energy(slot, attack.cost, db):
                            # How many more energy does it need?
                            deficit = len(attack.cost) - len(slot.attached_energy)
                            # Prefer matching type
                            type_match = e_type in attack.cost or "Colorless" in attack.cost
                            if type_match and deficit < best_deficit:
                                best_deficit = deficit
                                best_action = a
            if best_action:
                return best_action

        # Default: attach to active
        if active_actions:
            return active_actions[0]
        if energy_actions:
            return energy_actions[0]
        return None

    # ================================================================
    # Attack selection (with simple lookahead)
    # ================================================================

    def _choose_attack(self, state: GameState, attack_actions: list[Action]) -> Action | None:
        """Choose the best attack, considering KO potential and damage efficiency."""
        db = get_card_db()
        player_idx = state.active_player
        p = state.current_player
        opp = state.opponent

        if not attack_actions or not p.active or not opp.active:
            return None

        best_attack = None
        best_score = -1

        for a in attack_actions:
            score = evaluate_attack(state, player_idx, a.attack_index)

            # Additional lookahead: if we can KO, strongly prefer that attack
            if can_ko(p.active, opp.active, a.attack_index):
                score += 300  # Stack on top of the KO bonus in evaluate_attack

            if score > best_score:
                best_score = score
                best_attack = a

        if best_score > 0:
            return best_attack
        return None

    # ================================================================
    # Retreat logic (considers what bench Pokemon can do)
    # ================================================================

    def _should_retreat(self, state: GameState, retreat_actions: list[Action],
                        attack_actions: list[Action]) -> Action | None:
        """Decide whether to retreat, factoring in what bench can do vs staying."""
        db = get_card_db()
        p = state.current_player
        opp = state.opponent

        if not p.active or not retreat_actions:
            return None

        active_card = db.get(p.active.card_id)
        remaining_hp = active_card.hp - p.active.damage

        should_retreat = False

        # Retreat if about to die
        if remaining_hp <= 20 and p.bench:
            should_retreat = True

        # Retreat if active can't attack but bench can
        has_attack = any(
            _can_pay_energy(p.active, atk.cost, db)
            for atk in active_card.attacks
        )
        if not has_attack and p.bench:
            for slot in p.bench:
                bench_card = db.get(slot.card_id)
                if any(_can_pay_energy(slot, atk.cost, db) for atk in bench_card.attacks):
                    should_retreat = True
                    break

        # Retreat if bench Pokemon can KO but active can't
        if opp.active and not should_retreat and p.bench:
            active_can_ko = False
            if has_attack:
                for i, atk in enumerate(active_card.attacks):
                    if _can_pay_energy(p.active, atk.cost, db):
                        if can_ko(p.active, opp.active, i):
                            active_can_ko = True
                            break

            if not active_can_ko:
                for bench_idx, slot in enumerate(p.bench):
                    bench_card = db.get(slot.card_id)
                    for i, atk in enumerate(bench_card.attacks):
                        if _can_pay_energy(slot, atk.cost, db):
                            if can_ko(slot, opp.active, i):
                                # A bench Pokemon can KO — retreat to it
                                for ra in retreat_actions:
                                    if ra.new_active == bench_idx:
                                        return ra

        if should_retreat:
            # Pick the best bench Pokemon to swap in
            best = None
            best_score = -1
            for a in retreat_actions:
                slot = p.bench[a.new_active]
                card = db.get(slot.card_id)
                s = card.hp - slot.damage
                for attack in card.attacks:
                    if _can_pay_energy(slot, attack.cost, db):
                        s += 50 + attack.base_damage
                        break
                if s > best_score:
                    best_score = s
                    best = a
            return best

        return None

    # ================================================================
    # Helpers
    # ================================================================

    def _find_slot(self, player, slot_idx):
        """Get slot by index: 0 = active, 1+ = bench."""
        if slot_idx == 0:
            return player.active
        idx = slot_idx - 1
        if 0 <= idx < len(player.bench):
            return player.bench[idx]
        return None

    def choose_active(self, state: GameState, player_idx: int) -> int:
        """Choose best starting active Pokemon."""
        db = get_card_db()
        p = state.players[player_idx]

        basics = []
        for i, cid in enumerate(p.hand):
            card = db.get(cid)
            if card.is_pokemon and card.is_basic:
                score = card.hp
                if card.attacks:
                    min_cost = min(len(a.cost) for a in card.attacks)
                    score += (5 - min_cost) * 20
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
        opp = state.players[1 - player_idx]

        if not p.bench:
            return 0

        best_idx = 0
        best_score = -1
        for i, slot in enumerate(p.bench):
            card = db.get(slot.card_id)
            score = card.hp - slot.damage
            for attack in card.attacks:
                if _can_pay_energy(slot, attack.cost, db):
                    score += 100 + attack.base_damage
                    # Bonus if this Pokemon can KO the opponent's active
                    if opp.active:
                        for ai, atk in enumerate(card.attacks):
                            if _can_pay_energy(slot, atk.cost, db) and can_ko(slot, opp.active, ai):
                                score += 200
                                break
                    break
            if score > best_score:
                best_score = score
                best_idx = i

        return best_idx
