"""Read-only diagnostics for the decision kernel (router model + audit log)."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.crud import list_decision_logs
from app.db.session import get_db
from app.decision import router as decision_router
from app.decision.evaluate import evaluate

router = APIRouter()


@router.get("/overview")
def decision_overview(
    limit: int = 30,
    scope: Optional[str] = None,
    db: Any = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    logs = list_decision_logs(db, limit=limit, scope=scope)
    evaluation: dict[str, Any] = {}
    try:
        evaluation = evaluate()
    except Exception:
        evaluation = {}

    return {
        "dataset": decision_router.describe_dataset(),
        "evaluation": evaluation,
        "logs": [
            {
                "id": getattr(row, "id", None),
                "scope": getattr(row, "scope", None),
                "reference_id": getattr(row, "reference_id", None),
                "label": getattr(row, "label", None),
                "confidence": getattr(row, "confidence", None),
                "layer": getattr(row, "layer", None),
                "keyword": getattr(row, "keyword", None),
                "elapsed_ms": getattr(row, "elapsed_ms", None),
                "text": getattr(row, "text", None),
                "created_at": str(getattr(row, "created_at", None)),
            }
            for row in logs
        ],
    }
