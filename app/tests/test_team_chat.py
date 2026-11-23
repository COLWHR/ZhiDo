import random
from types import SimpleNamespace
from unittest.mock import patch


def _register(client, suffix):
    username = f"team_{suffix}_{random.randint(1000, 9999)}"
    client.post("/api/v1/auth/register", json={"username": username, "password": "password", "role": "user"})
    res = client.post("/api/v1/auth/login", data={"username": username, "password": "password"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _create_persona(client, headers, name):
    res = client.post(
        "/api/v1/personas/",
        headers=headers,
        json={
            "name": name,
            "title": "T",
            "bio": "B",
            "theories": ["X"],
            "stance": "S",
            "system_prompt": "你是一个乐于助人的智能体。",
            "is_public": False,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _fake_stream(*args, **kwargs):
    def generator():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="收到，"))])
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="这是团队回复。"))])

    return generator()


def test_team_crud_flow(client):
    headers = _register(client, "crud")
    p1 = _create_persona(client, headers, "数学大师")
    p2 = _create_persona(client, headers, "写作助手")

    res = client.post(
        "/api/v1/teams/",
        headers=headers,
        json={"name": "学习小组", "description": "作业协作", "persona_ids": [p1, p2]},
    )
    assert res.status_code == 200, res.text
    team = res.json()
    team_id = team["id"]
    assert team["name"] == "学习小组"
    assert len(team["members"]) == 2

    res = client.get("/api/v1/teams/", headers=headers)
    assert res.status_code == 200
    assert any(t["id"] == team_id for t in res.json())

    p3 = _create_persona(client, headers, "英语教练")
    res = client.post(f"/api/v1/teams/{team_id}/members", headers=headers, json={"persona_ids": [p3]})
    assert res.status_code == 200
    assert len(res.json()["members"]) == 3

    res = client.delete(f"/api/v1/teams/{team_id}/members/{p3}", headers=headers)
    assert res.status_code == 200
    res = client.get(f"/api/v1/teams/{team_id}", headers=headers)
    assert len(res.json()["members"]) == 2

    res = client.delete(f"/api/v1/teams/{team_id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_team_stream_without_mention_does_not_call_llm(client):
    headers = _register(client, "nomention")
    p1 = _create_persona(client, headers, "数学大师")
    team = client.post(
        "/api/v1/teams/", headers=headers, json={"name": "静默群", "persona_ids": [p1]}
    ).json()

    with patch("app.api.v1.endpoints.teams.get_chat_completion") as mock_llm:
        response = client.post(
            f"/api/v1/teams/{team['id']}/chat/stream",
            headers=headers,
            json={"content": "大家随便聊聊", "mentioned_persona_ids": []},
        )

    assert response.status_code == 200
    mock_llm.assert_not_called()
    body = response.text
    assert "系统" in body or "@" in body
    assert '"type": "system"' in body

    messages = client.get(f"/api/v1/teams/{team['id']}/messages", headers=headers).json()
    assert any(m["sender_type"] == "user" for m in messages)
    assert any(m["sender_type"] == "system" for m in messages)
    assert not any(m["sender_type"] == "assistant" for m in messages)


def test_team_stream_mention_replies_and_persists(client):
    headers = _register(client, "mention")
    p1 = _create_persona(client, headers, "数学大师")
    team = client.post(
        "/api/v1/teams/", headers=headers, json={"name": "答疑群", "persona_ids": [p1]}
    ).json()

    with patch("app.api.v1.endpoints.teams.get_chat_completion", side_effect=_fake_stream):
        response = client.post(
            f"/api/v1/teams/{team['id']}/chat/stream",
            headers=headers,
            json={"content": "帮我解这道题", "mentioned_persona_ids": [p1]},
        )

    assert response.status_code == 200
    body = response.text
    assert '"type": "agent_start"' in body
    assert "收到，" in body
    assert "这是团队回复。" in body
    assert '"type": "agent_end"' in body

    messages = client.get(f"/api/v1/teams/{team['id']}/messages", headers=headers).json()
    assistant = [m for m in messages if m["sender_type"] == "assistant"]
    assert len(assistant) == 1
    assert assistant[0]["persona_id"] == p1
    assert assistant[0]["speaker_name"] == "数学大师"
    assert "团队回复" in assistant[0]["content"]


def test_team_text_mention_fallback(client):
    headers = _register(client, "textmention")
    p1 = _create_persona(client, headers, "写作助手")
    team = client.post(
        "/api/v1/teams/", headers=headers, json={"name": "文案群", "persona_ids": [p1]}
    ).json()

    with patch("app.api.v1.endpoints.teams.get_chat_completion", side_effect=_fake_stream):
        response = client.post(
            f"/api/v1/teams/{team['id']}/chat/stream",
            headers=headers,
            json={"content": "@写作助手 帮我润色这段文案", "mentioned_persona_ids": []},
        )

    assert response.status_code == 200
    assert '"type": "agent_start"' in response.text

    messages = client.get(f"/api/v1/teams/{team['id']}/messages", headers=headers).json()
    assert any(m["sender_type"] == "assistant" and m["persona_id"] == p1 for m in messages)


def test_team_create_requires_member(client):
    headers = _register(client, "emptygroup")
    res = client.post(
        "/api/v1/teams/",
        headers=headers,
        json={"name": "空群", "description": "", "persona_ids": []},
    )
    assert res.status_code == 400
    assert "成员" in res.json()["detail"]


def test_team_empty_message_rejected(client):
    headers = _register(client, "emptymsg")
    p1 = _create_persona(client, headers, "数学大师")
    team = client.post(
        "/api/v1/teams/", headers=headers, json={"name": "校验群", "persona_ids": [p1]}
    ).json()

    res = client.post(
        f"/api/v1/teams/{team['id']}/chat/stream",
        headers=headers,
        json={"content": "   ", "attachments": [], "mentioned_persona_ids": [p1]},
    )
    assert res.status_code == 400
    assert "附件" in res.json()["detail"]


def test_team_multi_member_both_reply_and_persist(client):
    headers = _register(client, "multi")
    p1 = _create_persona(client, headers, "数学大师")
    p2 = _create_persona(client, headers, "写作助手")
    team = client.post(
        "/api/v1/teams/", headers=headers, json={"name": "协作群", "persona_ids": [p1, p2]}
    ).json()

    with patch("app.api.v1.endpoints.teams.get_chat_completion", side_effect=_fake_stream):
        response = client.post(
            f"/api/v1/teams/{team['id']}/chat/stream",
            headers=headers,
            json={"content": "两位都来看看", "mentioned_persona_ids": [p1, p2]},
        )

    assert response.status_code == 200
    body = response.text
    assert body.count('"type": "agent_start"') == 2

    messages = client.get(f"/api/v1/teams/{team['id']}/messages", headers=headers).json()
    assistant = [m for m in messages if m["sender_type"] == "assistant"]
    assert len(assistant) == 2
    assert {m["persona_id"] for m in assistant} == {p1, p2}


def test_orchestrator_filters_system_and_trims_history():
    from app.services import team_orchestrator

    msgs = [
        SimpleNamespace(sender_type="system", content="引导提示", attachments=[]),
        SimpleNamespace(sender_type="user", content="你好", attachments=[]),
        SimpleNamespace(sender_type="assistant", content="回复一", attachments=[]),
        SimpleNamespace(sender_type="assistant", content="回复二", attachments=[]),
        SimpleNamespace(sender_type="assistant", content="回复三", attachments=[]),
    ]
    context = team_orchestrator.history_to_context(msgs)
    assert all("引导提示" not in c["content"] for c in context)
    assert len(context) == 4

    trimmed = team_orchestrator.trim_context(context, 2)
    assert len(trimmed) == 2
    assert trimmed[-1]["content"] == "回复三"


def test_team_doc_request_attaches_file_artifact(client):
    headers = _register(client, "docart")
    p1 = _create_persona(client, headers, "写作助手")
    team = client.post(
        "/api/v1/teams/", headers=headers, json={"name": "文档群", "persona_ids": [p1]}
    ).json()

    with patch("app.api.v1.endpoints.teams.get_chat_completion", side_effect=_fake_stream):
        response = client.post(
            f"/api/v1/teams/{team['id']}/chat/stream",
            headers=headers,
            json={"content": "帮我整理一份项目报告", "mentioned_persona_ids": [p1]},
        )

    assert response.status_code == 200
    assert '"type": "artifact"' in response.text

    messages = client.get(f"/api/v1/teams/{team['id']}/messages", headers=headers).json()
    assistant = [m for m in messages if m["sender_type"] == "assistant"]
    assert len(assistant) == 1
    atts = assistant[0]["attachments"]
    assert len(atts) == 1
    assert atts[0]["kind"] == "file"
    assert atts[0]["storage_url"]


def test_team_image_request_attaches_png_artifact(client):
    headers = _register(client, "imgart")
    p1 = _create_persona(client, headers, "设计助手")
    team = client.post(
        "/api/v1/teams/", headers=headers, json={"name": "配图群", "persona_ids": [p1]}
    ).json()

    with patch("app.api.v1.endpoints.teams.get_chat_completion", side_effect=_fake_stream):
        response = client.post(
            f"/api/v1/teams/{team['id']}/chat/stream",
            headers=headers,
            json={"content": "画一张流程示意图", "mentioned_persona_ids": [p1]},
        )

    assert response.status_code == 200
    messages = client.get(f"/api/v1/teams/{team['id']}/messages", headers=headers).json()
    assistant = [m for m in messages if m["sender_type"] == "assistant"]
    assert len(assistant) == 1
    atts = assistant[0]["attachments"]
    assert len(atts) == 1
    assert atts[0]["kind"] == "image"
    assert atts[0]["file_name"].endswith(".png")


def test_team_plain_reply_has_no_artifact(client):
    headers = _register(client, "plainart")
    p1 = _create_persona(client, headers, "数学大师")
    team = client.post(
        "/api/v1/teams/", headers=headers, json={"name": "闲聊群", "persona_ids": [p1]}
    ).json()

    with patch("app.api.v1.endpoints.teams.get_chat_completion", side_effect=_fake_stream):
        client.post(
            f"/api/v1/teams/{team['id']}/chat/stream",
            headers=headers,
            json={"content": "这道题怎么做", "mentioned_persona_ids": [p1]},
        )

    messages = client.get(f"/api/v1/teams/{team['id']}/messages", headers=headers).json()
    assistant = [m for m in messages if m["sender_type"] == "assistant"]
    assert len(assistant) == 1
    assert assistant[0]["attachments"] == []


def test_team_other_user_cannot_access(client):
    owner = _register(client, "owner")
    outsider = _register(client, "outsider")
    p1 = _create_persona(client, owner, "私有智能体")
    team = client.post(
        "/api/v1/teams/", headers=owner, json={"name": "私有群", "persona_ids": [p1]}
    ).json()

    res = client.get(f"/api/v1/teams/{team['id']}", headers=outsider)
    assert res.status_code == 403

    res = client.get(f"/api/v1/teams/{team['id']}/messages", headers=outsider)
    assert res.status_code == 403
