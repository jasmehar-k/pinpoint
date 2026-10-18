-- Pinpoint schema. Idempotent: safe to rerun via scripts/init_db.

create extension if not exists vector;

create table if not exists people (
    id            text primary key,
    name          text not null,
    team          text not null,
    role          text not null,
    manager_id    text references people(id),
    github_login  text unique,
    slack_handle  text not null unique,
    slack_user_id text,                      -- null = sends are simulated
    open_reviews  int not null default 0     -- seeded by gen_meetings
);

create table if not exists topics (
    id   text primary key,
    name text not null
);

-- One row per PR, Slack thread, file or promoted answer.
-- 384 = BAAI/bge-small-en-v1.5 via fastembed. Must match embeddings.py.
create table if not exists artifacts (
    id        text primary key,
    source    text not null check (source in ('slack', 'github', 'seed')),
    kind      text not null check (kind in ('pr', 'thread', 'file', 'answer')),
    title     text,
    text      text not null,
    url       text not null,
    timestamp timestamptz not null,
    embedding vector(384)
);

create index if not exists artifacts_embedding_idx
    on artifacts using hnsw (embedding vector_cosine_ops);

-- From file paths (GitHub) or LLM tags (Slack).
create table if not exists artifact_topics (
    artifact_id text references artifacts(id) on delete cascade,
    topic_id    text references topics(id),
    primary key (artifact_id, topic_id)
);

create table if not exists events (
    id          bigserial primary key,
    source      text not null check (source in ('slack', 'github', 'seed')),
    type        text not null check (type in ('authored', 'reviewed', 'answered', 'asked', 'owns')),
    person_id   text not null references people(id),
    artifact_id text not null references artifacts(id) on delete cascade,
    paths       text[] not null default '{}',
    timestamp   timestamptz not null,
    url         text not null,
    unique (type, person_id, artifact_id)
);

create index if not exists events_person_idx on events (person_id);
create index if not exists events_artifact_idx on events (artifact_id);

-- Precomputed by scripts/score. evidence = top 3 [{type, title, url, timestamp}].
create table if not exists expertise (
    person_id   text references people(id),
    topic_id    text references topics(id),
    score       double precision not null,
    counts      jsonb not null default '{}',   -- {"authored": 42, "answered": 11, ...}
    evidence    jsonb not null default '[]',
    last_active timestamptz,
    primary key (person_id, topic_id)
);

create table if not exists meetings (
    id        text primary key,
    title     text not null,
    attendees text[] not null,
    start_at  timestamptz not null,
    end_at    timestamptz not null,
    recurring boolean not null default false,
    seeded    boolean not null default true    -- false = booked through Pinpoint; reset_demo deletes these
);

create index if not exists meetings_attendees_idx on meetings using gin (attendees);

create table if not exists pending_actions (
    id           text primary key,
    kind         text not null check (kind in ('send_message', 'schedule_meeting')),
    status       text not null default 'pending' check (status in ('pending', 'executed', 'rejected', 'failed')),
    requested_by text not null references people(id),
    payload      jsonb not null,
    created_at   timestamptz not null default now(),
    executed_at  timestamptz,
    result       jsonb
);

create table if not exists corrections (
    id           bigserial primary key,
    expert_id    text not null references people(id),
    topic_id     text references topics(id),
    kind         text not null check (kind in ('not_owner', 'redirect')),
    redirect_to  text references people(id),
    reported_by  text not null references people(id),
    note         text,
    created_at   timestamptz not null default now()
);

create table if not exists user_profiles (
    person_id  text primary key references people(id),
    started_on date not null,
    interests  text[] not null default '{}'
);

-- #help fast path: one row per question the bot answered, so restarts never reply twice
-- and reset_demo can delete the replies from Slack.
create table if not exists slack_replies (
    channel_id  text not null,
    message_ts  text not null,
    reply_ts    text,
    created_at  timestamptz not null default now(),
    primary key (channel_id, message_ts)
);
alter table slack_replies add column if not exists topic text;
alter table slack_replies add column if not exists promoted_at timestamptz;  -- someone reacted ✅
alter table slack_replies add column if not exists confirm_ts text;          -- our "saved" note
