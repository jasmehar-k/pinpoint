"""send_message and schedule_meeting never run directly: the agent creates a pending action, and
only POST /actions/{id}/approve executes it.

Approve claims the row with `where status = 'pending'`, so a double click runs it once.
Sends go to real Slack only in live mode for people with a slack_user_id; otherwise they're
simulated (the action still records what would have been sent)."""

import os
import uuid
from datetime import UTC, datetime

from psycopg.types.json import Jsonb

import config
from graph.availability import TZ, demo_week, free_slots, load_meetings
from org import people_by_id
from schema import PendingAction, ScheduleMeetingPayload, SendMessagePayload


class ActionError(Exception):
    pass


def _row_to_action(row) -> PendingAction:
    id_, kind, status, requested_by, payload, created_at, executed_at, result = row
    return PendingAction(id=id_, kind=kind, status=status, requested_by=requested_by, payload=payload,
                         created_at=created_at, executed_at=executed_at, result=result)


_COLUMNS = "id, kind, status, requested_by, payload, created_at, executed_at, result"


def create(conn, kind: str, payload: SendMessagePayload | ScheduleMeetingPayload, requested_by: str) -> PendingAction:
    row = conn.execute(
        f"insert into pending_actions (id, kind, requested_by, payload) values (%s, %s, %s, %s) returning {_COLUMNS}",
        (f"act-{uuid.uuid4().hex[:8]}", kind, requested_by, Jsonb(payload.model_dump(mode="json"))),
    ).fetchone()
    conn.commit()
    return _row_to_action(row)


def get(conn, action_id: str) -> PendingAction | None:
    row = conn.execute(f"select {_COLUMNS} from pending_actions where id = %s", (action_id,)).fetchone()
    return _row_to_action(row) if row else None


def _finish(conn, action_id: str, status: str, result: dict) -> PendingAction:
    row = conn.execute(
        f"update pending_actions set status = %s, result = %s where id = %s returning {_COLUMNS}",
        (status, Jsonb(result), action_id),
    ).fetchone()
    conn.commit()
    return _row_to_action(row)


def reject(conn, action_id: str) -> PendingAction:
    row = conn.execute(
        f"update pending_actions set status = 'rejected' where id = %s and status = 'pending' returning {_COLUMNS}",
        (action_id,),
    ).fetchone()
    conn.commit()
    if row is None:
        current = get(conn, action_id)
        if current is None:
            raise ActionError("not found")
        return current
    return _row_to_action(row)


def approve(conn, action_id: str, payload: dict | None = None, now: datetime | None = None) -> PendingAction:
    """Execute a pending action once. Returns the action in its final state."""
    now = now or datetime.now(UTC)
    current = get(conn, action_id)
    if current is None:
        raise ActionError("not found")
    if payload is not None:
        model = SendMessagePayload if current.kind == "send_message" else ScheduleMeetingPayload
        payload = model.model_validate(payload).model_dump(mode="json")
    # Claim it. Only one request gets the row back; a double click returns the current state.
    row = conn.execute(
        f"""
        update pending_actions set status = 'executed', executed_at = %s, payload = coalesce(%s, payload)
        where id = %s and status = 'pending' returning {_COLUMNS}
        """,
        (now, Jsonb(payload) if payload is not None else None, action_id),
    ).fetchone()
    conn.commit()
    if row is None:
        return get(conn, action_id)
    action = _row_to_action(row)
    try:
        if action.kind == "send_message":
            result = _send(action)
        else:
            result = _schedule(conn, action, now)
    except Exception as e:  # record the failure on the action instead of losing it
        return _finish(conn, action.id, "failed", {"error": str(e)})
    return _finish(conn, action.id, "executed", result)


def _send(action: PendingAction) -> dict:
    people = people_by_id()
    to, sender = people[action.payload.to], people.get(action.requested_by)
    live = config.MODE == "live" and to.slack_user_id and os.getenv("SLACK_BOT_TOKEN")
    if not live:
        return {"delivery": "simulated", "to": to.id}
    from connectors.slack import client  # only needed in live mode

    web = client()
    channel = web.conversations_open(users=to.slack_user_id)["channel"]["id"]
    by = f", on behalf of {sender.name}" if sender else ""
    res = web.chat_postMessage(channel=channel, text=f"*Pinpoint{by}:*\n{action.payload.text}")
    return {"delivery": "slack", "channel": channel, "ts": res["ts"]}


def _schedule(conn, action: PendingAction, now: datetime) -> dict:
    p = action.payload
    days = demo_week(p.slot.start.astimezone(TZ).date())
    meetings = load_meetings(conn, p.attendees, days)
    free = {s.start for s in free_slots(meetings, p.attendees, days, now)}
    if p.slot.start not in free:
        raise ActionError("that slot is no longer free for everyone")
    meeting_id = f"mtg-pinpoint-{uuid.uuid4().hex[:6]}"
    conn.execute(
        """
        insert into meetings (id, title, attendees, start_at, end_at, recurring, seeded)
        values (%s, %s, %s, %s, %s, false, false)
        """,
        (meeting_id, p.title, p.attendees, p.slot.start, p.slot.end),
    )
    conn.commit()
    return {"meeting_id": meeting_id}
