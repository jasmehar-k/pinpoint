"""Shared models: the normalized Event every connector emits, identity, and API responses.

API response models are the contract for /fixtures. tests/test_fixtures.py keeps them in sync.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["slack", "github", "seed"]
EventType = Literal["authored", "reviewed", "answered", "asked", "owns"]

EVENT_WEIGHTS: dict[str, float] = {
    "owns": 1.5,
    "authored": 1.0,
    "answered": 0.8,
    "reviewed": 0.7,
    "asked": 0.1,
}


class Artifact(BaseModel):
    """A searchable thing (PR, thread). Connectors emit these alongside events, so content
    by people outside people.json (bots, unmapped contributors) is still searchable."""

    id: str
    source: Source
    kind: Literal["pr", "thread", "file", "answer"]
    title: str | None = None
    text: str
    url: str
    timestamp: datetime
    paths: list[str] = Field(default_factory=list)
    # Set by connectors that know topics directly (e.g. LLM-tagged Slack threads).
    # Left empty, the loader derives topics from paths.
    topics: list[str] = Field(default_factory=list)


class Event(BaseModel):
    source: Source
    type: EventType
    person_id: str
    artifact_id: str
    text: str
    paths: list[str] = Field(default_factory=list)
    timestamp: datetime
    url: str
    title: str | None = None


class Person(BaseModel):
    id: str
    name: str
    team: str
    role: str
    manager: str | None
    github_login: str | None
    slack_handle: str
    # Set only for personas backed by a real Slack user. Null means sends are simulated.
    slack_user_id: str | None = None


class Org(BaseModel):
    teams: list[str]
    people: list[Person]


class Meeting(BaseModel):
    id: str
    title: str
    attendees: list[str]
    start: datetime
    end: datetime
    recurring: bool = False


# ---- API responses ----

class Health(BaseModel):
    status: Literal["ok"]
    mode: Literal["seeded", "live"]
    db: bool


class Citation(BaseModel):
    id: str
    title: str
    url: str
    source: Source


class Evidence(BaseModel):
    type: EventType
    title: str
    url: str
    timestamp: datetime


class Availability(BaseModel):
    person_id: str
    booked_pct: float = Field(ge=0, le=1)
    open_reviews: int = Field(ge=0)
    factor: float = Field(ge=0, le=1)


class Expert(BaseModel):
    person_id: str
    name: str
    team: str
    role: str
    topic: str
    expertise: float
    rank_score: float
    evidence_summary: str
    evidence: list[Evidence] = Field(max_length=3)
    availability: Availability | None = None
    badge: Literal["recommended", "busy"] | None = None
    same_team: bool = False


class ExpertsResponse(BaseModel):
    query: str
    experts: list[Expert]


class Slot(BaseModel):
    start: datetime
    end: datetime


class AvailabilityResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    people: list[Availability]
    mutual_free_slots: list[Slot]


class SendMessagePayload(BaseModel):
    to: str
    text: str


class ScheduleMeetingPayload(BaseModel):
    title: str
    attendees: list[str]
    slot: Slot


ActionStatus = Literal["pending", "executed", "rejected", "failed"]


class PendingAction(BaseModel):
    id: str
    kind: Literal["send_message", "schedule_meeting"]
    status: ActionStatus
    requested_by: str
    payload: SendMessagePayload | ScheduleMeetingPayload
    created_at: datetime
    executed_at: datetime | None = None
    # e.g. {"delivery": "slack"} or {"delivery": "simulated"}, or the meeting id
    result: dict | None = None


class ApproveRequest(BaseModel):
    """Body of POST /actions/{id}/approve. Pass payload to send the user's edits
    (edited DM text, a different slot); omit it to execute the draft as is."""

    payload: SendMessagePayload | ScheduleMeetingPayload | None = None


class ChatRequest(BaseModel):
    """Body of POST /chat."""

    message: str = Field(min_length=1)
    conversation_id: str | None = None  # omit on the first message; reuse the one in the response
    user: str  # person id of whoever is asking, e.g. "priya-shah"


class ThreadMessage(BaseModel):
    person_id: str | None  # null when the poster isn't in people.json
    name: str
    text: str


class ArtifactPerson(BaseModel):
    person_id: str
    name: str
    type: EventType  # how they're attached: authored, reviewed, asked, answered


class ArtifactResponse(BaseModel):
    """GET /artifacts/{id}: a PR or thread, for the artifact page and evidence clicks."""

    id: str
    source: Source
    kind: Literal["pr", "thread", "file", "answer"]
    title: str | None
    url: str
    timestamp: datetime
    topics: list[str]
    text: str
    messages: list[ThreadMessage] | None = None  # threads only, in order
    people: list[ArtifactPerson]


class ChatReply(BaseModel):
    text: str
    citations: list[Citation]


class ChatResponse(BaseModel):
    conversation_id: str
    reply: ChatReply
    experts: list[Expert] = Field(default_factory=list)
    pending_actions: list[PendingAction] = Field(default_factory=list)
    availability: AvailabilityResponse | None = None


class UserProfile(BaseModel):
    person_id: str
    started_on: date
    interests: list[str] = Field(default_factory=list)
