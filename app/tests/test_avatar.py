import io
from uuid import uuid4

from PIL import Image

from app.core.config import settings
from app.services.avatar_service import AVATAR_MAX_BYTES, AvatarImageError, normalise_avatar_bytes
from app.services.skill_runtime import UPLOADS_ROOT


def _username(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def _login(client):
    username = _username("avatar")
    client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password123", "role": "user"},
    )
    token = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "password123"},
    ).json()["access_token"]
    return username, {"Authorization": f"Bearer {token}"}


def _png_bytes(width=1200, height=800) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (60, 110, 90)).save(buffer, "PNG")
    return buffer.getvalue()


def test_normalise_avatar_always_produces_a_512_square_webp():
    payload = normalise_avatar_bytes(_png_bytes())

    image = Image.open(io.BytesIO(payload))
    assert image.format == "WEBP"
    assert image.size == (512, 512)
    assert len(payload) < AVATAR_MAX_BYTES


def test_normalise_rejects_non_images():
    try:
        normalise_avatar_bytes(b"not an image")
    except AvatarImageError as exc:
        assert "图片" in str(exc)
    else:
        raise AssertionError("garbage bytes should not pass")


def test_upload_avatar_endpoint_rejects_svg(client):
    _, headers = _login(client)

    response = client.post(
        "/api/v1/upload/avatar",
        headers=headers,
        files={"file": ("evil.svg", b"<svg onload=alert(1)></svg>", "image/svg+xml")},
    )

    assert response.status_code == 400


def test_upload_avatar_endpoint_rejects_oversized_payload(client):
    _, headers = _login(client)

    response = client.post(
        "/api/v1/upload/avatar",
        headers=headers,
        files={"file": ("big.png", b"0" * (AVATAR_MAX_BYTES + 1), "image/png")},
    )

    assert response.status_code == 413


def test_user_avatar_can_be_uploaded_and_reset(client, db):
    _, headers = _login(client)

    upload = client.post(
        "/api/v1/upload/avatar",
        headers=headers,
        files={"file": ("me.png", _png_bytes(900, 900), "image/png")},
    )
    assert upload.status_code == 200
    stored = upload.json()["storage_url"]
    assert stored.startswith("/uploads/avatars/")

    updated = client.put(
        "/api/v1/users/me/avatar",
        headers=headers,
        files={"file": ("me.png", _png_bytes(900, 900), "image/png")},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["avatar"].startswith("/uploads/avatars/")
    assert body["avatar_kind"] == "custom"
    assert body["avatar_updated_at"]

    me = client.get("/api/v1/users/me", headers=headers)
    assert me.json()["avatar"] == body["avatar"]

    reset = client.delete("/api/v1/users/me/avatar", headers=headers)
    assert reset.status_code == 200
    assert reset.json()["avatar"] is None
    assert reset.json()["avatar_kind"] == "initial"

    relative = body["avatar"].split("/uploads/", 1)[-1]
    assert not (UPLOADS_ROOT / relative).exists()


def test_persona_illustration_reports_missing_provider(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "IMAGE_GEN_API_KEY", None)
    _, headers = _login(client)

    created = client.post(
        "/api/v1/personas/",
        headers=headers,
        json={"name": "测试学者", "title": "哲学研究者", "bio": "研究伦理学"},
    )
    assert created.status_code == 200
    persona_id = created.json()["id"]

    response = client.post(
        f"/api/v1/personas/{persona_id}/avatar/generate",
        headers=headers,
        json={"style": "editorial"},
    )

    assert response.status_code == 503
    assert "插画" in response.json()["detail"]
