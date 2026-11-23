import random

from app.crud import list_decision_logs, log_decision
from app.decision import router as decision_router
from app.decision.dataset import SEED_SAMPLES, split_train_val
from app.decision.labels import ALL_LABELS


def _register(client, suffix):
    username = f"decision_{suffix}_{random.randint(1000, 9999)}"
    client.post("/api/v1/auth/register", json={"username": username, "password": "password", "role": "user"})
    res = client.post("/api/v1/auth/login", data={"username": username, "password": "password"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_seed_dataset_labels_are_valid():
    assert SEED_SAMPLES, "seed dataset must not be empty"
    for text, label in SEED_SAMPLES:
        assert label in ALL_LABELS, f"invalid label {label} for {text!r}"
        assert text.strip()


def test_dataset_split_is_consistent():
    train, val = split_train_val(SEED_SAMPLES, val_ratio=0.2, seed=42)
    assert len(train) + len(val) == len(SEED_SAMPLES)
    assert train and val


def test_predict_returns_full_schema():
    result = decision_router.predict("帮我写一份项目答辩报告")
    assert result["label"] in ALL_LABELS
    assert 0 <= result["confidence"] <= 1
    assert result["layer"] in {"model", "rule"}
    assert "elapsed_ms" in result
    assert "artifact" in result


def test_rule_fallback_when_model_missing(monkeypatch):
    monkeypatch.setattr(decision_router, "_bundle", None)
    monkeypatch.setattr(decision_router, "_bundle_loaded", True)

    result = decision_router.predict("画一张系统架构示意图")
    assert result["layer"] == "rule"
    assert result["label"] in ALL_LABELS


def test_decision_log_write_and_read(db):
    log_decision(
        db,
        scope="team",
        reference_id=1,
        user_id=1,
        text="测试决策落库",
        label="doc",
        confidence=0.91,
        layer="model",
        keyword=None,
        elapsed_ms=2.4,
    )
    logs = list_decision_logs(db, limit=10)
    assert len(logs) == 1
    row = logs[0]
    assert row.label == "doc"
    assert row.layer == "model"
    assert float(row.confidence) == 0.91


def test_overview_requires_auth(client):
    res = client.get("/api/v1/decision/overview")
    assert res.status_code in (401, 403)


def test_overview_endpoint_structure(client):
    headers = _register(client, "overview")
    res = client.get("/api/v1/decision/overview", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "dataset" in body
    assert "evaluation" in body
    assert "logs" in body
    assert "model_available" in body["dataset"]
    eval_body = body["evaluation"]
    if eval_body:
        assert "model" in eval_body
        assert "rule_baseline" in eval_body
