# Demo script

About 3 minutes. Harshita drives the laptop as Priya Shah (new hire, Integrations, day 3) and plays Marcus on her phone: Marcus's `slack_user_id` (`U0CA77SLTPE`) is hers, so the approved DM really arrives.

## Before you start

1. Root `.env` on the demo laptop has:
   - `DATABASE_URL` (Supabase session pooler string)
   - `OPENROUTER_API_KEY` and `LLM_MODEL`
   - `PINPOINT_MODE=live` and `SLACK_BOT_TOKEN`. Without both, the DM is only simulated (`result.delivery: "simulated"`) and nothing reaches the phone.
2. `frontend/.env.local` has `NEXT_PUBLIC_USE_FIXTURES=0`.
3. Start both, then open http://localhost:3000:
   ```
   cd backend && uv run uvicorn api.main:app        # :8000
   cd frontend && npm run dev                        # :3000
   ```
4. Warm up: ask one question, wait for the answer (real answers take ~20s), then reload the page for a clean chat.
5. Phone unlocked, Slack open, notifications on.
6. Conversations live in backend memory: restarting the backend means starting a new chat (reload the page).
7. **Reset between run-throughs:** `reset_demo` isn't built yet. Until it is, a second run finds Wed 10:30 already booked and offers the next free slot, which is fine to demo.

## Run-through

| # | Do | Say / point at |
| --- | --- | --- |
| 1 | Click **How does inbound email sync work?** | "Priya joined Integrations three days ago." While it loads (~20s): new hires lose days figuring out who to ask. |
| 2 | Click citation chip **1** | Every claim links to its source. The PR opens in a new tab; come back to the chat tab. |
| 3 | Scroll to the expert cards | Dana wrote most of this but is 78% booked; Victor 85%. Marcus reviewed 38 of Dana's Messaging PRs and is 35% booked, so he's Recommended. |
| 4 | Change a word in the draft, click **Approve and send** | Nothing is sent until you approve. **Hold up the phone: the DM from Pinpoint, on behalf of Priya, has arrived.** |
| 5 | Type **Can you book time with Marcus Wednesday morning?** | It finds times you're both free. Wed 10:30 is preselected. |
| 6 | Click **Book Wed 10:30 – 11:00 AM** | Booked and on both calendars. |
| 7 | Click **How are subscriptions and plan upgrades billed?** | Same pipeline, different expert: Isabel Moreno ranks first. |
| 8 | Close | "We only read public channels the bot is invited to, and anyone can opt out." |

Spare question if there's time: **How do workflow triggers and actions run?** (Elena Petrova ranks first).

## If something breaks

- **The model is slow or down:** wait; the backend falls back to a code-written answer on its own, with the same experts and citations.
- **The DM says "Simulated":** `PINPOINT_MODE` isn't `live` or `SLACK_BOT_TOKEN` is missing. Keep going and say the send is simulated for the demo.
- **"Couldn't get an answer: can't reach the backend":** restart uvicorn. If it won't come back, switch to fixtures: set `NEXT_PUBLIC_USE_FIXTURES=1` in `frontend/.env.local`, restart `npm run dev`, and run steps 1 to 6 only. In fixture mode every question gets the email-sync answer, so skip step 7.
