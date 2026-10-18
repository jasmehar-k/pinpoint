# Who does what

Two lanes, split by folder so we almost never edit the same files.

| | Backend (Claude) | Frontend + Slack + demo (teammate) |
| --- | --- | --- |
| Owns | `backend/` | `frontend/`, the Slack app, the demo script |
| Can't touch without a heads-up | `frontend/` | `backend/` |

Shared files: `fixtures/`, `people.json`, `CLAUDE.md`, `.env.example`. Pull before editing them and keep those commits small.

## The contract between lanes

The frontend builds against `/fixtures` and never waits on the backend. The API shape lives in three places that change together, in one commit, by whoever changes the shape:

- `backend/schema.py` (Python models)
- `frontend/src/lib/types.ts` (TypeScript types)
- `fixtures/*.json` (example responses; `uv run pytest` fails if they drift from the models)

Need a new field or route? Add it to the fixture and type first, tell the other person, and the backend fills it in.

## Backend lane (Claude)

In order. Each step ends with its tests passing and a commit.

1. Embeddings for all PRs, with the model cached in the repo so the offline demo works
2. Scoring + `find_experts` (`GET /experts`), plus the golden demo test (`pytest -m demo`): the demo questions, the PRs they should find, the expected expert order
3. Seeded Slack threads (~300, plus ~5 hand-written demo threads), then re-score
4. Fake meetings + `get_availability` (`GET /availability`), with Dana at 78%, Victor at 85%, Marcus at 35%
5. Agent loop (`POST /chat`): fixed search → experts → availability pipeline on the first question, the LLM writes the answer and draft, and code checks every name and URL
6. Approvals (`POST /actions/{id}/approve`): Slack DM or a meetings row, safe to click twice
7. `reset_demo`, seeded-only mode, a replay cache for the demo questions in case OpenRouter fails live

## Frontend + Slack lane (teammate)

**Slack (do first, it unblocks the real DM):**
- Create a free workspace and invite both of us
- Create a Slack app with bot scopes `channels:history`, `channels:read`, `users:read`, `chat:write`, `im:write`; install it and put the `xoxb-` token in `.env` as `SLACK_BOT_TOKEN`
- Create `#help` and invite the bot
- Put your own Slack user ID in `people.json` as `marcus-lee`'s `slack_user_id`. You are Marcus in the demo, so the approved DM lands on your phone.

**Chat UI (against fixtures, matching the mockups):**
- Chat panel with answer text and citation chips (`[n]` markers map to `reply.citations`)
- Expert cards: evidence line, evidence links, availability bar, Busy/Recommended badge, "Not the right person?" link
- Approve card for the DM: editable text, Approve sends the edited version, button locks after one click
- Approve card for the meeting + mini week view of free slots (show times in the org timezone, Pacific, not the browser's)
- Loading state: real answers can take 15s+, so disable input while waiting
- A page at `/artifacts/[id]` for seeded thread links (render the thread; fixture data is fine for now)
- Stacks on phone width
- Graph view is out of scope for now

All calls go through `frontend/src/lib/api.ts`. When a backend route is ready, you'll hear about it; flip `NEXT_PUBLIC_USE_FIXTURES=0` in `frontend/.env.local` to try it.

**Demo:**
- Pick 3 to 5 demo questions (the email sync one, plus a couple on other topics), so the golden test checks the right things
- Read real answers as they land and flag anything that sounds wrong, too long, or robotic
- Own the run-through and the pitch, including the one-line privacy note (public channels only, opt-out)

**Later (V1), if time allows:** live Slack ingest and the `#help` fast path. Both are Slack-heavy; we'll decide who takes them once the core loop works.

## Checkpoints

| When backend has | Frontend does |
| --- | --- |
| `GET /experts` | Expert cards on real data |
| `POST /chat` | Full chat on real data |
| `POST /actions/{id}/approve` | Real DM to Marcus (you), real meeting row |
| `reset_demo` | First full run-through, then two clean ones in a row |
