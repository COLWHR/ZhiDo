"""Online decision router with a three-tier fallback chain.

Chain order:
  1. trained ML classifier (if model bundle exists and confidence is high)
  2. deterministic keyword rules (fallback / low-confidence)
  3. upstream large-model arbitration remains the caller's responsibility

The router never raises on a missing model: it silently degrades to rules so
the chat flow keeps working offline or before the model is trained.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

import joblib

from app.decision.dataset import DATASET_CSV
from app.decision.labels import LABEL_ARTIFACT, rule_classify
from app.decision.train import MODEL_PATH

# Minimum model probability to accept the ML label; below this we fall back
# to the rule baseline.
DEFAULT_CONFIDENCE_THRESHOLD = 0.6

_bundle: Optional[Dict[str, Any]] = None
_bundle_loaded = False


def _load_bundle() -> Optional[Dict[str, Any]]:
    global _bundle, _bundle_loaded
    if _bundle_loaded:
        return _bundle
    _bundle_loaded = True
    if MODEL_PATH.exists():
        try:
            _bundle = joblib.load(MODEL_PATH)
        except Exception:  # pragma: no cover - corrupt bundle should not crash chat
            _bundle = None
    return _bundle


def model_available() -> bool:
    return _load_bundle() is not None


def predict(text: str, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> Dict[str, Any]:
    """Classify one request. Never raises; degrades to rules on failure."""
    started = time.perf_counter()
    bundle = _load_bundle()
    result: Dict[str, Any]

    if bundle is not None:
        pipeline = bundle.get("pipeline")
        if pipeline is not None:
            try:
                proba = pipeline.predict_proba([text])[0]
                classes = list(pipeline.classes_)
                best_idx = int(proba.argmax())
                label = str(classes[best_idx])
                confidence = float(proba[best_idx])
                if confidence >= confidence_threshold:
                    result = {
                        "label": label,
                        "confidence": confidence,
                        "layer": "model",
                        "keyword": None,
                    }
                else:
                    rule = rule_classify(text)
                    result = {
                        "label": rule["label"],
                        "confidence": rule["confidence"],
                        "layer": "rule",
                        "keyword": rule["keyword"],
                    }
                result["artifact"] = LABEL_ARTIFACT.get(result["label"])
                result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
                return result
            except Exception:
                # Fall through to rules on any inference error.
                pass

    rule = rule_classify(text)
    result = {
        "label": rule["label"],
        "confidence": rule["confidence"],
        "layer": "rule",
        "keyword": rule["keyword"],
        "artifact": LABEL_ARTIFACT.get(rule["label"]),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    return result


def describe_dataset() -> Dict[str, Any]:
    """Expose dataset / model status for the diagnostics panel."""
    return {
        "model_available": model_available(),
        "model_path": str(MODEL_PATH),
        "dataset_csv": str(DATASET_CSV),
    }
