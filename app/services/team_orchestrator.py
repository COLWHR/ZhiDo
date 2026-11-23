"""Orchestration helpers for the multi-agent team group chat.

The team module is intentionally isolated from the round-table forum: it owns its
own tables, CRUD and SSE endpoint. This service only holds pure, side-effect-free
helpers shared between the endpoint and tests.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def member_persona_dict(member: Any) -> Dict[str, Any]:
    """Build the persona dict expected by ``build_llm_messages`` from a member row."""
    persona = getattr(member, "persona", None)
    if persona is None:
        return {}
    return {
        "id": getattr(persona, "id", None),
        "name": getattr(persona, "name", ""),
        "title": getattr(persona, "title", None),
        "bio": getattr(persona, "bio", None),
        "system_prompt": getattr(persona, "system_prompt", None),
        "skills": getattr(persona, "skills", None) or ["chat.reply"],
        "skill_policy": getattr(persona, "skill_policy", None) or {},
        "modalities": getattr(persona, "modalities", None) or ["text"],
        "owner_id": getattr(persona, "owner_id", None),
    }


def _member_persona_id(member: Any) -> Optional[int]:
    pid = getattr(member, "persona_id", None)
    if pid is not None:
        return int(pid)
    persona = getattr(member, "persona", None)
    return getattr(persona, "id", None)


def resolve_mentioned_members(team: Any, mentioned_ids: List[int]) -> List[Any]:
    """Return the group members that were @-mentioned, preserving request order.

    Unknown or non-member ids are dropped silently so the endpoint can decide
    whether to fall back to a text-based mention match.
    """
    members = list(getattr(team, "members", []) or [])
    by_id: Dict[int, Any] = {}
    for member in members:
        pid = _member_persona_id(member)
        if pid is not None:
            by_id[int(pid)] = member

    resolved: List[Any] = []
    seen = set()
    for raw_id in mentioned_ids or []:
        try:
            pid = int(raw_id)
        except (TypeError, ValueError):
            continue
        if pid in by_id and pid not in seen:
            resolved.append(by_id[pid])
            seen.add(pid)
    return resolved


def parse_at_from_text(content: str, members: List[Any]) -> List[int]:
    """Fallback: detect ``@成员名`` mentions in the raw message text.

    The explicit ``mentioned_persona_ids`` submitted by the client takes
    precedence; this only fills in names the client did not resolve.
    """
    text = str(content or "")
    if not text:
        return []
    found: List[int] = []
    seen = set()
    for member in members:
        persona = getattr(member, "persona", None)
        name = str(getattr(persona, "name", "") or "").strip()
        if not name:
            continue
        if re.search(rf"@\s*{re.escape(name)}", text):
            pid = _member_persona_id(member)
            if pid is not None and pid not in seen:
                found.append(int(pid))
                seen.add(pid)
    return found


def history_to_context(messages: List[Any]) -> List[Dict[str, Any]]:
    """Convert persisted team messages into the ``context_messages`` shape.

    System guidance messages are excluded: they are UI hints, not agent utterances,
    and must not be fed back into the model as prior conversation.
    """
    context: List[Dict[str, Any]] = []
    for msg in messages or []:
        sender_type = str(getattr(msg, "sender_type", "") or "")
        if sender_type == "system":
            continue
        role = "user" if sender_type == "user" else "assistant"
        content = str(getattr(msg, "content", "") or "")
        attachments = getattr(msg, "attachments", []) or []
        entry: Dict[str, Any] = {"speaker": role, "content": content}
        if attachments:
            entry["attachments"] = attachments
        context.append(entry)
    return context


def trim_context(context: List[Dict[str, Any]], max_messages: int) -> List[Dict[str, Any]]:
    """Keep only the most recent ``max_messages`` context entries."""
    if max_messages <= 0 or len(context) <= max_messages:
        return context
    return context[-max_messages:]


def attachments_to_dicts(attachments: List[Any]) -> List[Dict[str, Any]]:
    """Normalize incoming attachment schemas to plain dicts for the runtime."""
    result: List[Dict[str, Any]] = []
    for att in attachments or []:
        if isinstance(att, dict):
            result.append(att)
        else:
            result.append(att.model_dump())
    return result
