from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Iterable

from app.services.skill_runtime import get_skill_catalog

logger = logging.getLogger(__name__)


def _row_value(row, key: str):
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _existing_columns(conn, table_name: str, is_postgres: bool) -> set[str]:
    if is_postgres:
        rs = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = ?
            """,
            [table_name],
        )
        return {str(_row_value(row, "column_name")) for row in getattr(rs, "rows", []) if _row_value(row, "column_name")}

    rs = conn.execute(f"PRAGMA table_info({table_name})")
    return {str(_row_value(row, "name")) for row in getattr(rs, "rows", []) if _row_value(row, "name")}


def _add_columns_if_missing(conn, table_name: str, columns: Iterable[tuple[str, str]], is_postgres: bool) -> None:
    existing = _existing_columns(conn, table_name, is_postgres)
    if not existing:
        # Table not created yet (fresh or legacy database); schema.sql owns creation.
        logger.debug("Skipping column migration for missing table %s", table_name)
        return
    for column_name, ddl in columns:
        if column_name in existing:
            continue
        logger.info("Adding missing column %s.%s", table_name, column_name)
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def ensure_round_schedule_table(conn, is_postgres: bool) -> None:
    """Create the RAAMS round scheduling record table on legacy databases."""
    if is_postgres:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS round_schedule_records (
                id SERIAL PRIMARY KEY,
                forum_id INTEGER NOT NULL,
                turn_count INTEGER DEFAULT 0,
                risk_level VARCHAR(10) DEFAULT 'L0',
                risk_signals JSONB DEFAULT '[]'::jsonb,
                escalated BOOLEAN DEFAULT FALSE,
                gate_action VARCHAR(20) DEFAULT 'normal',
                turn_mode VARCHAR(20) DEFAULT 'transition',
                uncertainty VARCHAR(10) DEFAULT 'low',
                interrupted_by_user BOOLEAN DEFAULT FALSE,
                selected_speaker VARCHAR(255),
                candidates JSONB DEFAULT '[]'::jsonb,
                speak_tokens INTEGER DEFAULT 0,
                latency_ms INTEGER DEFAULT 0,
                ablation JSONB DEFAULT '{}'::jsonb,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (forum_id) REFERENCES forums(id) ON DELETE CASCADE
            )
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS round_schedule_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            forum_id INTEGER NOT NULL,
            turn_count INTEGER DEFAULT 0,
            risk_level TEXT DEFAULT 'L0',
            risk_signals TEXT DEFAULT '[]',
            escalated INTEGER DEFAULT 0,
            gate_action TEXT DEFAULT 'normal',
            turn_mode TEXT DEFAULT 'transition',
            uncertainty TEXT DEFAULT 'low',
            interrupted_by_user INTEGER DEFAULT 0,
            selected_speaker TEXT,
            candidates TEXT DEFAULT '[]',
            speak_tokens INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            ablation TEXT DEFAULT '{}',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (forum_id) REFERENCES forums(id) ON DELETE CASCADE
        )
        """
    )


