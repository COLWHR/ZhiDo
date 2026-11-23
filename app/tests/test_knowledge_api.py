import random

from app.crud import build_knowledge_block


def _register_and_login(client, suffix="u"):
    username = f"kb_{suffix}_{random.randint(1000, 9999)}"
    client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "password", "role": "user"},
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "password"},
    )
    return response.json()["access_token"]


def _create_persona(client, token, name="KB 智能体"):
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        "/api/v1/personas/",
        headers=headers,
        json={
            "name": name,
            "title": "T",
            "bio": "B",
            "theories": ["X"],
            "stance": "S",
            "system_prompt": "SP",
            "is_public": False,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_knowledge_upload_list_delete_flow(client, db):
    token = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    persona_id = _create_persona(client, token)

    # Empty list initially
    res = client.get(f"/api/v1/personas/{persona_id}/knowledge", headers=headers)
    assert res.status_code == 200
    assert res.json() == []

    # Upload a text knowledge document
    content = "ZhiDo 平台支持多智能体圆桌协同；核心结论：知识库优先于通用认知。"
    res = client.post(
        f"/api/v1/personas/{persona_id}/knowledge",
        headers=headers,
        files={"file": ("note.txt", content.encode("utf-8"), "text/plain")},
    )
    assert res.status_code == 200, res.text
    doc = res.json()
    assert doc["file_name"] == "note.txt"
    assert doc["char_count"] > 0
    assert "知识库" in doc["extracted_text"]
    doc_id = doc["id"]

    # List returns the document
    res = client.get(f"/api/v1/personas/{persona_id}/knowledge", headers=headers)
    assert res.status_code == 200
    docs = res.json()
    assert len(docs) == 1
    assert docs[0]["id"] == doc_id

    # The knowledge block is assembled for prompt injection
    block = build_knowledge_block(db, persona_id)
    assert "note.txt" in block
    assert "知识库" in block

    # Delete
    res = client.delete(
        f"/api/v1/personas/{persona_id}/knowledge/{doc_id}", headers=headers
    )
    assert res.status_code == 200
    res = client.get(f"/api/v1/personas/{persona_id}/knowledge", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


def test_knowledge_rejects_binary_file(client):
    token = _register_and_login(client, "bin")
    headers = {"Authorization": f"Bearer {token}"}
    persona_id = _create_persona(client, token, "KB 二进制")

    res = client.post(
        f"/api/v1/personas/{persona_id}/knowledge",
        headers=headers,
        files={"file": ("image.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert res.status_code == 400


def test_knowledge_requires_authentication(client):
    res = client.get("/api/v1/personas/1/knowledge")
    assert res.status_code == 401


def test_knowledge_non_owner_forbidden(client):
    owner_token = _register_and_login(client, "owner")
    persona_id = _create_persona(client, owner_token, "KB 归属")
    other_token = _register_and_login(client, "other")
    other_headers = {"Authorization": f"Bearer {other_token}"}

    res = client.get(f"/api/v1/personas/{persona_id}/knowledge", headers=other_headers)
    assert res.status_code == 403

    res = client.post(
        f"/api/v1/personas/{persona_id}/knowledge",
        headers=other_headers,
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 403
