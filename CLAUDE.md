# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Pinpoint

Pinpoint turns a team's Slack and GitHub history into a live map of who knows what, so new hires can find the right person to ask, see if they have time, and reach out in one click.

Hackathon project. Challenge: build an AI agent that helps people succeed after they join a company. Optimize for a working end-to-end demo over completeness. Simple, explainable, and working beats clever and half-built.

## What it does

1. A new hire asks a question in the chat ("How does inbound email sync work, and who should I ask?").
2. The agent answers from indexed PRs and Slack threads, citing every claim with a link.
3. It ranks the people who know the topic, with evidence ("authored 42 PRs in messaging, answered 11 questions, active 2 days ago").
4. It checks bandwidth (meeting load + open reviews) and recommends someone who actually has time.
5. It drafts a Slack DM with context; the user approves, and it sends.
6. It finds mutual free slots and books a meeting; the user approves, and it writes the meeting.
7. A graph view shows people and topics; a bus factor mode flags topics with only one expert.

## Team

Two lanes: backend (`backend/`) and frontend + Slack + demo (`frontend/`, Slack app). See `docs/team.md` for who owns what and the order of work. Stay in your lane's folder; API shape changes update `schema.py`, `types.ts` and `fixtures/` together in one commit.

## Repo layout

```
/backend     FastAPI app (Python)
  /connectors   one adapter per source (slack, github), each emits normalized Events
  /seed         fake org generator: people, Slack threads, meetings
  /graph        scoring, expertise table, bus factor
  /agent        agent loop + tool definitions
  /api          routes: /graph, /chat, /experts, /actions, /health
/frontend    Next.js app
/fixtures    example JSON for every API response (frontend builds against these)
people.json  hand-written identity map for the seeded org
```

Keep this layout unless there's a strong reason to change it.

## Commands

Backend (Python 3.13, managed with `uv`; run from `backend/`, which is the import root, so modules import as `from schema import Event`):

```
uv sync                                   # install
uv run uvicorn api.main:app --reload      # API on :8000
uv run pytest                             # unit tests (no network, no DB)
uv run pytest tests/test_topics.py::test_known_paths   # one test
uv run pytest -m demo                     # golden demo tests against the real DB
uv run python -m scripts.init_db          # apply schema.sql (idempotent)
uv run python -m scripts.load_people      # upsert people.json + topics
uv run python -m scripts.ingest_github [--days 182] [--refresh]   # raw pages cached in backend/data/raw/github
uv run python -m scripts.ingest_slack [--days 90] [--channel help] [--no-tag] [--cached]   # public channels the bot is in; see docs/slack-setup.md
uv run python -m scripts.seed             # ~300 seeded threads; LLM output cached in backend/data/raw/seed, reruns are free
uv run python -m scripts.embed            # embed artifacts missing a vector (resumable)
uv run python -m scripts.score            # rebuild the expertise table
uv run python -m scripts.gen_meetings     # demo-week calendars + open review counts
uv run python -m scripts.reset_demo [--keep-slack]   # between rehearsals: deletes Pinpoint's Slack DMs, actions, booked meetings; regenerates calendars. Restart the API after
uv run python -m scripts.warm_demo        # runs seed/demo_questions.py so answers are in the LLM cache
```

LLM answers are cached on disk by exact prompt (`backend/data/llm_cache/`), so warmed demo questions answer in about a second and survive OpenRouter outages. The cache matches exact question text: `seed/demo_questions.py` must contain the frontend's `SUGGESTED_QUESTIONS` word for word (a test checks). Chat LLM calls time out after `LLM_TIMEOUT` (30s, no retries) and fall back to a code-written answer; seeding and tagging use `llm.batch_client()` (5 min, 2 retries). DB access goes through a small connection pool (`db.py`): opening a Supabase connection costs ~0.6s. Delete that folder to force fresh answers. The API reads `.env` only at startup: restart it after changing `PINPOINT_MODE`.

After any ingest or seed step, run `embed` then `score`, then `pytest -m demo`. Background commands don't inherit `cd`; use `uv run --directory /abs/path/backend ...`.

Pipeline steps go in `backend/scripts/` as `python -m scripts.<step>`.

Frontend (Next.js 16, run from `frontend/`):

```
npm install
npm run dev        # :3000
npm run lint
npm run typecheck  # next typegen + tsc; plain tsc fails on a clean checkout
npm run build
```

Next 16 has breaking changes vs older versions. Read `frontend/AGENTS.md` and the bundled docs in `frontend/node_modules/next/dist/docs/` before writing frontend code.

