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

Seeded Slack threads have no real Slack URL, so their evidence links point to `/artifacts/{id}`, which the frontend renders as a thread view.
