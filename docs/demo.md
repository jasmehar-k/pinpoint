# Demo video script

About 3 minutes. Every shot shows the agent **doing** something, and the human approving it. Check the submission's video length limit before the final cut.

**Who's on screen**
- **The app** is driven as Priya Shah (new hire, Integrations, day 3).
- **Marcus's Slack** is Harshita's account (`U0CA77SLTPE`), so the approved DM really arrives there. Record it on her screen or phone.
- **Priya's Slack** is Jasmehar's account (`U0CAXTS3BC0`), used for the `#help` shot.

It's a video, so shots can be recorded separately and cut together: the app flow, Marcus's Slack, and `#help`.

## Before recording

1. Root `.env` on the recording laptop has:
   - `DATABASE_URL` (Supabase session pooler string)
   - `OPENROUTER_API_KEY` and `LLM_MODEL`
   - `PINPOINT_MODE=live` and `SLACK_BOT_TOKEN`. Without both, the DM is only simulated and nothing reaches Marcus's Slack.
2. `frontend/.env.local` has `NEXT_PUBLIC_USE_FIXTURES=0`.
3. Reset and warm, from `backend/`:
   ```
   uv run --python 3.13 python -m scripts.reset_demo   # deletes Pinpoint's DMs, #help replies, actions, bookings, corrections; resets calendars
   uv run --python 3.13 python -m scripts.warm_demo    # caches every demo answer, including the #help one: ~1s each
   ```
   Run `warm_demo` twice: the second run should print about a second per question.
4. Start (or restart) all three, then open http://localhost:3000:
   ```
   cd backend && uv run --python 3.13 uvicorn api.main:app        # :8000
   cd backend && uv run --python 3.13 python -m scripts.help_bot --every 5   # #help bot, checks every 5s
   cd frontend && npm run dev                                      # :3000
   ```
5. **Screen:** browser full screen at 125% zoom so text reads on video, bookmarks bar hidden, Do Not Disturb on, other tabs closed.
6. **Slack:** sidebar tidy, `#help` open for the `#help` shot, Marcus's DMs open for the DM shot.
7. Paste the `#help` question from this file rather than typing it. It must match the cached text exactly; if macOS turns the apostrophe in "who's" curly, the answer takes 20 to 30 seconds instead of one.

**Between takes:** run `reset_demo`, then restart the API and `help_bot`. Otherwise the last take's DM, booking and `#help` reply show up in the next one.

## Shot list

| # | Time | On screen | Voiceover |
| --- | --- | --- | --- |
| 1 | 0:00 | The main page, nothing clicked | "This is Priya. She joined the Integrations team three days ago, and she's just picked up her first ticket: a customer says new emails take a few minutes to show up in their CRM. To fix it, she needs to understand how inbound email sync works. She doesn't know the code yet, or who owns it. Her manager is in meetings all day. So like most new hires, she'd either ping the most senior engineer whose name she's heard, who is swamped, or stay stuck." |
| 2 | 0:25 | Click **How does inbound email sync work?** | "Instead, she asks Pinpoint. It answers first, from the team's own work: PRs and Slack threads." |
| 3 | 0:40 | Click citation chip **2** (PR #26180 opens), come back | "Every sentence links to its source. If it can't cite it, it doesn't say it." |
| 4 | 0:55 | Scroll to the expert cards; the graph beside them; click **Show evidence** on Marcus; hover **Not the right person?** | "Then it finds who knows this, with receipts. Dana wrote most of it, 128 PRs, but she's 78% booked this week. Marcus reviewed 38 of her PRs and has time, so he's Recommended. The graph ranks by expertise alone: Marcus is third there, but first here, because he can actually help. And if it's ever wrong, **Not the right person?** corrects it for everyone, so it keeps getting better." |
| 5 | 1:30 | Change a word in the draft (it opens "I'm Priya, new on Integrations"), click **Approve and send** | "It drafts the message, with the context attached. **Nothing is sent until Priya approves.**" |
| 6 | 1:45 | **Cut to Marcus's Slack:** the DM from Pinpoint, on behalf of Priya, arrives | "And it lands in Marcus's Slack." |
| 7 | 1:52 | Back in the app, type **Can you book time with Marcus on Wednesday at 10:30am?** | "It checks both calendars and finds times they're both free." |
| 8 | 2:05 | Click **Book Wed 10:30 AM** | "One more approval, and it's on both calendars. From one question to the right person and a meeting, in about a minute." |
| 9 | 2:15 | **Cut to Priya's Slack, `#help`:** paste **who's the best person to ask about IMAP sync? new here**; Pinpoint replies in the thread; react ✅; "Saved as a known answer" appears | "Later, Priya has another question, and asks where people already do: `#help`. Nobody tagged Pinpoint. It answered on its own, with sources, who knows IMAP and how busy they are. One ✅ saves it as a known answer, so the next new hire gets it instantly." |
| 10 | 2:40 | Back in the app, click **Bus factor** above the graph | "For managers, the same data shows risk. Messaging depends on Dana alone, and she's 78% booked. Every question routed to Marcus is how a second expert grows." |
| 11 | 2:55 | The main page | "Pinpoint answers from evidence, routes around overload, and never acts without approval. It reads only public channels it's invited to, and its scores route questions; they never rate people. That's Pinpoint: helping every new hire find the right person, faster." |

**Optional shots, if there's room**
- **How are subscriptions and plan upgrades billed?** Same pipeline, different expert: Isabel Moreno (60 Billing PRs, about 34% booked) is Recommended.
- **whats pr 28080**: it pulls that exact PR, explains it, and recommends the author (Isabel) and a reviewer (Lena).

## What judges should see, shot by shot

| Criterion | Where it shows |
| --- | --- |
| Agentic logic (30%) | Shots 2 to 9: answers, then plans the next step (who, when), drafts, books, and acts in `#help` on its own; every action waits for approval |
| New hire relevance (20%) | Shot 1's story; the DM opens "I'm Priya, new on Integrations"; the saved answer helps the *next* new hire |
| Responsible AI (20%) | Citations (3), visible evidence and availability (4), corrections (4), approval before sending or booking (5, 8), public channels only and scores that never rate people (11) |
| Future of work (15%) | Bus factor for managers (10); spreading questions grows second experts |
| UX (10%) | One question to a booked meeting in about a minute; plain language; works in the app and in Slack |

## If a take goes wrong

- **An answer is slow ("Still digging through PRs and threads…"):** that question isn't cached. Stop, rerun `warm_demo`, reset, and retake.
- **The card says "Sent" but nothing arrives in Marcus's Slack:** simulated and real sends look the same in the app. `PINPOINT_MODE` isn't `live` or `SLACK_BOT_TOKEN` is missing; fix it, restart the API, reset and retake.
- **No reply in `#help` after 15s:** check the `help_bot` terminal. It only answers questions posted after it started, so restart it, then post the question again.
- **"Pinpoint can't connect right now":** the API is down. Restart it and retake.
