"""Authentication-related enums."""

from enum import StrEnum


class AuthMode(StrEnum):
    """Which identity provider validates the bearer token — see Phase 6."""

    SIMULATED = "simulated"
    ENTRA = "entra"
