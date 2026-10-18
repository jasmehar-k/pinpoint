# Slack setup

Gets the Pinpoint bot reading `#help` and able to DM people. About 15 minutes.

## 1. Workspace

Create a free workspace at slack.com/get-started (or use one you already admin). Invite your teammate by email.

## 2. Create the app from a manifest

Go to api.slack.com/apps, click **Create New App**, then **From a manifest**, pick the workspace, choose **YAML**, and paste:

```yaml
display_information:
  name: Pinpoint
  description: Finds who on the team knows what, and whether they have time.
features:
  bot_user:
    display_name: Pinpoint
    always_online: true
oauth_config:
  scopes:
    bot:
      - channels:history
      - channels:read
      - users:read
      - chat:write
      - im:write
settings:
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
```

No events, slash commands, or socket mode: Pinpoint polls, so it needs no public URL. Click **Next**, then **Create**.

## 3. Install and copy the token

In the app's sidebar open **Install App**, click **Install to Workspace**, and allow. Copy the **Bot User OAuth Token** (it starts with `xoxb-`) into the repo-root `.env`:

```
SLACK_BOT_TOKEN=xoxb-...
```

Never commit `.env` or paste the token anywhere else.

## 4. Channels

Create `#help` (and `#integrations` if you like). In each one, send:

```
/invite @Pinpoint
```

The bot only reads public channels it has been invited to.

## 5. Member IDs in people.json

In Slack, click a person's profile picture, open their profile, click the three dots, then **Copy member ID** (looks like `U07ABC123`).

In `people.json`, set `slack_user_id`:

- `marcus-lee`: your teammate's ID. They play Marcus, so the approved DM lands on their phone.
- `priya-shah`: your own ID. You play Priya.

Then reload people into the DB (from `backend/`):

```
uv run python -m scripts.load_people
```

## 6. Test questions

From your account (Priya), post 2 or 3 questions in `#help`, for example "How does inbound email sync work?". Answer each one **in the thread** from your teammate's account (Marcus).

## 7. Ingest

You need `DATABASE_URL` in `.env`, `scripts.init_db` and `scripts.load_people` already run, and `OPENROUTER_API_KEY` + `LLM_MODEL` for topic tagging (or add `--no-tag`). From `backend/`:

```
uv run python -m scripts.ingest_slack --channel help
```

Expected output, roughly:

```
reading 1 channels from https://your-workspace.slack.com/, last 90 days
  #help: fetched 3 threads
tagging 3 threads
stored 3 threads (3 with topics), events {'asked': 3, 'answered': 3}
```

Each run fetches fresh messages from Slack. Threads whose text hasn't changed keep their topics, so reruns only spend LLM calls on new or edited threads. Other flags: `--days 30`, `--channel help integrations`, `--no-tag`, `--cached` (reuse the last fetch, no Slack calls).

Then make the new threads searchable:

```
uv run python -m scripts.embed
```

Privacy: topic tagging sends thread text to the free model on OpenRouter. Only public channels the bot was invited to are read; keep anything sensitive out of them, or use `--no-tag`.

Check it worked in the Supabase SQL editor:

```sql
select type, count(*) from events where source = 'slack' group by type;
select id, title from artifacts where source = 'slack' order by timestamp desc limit 5;
```

## Troubleshooting

- **`not_in_channel`**: run `/invite @Pinpoint` in that channel.
- **`invalid_auth`** or **`not_authed`**: the token is wrong or empty. Use the **Bot** token (`xoxb-`), not a user token (`xoxp-`). Reinstalling the app issues a new token; copy it again.
- **`missing_scope`**: add the scope under **OAuth & Permissions**, click **Reinstall to Workspace**, and copy the new token.
- **Zero threads**: the bot isn't in the channel (the summary lists skipped channels), the channel is private (not read on purpose), the messages are older than `--days`, or you passed `--cached` and got an old copy.
- **Threads stored but no events**: the posters' `slack_user_id` isn't set in `people.json`, so they show up as "Someone". Fix step 5 and rerun.
