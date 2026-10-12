"""Vehicle-related enums."""

from enum import StrEnum


class VehicleCategory(StrEnum):
    ECONOMY = "economy"
    COMPACT = "compact"
    SUV = "suv"
    PREMIUM = "premium"
    VAN = "van"
