from typing import Annotated, Any
from fastapi import Depends, HTTPException, WebSocket, WebSocketException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.core.security import decode_token
from app.db.session import get_db
from app.crud import get_user_by_username
from app.schemas import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def _get_user_from_token(token: str, db: Any, *, expected_token_type: str = "access"):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_type = str(payload.get("token_type") or "access")
        if expected_token_type and token_type != expected_token_type:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
        
    user = get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Any = Depends(get_db)):
    return _get_user_from_token(token, db)


def require_admin(current_user: Annotated[Any, Depends(get_current_user)]) -> Any:
    """Dependency that only admits admin / god accounts into the admin console."""
    role = str(getattr(current_user, "role", "user") or "user")
    if role not in {"admin", "god"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


async def get_current_user_ws(websocket: WebSocket, db: Any = Depends(get_db)):
    """Authenticate a WebSocket handshake.

    Only a short-lived ws ticket (or an Authorization header) is accepted, so a
    long-lived access JWT never has to appear in the URL or the access log.
    """
    ticket = websocket.query_params.get("ticket")
    token = None

    if not ticket:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not ticket and not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    credential = ticket or token
    try:
        payload = decode_token(credential)
    except JWTError as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from exc

    token_type = str(payload.get("token_type") or "")
    forum_id = websocket.path_params.get("forum_id")
    if ticket:
        if token_type != "ws_ticket" or str(payload.get("forum_id")) != str(forum_id):
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    elif token_type != "access":
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    username = payload.get("sub")
    if not username:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    user = get_user_by_username(db, username=username)
    if user is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return user
