from __future__ import annotations

import logging
from typing import Any, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_current_user
from app.crud import (
    create_knowledge_doc,
    delete_knowledge_doc,
    get_persona,
    get_knowledge_doc,
    list_knowledge_docs,
)
from app.db.session import get_db
from app.schemas import KnowledgeDocCreate, KnowledgeDocResponse
from app.services.knowledge_service import store_knowledge_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/personas", tags=["knowledge"])


def _ensure_persona_owner(db: Any, persona_id: int, current_user: Any) -> Any:
    persona = get_persona(db, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="智能体不存在")
    if persona.owner_id != current_user.id and current_user.role not in {"admin", "god"}:
        raise HTTPException(status_code=403, detail="无权管理该智能体的知识库")
    return persona


@router.get("/{persona_id}/knowledge", response_model=List[KnowledgeDocResponse])
def list_persona_knowledge(
    persona_id: int,
    db: Any = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    _ensure_persona_owner(db, persona_id, current_user)
    docs = list_knowledge_docs(db, persona_id)
    return [KnowledgeDocResponse.model_validate(doc) for doc in docs]


@router.post("/{persona_id}/knowledge", response_model=KnowledgeDocResponse)
async def upload_persona_knowledge(
    persona_id: int,
    file: UploadFile = File(...),
    db: Any = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    _ensure_persona_owner(db, persona_id, current_user)

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="请选择要上传的知识库文件")

    payload = store_knowledge_file(file, persona_id=persona_id, owner_id=current_user.id)
    doc = create_knowledge_doc(db, KnowledgeDocCreate(**payload))
    return KnowledgeDocResponse.model_validate(doc)


@router.delete("/{persona_id}/knowledge/{doc_id}")
def delete_persona_knowledge(
    persona_id: int,
    doc_id: int,
    db: Any = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    _ensure_persona_owner(db, persona_id, current_user)

    doc = get_knowledge_doc(db, doc_id)
    if not doc or doc.persona_id != persona_id:
        raise HTTPException(status_code=404, detail="知识库文件不存在")

    success = delete_knowledge_doc(db, doc_id)
    if not success:
        raise HTTPException(status_code=500, detail="删除知识库文件失败")
    return {"success": True, "id": doc_id}
