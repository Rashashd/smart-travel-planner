"""Schema validation — pure Pydantic, no DB or HTTP required."""

import pytest
from pydantic import ValidationError

from app.tools.classifier_tool import ClassifyInput
from app.tools.live_tool import LiveConditionsInput, ToolError
from app.tools.rag_tool import RAGInput


# ── ClassifyInput ─────────────────────────────────────────────────────────────

def test_classify_input_valid():
    data = ClassifyInput(
        avg_temp_c=25.0,
        beach_score=8,
        mountain_score=2,
        cultural_sites_score=5,
        nightlife_score=4,
        avg_daily_cost_usd=120.0,
        luxury_index=3,
        family_friendly_score=7,
    )
    assert data.beach_score == 8


def test_classify_input_rejects_beach_score_above_max():
    with pytest.raises(ValidationError):
        ClassifyInput(
            avg_temp_c=25.0,
            beach_score=11,  # max is 10
            mountain_score=2,
            cultural_sites_score=5,
            nightlife_score=4,
            avg_daily_cost_usd=120.0,
            luxury_index=3,
            family_friendly_score=7,
        )


def test_classify_input_rejects_negative_daily_cost():
    with pytest.raises(ValidationError):
        ClassifyInput(
            avg_temp_c=25.0,
            beach_score=5,
            mountain_score=5,
            cultural_sites_score=5,
            nightlife_score=5,
            avg_daily_cost_usd=-1.0,  # ge=0
            luxury_index=5,
            family_friendly_score=5,
        )


def test_classify_input_rejects_temp_below_min():
    with pytest.raises(ValidationError):
        ClassifyInput(
            avg_temp_c=-60.0,  # ge=-50
            beach_score=5,
            mountain_score=5,
            cultural_sites_score=5,
            nightlife_score=5,
            avg_daily_cost_usd=100.0,
            luxury_index=5,
            family_friendly_score=5,
        )


# ── LiveConditionsInput ───────────────────────────────────────────────────────

def test_live_conditions_input_valid():
    data = LiveConditionsInput(city="Paris", country="France")
    assert data.city == "Paris"


def test_live_conditions_input_rejects_empty_city():
    with pytest.raises(ValidationError):
        LiveConditionsInput(city="", country="France")


def test_live_conditions_input_rejects_empty_country():
    with pytest.raises(ValidationError):
        LiveConditionsInput(city="Paris", country="")


# ── RAGInput ──────────────────────────────────────────────────────────────────

def test_rag_input_valid():
    data = RAGInput(query="best beaches in Thailand")
    assert data.query == "best beaches in Thailand"


def test_rag_input_rejects_too_short():
    with pytest.raises(ValidationError):
        RAGInput(query="ab")  # min_length=3


# ── ToolError ─────────────────────────────────────────────────────────────────

def test_tool_error_retryable():
    err = ToolError(error="network timeout", retryable=True)
    assert err.retryable is True


def test_tool_error_not_retryable():
    err = ToolError(error="classification failed", retryable=False)
    assert err.retryable is False
