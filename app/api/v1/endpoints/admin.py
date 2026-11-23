from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import require_admin
from app.core.cache import cache_service
from app.core.roles import VALID_ROLES
from app.crud import (
    delete_knowledge_doc,
    get_persona,
    list_knowledge_docs,
    list_skills,
    update_persona,
    user_cache_key,
)
from app.db.client import db_execute_commit, fetch_all, fetch_one
from app.db.session import get_db
from app.schemas import PersonaUpdate
from app.services import credit_service, system_config_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Request bodies ---

class CreditAdjustRequest(BaseModel):
    amount: int
    note: Optional[str] = None


class RoleUpdateRequest(BaseModel):
    role: str


class ConfigUpdateRequest(BaseModel):
    value: Optional[str] = None


class SkillAdminUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    params_schema: Optional[dict[str, Any]] = None


def _audit(db: Any, actor_id: int, action: str, target_type: Optional[str] = None,
           target_id: Optional[int] = None, detail: Optional[str] = None) -> None:
    try:
        db_execute_commit(
            db,
            """
            INSERT INTO admin_audit_logs (actor_id, action, target_type, target_id, detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [actor_id, action, target_type, target_id, detail, datetime.now()],
        )
    except Exception as exc:  # pragma: no cover - audit must not break the request
        logger.warning("Failed to write admin audit log: %s", exc)


# --- Overview ---

@router.get("/overview")
def admin_overview(db: Any = Depends(get_db), _: Any = Depends(require_admin)):
    summary = credit_service.get_summary(db)
    counts: dict[str, int] = {}
    for label, table in (("personas", "personas"), ("skills", "skills"), ("forums", "forums")):
        rs = db.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
        row = fetch_one(rs)
        counts[label] = int(getattr(row, "cnt", 0) or 0)
    return {"credits": summary, "counts": counts}


# --- Users & credits ---

@router.get("/users")
def admin_list_users(
    keyword: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Any = Depends(get_db),
    _: Any = Depends(require_admin),
):
    if keyword:
        like = f"%{keyword.strip()}%"
        rs = db.execute(
            """
            SELECT id, username, role, avatar, created_at, credits_balance
            FROM users WHERE username LIKE ? ORDER BY id ASC LIMIT ? OFFSET ?
            """,
            [like, limit, offset],
        )
    else:
        rs = db.execute(
            """
            SELECT id, username, role, avatar, created_at, credits_balance
            FROM users ORDER BY id ASC LIMIT ? OFFSET ?
            """,
            [limit, offset],
        )
    rows = fetch_all(rs)
    return [
        {
            "id": getattr(r, "id", None),
            "username": getattr(r, "username", None),
            "role": getattr(r, "role", "user"),
            "avatar": getattr(r, "avatar", None),
            "created_at": getattr(r, "created_at", None),
            "credits_balance": int(getattr(r, "credits_balance", 0) or 0),
        }
        for r in rows
    ]


@router.get("/users/{user_id}/transactions")
def admin_user_transactions(
    user_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: Any = Depends(get_db),
    _: Any = Depends(require_admin),
):
    return credit_service.list_transactions(db, user_id=user_id, limit=limit)


@router.patch("/users/{user_id}/credits")
def admin_adjust_credits(
    user_id: int,
    payload: CreditAdjustRequest,
    db: Any = Depends(get_db),
    admin: Any = Depends(require_admin),
):
    target = fetch_one(db.execute("SELECT id, username FROM users WHERE id = ?", [user_id]))
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    result = credit_service.adjust(db, user_id, payload.amount, note=payload.note)
    cache_service.delete_cache(user_cache_key(getattr(target, "username", "")))
    _audit(
        db, admin.id, "adjust_credits", target_type="user", target_id=user_id,
        detail=f"调整 {payload.amount} 积分，余额 {result['balance']}；备注：{payload.note or ''}",
    )
    return {"id": user_id, "username": getattr(target, "username", None), **result}


@router.patch("/users/{user_id}/role")
def admin_set_role(
    user_id: int,
    payload: RoleUpdateRequest,
    db: Any = Depends(get_db),
    admin: Any = Depends(require_admin),
):
    role = payload.role.strip().lower()
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="无效角色")
    target = fetch_one(db.execute("SELECT id, username FROM users WHERE id = ?", [user_id]))
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    db_execute_commit(db, "UPDATE users SET role = ? WHERE id = ?", [role, user_id])
    cache_service.delete_cache(user_cache_key(getattr(target, "username", "")))
    _audit(db, admin.id, "set_role", target_type="user", target_id=user_id, detail=f"角色改为 {role}")
    return {"id": user_id, "role": role}


# --- System configuration (LLM API + credit rules) ---

@router.get("/config")
def admin_list_config(
    category: Optional[str] = Query(default=None),
    db: Any = Depends(get_db),
    _: Any = Depends(require_admin),
):
    return system_config_service.list_configs(db, category=category)


@router.put("/config/{key}")
def admin_update_config(
    key: str,
    payload: ConfigUpdateRequest,
    db: Any = Depends(get_db),
    admin: Any = Depends(require_admin),
):
    system_config_service.set_config(db, key, payload.value, actor_id=admin.id)
    _audit(db, admin.id, "update_config", target_type="config", detail=f"{key} = {payload.value}")
    return {"config_key": key, "config_value": payload.value}


# --- Personas (built-in / custom agents) ---

@router.get("/personas")
def admin_list_personas(
    db: Any = Depends(get_db),
    _: Any = Depends(require_admin),
):
    rs = db.execute(
        """
        SELECT p.*, u.username AS owner_name
        FROM personas p LEFT JOIN users u ON u.id = p.owner_id
        ORDER BY p.id DESC
        """
    )
    rows = fetch_all(rs)
    return [
        {
            "id": getattr(r, "id", None),
            "name": getattr(r, "name", None),
            "title": getattr(r, "title", None),
            "bio": getattr(r, "bio", None),
            "stance": getattr(r, "stance", None),
            "system_prompt": getattr(r, "system_prompt", None),
            "owner_id": getattr(r, "owner_id", None),
            "owner_name": getattr(r, "owner_name", None),
            "is_public": getattr(r, "is_public", 0),
            "skills": getattr(r, "skills", None),
            "modalities": getattr(r, "modalities", None),
            "created_at": getattr(r, "created_at", None),
        }
        for r in rows
    ]


@router.put("/personas/{persona_id}")
def admin_update_persona(
    persona_id: int,
    payload: PersonaUpdate,
    db: Any = Depends(get_db),
    admin: Any = Depends(require_admin),
):
    persona = get_persona(db, persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    updated = update_persona(db, persona_id, payload)
    _audit(db, admin.id, "update_persona", target_type="persona", target_id=persona_id, detail=f"编辑智能体 {persona.name}")
    return updated


@router.get("/personas/{persona_id}/knowledge")
def admin_list_knowledge(
    persona_id: int,
    db: Any = Depends(get_db),
    _: Any = Depends(require_admin),
):
    return list_knowledge_docs(db, persona_id)


@router.delete("/knowledge/{doc_id}")
def admin_delete_knowledge(
    doc_id: int,
    db: Any = Depends(get_db),
    admin: Any = Depends(require_admin),
):
    success = delete_knowledge_doc(db, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="知识库文件不存在")
    _audit(db, admin.id, "delete_knowledge", target_type="knowledge", target_id=doc_id)
    return {"success": True, "id": doc_id}


# --- Skills ---

@router.get("/skills")
def admin_list_skills(
    db: Any = Depends(get_db),
    _: Any = Depends(require_admin),
):
    return list_skills(db)


@router.put("/skills/{skill_id}")
def admin_update_skill(
    skill_id: int,
    payload: SkillAdminUpdate,
    db: Any = Depends(get_db),
    admin: Any = Depends(require_admin),
):
    existing = fetch_one(db.execute("SELECT id, skill_key, name FROM skills WHERE id = ?", [skill_id]))
    if existing is None:
        raise HTTPException(status_code=404, detail="Skill 不存在")

    updates = payload.model_dump(exclude_unset=True)
    if "params_schema" in updates and updates["params_schema"] is not None:
        import json
        updates["params_schema"] = json.dumps(updates["params_schema"])

    set_clauses = []
    values: list[Any] = []
    for key, value in updates.items():
        set_clauses.append(f"{key} = ?")
        values.append(value)
    if set_clauses:
        values.append(skill_id)
        db_execute_commit(
            db,
            f"UPDATE skills SET {', '.join(set_clauses)}, updated_at = ? WHERE id = ?",
            [*values, datetime.now()],
        )
    _audit(db, admin.id, "update_skill", target_type="skill", target_id=skill_id, detail=f"编辑 Skill {existing.skill_key}")
    return {"id": skill_id, "skill_key": existing.skill_key}


# --- Audit logs ---

@router.get("/audit-logs")
def admin_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Any = Depends(get_db),
    _: Any = Depends(require_admin),
):
    rs = db.execute("SELECT * FROM admin_audit_logs ORDER BY id DESC LIMIT ?", [limit])
    rows = fetch_all(rs)
    return [
        {
            "id": getattr(r, "id", None),
            "actor_id": getattr(r, "actor_id", None),
            "action": getattr(r, "action", None),
            "target_type": getattr(r, "target_type", None),
            "target_id": getattr(r, "target_id", None),
            "detail": getattr(r, "detail", None),
            "created_at": getattr(r, "created_at", None),
        }
        for r in rows
    ]
