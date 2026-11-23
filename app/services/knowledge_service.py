from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.services.skill_runtime import (
    UPLOADS_ROOT,
    attachment_public_url,
    file_sha256,
    make_attachment_path,
    read_text_attachment,
)

logger = logging.getLogger(__name__)

# Knowledge bases are document-oriented: only text-bearing formats are parsed
# and injected into the agent prompt. Binary media (images/audio/video) belong
# to the chat attachment flow, not the knowledge base.
KNOWLEDGE_ALLOWED_SUFFIXES = {
    ".txt", ".md", ".csv", ".json", ".jsonl", ".xml", ".html", ".htm",
    ".py", ".ts", ".js", ".css", ".yml", ".yaml", ".docx",
}

# Per-document text cap so a single large file cannot blow up the prompt.
KNOWLEDGE_MAX_CHARS_PER_DOC = 8000


def validate_knowledge_suffix(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix not in KNOWLEDGE_ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="仅支持文本类知识库文件：txt / md / csv / json / xml / html / 代码文件 / docx",
        )
    return suffix


def extract_knowledge_text(path: Path) -> str:
    """Read and trim the readable text of an uploaded knowledge document."""
    try:
        text = read_text_attachment(path) or ""
    except Exception as exc:
        logger.warning("Failed to parse knowledge file %s: %s", path.name, exc)
        return ""
    return text.strip()[:KNOWLEDGE_MAX_CHARS_PER_DOC]


def _write_with_limit(file: UploadFile, target_path: Path) -> int:
    max_bytes = max(1, settings.MAX_UPLOAD_SIZE_MB) * 1024 * 1024
    written = 0
    try:
        with target_path.open("wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件过大，最大允许 {settings.MAX_UPLOAD_SIZE_MB}MB",
                    )
                buffer.write(chunk)
    except Exception:
        target_path.unlink(missing_ok=True)
        raise
    return written


def store_knowledge_file(file: UploadFile, persona_id: int, owner_id: int) -> dict[str, Any]:
    """Validate, persist and parse an uploaded knowledge document.

    Returns a payload ready for the KnowledgeDocCreate schema. The caller is
    responsible for persisting it through the CRUD layer.
    """
    file_name = Path(file.filename or "knowledge.bin").name
    validate_knowledge_suffix(file_name)

    target_path = make_attachment_path(file_name, prefix="knowledge")
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        size = _write_with_limit(file, target_path)
    except HTTPException:
        raise
    except Exception as exc:
        target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"知识库文件保存失败: {exc}")

    relative_path = target_path.relative_to(UPLOADS_ROOT.parent)
    storage_url = attachment_public_url(relative_path)
    sha256 = file_sha256(target_path)
    extracted_text = extract_knowledge_text(target_path)

    return {
        "persona_id": persona_id,
        "owner_id": owner_id,
        "file_name": file_name,
        "mime_type": file.content_type,
        "size": size,
        "storage_url": storage_url,
        "sha256": sha256,
        "extracted_text": extracted_text,
        "char_count": len(extracted_text),
        "status": "ready" if extracted_text else "unparsed",
        "meta": {
            "original_name": file_name,
            "path": str(relative_path).replace("\\", "/"),
            "suffix": target_path.suffix.lower(),
        },
    }
