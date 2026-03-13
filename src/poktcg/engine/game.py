"""Core game engine: game loop, turn structure, effect execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from poktcg.cards.card_db import CardDB, CardData, get_card_db
from poktcg.cards.effects import get_attack_effect, get_trainer_effect, get_power_hooks, is_muk_active, power_usable
from poktcg.engine.state import GameState, PlayerState, PokemonSlot, Phase, SpecialCondition
from poktcg.engine.actions import Action, ActionType, get_legal_actions, _can_pay_energy
from poktcg.engine.damage import calculate_damage
from poktcg.engine.rng import GameRNG

# Import all card effect modules to trigger registration
import poktcg.cards.pokemon.base1
import poktcg.cards.pokemon.base2
import poktcg.cards.pokemon.base3
import poktcg.cards.pokemon.basep
import poktcg.cards.trainers


class Player(Protocol):
    """Interface for AI players."""

    def choose_action(self, state: GameState, legal_actions: list[Action]) -> Action:
        ...

    def choose_active(self, state: GameState, player_idx: int) -> int:
        """Choose which basic Pokémon to put as active during setup.
        Returns index into hand of basic Pokémon."""
        ...

    def choose_bench(self, state: GameState, player_idx: int, basics_in_hand: list[int]) -> list[int]:
        """Choose which basics to bench during setup.
        Returns indices into hand."""
        ...

    def choose_new_active(self, state: GameState, player_idx: int) -> int:
        """Choose new active from bench when active is KO'd.
        Returns bench index."""
        ...


@dataclass
class GameResult:
    winner: int  # 0 or 1
    turns: int
    reason: str

    def __repr__(self) -> str:
        return f"Player {self.winner} wins in {self.turns} turns ({self.reason})"


MAX_TURNS = 200  # Safety limit to prevent infinite games


class Game:
    def __init__(
        self,
        player0: Player,
        player1: Player,
        deck0: list[str],
        deck1: list[str],
        seed: int | None = None,
    ):
        self.players = [player0, player1]
        self.rng = GameRNG(seed)
        self.db = get_card_db()
        self.state = GameState(
            players=[
                PlayerState(deck=list(deck0), hand=[], discard=[], prizes=[]),
                PlayerState(deck=list(deck1), hand=[], discard=[], prizes=[]),
            ],
            phase=Phase.SETUP,
        )

    def play(self) -> GameResult:
        """Play a complete game, return result."""
        self._setup()
        while not self.state.is_finished:
            if self.state.turn >= MAX_TURNS:
                # Draw if game goes too long
                self.state.phase = Phase.FINISHED
                self.state.winner = 0  # Arbitrary tie-breaker
                self.state.game_over_reason = "max turns reached"
                break
            self._play_turn()
        return GameResult(
            winner=self.state.winner if self.state.winner is not None else 0,
            turns=self.state.turn,
            reason=self.state.game_over_reason,
        )

    def _setup(self):
        """Setup phase: shuffle, draw, mulligan, place Pokémon, set prizes."""
        for i in range(2):
            self.rng.shuffle(self.state.players[i].deck)

        # Draw 7 cards each, handle mulligans
        for i in range(2):
            self._draw_initial_hand(i)

        # Handle mulligans
        for i in range(2):
            while not self._has_basic_in_hand(i):
                mulligan_count = self._mulligan(i)
                # Opponent draws 2 cards per mulligan (1999 rule)
                opp = 1 - i
                self.state.players[opp].draw_cards(2)

        # Each player places active and bench
        for i in range(2):
            self._place_initial_pokemon(i)

        # Set 6 prizes each
        for i in range(2):
            p = self.state.players[i]
            for _ in range(6):
                if p.deck:
                    p.prizes.append(p.deck.pop(0))

        # Coin flip for who goes first (winner goes first AND can attack)
        if self.rng.coin_flip():
            self.state.active_player = 0
        else:
            self.state.active_player = 1

        self.state.turn = 1
        self.state.phase = Phase.PLAYER_TURN

    def _draw_initial_hand(self, player_idx: int):
        p = self.state.players[player_idx]
        p.draw_cards(7)

    def _has_basic_in_hand(self, player_idx: int) -> bool:
        p = self.state.players[player_idx]
        return any(
            self.db.get(cid).is_pokemon and self.db.get(cid).is_basic
            for cid in p.hand
        )

    def _mulligan(self, player_idx: int) -> int:
        """Shuffle hand back, draw 7 new. Returns 1."""
        p = self.state.players[player_idx]
        p.deck.extend(p.hand)
        p.hand.clear()
        self.rng.shuffle(p.deck)
        p.draw_cards(7)
        return 1

    def _place_initial_pokemon(self, player_idx: int):
        """AI places active and optional bench Pokémon."""
        p = self.state.players[player_idx]
        player = self.players[player_idx]

        # Find basics in hand
        basics = [
            i for i, cid in enumerate(p.hand)
            if self.db.get(cid).is_pokemon and self.db.get(cid).is_basic
        ]

        if not basics:
            return  # Shouldn't happen after mulligan check

        # Choose active
        active_idx = player.choose_active(self.state, player_idx)
        if active_idx not in basics:
            active_idx = basics[0]

        card_id = p.hand[active_idx]
        p.active = PokemonSlot(
            pokemon_stack=[card_id],
            turn_played=0,
        )
        p.hand.pop(active_idx)

        # Choose bench (recalculate basics indices after removing active)
        remaining_basics = [
            i for i, cid in enumerate(p.hand)
            if self.db.get(cid).is_pokemon and self.db.get(cid).is_basic
        ]

        bench_choices = player.choose_bench(self.state, player_idx, remaining_basics)
        # Place bench in reverse order to keep indices valid
        bench_choices = sorted(set(bench_choices) & set(remaining_basics), reverse=True)
        for idx in bench_choices[:5]:  # Max 5 bench
            card_id = p.hand[idx]
            p.bench.append(PokemonSlot(
                pokemon_stack=[card_id],
                turn_played=0,
            ))
            p.hand.pop(idx)

    def _play_turn(self):
        """Execute one full turn for the active player."""
        player_idx = self.state.active_player
        p = self.state.players[player_idx]
        player = self.players[player_idx]

        # Reset per-turn flags
        p.energy_attached_this_turn = False
        for slot in p.all_pokemon_slots():
            slot.used_power_this_turn = False

        # 1. Draw a card
        card = p.draw_card()
        if card is None:
            # Deck out!
            self._end_game(1 - player_idx, "deck out")
            return

        # 2. Action loop
        turn_ended = False
        action_count = 0
        max_actions = 100  # Safety limit per turn

        while not turn_ended and action_count < max_actions:
            if self.state.is_finished:
                return

            legal = get_legal_actions(self.state)
            action = player.choose_action(self.state, legal)

            # Validate action is legal
            if action.type == ActionType.PASS_TURN:
                turn_ended = True
                break

            if action.type == ActionType.ATTACK:
                self._execute_attack(player_idx, action)
                turn_ended = True
            else:
                self._execute_action(player_idx, action)

            action_count += 1

            # Check if game ended (e.g., from KO during trainer play)
            if self.state.is_finished:
                return

        if not self.state.is_finished:
            self._between_turns(player_idx)

    def _execute_action(self, player_idx: int, action: Action):
        """Execute a non-attack action."""
        p = self.state.players[player_idx]

        if action.type == ActionType.PLAY_BASIC:
            if len(p.bench) < 5:
                idx = p.hand.index(action.card_id)
                card_id = p.hand.pop(idx)
                p.bench.append(PokemonSlot(
                    pokemon_stack=[card_id],
                    turn_played=self.state.turn,
                ))

        elif action.type == ActionType.EVOLVE:
            idx = p.hand.index(action.card_id)
            card_id = p.hand.pop(idx)
            slot = self._get_slot(p, action.target_slot)
            if slot:
                slot.pokemon_stack.append(card_id)
                slot.turn_evolved = self.state.turn
                # Evolution removes special conditions
                slot.conditions.clear()

        elif action.type == ActionType.ATTACH_ENERGY:
            if not p.energy_attached_this_turn:
                idx = p.hand.index(action.card_id)
                card_id = p.hand.pop(idx)
                slot = self._get_slot(p, action.target_slot)
                if slot:
                    slot.attached_energy.append(card_id)
                    p.energy_attached_this_turn = True

        elif action.type == ActionType.PLAY_TRAINER:
            self._play_trainer(player_idx, action)

        elif action.type == ActionType.RETREAT:
            self._execute_retreat(player_idx, action)

    def _execute_retreat(self, player_idx: int, action: Action):
        """Execute a retreat action."""
        p = self.state.players[player_idx]
        if not p.active or not p.bench:
            return

        active_card = self.db.get(p.active.card_id)
        retreat_cost = active_card.retreat_cost

        # Check confusion
        if SpecialCondition.CONFUSED in p.active.conditions:
            if not self.rng.coin_flip():
                return  # Retreat fails, energy NOT discarded (1999 rule varies)

        # Discard energy for retreat cost
        if len(p.active.attached_energy) < retreat_cost:
            return

        for _ in range(retreat_cost):
            if p.active.attached_energy:
                energy_id = p.active.attached_energy.pop(0)
                p.discard.append(energy_id)

        # Swap active with bench
        bench_idx = action.new_active
        if 0 <= bench_idx < len(p.bench):
            old_active = p.active
            # Clear conditions on retreat
            old_active.conditions.clear()
            p.active = p.bench[bench_idx]
            p.bench[bench_idx] = old_active

    def _execute_attack(self, player_idx: int, action: Action):
        """Execute an attack."""
        p = self.state.players[player_idx]
        opp_idx = 1 - player_idx
        opp = self.state.players[opp_idx]

        if not p.active or not opp.active:
            return

        attacker = p.active
        defender = opp.active
        attack_card = self.db.get(attacker.card_id)
        attack = attack_card.attacks[action.attack_index]

        # Handle confusion
        if SpecialCondition.CONFUSED in attacker.conditions:
            if not self.rng.coin_flip():
                # Attack self for 20 damage (applies weakness/resistance in 1999)
                self_damage = 20
                # Apply weakness to self
                own_card = self.db.get(attacker.card_id)
                for w in own_card.weaknesses:
                    if w.energy_type in set(own_card.types):
                        self_damage *= 2
                        break
                for r in own_card.resistances:
                    if r.energy_type in set(own_card.types):
                        self_damage -= 30
                        break
                self_damage = max(0, self_damage)
                attacker.damage += self_damage
                self._check_ko(player_idx, 0)  # Check if confused self-KO
                return

        # Calculate and apply damage
        base_damage = attack.base_damage

        # Handle attack effects (for now, just simple damage)
        # TODO: Phase 2 will add effect processing here
        if attack.has_effect:
            base_damage = self._process_attack_effect(player_idx, action, base_damage)

        if base_damage > 0:
            final_damage = calculate_damage(attacker, defender, base_damage)
            defender.damage += final_damage

        # Check KOs everywhere (attacks can damage self, bench, etc.)
        self._check_all_kos()

    def _process_attack_effect(self, player_idx: int, action: Action, base_damage: int) -> int:
        """Process attack effects via the effect registry."""
        p = self.state.players[player_idx]
        card_id = p.active.card_id if p.active else action.card_id

        effect_fn = get_attack_effect(card_id, action.attack_index)
        if effect_fn:
            return effect_fn(self, player_idx, action.attack_index, base_damage)

        # Check for duplicate cards (same name, different set/rarity)
        # Try finding effect by card name + attack name
        card = self.db.get(card_id)
        for other_id, other_card in self.db.cards.items():
            if other_id != card_id and other_card.name == card.name:
                effect_fn = get_attack_effect(other_id, action.attack_index)
                if effect_fn:
                    return effect_fn(self, player_idx, action.attack_index, base_damage)

        return base_damage

    def _play_trainer(self, player_idx: int, action: Action):
        """Play a trainer card using the effect registry."""
        p = self.state.players[player_idx]
        if action.card_id not in p.hand:
            return

        card = self.db.get(action.card_id)
        effect_fn = get_trainer_effect(action.card_id, card.name)

        # Remove from hand and put in discard
        idx = p.hand.index(action.card_id)
        card_id = p.hand.pop(idx)
        p.discard.append(card_id)

        # Execute effect
        if effect_fn:
            effect_fn(self, player_idx)

        # Check for KOs from trainer effects (e.g., bench damage)
        self._check_all_kos()

    def _check_all_kos(self):
        """Check all Pokemon for KOs (after effects that could damage multiple Pokemon)."""
        for pi in range(2):
            p = self.state.players[pi]
            # Check bench first (reverse order to keep indices valid)
            for i in range(len(p.bench) - 1, -1, -1):
                slot = p.bench[i]
                card = self.db.get(slot.card_id)
                if slot.damage >= card.hp:
                    self._check_ko(pi, i + 1)
                    if self.state.is_finished:
                        return
            # Then check active
            if p.active:
                card = self.db.get(p.active.card_id)
                if p.active.damage >= card.hp:
                    self._check_ko(pi, 0)
                    if self.state.is_finished:
                        return

    def _check_ko(self, player_idx: int, slot_idx: int):
        """Check if a Pokémon is knocked out and handle it."""
        p = self.state.players[player_idx]
        opp_idx = 1 - player_idx
        opp = self.state.players[opp_idx]

        slot = self._get_slot(p, slot_idx)
        if slot is None:
            return

        card = self.db.get(slot.card_id)
        if slot.damage >= card.hp:
            # KO! Discard all cards
            for cid in slot.pokemon_stack:
                p.discard.append(cid)
            for cid in slot.attached_energy:
                p.discard.append(cid)

            if slot_idx == 0:
                # Active KO'd
                p.active = None
            else:
                # Bench KO'd
                p.bench.pop(slot_idx - 1)

            # Opponent takes a prize
            if opp.prizes:
                prize_card = opp.prizes.pop(0)
                opp.hand.append(prize_card)

                # Check win: all prizes taken
                if not opp.prizes:
                    self._end_game(opp_idx, "all prizes taken")
                    return

            # Check win: no Pokémon left
            if p.active is None and not p.bench:
                self._end_game(opp_idx, "no Pokémon remaining")
                return

            # If active was KO'd, need to promote from bench
            if p.active is None and p.bench:
                # AI chooses new active
                player = self.players[player_idx]
                bench_idx = player.choose_new_active(self.state, player_idx)
                if bench_idx < 0 or bench_idx >= len(p.bench):
                    bench_idx = 0
                p.active = p.bench.pop(bench_idx)

    def _between_turns(self, player_idx: int):
        """Between-turns phase: special conditions, cleanup."""
        p = self.state.players[player_idx]

        if p.active:
            conditions_to_remove = set()

            # Poison: 10 damage between turns
            if SpecialCondition.POISONED in p.active.conditions:
                p.active.damage += 10
                self._check_ko(player_idx, 0)
                if self.state.is_finished:
                    return

            # Sleep: flip to wake up
            if SpecialCondition.ASLEEP in p.active.conditions:
                if self.rng.coin_flip():
                    conditions_to_remove.add(SpecialCondition.ASLEEP)

            # Paralysis: remove after the turn
            if SpecialCondition.PARALYZED in p.active.conditions:
                conditions_to_remove.add(SpecialCondition.PARALYZED)

            p.active.conditions -= conditions_to_remove

        # Clear PlusPower and Defender
        for slot in p.all_pokemon_slots():
            slot.pluspower_count = 0
            slot.defender_count = 0

        # Switch active player
        self.state.active_player = 1 - self.state.active_player
        self.state.turn += 1
        self.state.phase = Phase.PLAYER_TURN

    def _end_game(self, winner: int, reason: str):
        self.state.phase = Phase.FINISHED
        self.state.winner = winner
        self.state.game_over_reason = reason

    def _get_slot(self, player: PlayerState, slot_idx: int) -> Optional[PokemonSlot]:
        """Get slot by index: 0 = active, 1+ = bench."""
        if slot_idx == 0:
            return player.active
        bench_idx = slot_idx - 1
        if 0 <= bench_idx < len(player.bench):
            return player.bench[bench_idx]
        return None
