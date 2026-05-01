import httpx
import structlog
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

log = structlog.get_logger(__name__)


class TripPlanEvent(BaseModel):
    user_email: str
    plan: str


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(httpx.HTTPError),
)
async def _post(url: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()


async def deliver_trip_plan(url: str, event: TripPlanEvent) -> None:
    payload = {"text": f"*Trip plan for {event.user_email}:*\n{event.plan[:3000]}"}
    try:
        await _post(url, payload)
        log.info("webhook.delivered", user=event.user_email)
    except Exception:
        log.exception("webhook.failed", user=event.user_email)
