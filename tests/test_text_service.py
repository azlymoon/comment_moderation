import math

from app.core import models
from app.services import text as text_service


class _DummyClassifier:
    def __init__(self, scores):
        self._scores = scores

    def __call__(self, input_text):
        return [self._scores]


def _stub_toxicity(monkeypatch, scores):
    monkeypatch.setattr(text_service, "_get_toxicity_classifier", lambda: _DummyClassifier(scores))


def _stub_sentiment(monkeypatch, label="POSITIVE", score=0.0):
    monkeypatch.setattr(
        text_service,
        "_get_sentiment_classifier",
        lambda: _DummyClassifier({"label": label, "score": score}),
    )


def test_evaluate_text_approves_low_risk(monkeypatch):
    _stub_toxicity(
        monkeypatch,
        [
            {"label": "toxic", "score": 0.1},
            {"label": "severe_toxic", "score": 0.05},
            {"label": "obscene", "score": 0.2},
            {"label": "threat", "score": 0.01},
            {"label": "insult", "score": 0.03},
            {"label": "identity_hate", "score": 0.02},
        ],
    )
    _stub_sentiment(monkeypatch, label="POSITIVE", score=0.95)

    result = text_service.evaluate_text("Have a great day!")

    assert result.decision is models.ModerationDecision.APPROVED
    assert math.isclose(result.confidence_score, 0.2, rel_tol=1e-6)
    assert result.label_scores["keyword_heuristic"] == 0.0
    assert result.label_scores["sentiment_negative"] == 0.0
    assert result.model_version == "unitary/toxic-bert"


def test_evaluate_text_requests_human_review_for_mid_toxicity(monkeypatch):
    _stub_toxicity(
        monkeypatch,
        [
            {"label": "toxic", "score": 0.7},
            {"label": "severe_toxic", "score": 0.1},
            {"label": "obscene", "score": 0.05},
            {"label": "threat", "score": 0.05},
            {"label": "insult", "score": 0.05},
            {"label": "identity_hate", "score": 0.05},
        ],
    )
    _stub_sentiment(monkeypatch, label="POSITIVE", score=0.8)

    result = text_service.evaluate_text("Neutral wording with some tension")

    assert result.decision is models.ModerationDecision.HUMAN_REVIEW
    assert math.isclose(result.confidence_score, 0.7, rel_tol=1e-6)


def test_evaluate_text_rejects_high_toxicity(monkeypatch):
    _stub_toxicity(
        monkeypatch,
        [
            {"label": "toxic", "score": 0.1},
            {"label": "severe_toxic", "score": 0.1},
            {"label": "obscene", "score": 0.15},
            {"label": "threat", "score": 0.1},
            {"label": "insult", "score": 0.92},
            {"label": "identity_hate", "score": 0.05},
        ],
    )
    _stub_sentiment(monkeypatch, label="POSITIVE", score=0.2)

    result = text_service.evaluate_text("You are an idiot")

    assert result.decision is models.ModerationDecision.REJECTED
    assert math.isclose(result.confidence_score, 0.92, rel_tol=1e-6)


def test_evaluate_text_rejects_on_keyword_heuristic(monkeypatch):
    _stub_toxicity(
        monkeypatch,
        [
            {"label": "toxic", "score": 0.1},
            {"label": "severe_toxic", "score": 0.05},
            {"label": "obscene", "score": 0.1},
            {"label": "threat", "score": 0.1},
            {"label": "insult", "score": 0.1},
            {"label": "identity_hate", "score": 0.1},
        ],
    )
    _stub_sentiment(monkeypatch, label="POSITIVE", score=0.1)

    result = text_service.evaluate_text("I will kill this thread")

    assert result.decision is models.ModerationDecision.REJECTED
    assert math.isclose(result.confidence_score, 0.95, rel_tol=1e-6)
    assert math.isclose(result.label_scores["keyword_heuristic"], 0.95, rel_tol=1e-6)


def test_evaluate_text_human_review_on_negative_sentiment(monkeypatch):
    _stub_toxicity(
        monkeypatch,
        [
            {"label": "toxic", "score": 0.1},
            {"label": "severe_toxic", "score": 0.1},
            {"label": "obscene", "score": 0.1},
            {"label": "threat", "score": 0.1},
            {"label": "insult", "score": 0.1},
            {"label": "identity_hate", "score": 0.1},
        ],
    )
    _stub_sentiment(monkeypatch, label="NEGATIVE", score=0.88)

    result = text_service.evaluate_text("I am really disappointed with this")

    assert result.decision is models.ModerationDecision.HUMAN_REVIEW
    assert math.isclose(result.confidence_score, 0.88, rel_tol=1e-6)
    assert math.isclose(result.label_scores["sentiment_negative"], 0.88, rel_tol=1e-6)
