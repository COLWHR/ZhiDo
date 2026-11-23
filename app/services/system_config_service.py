"""Dynamic system configuration persisted in the database.

Values in ``system_config`` override ``.env`` / environment variables at
runtime. A short in-process cache keeps hot reads (LLM client build, credit
estimation) off the database; the cache is refreshed on startup and after any
admin write.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Optional

from app.core.config import settings
from app.db.client import fetch_all, fetch_one

logger = logging.getLogger(__name__)

# In-process cache: config_key -> raw string value.
_cache: dict[str, str] = {}
_cache_loaded = False


def refresh_config_cache(db: Any) -> None:
    """Reload every config row into the in-process cache."""
    global _cache_loaded
    try:
        rs = db.execute("SELECT config_key, config_value FROM system_config")
        rows = fetch_all(rs)
        _cache.clear()
        for row in rows:
            key = getattr(row, "config_key", None)
            if key is not None:
                _cache[str(key)] = "" if getattr(row, "config_value", None) is None else str(getattr(row, "config_value"))
        _cache_loaded = True
        logger.debug("System config cache refreshed with %s entries.", len(_cache))
    except Exception as exc:  # pragma: no cover - defensive, keep app booting
        logger.warning("Failed to refresh system config cache: %s", exc)
        _cache_loaded = False


def _raw(key: str) -> Optional[str]:
    value = _cache.get(key)
    if value is None:
        return None
    value = value.strip()
    return value or None


def get_config(db: Any, key: str, default: Optional[str] = None) -> Optional[str]:
    """Read a raw config value, falling back to the database when the cache is empty."""
    global _cache_loaded
    if not _cache_loaded:
        refresh_config_cache(db)
    cached = _raw(key)
    if cached is not None:
        return cached
    try:
        rs = db.execute("SELECT config_value FROM system_config WHERE config_key = ?", [key])
        row = fetch_one(rs)
        if row is not None and getattr(row, "config_value", None) is not None:
            return str(row.config_value)
    except Exception as exc:  # pragma: no cover
        logger.warning("Config lookup failed for %s: %s", key, exc)
    return default


def get_config_str(db: Any, key: str, default: str = "") -> str:
    value = get_config(db, key, None)
    return value if value is not None else default


def get_config_int(db: Any, key: str, default: int = 0) -> int:
    raw = get_config(db, key, None)
    if raw is None or raw == "":
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


def get_config_bool(db: Any, key: str, default: bool = False) -> bool:
    raw = get_config(db, key, None)
    if raw is None:
        return default
    return raw.strip().lower() in {"true", "1", "yes", "on", "是"}


def set_config(db: Any, key: str, value: Any, actor_id: Optional[int] = None) -> dict[str, Any]:
    """Upsert a config value and refresh the in-process cache."""
    text_value = "" if value is None else str(value)
    now = datetime.now()
    db_execute = db.execute
    # Reuse transactional commit helper when available.
    from app.db.client import db_execute_commit

    db_execute_commit(
        db,
        """
        INSERT INTO system_config (config_key, config_value, updated_by, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(config_key) DO UPDATE SET
            config_value = excluded.config_value,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at
        """,
        [key, text_value, actor_id, now],
    )
    _cache[key] = text_value
    return {"config_key": key, "config_value": text_value, "updated_at": now}


def list_configs(db: Any, category: Optional[str] = None) -> list[dict[str, Any]]:
    if category:
        rs = db.execute(
            "SELECT * FROM system_config WHERE category = ? ORDER BY category, config_key",
            [category],
        )
    else:
        rs = db.execute("SELECT * FROM system_config ORDER BY category, config_key")
    rows = fetch_all(rs)
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "key": getattr(row, "config_key", None),
                "value": getattr(row, "config_value", None),
                "category": getattr(row, "category", None),
                "label": getattr(row, "label", None),
                "description": getattr(row, "description", None),
                "updated_at": getattr(row, "updated_at", None),
                "updated_by": getattr(row, "updated_by", None),
            }
        )
    return result


# --- Resolved LLM settings: DB override wins, .env / env var is the fallback ---

def _override_or_env(key: str, env_names: list[str], fallback: str) -> str:
    override = _raw(key)
    if override is not None:
        return override
    for env_name in env_names:
        env_value = os.environ.get(env_name)
        if env_value:
            return env_value
    return fallback


def resolved_api_key() -> str:
    return _override_or_env("llm.api_key", ["API_KEY", "ZHIPUAI_API_KEY"], settings.API_KEY or "")


def resolved_base_url() -> str:
    return _override_or_env("llm.base_url", ["BASE_URL"], settings.final_base_url)


def resolved_model_name() -> str:
    return _override_or_env("llm.model_name", ["MODEL_NAME"], settings.final_model_name)


def resolved_vision_model() -> str:
    return _override_or_env("llm.vision_model", ["VOLC_VISION_MODEL"], settings.VOLC_VISION_MODEL or "")


def resolved_vision_base_url() -> str:
    return _override_or_env("llm.vision_base_url", ["VOLC_BASE_URL"], settings.VOLC_BASE_URL or "")


def resolved_vision_api_key() -> str:
    return _override_or_env("llm.vision_api_key", ["VOLC_API_KEY"], settings.VOLC_API_KEY or "")
