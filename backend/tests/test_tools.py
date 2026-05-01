"""Tool isolation tests — real classifier, mocked HTTP."""

from unittest.mock import MagicMock, patch

import httpx
import joblib
import pytest

from app.tools.classifier_tool import make_classifier_tool
from app.tools.live_tool import ToolError, _live_conditions

from tests.conftest import CLASSIFIER_PATH


# ── Classifier tool ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def real_classifier():
    return joblib.load(CLASSIFIER_PATH)


async def test_classifier_returns_prediction(real_classifier):
    tool = make_classifier_tool(real_classifier)
    result = await tool.coroutine(
        avg_temp_c=28.0,
        beach_score=9,
        mountain_score=1,
        cultural_sites_score=3,
        nightlife_score=5,
        avg_daily_cost_usd=80.0,
        luxury_index=4,
        family_friendly_score=6,
    )
    assert isinstance(result, dict)
    assert "predicted_style" in result
    assert "probabilities" in result
    # rf_tuned was trained on 6 classes
    assert len(result["probabilities"]) == 6
    assert sum(result["probabilities"].values()) == pytest.approx(1.0, abs=0.01)


async def test_classifier_returns_tool_error_on_failure():
    broken = MagicMock()
    broken.predict.side_effect = RuntimeError("model corrupted")
    tool = make_classifier_tool(broken)
    result = await tool.coroutine(
        avg_temp_c=20.0,
        beach_score=5,
        mountain_score=5,
        cultural_sites_score=5,
        nightlife_score=5,
        avg_daily_cost_usd=100.0,
        luxury_index=5,
        family_friendly_score=5,
    )
    assert isinstance(result, ToolError)
    assert result.retryable is False


# ── Live tool ─────────────────────────────────────────────────────────────────

async def test_live_tool_returns_tool_error_on_timeout():
    # Patch _fetch_weather directly to avoid real HTTP calls and retry delays
    with patch("app.tools.live_tool._fetch_weather", side_effect=httpx.TimeoutException("timeout")):
        result = await _live_conditions("Paris", "France")

    assert isinstance(result, ToolError)
    assert result.retryable is True


async def test_live_tool_returns_tool_error_on_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 500
    http_error = httpx.HTTPStatusError("server error", request=MagicMock(), response=mock_response)

    with patch("app.tools.live_tool._fetch_weather", side_effect=http_error):
        result = await _live_conditions("Tokyo", "Japan")

    assert isinstance(result, ToolError)
    assert result.retryable is False
