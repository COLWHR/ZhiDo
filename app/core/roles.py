from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

VALID_ROLES = {"user", "admin", "god"}
ROLE_ALIASES = {"u": "user", "": "user", "normal": "user"}


def resolve_registration_role(requested: str | None) -> str:
    """Never let a public registration endpoint pick its own privilege level.

    Elevated roles are only honoured when an operator explicitly turns on
    ALLOW_ROLE_SELECTION (e.g. seeding an initial admin). Otherwise the account
    is created as a plain user and the attempt is logged.
    """
    role = (requested or "user").strip().lower()
    role = ROLE_ALIASES.get(role, role)
    if role not in VALID_ROLES:
        role = "user"

    if role != "user" and not settings.ALLOW_ROLE_SELECTION:
        logger.warning("Registration attempted to claim role=%s; downgraded to user.", role)
        return "user"
    return role
