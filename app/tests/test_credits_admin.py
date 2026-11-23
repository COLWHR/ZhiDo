"""Targeted tests for the prepaid credit ledger, dynamic config and admin console."""
import random

import pytest

from app.services import credit_service, system_config_service
from app.services.credit_service import InsufficientCreditsError


def _register(client, role: str = "user"):
    username = f"u_{random.randint(100000, 999999)}"
    resp = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password", "role": role},
    )
    assert resp.status_code in (200, 201), resp.text
    login = client.post(
        "/api/v1/auth/login", data={"username": username, "password": "password"}
    )
    token = login.json()["access_token"]
    return username, token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_signup_bonus_granted(client):
    _, token = _register(client)
    resp = client.get("/api/v1/users/me/credits", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance"] == 1000
    assert body["transactions"], "注册应产生一条赠送流水"
    assert body["transactions"][0]["category"] == "signup"


def test_admin_console_forbidden_for_plain_user(client):
    _, token = _register(client, role="user")
    resp = client.get("/api/v1/admin/overview", headers=_auth(token))
    assert resp.status_code == 403


def test_admin_console_open_for_admin(client):
    _, token = _register(client, role="admin")
    resp = client.get("/api/v1/admin/overview", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert "credits" in body and "counts" in body


def test_admin_adjust_credits_updates_balance(client):
    admin_name, admin_token = _register(client, role="admin")
    target_name, target_token = _register(client)

    me = client.get("/api/v1/users/me", headers=_auth(target_token)).json()
    user_id = me["id"]

    resp = client.patch(
        f"/api/v1/admin/users/{user_id}/credits",
        headers=_auth(admin_token),
        json={"amount": -200, "note": "测试扣减"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["balance"] == 800

    after = client.get("/api/v1/users/me/credits", headers=_auth(target_token)).json()
    assert after["balance"] == 800


def test_admin_can_change_role_to_admin(client):
    _, admin_token = _register(client, role="admin")
    target_name, target_token = _register(client)
    me = client.get("/api/v1/users/me", headers=_auth(target_token)).json()

    resp = client.patch(
        f"/api/v1/admin/users/{me['id']}/role",
        headers=_auth(admin_token),
        json={"role": "admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"

    # The elevated account can now reach the admin console.
    assert client.get("/api/v1/admin/overview", headers=_auth(target_token)).status_code == 200


def test_config_seeded_and_updatable(client):
    _, admin_token = _register(client, role="admin")

    listing = client.get("/api/v1/admin/config", headers=_auth(admin_token)).json()
    seeded = {item["key"]: item["value"] for item in listing}
    assert "credit.vision_per_call" in seeded
    assert "llm.model_name" in seeded

    resp = client.put(
        "/api/v1/admin/config/credit.vision_per_call",
        headers=_auth(admin_token),
        json={"value": "7"},
    )
    assert resp.status_code == 200

    listing = client.get("/api/v1/admin/config", headers=_auth(admin_token)).json()
    updated = {item["key"]: item["value"] for item in listing}
    assert updated["credit.vision_per_call"] == "7"


def test_insufficient_balance_blocks_charge(db):
    db.execute(
        "INSERT INTO users (username, password_hash, role, credits_balance) VALUES (?, ?, ?, ?)",
        ["charger", "hash", "user", 1000],
    )
    from app.db.client import fetch_one
    row = fetch_one(db.execute("SELECT id FROM users WHERE username = ?", ["charger"]))
    user_id = getattr(row, "id", None)

    with pytest.raises(InsufficientCreditsError):
        # 100k vision calls far exceed the 1000-credit balance.
        credit_service.charge(db, user_id, vision_count=100_000, category="vision")


def test_audit_log_written_on_admin_action(client):
    _, admin_token = _register(client, role="admin")
    target_name, target_token = _register(client)
    me = client.get("/api/v1/users/me", headers=_auth(target_token)).json()

    client.patch(
        f"/api/v1/admin/users/{me['id']}/credits",
        headers=_auth(admin_token),
        json={"amount": 50},
    )
    logs = client.get("/api/v1/admin/audit-logs", headers=_auth(admin_token)).json()
    assert any(log["action"] == "adjust_credits" for log in logs)
