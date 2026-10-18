Example responses for every API route. The frontend builds against these until the real endpoints land. Models live in `backend/schema.py`; `backend/tests/test_fixtures.py` fails if a fixture drifts from its model.

| Route | Fixture | Model |
| --- | --- | --- |
| `GET /health` | `health.json` | `Health` |
| `GET /experts?q=` | `experts.json` | `ExpertsResponse` |
| `POST /chat` (first turn) | `chat.json` | `ChatResponse` |
| `POST /chat` (scheduling turn) | `chat_schedule.json` | `ChatResponse` |
| `GET /availability?people=&window=` | `availability.json` | `AvailabilityResponse` |
| `POST /actions/{id}/approve` (DM) | `action_approve_message.json` | `PendingAction` |
| `POST /actions/{id}/approve` (meeting) | `action_approve_meeting.json` | `PendingAction` |
| `GET /artifacts/{id}` | `artifact.json` | `ArtifactResponse` |
| `GET /graph` | `graph.json` (real data) | `GraphResponse` |
| `POST /actions/{id}/rewrite` | same shape as a pending action | `PendingAction` |

Request bodies (no fixtures, models in `schema.py`):

- `POST /chat`: `ChatRequest` `{ message, conversation_id?, user }`. Omit `conversation_id` on the first message, then reuse the one from the response.
- `POST /actions/{id}/rewrite`: `RewriteRequest` `{ style: "shorter" }`. Rewrites a pending DM's text and returns the updated action. 409 if it isn't a pending DM.
- `POST /actions/{id}/approve`: `ApproveRequest` `{ payload? }`. Send `payload` with the user's edits (DM text, chosen slot); omit it to execute the draft unchanged.

Seeded Slack threads have no real Slack URL, so their evidence links point to `/artifacts/{id}`, which the frontend renders as a thread view.
