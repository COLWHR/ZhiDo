from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from typing import Annotated, Any
from app.db.session import get_db
from app.schemas import UserCreate, UserResponse
from app.crud import get_user_by_username, create_user, update_user_avatar
from app.api.deps import get_current_user
from app.core.roles import resolve_registration_role
from app.services.avatar_service import (
    AVATAR_MAX_BYTES,
    AvatarImageError,
    delete_avatar_files,
    save_avatar_bytes,
)

router = APIRouter()

@router.post("/", response_model=UserResponse)
def create_new_user(user: UserCreate, db: Any = Depends(get_db)):
    db_user = get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    user = user.model_copy(update={"role": resolve_registration_role(user.role)})
    return create_user(db=db, user=user)

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: Annotated[Any, Depends(get_current_user)]):
    return current_user

@router.put("/me/avatar", response_model=UserResponse)
async def upload_my_avatar(
    file: UploadFile = File(...),
    current_user: Annotated[Any, Depends(get_current_user)] = None,
    db: Any = Depends(get_db),
):
    """Upload a personal avatar: square-cropped, re-encoded, max 2MB."""
    content_type = (file.content_type or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")

    raw = await file.read(AVATAR_MAX_BYTES + 1)
    if len(raw) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=413, detail="头像文件不能超过 2MB")

    try:
        stored = save_avatar_bytes(raw, scope="users", owner_key=current_user.id)
    except AvatarImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    previous = getattr(current_user, "avatar", None)
    user = update_user_avatar(db, current_user.id, stored["storage_url"], "custom")
    if previous and previous != stored["storage_url"]:
        delete_avatar_files(previous)
    return user


@router.delete("/me/avatar", response_model=UserResponse)
def reset_my_avatar(
    current_user: Annotated[Any, Depends(get_current_user)] = None,
    db: Any = Depends(get_db),
):
    previous = getattr(current_user, "avatar", None)
    user = update_user_avatar(db, current_user.id, None, "initial")
    delete_avatar_files(previous)
    return user


@router.get("/me/credits")
def read_my_credits(
    current_user: Annotated[Any, Depends(get_current_user)],
    db: Any = Depends(get_db),
):
    from app.services import credit_service
    balance = credit_service.get_balance(db, current_user.id)
    transactions = credit_service.list_transactions(db, user_id=current_user.id, limit=20)
    return {"balance": balance, "transactions": transactions}


@router.get("/{username}", response_model=UserResponse)
def read_user(username: str, db: Any = Depends(get_db)):
    db_user = get_user_by_username(db, username=username)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user