def ensure_knowledge_schema(conn, is_postgres: bool) -> None:
    """Create the persona knowledge-base table on legacy databases."""
    if is_postgres:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS persona_knowledge (
                id SERIAL PRIMARY KEY,
                persona_id INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                mime_type TEXT,
                size INTEGER,
                storage_url TEXT NOT NULL,
                sha256 VARCHAR(128),
                extracted_text TEXT,
                char_count INTEGER DEFAULT 0,
                status VARCHAR(50) DEFAULT 'ready',
                meta JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE CASCADE,
                FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS persona_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            persona_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            mime_type TEXT,
            size INTEGER,
            storage_url TEXT NOT NULL,
            sha256 TEXT,
            extracted_text TEXT,
            char_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ready',
            meta TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE CASCADE,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def ensure_credit_config_schema(conn, is_postgres: bool) -> None:
    """Create credit ledger / system config / audit tables and backfill the balance column."""
    _add_columns_if_missing(
        conn,
        "users",
        [("credits_balance", "INTEGER DEFAULT 1000")],
        is_postgres,
    )

    if is_postgres:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS credit_transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                change_amount INTEGER NOT NULL,
                balance_after INTEGER NOT NULL DEFAULT 0,
                reason TEXT NOT NULL,
                category VARCHAR(50) DEFAULT 'text',
                tokens_input INTEGER DEFAULT 0,
                tokens_output INTEGER DEFAULT 0,
                vision_count INTEGER DEFAULT 0,
                reference_type VARCHAR(50),
                reference_id INTEGER,
                note TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS system_config (
                id SERIAL PRIMARY KEY,
                config_key VARCHAR(255) NOT NULL UNIQUE,
                config_value TEXT,
                category VARCHAR(50) DEFAULT 'system',
                label TEXT,
                description TEXT,
                updated_by INTEGER,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_audit_logs (
                id SERIAL PRIMARY KEY,
                actor_id INTEGER,
                action TEXT NOT NULL,
                target_type VARCHAR(50),
                target_id INTEGER,
                detail TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            change_amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            category TEXT DEFAULT 'text',
            tokens_input INTEGER DEFAULT 0,
            tokens_output INTEGER DEFAULT 0,
            vision_count INTEGER DEFAULT 0,
            reference_type TEXT,
            reference_id INTEGER,
            note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT NOT NULL UNIQUE,
            config_value TEXT,
            category TEXT DEFAULT 'system',
            label TEXT,
            description TEXT,
            updated_by INTEGER,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id INTEGER,
            detail TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )


# Default dynamic configuration. Empty LLM values mean "fall back to .env / env var".
DEFAULT_CONFIG_DEFAULTS: list[dict[str, Any]] = [
    {"key": "llm.api_key", "value": "", "category": "llm", "label": "大模型 API Key", "description": "留空则使用 .env / 环境变量中的 API_KEY"},
    {"key": "llm.base_url", "value": "", "category": "llm", "label": "模型接口地址", "description": "留空则使用 .env / 环境变量中的 BASE_URL"},
    {"key": "llm.model_name", "value": "", "category": "llm", "label": "文本模型名称", "description": "留空则使用默认 MODEL_NAME"},
    {"key": "llm.vision_model", "value": "", "category": "llm", "label": "视觉模型名称", "description": "留空则使用默认 VOLC_VISION_MODEL"},
    {"key": "llm.vision_base_url", "value": "", "category": "llm", "label": "视觉模型接口地址", "description": "留空则使用默认 VOLC_BASE_URL"},
    {"key": "llm.vision_api_key", "value": "", "category": "llm", "label": "视觉模型 API Key", "description": "留空则使用默认 VOLC_API_KEY"},
    {"key": "credit.signup_bonus", "value": "1000", "category": "credit", "label": "新用户赠送积分", "description": "注册时一次性赠送的积分额度"},
    {"key": "credit.per_1k_text_tokens", "value": "1", "category": "credit", "label": "每 1000 文本 token 积分", "description": "按估算 token 折算的扣费标准"},
    {"key": "credit.vision_per_call", "value": "5", "category": "credit", "label": "每次图片识别扣费", "description": "含图片输入的调用固定扣除的积分"},
    {"key": "credit.min_balance", "value": "0", "category": "credit", "label": "最低余额阈值", "description": "低于该余额时禁止发起新调用"},
]


def seed_default_config(conn) -> None:
    """Insert default config rows that do not exist yet; never overwrite operator values."""
    for item in DEFAULT_CONFIG_DEFAULTS:
        conn.execute(
            """
            INSERT INTO system_config (config_key, config_value, category, label, description)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(config_key) DO NOTHING
            """,
            [item["key"], item["value"], item["category"], item["label"], item["description"]],
        )


def ensure_multimodal_schema(conn, is_postgres: bool) -> None:
    user_columns = [
        ("avatar", "TEXT"),
        (
            "avatar_kind",
            "VARCHAR(50) DEFAULT 'initial'" if is_postgres else "TEXT DEFAULT 'initial'",
        ),
        ("avatar_updated_at", "TIMESTAMP WITH TIME ZONE" if is_postgres else "DATETIME"),
    ]

    persona_columns = [
        ("avatar", "TEXT"),
        ("skills", "JSONB DEFAULT '[]'::jsonb" if is_postgres else "TEXT DEFAULT '[]'"),
        ("skill_policy", "JSONB DEFAULT '{}'::jsonb" if is_postgres else "TEXT DEFAULT '{}'"),
        ("modalities", "JSONB DEFAULT '[\"text\"]'::jsonb" if is_postgres else "TEXT DEFAULT '[\"text\"]'"),
        ("capabilities_version", "INTEGER DEFAULT 1"),
    ]

    chat_message_columns = [
        ("message_type", "VARCHAR(50) DEFAULT 'text'" if is_postgres else "TEXT DEFAULT 'text'"),
        ("metadata", "JSONB DEFAULT '{}'::jsonb" if is_postgres else "TEXT DEFAULT '{}'"),
    ]

    attachment_columns = [
        ("persona_id", "INTEGER"),
        ("chat_message_id", "INTEGER"),
        ("session_id", "INTEGER"),
        ("kind", "VARCHAR(50)" if is_postgres else "TEXT"),
        ("preview_url", "TEXT"),
        ("sha256", "VARCHAR(128)" if is_postgres else "TEXT"),
        ("meta", "JSONB DEFAULT '{}'::jsonb" if is_postgres else "TEXT DEFAULT '{}'"),
    ]

    artifact_columns = [
        ("persona_id", "INTEGER"),
        ("task_run_id", "INTEGER"),
        ("preview_url", "TEXT"),
        ("version", "INTEGER DEFAULT 1"),
        ("status", "VARCHAR(50) DEFAULT 'ready'" if is_postgres else "TEXT DEFAULT 'ready'"),
        ("meta", "JSONB DEFAULT '{}'::jsonb" if is_postgres else "TEXT DEFAULT '{}'"),
    ]

    task_run_columns = [
        ("persona_id", "INTEGER"),
        ("skill_key", "VARCHAR(255)" if is_postgres else "TEXT"),
        ("session_id", "INTEGER"),
        ("status", "VARCHAR(50) DEFAULT 'queued'" if is_postgres else "TEXT DEFAULT 'queued'"),
        ("progress", "INTEGER DEFAULT 0"),
        ("input_payload", "JSONB DEFAULT '{}'::jsonb" if is_postgres else "TEXT DEFAULT '{}'"),
        ("output_payload", "JSONB DEFAULT '{}'::jsonb" if is_postgres else "TEXT DEFAULT '{}'"),
        ("error_message", "TEXT"),
        ("finished_at", "TIMESTAMP WITH TIME ZONE" if is_postgres else "DATETIME"),
    ]

    _add_columns_if_missing(conn, "users", user_columns, is_postgres)
    _add_columns_if_missing(conn, "personas", persona_columns, is_postgres)
    _add_columns_if_missing(conn, "chat_messages", chat_message_columns, is_postgres)
    _add_columns_if_missing(conn, "attachments", attachment_columns, is_postgres)
    _add_columns_if_missing(conn, "artifacts", artifact_columns, is_postgres)
    _add_columns_if_missing(conn, "task_runs", task_run_columns, is_postgres)
    ensure_round_schedule_table(conn, is_postgres)
    ensure_knowledge_schema(conn, is_postgres)
    ensure_credit_config_schema(conn, is_postgres)


def ensure_team_schema(conn, is_postgres: bool) -> None:
    """Create the multi-agent team group-chat tables on legacy databases."""
    if is_postgres:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS teams (
                id SERIAL PRIMARY KEY,
                owner_id INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                description TEXT DEFAULT '',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS team_members (
                id SERIAL PRIMARY KEY,
                team_id INTEGER NOT NULL,
                persona_id INTEGER NOT NULL,
                role VARCHAR(20) DEFAULT 'member',
                joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (team_id, persona_id),
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS team_messages (
                id SERIAL PRIMARY KEY,
                team_id INTEGER NOT NULL,
                sender_type VARCHAR(20) NOT NULL,
                user_id INTEGER,
                persona_id INTEGER,
                speaker_name VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                attachments JSONB DEFAULT '[]'::jsonb,
                mentioned_persona_ids JSONB DEFAULT '[]'::jsonb,
                message_type VARCHAR(20) DEFAULT 'text',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE SET NULL
            )
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            persona_id INTEGER NOT NULL,
            role TEXT DEFAULT 'member',
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (team_id, persona_id),
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS team_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            user_id INTEGER,
            persona_id INTEGER,
            speaker_name TEXT NOT NULL,
            content TEXT NOT NULL,
            attachments TEXT DEFAULT '[]',
            mentioned_persona_ids TEXT DEFAULT '[]',
            message_type TEXT DEFAULT 'text',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (persona_id) REFERENCES personas(id) ON DELETE SET NULL
        )
        """
    )


def ensure_decision_schema(conn, is_postgres: bool) -> None:
    """Persist each router decision (label / confidence / layer / latency) for audit."""
    if is_postgres:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_logs (
                id SERIAL PRIMARY KEY,
                scope VARCHAR(20) NOT NULL,
                reference_id INTEGER,
                user_id INTEGER,
                persona_id INTEGER,
                text TEXT DEFAULT '',
                label VARCHAR(20) NOT NULL,
                confidence DOUBLE PRECISION,
                layer VARCHAR(10) NOT NULL,
                keyword TEXT,
                elapsed_ms DOUBLE PRECISION,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            reference_id INTEGER,
            user_id INTEGER,
            persona_id INTEGER,
            text TEXT DEFAULT '',
            label TEXT NOT NULL,
            confidence REAL,
            layer TEXT NOT NULL,
            keyword TEXT,
            elapsed_ms REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def seed_default_skills(conn) -> None:
    catalog = get_skill_catalog()
    if not catalog:
        return

    for skill in catalog:
        timestamp = datetime.now()
        conn.execute(
            """
            INSERT INTO skills (
                skill_key, name, category, description, input_modalities, output_types,
                required_models, required_tools, params_schema, permission_scope,
                cost_level, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(skill_key) DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                description = excluded.description,
                input_modalities = excluded.input_modalities,
                output_types = excluded.output_types,
                required_models = excluded.required_models,
                required_tools = excluded.required_tools,
                params_schema = excluded.params_schema,
                permission_scope = excluded.permission_scope,
                cost_level = excluded.cost_level,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            [
                skill["skill_key"],
                skill["name"],
                skill["category"],
                skill.get("description"),
                json.dumps(skill.get("input_modalities", [])),
                json.dumps(skill.get("output_types", [])),
                json.dumps(skill.get("required_models", [])),
                json.dumps(skill.get("required_tools", [])),
                json.dumps(skill.get("params_schema", {})),
                json.dumps(skill.get("permission_scope", [])),
                skill.get("cost_level", "low"),
                skill.get("status", "active"),
                timestamp,
                timestamp,
            ],
        )
