from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_current_user
from app.core.config import settings
from app.crud import create_attachment
from app.db.session import get_db
from app.schemas import AttachmentCreate, AttachmentResponse, AvatarUploadResponse
from app.services.avatar_service import (
    AVATAR_MAX_BYTES,
    AvatarImageError,
    save_avatar_bytes,
)
from app.services.skill_runtime import (
    UPLOADS_ROOT,
    attachment_public_url,
    file_sha256,
    infer_attachment_kind,
    make_attachment_path,
)

router = APIRouter()

# Only formats the product actually renders. Notably no .html/.svg/.js/.exe:
# uploads are served from the app origin, so scripts must never be accepted.
ALLOWED_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".xlsx", ".pptx",
    ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".webm",
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def _validate_file(file: UploadFile, image_only: bool) -> tuple[str, str]:
    file_name = Path(file.filename or "upload.bin").name
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    kind = infer_attachment_kind(file.content_type, file_name)
    if image_only and (kind != "image" or suffix not in IMAGE_SUFFIXES):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    return file_name, kind


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


def _store_upload(file: UploadFile, current_user, db, image_only: bool = False) -> AttachmentResponse:
    file_name, kind = _validate_file(file, image_only)

    target_path = make_attachment_path(file_name)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        size = _write_with_limit(file, target_path)
    except Exception:
        target_path.unlink(missing_ok=True)
        raise

    relative_path = target_path.relative_to(UPLOADS_ROOT.parent)
    storage_url = attachment_public_url(relative_path)
    preview_url = storage_url if kind == "image" else None
    sha256 = file_sha256(target_path)

    attachment = create_attachment(
        db,
        AttachmentCreate(
            owner_id=current_user.id,
            file_name=file_name,
            mime_type=file.content_type,
            size=size,
            kind=kind,
            storage_url=storage_url,
            preview_url=preview_url,
            sha256=sha256,
            meta={
                "original_name": file_name,
                "path": str(relative_path).replace("\\", "/"),
            },
        ),
    )

    return AttachmentResponse.model_validate(attachment)


@router.post("/upload/asset", response_model=AttachmentResponse)
async def upload_asset(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        return _store_upload(file, current_user, db, image_only=False)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"File upload failed: {exc}")


@router.post("/upload/avatar", response_model=AvatarUploadResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """Square-crop, normalise and store an avatar.

    Everything is re-encoded through Pillow, so EXIF is dropped, the payload is
    bounded and only raster formats survive — SVG is never accepted.
    """
    content_type = (file.content_type or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")

    suffix = Path(Path(file.filename or "avatar.bin").name).suffix.lower()
    if suffix == ".svg" or suffix not in IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持 jpg / png / webp / gif / bmp")

    raw = await file.read(AVATAR_MAX_BYTES + 1)
    if len(raw) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=413, detail="头像文件不能超过 2MB")

    try:
        stored = save_avatar_bytes(raw, scope="avatars", owner_key=current_user.id)
    except AvatarImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return AvatarUploadResponse(**stored)


@router.post("/upload/image", response_model=AttachmentResponse)
async def upload_image(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    try:
        return _store_upload(file, current_user, db, image_only=True)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {exc}")
