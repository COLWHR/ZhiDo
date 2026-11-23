"""Offline evaluation: ML classifier vs keyword rule baseline.

Usage:
    python -m app.decision.evaluate
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from sklearn.metrics import accuracy_score, f1_score

from app.decision.dataset import load_dataset, split_train_val
from app.decision.labels import ALL_LABELS, rule_classify
from app.decision.router import predict


def _metrics(y_true: List[str], y_pred: List[str]) -> Dict[str, Any]:
    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "macro_f1": round(
            f1_score(y_true, y_pred, average="macro", labels=ALL_LABELS, zero_division=0), 4
        ),
    }


def evaluate() -> Dict[str, Any]:
    samples = load_dataset()
    _, val_set = split_train_val(samples)
    texts = [s["text"] for s in val_set]
    labels = [s["label"] for s in val_set]

    # ML chain (model -> rule fallback)
    ml_pred: List[str] = []
    started = time.perf_counter()
    for text in texts:
        ml_pred.append(predict(text)["label"])
    ml_elapsed = round((time.perf_counter() - started) * 1000 / max(1, len(texts)), 3)

    # Pure rule baseline
    rule_pred = [rule_classify(text)["label"] for text in texts]

    return {
        "val_size": len(texts),
        "model": _metrics(labels, ml_pred),
        "rule_baseline": _metrics(labels, rule_pred),
        "ml_avg_ms_per_request": ml_elapsed,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
