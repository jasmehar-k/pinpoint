# Demo script

About 3½ minutes. Every beat shows the agent **doing** something, and the human approving it.

**Roles**
- **Harshita** drives the laptop as Priya Shah (new hire, Integrations, day 3) and has her phone out as Marcus: Marcus's `slack_user_id` (`U0CA77SLTPE`) is hers, so the approved DM really arrives.
- **Jasmehar** narrates, and posts in `#help` from her own Slack account, which is Priya's (`U0CAXTS3BC0`).

## Before you start

1. Root `.env` on the demo laptop has:
   - `DATABASE_URL` (Supabase session pooler string)
   - `OPENROUTER_API_KEY` and `LLM_MODEL`
   - `PINPOINT_MODE=live` and `SLACK_BOT_TOKEN`. Without both, the DM is only simulated and nothing reaches the phone.
2. `frontend/.env.local` has `NEXT_PUBLIC_USE_FIXTURES=0`.
3. Before **each** run-through, from `backend/`:
   ```
   uv run --python 3.13 python -m scripts.reset_demo   # deletes Pinpoint's DMs, #help replies, actions, bookings, corrections; resets calendars
   uv run --python 3.13 python -m scripts.warm_demo    # caches the demo answers, including the #help one: ~1s on stage instead of ~30s
   ```
4. Start (or restart) all three, then open http://localhost:3000. Restart the backend after the reset: conversations live in its memory.
   ```
   cd backend && uv run --python 3.13 uvicorn api.main:app        # :8000
   cd backend && uv run --python 3.13 python -m scripts.help_bot --every 5   # #help bot, checks every 5s for the demo
   cd frontend && npm run dev                                      # :3000
   ```
5. Check `warm_demo` printed about a second per question on a second run.
6. Phone unlocked, Slack open on `#help`, notifications on. Jasmehar has `#help` open on her laptop.
7. Jasmehar copies the `#help` question from this file and pastes it. It must match the cached text exactly; if macOS turns the apostrophe in "who's" curly, the answer takes 20 to 30 seconds instead of one.

## Run-through

| # | Time | Do | Say / point at |
| --- | --- | --- | --- |
| 1 | 0:00 | Main page, nothing clicked | **The problem:** "New hires spend their first weeks not knowing who to ask. They ping the most senior person, who is swamped, or they stay stuck. **The user:** Priya, three days into Integrations." |
| 2 | 0:20 | Click **How does inbound email sync work?** | "Pinpoint answers first, from the team's own PRs and Slack threads." |
| 3 | 0:35 | Click citation chip **2** (PR #26180 opens), come back | "Every sentence links to its source. If it can't cite it, it doesn't say it." |
| 4 | 0:50 | Scroll to the expert cards; point at the graph; click **Show evidence** on Marcus | "Then it finds who knows this, with receipts. Dana wrote most of it, 128 PRs, but she's 78% booked. Marcus reviewed 38 of her PRs and has time, so he's Recommended. The graph ranks by expertise alone: Marcus is third there, first here, because he has time. To enable Pinpoint to be ever-improving, if it's wrong, click **Not the right person?** and it corrects it for everyone." |
| 5 | 1:25 | Change a word in the draft (it opens "I'm Priya, new on Integrations"), click **Approve and send** | "It drafted the DM with the context attached. **Nothing is sent until Priya approves.**" **Harshita holds up the phone: the DM from Pinpoint, on behalf of Priya, has arrived.** |
| 6 | 1:45 | Type **Can you book time with Marcus on Wednesday at 10:30am?**. "It checks both calendars and offers times they're both free." |
| 7 | 2:00 | Click **Book Wed 10:30 AM** | "Approve again, and it's on both calendars." |
| 8 | 2:10 | Switch to Slack `#help`. "say Priya had more questions"; type **who's the best person to ask about IMAP sync? new here** (Pinpoint has replied in the thread). React ✅ on the reply | "It also works where people already ask. Nobody tagged it: it answered on its own, with sources, who knows IMAP and how booked they are. The ✅ saves this as a known answer, so the next new hire gets it instantly." Point at "Saved as a known answer". |
| 9 | 2:40 | Back in the app, click **Bus factor** above the graph | "For managers, the same data shows risk. Messaging depends on Dana alone, and she's 78% booked. Routing questions to Marcus is how a second expert grows." |
| 10 | 3:00 | Close | "Pinpoint answers from evidence, routes around overload, and never acts without approval. It reads only public channels it's invited to, and its scores route questions; they never rate people." |

**Spare beats if there's time**
- **How are subscriptions and plan upgrades billed?** Same pipeline, different expert: Isabel Moreno (60 Billing PRs, about 34% booked) is Recommended.
- **whats pr 28080**: it pulls that exact PR, explains it, and recommends the author (Isabel) and a reviewer (Lena).

## What judges should see, beat by beat

| Criterion | Where it shows |
| --- | --- |
| Agentic logic (30%) | Beats 2 to 8: answers, then plans the next step (who, when), drafts, books, and acts in `#help` on its own; every action waits for approval |
| New hire relevance (20%) | Beat 1 framing; the DM opens "I'm Priya, new on Integrations"; the saved answer helps the *next* new hire |
| Responsible AI (20%) | Citations (3), visible evidence and availability (4), corrections (4), approval before sending or booking (5, 7), public channels only and scores that never rate people (10) |
| Future of work (15%) | Bus factor for managers (9); spreading questions grows second experts; Workday as the org data source (10) |
| UX (10%) | One question to a booked meeting in about a minute; plain language; works in the app and in Slack |

## If something breaks

- **The answer is slow ("Still digging through PRs and threads…"):** the question isn't cached. Keep talking; after 30s a code-written answer appears with the same experts and citations. Next time, rerun `warm_demo`.
- **The card says "Sent" but nothing arrives on the phone:** simulated and real sends look the same in the app, so the phone is the only check. `PINPOINT_MODE` isn't `live` or `SLACK_BOT_TOKEN` is missing. Keep going and say the send is simulated for the demo.
- **No reply in `#help` after 15s:** check the `help_bot` terminal. It only answers questions posted after it started, so start it before the demo and post a fresh question. If it's down, skip beat 8 and describe it.
- **"Couldn't get an answer: Pinpoint can't connect right now":** the backend is down; restart uvicorn. If it won't come back, switch to fixtures: set `NEXT_PUBLIC_USE_FIXTURES=1` in `frontend/.env.local`, restart `npm run dev`, and run beats 1 to 7 only. In fixture mode every question gets the email-sync answer, so skip the spare beats.
