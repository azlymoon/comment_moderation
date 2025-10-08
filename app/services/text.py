from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable, List

from app.core import models

# Keyword heuristics help catch obvious abusive phrasing without retraining the model.
TOXIC_KEYWORDS: Dict[str, float] = {
    "hate": 0.7,
    "idiot": 0.9,
    "stupid": 0.75,
    "kill": 0.95,
    "spam": 0.8,
    "trash": 0.6,
}

TOXIC_LABELS: Iterable[str] = (
    "toxic",
    "severe_toxic",
    "obscene",
    "threat",
    "insult",
    "identity_hate",
)


@lru_cache(maxsize=1)
def _get_toxicity_classifier():
    try:
        from transformers import pipeline
    except ImportError as exc:  # pragma: no cover - informative failure path
        raise RuntimeError(
            "Package 'transformers' is required for ML-based moderation. "
            "Install it with `pip install transformers torch`."
        ) from exc

    return pipeline(
        "text-classification",
        model="unitary/toxic-bert",
        tokenizer="unitary/toxic-bert",
        truncation=True,
        return_all_scores=True,
    )


@lru_cache(maxsize=1)
def _get_sentiment_classifier():
    try:
        from transformers import pipeline
    except ImportError as exc:  # pragma: no cover - informative failure path
        raise RuntimeError(
            "Package 'transformers' is required for sentiment-based moderation. "
            "Install it with `pip install transformers torch`."
        ) from exc

    return pipeline(
        "sentiment-analysis",
        model="distilbert-base-uncased-finetuned-sst-2-english",
    )


def _aggregate_scores(raw_scores: List[Dict[str, float]]) -> Dict[str, float]:
    return {item["label"]: float(item["score"]) for item in raw_scores}


def _keyword_score(text: str) -> float:
    lowered = text.lower()
    score = 0.0
    for token, weight in TOXIC_KEYWORDS.items():
        if token in lowered:
            score = max(score, weight)
    return score


def _negative_sentiment_score(text: str) -> float:
    sentiment_classifier = _get_sentiment_classifier()
    sentiment = sentiment_classifier(text)[0]
    if sentiment["label"].upper() == "NEGATIVE":
        return float(sentiment["score"])
    return 0.0


def evaluate_text(text: str) -> models.ModerationResult:
    """Classify text toxicity using ML model plus lexical and sentiment heuristics."""
    classifier = _get_toxicity_classifier()
    outputs = classifier(text)
    scores = _aggregate_scores(outputs[0])

    keyword_score = _keyword_score(text)
    scores["keyword_heuristic"] = keyword_score

    sentiment_score = _negative_sentiment_score(text)
    scores["sentiment_negative"] = sentiment_score

    toxicity_signal = max(
        [scores.get(label, 0.0) for label in TOXIC_LABELS] + [keyword_score]
    )

    if toxicity_signal >= 0.85:
        decision = models.ModerationDecision.REJECTED
        confidence = toxicity_signal
    elif toxicity_signal >= 0.55:
        decision = models.ModerationDecision.HUMAN_REVIEW
        confidence = toxicity_signal
    elif sentiment_score >= 0.8:
        decision = models.ModerationDecision.HUMAN_REVIEW
        confidence = sentiment_score
    else:
        decision = models.ModerationDecision.APPROVED
        confidence = max(toxicity_signal, sentiment_score)

    return models.ModerationResult(
        request_id="",
        decision=decision,
        confidence_score=confidence,
        model_version="unitary/toxic-bert",
        label_scores=scores,
    )
