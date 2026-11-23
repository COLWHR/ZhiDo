from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.security import create_access_token, create_ws_ticket, decode_token
from app.db.client import fetch_one
from app.services.skill_runtime import _safe_storage_path, UPLOADS_ROOT


def _username(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def register_and_login(client, role="user"):
    username = _username("sec")
    client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123", "role": role},
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "password123"},
    )
    token = response.json()["access_token"]
    return username, {"Authorization": f"Bearer {token}"}


def test_public_registration_cannot_claim_god(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_ROLE_SELECTION", False)

    username = _username("god")
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123", "role": "god"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "user"

    row = fetch_one(db.execute("SELECT role FROM users WHERE username = ?", [username]))
    assert row is not None and row.role == "user"


def test_users_endpoint_cannot_create_admin(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_ROLE_SELECTION", False)

    username = _username("admin")
    response = client.post(
        "/api/v1/users/",
        json={"username": username, "password": "password123", "role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "user"


def test_agents_chat_requires_authentication(client):
    response = client.post(
        "/api/v1/agents/chat",
        json={"persona_json": {"id": 1}, "theme": "hi", "context_messages": []},
    )
    assert response.status_code == 401


def test_agents_chat_stream_requires_authentication(client):
    response = client.post(
        "/api/v1/agents/chat/stream",
        json={"persona_json": {"id": 1}, "theme": "hi", "context_messages": []},
    )
    assert response.status_code == 401


def test_attachment_path_traversal_is_blocked(tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("SECRET", encoding="utf-8")

    assert _safe_storage_path(str(outside)) is None
    assert _safe_storage_path("/uploads/../../.env") is None
    assert _safe_storage_path("uploads/../.env") is None


def test_attachment_path_allows_uploads_root():
    assert _safe_storage_path("/uploads/attachments/demo.png") == (UPLOADS_ROOT / "attachments" / "demo.png").resolve()


def test_upload_rejects_executable_html(client):
    _, headers = register_and_login(client)
    response = client.post(
        "/api/v1/upload/asset",
        files={"file": ("evil.html", b"<script>alert(1)</script>", "text/html")},
        headers=headers,
    )
    assert response.status_code == 400


def test_upload_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    _, headers = register_and_login(client)
    payload = b"a" * (1024 * 1024 + 512)
    response = client.post(
        "/api/v1/upload/asset",
        files={"file": ("big.txt", payload, "text/plain")},
        headers=headers,
    )
    assert response.status_code == 413


def test_ws_ticket_is_scoped_and_short_lived():
    token = create_ws_ticket("alice", 7)
    payload = decode_token(token)
    assert payload["token_type"] == "ws_ticket"
    assert payload["forum_id"] == 7
    assert 0 < payload["exp"] - payload["iat"] <= settings.WS_TICKET_EXPIRE_SECONDS


def test_websocket_rejects_long_lived_access_token(client):
    access_token = create_access_token("alice")
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/forums/999999/ws?token={access_token}"):
            pass
