"""Train the intent router on the labelled seed dataset.

Lightweight CPU pipeline: char n-gram TF-IDF + Multinomial Naive Bayes.
The trained bundle (vectorizer + classifier + label set) is persisted with
joblib so the online router can load it without retraining.

Usage:
    python -m app.decision.train
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix

from app.decision.dataset import load_dataset, split_train_val
from app.decision.labels import ALL_LABELS

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_PATH = MODELS_DIR / "intent_router.joblib"


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1),
            ),
            ("clf", MultinomialNB(alpha=0.1)),
        ]
    )


def _xy(samples: List[Dict[str, str]]) -> Tuple[List[str], List[str]]:
    return [s["text"] for s in samples], [s["label"] for s in samples]


def train_and_save(model_path: Path = MODEL_PATH) -> Dict[str, Any]:
    samples = load_dataset()
    train_set, val_set = split_train_val(samples)
    x_train, y_train = _xy(train_set)
    x_val, y_val = _xy(val_set)

    pipeline = build_pipeline()
    pipeline.fit(x_train, y_train)

    if x_val:
        preds = pipeline.predict(x_val)
        metrics: Dict[str, Any] = {
            "accuracy": accuracy_score(y_val, preds),
            "macro_f1": f1_score(y_val, preds, average="macro", labels=ALL_LABELS, zero_division=0),
            "confusion_matrix": confusion_matrix(y_val, preds, labels=ALL_LABELS).tolist(),
            "val_size": len(x_val),
        }
    else:
        metrics = {"accuracy": None, "macro_f1": None, "val_size": 0}

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": pipeline,
            "labels": ALL_LABELS,
            "train_size": len(x_train),
        },
        model_path,
    )
    return {"metrics": metrics, "train_size": len(x_train), "model_path": str(model_path)}


if __name__ == "__main__":
    result = train_and_save()
    print(json.dumps(result, ensure_ascii=False, indent=2))
