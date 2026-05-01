import asyncio

import httpx
import structlog
from cachetools import TTLCache
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings

log = structlog.get_logger(__name__)

# ToolError is defined here and imported by rag_tool and classifier_tool
class ToolError(BaseModel):
    error: str
    retryable: bool


class LiveConditionsInput(BaseModel):
    city: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)


def _make_caches(ttl: int) -> tuple[TTLCache, TTLCache]:
    # weather keyed by city name, FX keyed by base currency
    return TTLCache(maxsize=256, ttl=ttl), TTLCache(maxsize=32, ttl=ttl)


# Initialise caches once at import time using the configured TTL
_s = get_settings()
_weather_cache: TTLCache = TTLCache(maxsize=256, ttl=_s.weather_cache_ttl)
_fx_cache: TTLCache = TTLCache(maxsize=32, ttl=_s.weather_cache_ttl)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True,
)
async def _fetch_weather(client: httpx.AsyncClient, city: str) -> dict:
    key = city.lower()
    if key in _weather_cache:
        log.info("live_tool.weather_cache_hit", city=city)
        return _weather_cache[key]

    geo = await client.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1},
    )
    geo.raise_for_status()
    results = geo.json().get("results", [])
    if not results:
        return {"error": f"City not found: {city}"}

    lat, lon = results[0]["latitude"], results[0]["longitude"]
    weather = await client.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,precipitation,weathercode",
            "forecast_days": 1,
        },
    )
    weather.raise_for_status()
    current = weather.json().get("current", {})
    result = {
        "city": city,
        "temp_c": current.get("temperature_2m"),
        "precipitation_mm": current.get("precipitation"),
    }
    _weather_cache[key] = result
    log.info("live_tool.weather_cache_miss", city=city)
    return result


async def _fetch_fx(client: httpx.AsyncClient, base: str = "USD") -> dict:
    key = base.upper()
    if key in _fx_cache:
        log.info("live_tool.fx_cache_hit", base=base)
        return _fx_cache[key]

    try:
        r = await client.get(f"https://open.er-api.com/v6/latest/{base}", timeout=10.0)
        r.raise_for_status()
        rates = r.json().get("rates", {})
        result = {k: rates[k] for k in ["EUR", "GBP", "JPY", "THB", "LBP"] if k in rates}
        _fx_cache[key] = result
        log.info("live_tool.fx_cache_miss", base=base)
        return result
    except Exception:
        log.warning("live_tool.fx_failed", base=base)
        return {}


def _mock_flights(city: str) -> dict:
    prices = {"Paris": 420, "Tokyo": 890, "Bali": 650, "Bangkok": 520, "Lisbon": 310}
    return {
        "cheapest_round_trip_usd": prices.get(city, 550),
        "best_booking_window": "6-8 weeks ahead",
        "note": "Mock data — check Google Flights for real prices.",
    }


async def _live_conditions(city: str, country: str) -> dict | ToolError:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            weather, fx = await asyncio.gather(
                _fetch_weather(client, city),
                _fetch_fx(client, "USD"),
            )
        return {"weather": weather, "fx_rates_from_usd": fx, "flights": _mock_flights(city)}
    except httpx.HTTPStatusError as e:
        log.error("live_tool.http_error", city=city, status=e.response.status_code)
        return ToolError(error=f"Weather API returned HTTP {e.response.status_code}", retryable=False)
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        log.error("live_tool.network_error", city=city, error=str(e))
        return ToolError(error=f"Weather API unreachable: {e}", retryable=True)
    except Exception:
        log.exception("live_tool.unexpected_error", city=city)
        return ToolError(error="Unexpected error fetching live conditions", retryable=False)


def make_live_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_live_conditions,
        name="get_live_conditions",
        description="Get live weather, flight estimates, and FX rates for a city.",
        args_schema=LiveConditionsInput,
    )
