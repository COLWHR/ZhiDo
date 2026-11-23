from __future__ import annotations

import json
from typing import Any, Optional

from app.db.client import fetch_one, fetch_all, db_execute_commit


def create_round_record(db, record: dict[str, Any]):
    """Insert one RAAMS round scheduling record.

    record keys: forum_id, turn_count, risk_level, risk_signals(list), escalated(bool),
    gate_action, turn_mode, uncertainty, interrupted_by_user(bool), selected_speaker,
    candidates(list[dict]), speak_tokens, latency_ms, ablation(dict).
    """
    risk_signals = json.dumps(record.get("risk_signals", []), ensure_ascii=False)
    candidates = json.dumps(record.get("candidates", []), ensure_ascii=False)
    ablation = json.dumps(record.get("ablation", {}), ensure_ascii=False)
    escalated = 1 if record.get("escalated") else 0
    interrupted = 1 if record.get("interrupted_by_user") else 0

    rs = db_execute_commit(
        db,
        """
        INSERT INTO round_schedule_records (
            forum_id, turn_count, risk_level, risk_signals, escalated, gate_action,
            turn_mode, uncertainty, interrupted_by_user, selected_speaker,
            candidates, speak_tokens, latency_ms, ablation
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING *
        """,
        [
            record["forum_id"],
            record.get("turn_count", 0),
            record.get("risk_level", "L0"),
            risk_signals,
            escalated,
            record.get("gate_action", "normal"),
            record.get("turn_mode", "transition"),
            record.get("uncertainty", "low"),
            interrupted,
            record.get("selected_speaker"),
            candidates,
            record.get("speak_tokens", 0),
            record.get("latency_ms", 0),
            ablation,
        ],
    )
    return fetch_one(rs)


def get_round_records(db, forum_id: int, limit: Optional[int] = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM round_schedule_records WHERE forum_id = ? ORDER BY turn_count ASC, id ASC"
    params: list[Any] = [forum_id]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    rs = db.execute(query, params)
    return fetch_all(rs)
