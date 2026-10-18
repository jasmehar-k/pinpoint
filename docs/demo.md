# Demo script

About 3 minutes. Harshita drives the laptop as Priya Shah (new hire, Integrations, day 3) and plays Marcus on her phone: Marcus's `slack_user_id` (`U0CA77SLTPE`) is hers, so the approved DM really arrives.

## Before you start

1. Root `.env` on the demo laptop has:
   - `DATABASE_URL` (Supabase session pooler string)
   - `OPENROUTER_API_KEY` and `LLM_MODEL`
   - `PINPOINT_MODE=live` and `SLACK_BOT_TOKEN`. Without both, the DM is only simulated (`result.delivery: "simulated"`) and nothing reaches the phone.
2. `frontend/.env.local` has `NEXT_PUBLIC_USE_FIXTURES=0`.
3. Before **each** run-through, from `backend/`:
   ```
   uv run --python 3.13 python -m scripts.reset_demo   # deletes Pinpoint's DMs, actions and booked meetings; resets calendars
   uv run --python 3.13 python -m scripts.warm_demo    # caches the demo answers: ~3s on stage instead of ~30s
   ```
4. Start (or restart) both, then open http://localhost:3000. Restart the backend after the reset: conversations live in its memory.
   ```
   cd backend && uv run --python 3.13 uvicorn api.main:app   # :8000
   cd frontend && npm run dev                                 # :3000
   ```
5. Check `warm_demo` printed about a second per question on a second run. A question that isn't cached waits up to 30s for the model, then gets a code-written answer.
6. Phone unlocked, Slack open, notifications on.

## Run-through

| # | Do | Say / point at |
| --- | --- | --- |
| 1 | Click **How does inbound email sync work?** | "Priya joined Integrations three days ago." New hires lose days figuring out who to ask. |
| 2 | Click citation chip **1** | Every claim links to its source: PR #26180 opens in a new tab. Come back to the chat tab. |
| 3 | Scroll to the expert cards | Dana wrote most of this (128 Messaging PRs) but is 78% booked; Victor 84%. Marcus reviewed 38 of Dana's Messaging PRs and is 35% booked, so he's Recommended. |
| 4 | Change a word in the draft (it opens "I'm Priya, new on Integrations"), click **Approve and send** | Nothing is sent until you approve. **Hold up the phone: the DM from Pinpoint, on behalf of Priya, has arrived.** |
| 5 | Type **Can you book time with Marcus on Wednesday at 10:30am?** | It finds times you're both free. Wed 10:30 is preselected. |
| 6 | Click **Book Wed 10:30 – 11:00 AM** | Booked and on both calendars. |
| 7 | Type **How are subscriptions and plan upgrades billed?** | Same pipeline, different expert: Isabel Moreno (60 Billing PRs, 34% booked) is Recommended. |
| 8 | Close | "We only read public channels the bot is invited to, and anyone can opt out." |

Spare question if there's time: **How do workflow triggers and actions run?** Elena Petrova knows it best but is 70% booked, so Ken Watanabe, who reviewed 17 of her Workflow PRs, is Recommended.

## If something breaks

- **The answer is slow ("Still digging through PRs and threads…"):** the question isn't cached. Keep talking; after 30s a code-written answer appears with the same experts and citations. Next time, rerun `warm_demo`.
- **The DM says "Simulated":** `PINPOINT_MODE` isn't `live` or `SLACK_BOT_TOKEN` is missing. Keep going and say the send is simulated for the demo.
- **"Couldn't get an answer: can't reach the backend":** restart uvicorn. If it won't come back, switch to fixtures: set `NEXT_PUBLIC_USE_FIXTURES=1` in `frontend/.env.local`, restart `npm run dev`, and run steps 1 to 6 only. In fixture mode every question gets the email-sync answer, so skip step 7.
