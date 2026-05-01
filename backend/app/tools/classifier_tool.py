import asyncio

import pandas as pd
import structlog
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.tools.live_tool import ToolError

log = structlog.get_logger(__name__)


class ClassifyInput(BaseModel):
    avg_temp_c: float = Field(..., ge=-50, le=50)
    beach_score: int = Field(..., ge=0, le=10)
    mountain_score: int = Field(..., ge=0, le=10)
    cultural_sites_score: int = Field(..., ge=0, le=10)
    nightlife_score: int = Field(..., ge=0, le=10)
    avg_daily_cost_usd: float = Field(..., ge=0)
    luxury_index: int = Field(..., ge=0, le=10)
    family_friendly_score: int = Field(..., ge=0, le=10)


def make_classifier_tool(classifier) -> StructuredTool:
    async def _classify(
        avg_temp_c: float,
        beach_score: int,
        mountain_score: int,
        cultural_sites_score: int,
        nightlife_score: int,
        avg_daily_cost_usd: float,
        luxury_index: int,
        family_friendly_score: int,
    ) -> dict | ToolError:
        try:
            x = pd.DataFrame([{
                "avg_temp_c": avg_temp_c,
                "beach_score": beach_score,
                "mountain_score": mountain_score,
                "cultural_sites_score": cultural_sites_score,
                "nightlife_score": nightlife_score,
                "avg_daily_cost_usd": avg_daily_cost_usd,
                "luxury_index": luxury_index,
                "family_friendly_score": family_friendly_score,
            }])
            # asyncio.to_thread — classifier.predict is CPU-bound, never block the event loop
            pred = await asyncio.to_thread(classifier.predict, x)
            proba = await asyncio.to_thread(classifier.predict_proba, x)
            return {
                "predicted_style": pred[0],
                "probabilities": dict(zip(
                    classifier.classes_,
                    [round(float(p), 3) for p in proba[0]],
                )),
            }
        except Exception:
            log.exception("classifier_tool.failure")
            return ToolError(error="Classification failed", retryable=False)

    return StructuredTool.from_function(
        coroutine=_classify,
        name="classify_destination",
        description="Classify a destination by travel style given numeric feature scores.",
        args_schema=ClassifyInput,
    )
