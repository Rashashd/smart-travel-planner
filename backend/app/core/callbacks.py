import time
from typing import Any

import structlog
from langchain_core.callbacks import BaseCallbackHandler

log = structlog.get_logger(__name__)

_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}
# observability instrumentation for agent runs

# we use these callbacks to let langgraph call them at the right time during execution, so we don't manually instrument every single LLM and tool call in the agent code


# basecallbackhandler is a class from langchain
# essentially an interface that guarantees langgraph knows how to talk to the callback objects
class _TokenLogger(BaseCallbackHandler):
    # Logs prompt + completion token counts after every LLM call, it is used by cost tracker

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        for generation in response.generations:
            for g in generation:
                # tries to get token usage
                usage = getattr(g.message, "usage_metadata", None) or getattr(g, "generation_info", {})
                if not usage:
                    continue
                prompt_tokens = usage.get("input_tokens") or usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("output_tokens") or usage.get("completion_tokens", 0)
                model = getattr(g.message, "response_metadata", {}).get("model_name", "unknown")
                log.info(
                    "llm.tokens",
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                )


class CostTracker(BaseCallbackHandler):
    # Accumulates token counts across all LLM calls in one agent run and computes cost

    # defining attributes for the class
    def __init__(self):
        self._cost_usd: float = 0.0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        for generation in response.generations:
            for g in generation:
                usage = getattr(g.message, "usage_metadata", None) or getattr(g, "generation_info", {})
                if not usage:
                    continue
                prompt = usage.get("input_tokens") or usage.get("prompt_tokens", 0)
                completion = usage.get("output_tokens") or usage.get("completion_tokens", 0)
                self.prompt_tokens += prompt
                self.completion_tokens += completion
                model = getattr(g.message, "response_metadata", {}).get("model_name", "")
                for key, prices in _PRICING.items():
                    if key in model:
                        self._cost_usd += (
                            prompt * prices["input"] + completion * prices["output"]
                        ) / 1_000_000
                        break

    @property
    def cost_usd(self) -> float:
        return round(self._cost_usd, 6)


class ToolTimingCallback(BaseCallbackHandler):
    # Records how long each tool call takes and whether it errored

    def __init__(self):
        self._starts: dict[str, float] = {}
        self.durations: list[float | None] = []
        self.errors: list[str | None] = []

    def on_tool_start(self, serialized, input_str, *, run_id, **kwargs):
        self._starts[str(run_id)] = time.perf_counter()
        self.errors.append(None)

    def on_tool_end(self, output, *, run_id, **kwargs):
        start = self._starts.pop(str(run_id), None)
        self.durations.append(round(time.perf_counter() - start, 3) if start else None)

    def on_tool_error(self, error, *, run_id, **kwargs):
        start = self._starts.pop(str(run_id), None)
        self.durations.append(round(time.perf_counter() - start, 3) if start else None)
        if self.errors:
            self.errors[-1] = str(error)
