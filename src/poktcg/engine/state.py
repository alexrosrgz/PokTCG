"""Game state model for the Pokémon TCG engine."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Phase(Enum):
    SETUP = "setup"
    PLAYER_TURN = "player_turn"
    BETWEEN_TURNS = "between_turns"
    FINISHED = "finished"


class SpecialCondition(Enum):
    ASLEEP = "asleep"
    CONFUSED = "confused"
    PARALYZED = "paralyzed"
    POISONED = "poisoned"


@dataclass
class PokemonSlot:
    """A Pokémon in play (active or benched)."""
    pokemon_stack: list[str]  # Card IDs: bottom = basic, top = highest evolution
    damage: int = 0  # Total damage (in HP, not counters)
    attached_energy: list[str] = field(default_factory=list)  # Energy card IDs
    conditions: set[SpecialCondition] = field(default_factory=set)
    turn_played: int = 0  # Turn this Pokemon was put into play
    turn_evolved: int = 0  # Turn this Pokemon was last evolved
    used_power_this_turn: bool = False
    # Temporary per-turn effects
    pluspower_count: int = 0  # PlusPower attached this turn
    defender_count: int = 0  # Defender attached this turn

    @property
    def card_id(self) -> str:
        """The current (top) Pokémon card ID."""
        return self.pokemon_stack[-1]

    @property
    def basic_card_id(self) -> str:
        """The basic Pokémon card ID at the bottom of the stack."""
        return self.pokemon_stack[0]

    def clone(self) -> PokemonSlot:
        return PokemonSlot(
            pokemon_stack=self.pokemon_stack[:],
            damage=self.damage,
            attached_energy=self.attached_energy[:],
            conditions=set(self.conditions),
            turn_played=self.turn_played,
            turn_evolved=self.turn_evolved,
            used_power_this_turn=self.used_power_this_turn,
            pluspower_count=self.pluspower_count,
            defender_count=self.defender_count,
        )


@dataclass
class PlayerState:
    """State of one player."""
    deck: list[str]  # Card IDs (order matters - top of deck is index 0)
    hand: list[str]  # Card IDs
    discard: list[str]  # Card IDs
    prizes: list[str]  # Card IDs (face down)
    active: Optional[PokemonSlot] = None
    bench: list[PokemonSlot] = field(default_factory=list)  # Max 5
    energy_attached_this_turn: bool = False

    def clone(self) -> PlayerState:
        return PlayerState(
            deck=self.deck[:],
            hand=self.hand[:],
            discard=self.discard[:],
            prizes=self.prizes[:],
            active=self.active.clone() if self.active else None,
            bench=[s.clone() for s in self.bench],
            energy_attached_this_turn=self.energy_attached_this_turn,
        )

    def all_pokemon_slots(self) -> list[PokemonSlot]:
        """All Pokémon in play (active + bench)."""
        slots = []
        if self.active:
            slots.append(self.active)
        slots.extend(self.bench)
        return slots

    def get_slot_index(self, slot: PokemonSlot) -> int:
        """Get slot index: 0 = active, 1-5 = bench."""
        if slot is self.active:
            return 0
        for i, s in enumerate(self.bench):
            if slot is s:
                return i + 1
        raise ValueError("Slot not found")

    def draw_card(self) -> Optional[str]:
        """Draw from top of deck. Returns card ID or None if empty."""
        if not self.deck:
            return None
        card_id = self.deck.pop(0)
        self.hand.append(card_id)
        return card_id

    def draw_cards(self, n: int) -> list[str]:
        """Draw n cards. Returns list of drawn card IDs."""
        drawn = []
        for _ in range(n):
            card = self.draw_card()
            if card is None:
                break
            drawn.append(card)
        return drawn


@dataclass
class GameState:
    """Complete game state."""
    players: list[PlayerState]  # Always 2 players
    turn: int = 0
    active_player: int = 0  # 0 or 1
    phase: Phase = Phase.SETUP
    winner: Optional[int] = None  # 0, 1, or None
    game_over_reason: str = ""

    def clone(self) -> GameState:
        return GameState(
            players=[p.clone() for p in self.players],
            turn=self.turn,
            active_player=self.active_player,
            phase=self.phase,
            winner=self.winner,
            game_over_reason=self.game_over_reason,
        )

    @property
    def current_player(self) -> PlayerState:
        return self.players[self.active_player]

    @property
    def opponent(self) -> PlayerState:
        return self.players[1 - self.active_player]

    @property
    def is_finished(self) -> bool:
        return self.phase == Phase.FINISHED
