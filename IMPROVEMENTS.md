# Future Improvements

## Real Data & Quality

- **Replace mock flight data**: `_mock_flights()` in `live_tool.py` returns hardcoded prices for known cities and $550 for everything else. Replace with a real API (Amadeus, Skyscanner) for accurate prices.
- **Ingest more destinations**: the RAG knowledge base only covers 12 Wikivoyage destinations. Adding 50–100 more would dramatically improve answer quality.
- **Classifier confidence threshold**: if the classifier's `predict_proba` score is below ~60%, tell the user "I'm not sure what type of trip this is" instead of confidently guessing wrong.

## User Experience

- **Streaming responses**: right now the UI waits for the full answer before showing anything. LangGraph supports `astream_events` for token-by-token output, which feels much faster even if total time is the same.
- **Multi-destination planning**: the agent currently handles one destination at a time. Supporting itineraries like "Paris → Rome → Barcelona" would be a major feature.
- **Show cost per message in the UI**: `cost_usd` is now saved in `agent_runs`. Surface it in the chat UI so users can see what each response cost.

## Security

- **Secret management with HashiCorp Vault**: right now secrets (`OPENAI_API_KEY`, `JWT_SECRET`, `SLACK_WEBHOOK_URL`) live in a `.env` file on disk. In production, store them in HashiCorp Vault (or AWS Secrets Manager / GCP Secret Manager) and fetch them at startup via the Vault API. This means secrets are never on disk, access is audited, and rotating a key doesn't require redeploying the app.

## Reliability

- **Persistent checkpointer**: `MemorySaver` in `agent.py` stores conversation memory in-process. If the server restarts, all memory is lost. Replace with `AsyncSqliteSaver` or a Postgres-backed checkpointer so memory truly survives restarts.
- **Rate limiting on `/chat`**: one user can currently spam the OpenAI API with no limit. Add per-user rate limiting (e.g. slowapi) to control costs.
- **Shared cache with Redis**: the TTL caches for weather and FX rates (`live_tool.py`) live in-process. If you ever run more than one backend container, each has its own cache. Moving to Redis fixes this and survives restarts.

## Observability

- **Admin endpoint**: add a `/admin/runs` endpoint that lists recent agent runs with their cost, duration, and tool calls, so you can browse query history without opening the database directly.
- **Cost dashboard**: query `SELECT SUM(cost_usd) FROM agent_runs` to track total spend. Could be a simple `/admin/stats` endpoint.

## ML

- **More training data**: 150 rows (25 per class) is the bare minimum. More rows = more robust classifier, especially for the Culture/Family confusion.
- **SHAP explanations**: add SHAP values to classifier output so the agent can explain *why* it classified a destination a certain way: "Bali is Relaxation because beach_score=9 and avg_daily_cost=45."

## Priority Order

1. **Streaming responses**: biggest UX improvement, moderate effort
2. **Persistent checkpointer**: fixes a real bug (memory resets on restart)
3. **Real flight data**: removes the most obviously fake part of the product
4. **More Wikivoyage destinations**: improves RAG answer quality across the board