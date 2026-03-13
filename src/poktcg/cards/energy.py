from enum import Enum


class EnergyType(Enum):
    GRASS = "Grass"
    FIRE = "Fire"
    WATER = "Water"
    LIGHTNING = "Lightning"
    PSYCHIC = "Psychic"
    FIGHTING = "Fighting"
    COLORLESS = "Colorless"

    @classmethod
    def from_str(cls, s: str) -> "EnergyType":
        return cls(s)