Fixtures: `frontend/public/fixtures` is a symlink to `/fixtures`. Fixture mode is on unless `NEXT_PUBLIC_USE_FIXTURES=0` (set in `frontend/.env.local`; Next doesn't read the root `.env`). All API calls go through `frontend/src/lib/api.ts`. `frontend/src/lib/types.ts` mirrors `backend/schema.py`, and `backend/tests/test_fixtures.py` fails if a fixture drifts from its model. When you change an API shape, update the model, the TS type and the fixture together.

## Stack

| Layer | Choice |
| --- | --- |
| Backend | Python, FastAPI |
| DB | Postgres + pgvector on Supabase (use the session pooler connection string, not the direct one) |
| Graph math | NetworkX in memory. No graph database. |
| LLM | Free open-source model on OpenRouter, via the `openai` SDK (`backend/llm.py`). Model name in `LLM_MODEL`; must support tool calling. Used for the agent loop, topic tagging, seed generation |
| Embeddings | Local, free: fastembed + `BAAI/bge-small-en-v1.5` (384 dims, CPU, works offline), `backend/embeddings.py`. Stored in pgvector |
| Frontend | Next.js + react-force-graph |
| Integrations | Nango for Slack/GitHub OAuth; fallback is raw tokens in `.env` |
| Slack SDK | `slack_sdk` |
| GitHub | GraphQL API with a personal access token |

Secrets live in `.env` only. Never commit `.env`, tokens, or connection strings. Keep `.env.example` updated with every key name.

## Data strategy

There is no real company data. Two layers, both loaded through the same Event schema:

**Seeded org ("Acme")**
- ~25 fake engineers across 4 teams (Integrations, Platform, Product, Core), defined in `people.json`.
- GitHub history comes from the real open-source repo **twentyhq/twenty** (open-source CRM). Real contributors are mapped to fake Acme personas in `people.json`. Never show real contributor names in the UI.
- Ingest only the last ~6 months of `packages/twenty-server` and `packages/twenty-front`.
- ~300 Slack-style Q&A threads generated by an LLM. Pick each thread's answerer from people who own that topic in the GitHub data, so Slack and GitHub agree on who the experts are.
- Fake calendars: every person gets a week of meetings (daily team standup, weekly 1:1 with manager, 2 to 4 project meetings). A few seniors are 70%+ booked so bandwidth routing visibly kicks in. Generate relative to today so the demo week is always the current week.

**Live layer**
- The team's real Slack workspace (public channels only) and real GitHub.
- Team members are real people inside Acme, so a recommendation can lead to a real DM.

**No real calendars.** All availability and scheduling run on the fake `meetings` table. Keep it behind `get_availability()` so a real calendar API could be swapped in later.

## Topics

Topics = top-level modules of the Twenty server, plus a few non-code ones:
Workflow, Messaging (email sync), Calendar sync, Billing, Auth, Metadata (custom objects), File storage, Message queue / jobs, Frontend, Deploys, On-call.

Map files to topics by path. For Slack threads, the LLM tags 1 to 3 topics per thread from this fixed list (or "other"). Batch ~25 threads per call, and generate seed threads ~10 per call: free OpenRouter models are rate-limited per minute and per day. Do not use clustering to discover topics.

Path map, checked against the repo. Source of truth is `backend/topics.py`; first match wins. Server prefixes are under `packages/twenty-server/src/`, frontend (`front:`) under `packages/twenty-front/src/modules/`:

| Topic | Prefixes |
| --- | --- |
| Messaging | `modules/messaging`, `engine/core-modules/messaging`, `modules/connected-account`, `modules/blocklist`, `modules/match-participant`, `modules/emailing`, `engine/core-modules/imap-smtp-caldav-connection`, front: `accounts`, `settings/accounts` |
| Calendar sync | `modules/calendar`, `engine/core-modules/calendar` |
| Workflow | `modules/workflow`, `engine/core-modules/workflow`, front: `workflow` |
| Billing | `engine/core-modules/billing`, front: `settings/billing` |
| Auth | `engine/core-modules/{auth,sso,two-factor-authentication,jwt}`, front: `auth`, `settings/{security,two-factor-authentication}` |
| Metadata | `engine/metadata-modules`, `engine/workspace-manager`, `database/commands` (upgrade migrations), `test/integration/metadata`, front: `object-metadata`, `metadata-store`, `settings/data-model` |
| File storage | `engine/core-modules/{file-storage,file}`, front: `file-upload`, `file` |
| Message queue / jobs | `engine/core-modules/{message-queue,cron}` |
| Frontend | everything else in `packages/twenty-front/` |

Feature folders in the frontend count toward the feature, so UI work on, say, the data model settings makes you a Metadata expert. Deploys and On-call have no code paths. Their experts come from Slack only. About 16% of PRs match no prefix (shared utils); they still get embedded but add to no topic score.

Search quality is guarded by `tests/test_demo.py` (`uv run pytest -m demo`, real DB). Rerun it after changing the path map, the embedding text or the embedding model.

## Demo data decisions

Grounded in the last 6 months of Twenty history (3,853 squash-merged PRs, all titled `... (#N)`, so commit author = PR author):

Counts shift a little whenever the path map changes; these are from the current map.

- **Dana Okafor = `neo773`**: authored 128 of 292 Messaging PRs, by far the top author.
- **Marcus Lee = `charlesBochet`**: reviewed 38 of Dana's Messaging PRs (Victor reviewed 41; nobody else more than 14). Seed him at ~35% booked. Evidence lines come from real counts, never "most".
- **`FelixMalfait` (founder) = a senior lead persona booked ~85%**. He scores #2 on Messaging and tops most other topics, so he must be busy or he swamps every recommendation. Demo line: top two experts are swamped, Marcus has time.
- Exclude `CoreTeamTwenty` (shared account) and bots from people and scoring.
- **Marcus's `slack_handle` maps to a real teammate**, so the approved DM really arrives. Sends to other fake personas are simulated: the action is marked sent and nothing reaches Slack.
- **Open review counts are seeded per person** by `gen_meetings`, not pulled from GitHub, so availability stays deterministic and tunable.

## Schema

Every connector outputs normalized events. Nothing downstream should know which source an event came from.

```
Event {
  source:      "slack" | "github" | "seed"
  type:        "authored" | "reviewed" | "answered" | "asked" | "owns"
  person_id:   canonical person id
  artifact_id: PR, thread, file
  text:        content to embed (PR title + body, thread text)
  paths:       changed files (GitHub only)
  timestamp
  url:         link back to the source, used as evidence
}
```

Tables: `people`, `topics`, `artifacts`, `events`, `expertise`, `meetings`, `pending_actions`, `corrections`, `user_profiles`, plus `artifact_topics` (artifact to topic, from paths or LLM tags). DDL is `backend/schema.sql`. Notes:
- An event's text lives on its artifact (embedding `vector(384)`; it must match the model in `embeddings.py`).
- `meetings` uses `start_at`/`end_at` (`end` is reserved) and a `seeded` flag; `reset_demo` deletes rows with `seeded = false`.
- `people.open_reviews` is seeded by `gen_meetings`.
- `people.slack_user_id` set = real Slack DM; null = simulated send (`result.delivery = "simulated"`).
- Seeded Slack threads have no real URL; their evidence links are `/artifacts/{id}`, rendered by the frontend.

```
Meeting { id, title, attendees[person_id], start, end, recurring }
```

Identity: `people.json` maps each person's Slack handle, GitHub login, team, role, and manager. Don't build automatic identity matching. For live users connected through Nango, the connection carries their identity.

## Expertise scoring

Keep it dumb and explainable. Every score must be able to show its evidence.

```
score(person, topic) = sum over events e of: weight(type(e)) * 0.5 ^ (age_days(e) / 90)
```

| Evidence | Weight |
| --- | --- |
| owns (CODEOWNERS) | 1.5 |
| authored merged PR | 1.0 |
| answered in Slack | 0.8 |
| reviewed PR | 0.7 |
| asked | 0.1 |

Twenty's CODEOWNERS only covers CI/config files, so ownership comes mostly from authorship and reviews.

- Store the top 3 evidence links per (person, topic).
- `find_experts(query)`: embed the query, get the top 40 artifacts by similarity (20 was too few for prolific authors), keep those within 0.10 of the best match (otherwise dozens of loosely related PRs outvote the few threads that answer the question), aggregate the people on them by similarity x type weight x decay. The question's topic is the one most retrieved artifacts share (similarity-weighted); the evidence line uses that topic's `expertise` counts. Candidates who reviewed 10+ of the top expert's PRs in that topic get "Reviewed N of Dana's Messaging PRs". Code: `backend/graph/experts.py`, `backend/graph/scoring.py`.
- Availability factor (0 to 1) from % of working hours booked this week + open review count. Final rank = expertise x availability. Compute availability only for the top 5 candidates.
- Bus factor: per topic, count people above a score threshold. 1 = red, 2 = amber, 3+ = green.
- Corrections ("I don't own this anymore", "ask X instead") write to `corrections` and down-weight or redirect that edge.

## Agent

| Tool | Does | Needs approval |
| --- | --- | --- |
| `search_knowledge(query)` | Vector search over PRs and threads; returns snippets + URLs | No |
| `find_experts(query or topic)` | Ranked people with scores and top evidence | No |
| `get_availability(people, window)` | Booked %, open reviews, availability factor, mutual free 30-min slots | No |
| `draft_message(to, question, context)` | Returns an editable draft | No |
| `send_message(to, text)` | Slack DM | **Yes** |
| `schedule_meeting(people, slot, title)` | Writes a row to `meetings` | **Yes** |

Hard rules for the agent:
- Only name people returned by `find_experts`. Never invent an expert.
- Every claim about code or process cites a URL from `search_knowledge`.
- Try to answer the question before routing to a person.
- Prefer experts on the user's own team when scores are close (read `user_profiles`).
- `send_message` and `schedule_meeting` never execute directly. They create a `pending_actions` row. Only `POST /actions/{id}/approve` executes them.

Slack sends go out as the bot ("Pinpoint, on behalf of Priya"). Sending as the user is out of scope. A send reaches real Slack only when `PINPOINT_MODE=live` and the recipient has a `slack_user_id`; otherwise it's simulated (`result.delivery = "simulated"`).

**How it's built** (`backend/agent/`): the tools are plain functions, and the free model only writes prose, because it's slow (~20s per answer) and unreliable at multi-step tool loops.
- **Question turn** (`chat.py`): code runs search -> `find_experts` -> availability, then one LLM call writes the answer with [n] citations plus the DM draft. Sources are labeled PR or THREAD, at most 3 threads, so real PRs anchor answers.
- **Code enforces the hard rules** (`compose.py`): citations are renumbered and any marker without a source is dropped; the answer may not name anyone (routing is a code-written sentence from real numbers); the DM may name only the asker and recipient; LLM failure falls back to code-written text.
- **Follow-ups** are detected by regex, not the LLM: "book time Wednesday 10:30" -> mutual free slots -> pending `schedule_meeting`; "message Dana instead" -> new DM draft.
- **Approve** claims the row with `where status = 'pending'` (double clicks run once) and rechecks the slot before booking.
- Conversation state is in memory, so restarting the API forgets open conversations.

**Seeded threads are checked**: generated text may only use PR numbers and code identifiers that appear in the PRs given to that batch; sentences with anything else are dropped, and threads left with nothing verifiable are skipped (`seed/threads.py`).

## Frontend

**MVP and V1 are chat-only.** No graph view, no bus factor view. Don't build graph UI or graph-only backend (NetworkX layout, `/graph` route, bus factor) until it's pulled back into scope. The graph notes below are deferred, kept for later.

- Graph (deferred) shows **people and topic nodes only**. Artifacts appear on click, never as nodes (avoid the hairball). Person node size = score, color = team. Clicking a topic highlights its experts and dims everything else.
- Graph modes: Experts / Bus factor.
- Chat shows answers with citation chips, expert cards (evidence line, availability bar, Busy/Recommended badge, "Not the right person?" correction link), approve cards for DMs and meetings, and a mini week view for scheduling.
- Selecting an expert in chat highlights them in the graph, and vice versa.
- No mockups exist yet; Harshita (frontend lane) is designing them. Until then, design from this section, `docs/team.md` and the fixtures.

Build the frontend against `/fixtures` JSON from hour 0. Swap to real endpoints when they land.

## Scope

**MVP (must work end to end first)**
- Schema, `people.json`, seeded Acme data loaded
- GitHub ingest of twentyhq/twenty
- Scoring + `find_experts` with evidence links
- Chat agent: question in, answer + ranked experts + citations out
- Draft + approve + send Slack DM

**V1**
- Live Slack ingest
- Fake meetings: bandwidth factor + scheduling
- Slack #help fast path: poll the channel every ~30s (not the Events API, which needs a public URL), reply in-thread with past answers and owners
- Promotion loop: "That answered it" saves the answer as a new artifact
- Correction button
- Per-user profile

**Deferred (post-V1):** graph view with topic focus, bus factor view, graph ⇄ chat linking.

**Stretch:** Notion/Confluence connector, Gmail fallback send, live Slack events, real Google Calendar for one account.

**Out of scope:** Microsoft Teams, real company data, automatic identity matching, topic clustering, graph databases, Meet transcripts.

## Conventions

- Ingest once into the DB. Never query Slack or GitHub live for search. Respect rate limits; batch API and embedding calls.
- Only ingest public Slack channels. The bot must be invited to a channel to read it.
- Keep connectors isolated: adding a source means adding one adapter, nothing else.
- Write small, testable functions. A `scripts/` entry point per pipeline step (`seed`, `ingest_github`, `ingest_slack`, `embed`, `score`, `gen_meetings`) so steps can be rerun independently.
- Provide `scripts/reset_demo` to restore demo state (meetings, pending actions).
- Keep a seeded-only mode that works with no network access to Slack or Nango, as a demo fallback.
- Don't add dependencies without a reason. Don't introduce new services (Redis, Neo4j, etc.).
- When unsure between two approaches, pick the one that's faster to demo and easier to explain.

## Demo persona

Priya Shah, new hire on Integrations, day 3. Example flow: asks how inbound email sync works → top expert Dana Okafor is 78% booked → Pinpoint recommends Marcus Lee (reviewed most of Dana's sync PRs, 35% booked) → drafts a DM → books Wed 10:30 AM.
