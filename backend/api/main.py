from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import config
import db
from agent import actions
from agent.chat import handle
from artifacts import get_artifact
from embeddings import embed_query
from graph.availability import get_availability
from graph.experts import apply_availability, find_experts
from graph.view import build_graph
from search import search_artifacts
from org import people_by_id
from topics import TOPICS
from schema import (ApproveRequest, ArtifactResponse, AvailabilityResponse, ChatRequest, ChatResponse, Correction,
                    CorrectionRequest, ExpertsResponse, GraphResponse, Health, PendingAction, RewriteRequest)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pay one-time costs at startup, not on the first question: the embedding model, the DB pool,
    # the people file, and a first vector search.
    embed_query("warm up")
    if config.DATABASE_URL:
        try:
            with db.connect() as conn:
                search_artifacts(conn, "warm up", k=1)
            people_by_id()
        except Exception as e:  # the API still starts; /health will show db: false
            print(f"startup warm-up skipped: {e}")
    yield


app = FastAPI(title="Pinpoint", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=Health)
def health() -> Health:
    if not db.ping():
        return Health(status="ok", mode=config.MODE, db=False)
    with db.connect() as conn:
        synced_at = conn.execute("select max(synced_at) from sync_log").fetchone()[0]
    return Health(status="ok", mode=config.MODE, db=True, synced_at=synced_at)


@app.get("/experts", response_model=ExpertsResponse)
def experts(q: str = Query(min_length=2), user: str | None = None) -> ExpertsResponse:
    with db.connect() as conn:
        experts = find_experts(conn, q, asker_id=user)
        if experts:
            avail = get_availability(conn, [e.person_id for e in experts], datetime.now(UTC))
            experts = apply_availability(experts, avail.people)
        return ExpertsResponse(query=q, experts=experts)


@app.get("/availability", response_model=AvailabilityResponse)
def availability(people: str = Query(description="comma-separated person ids")) -> AvailabilityResponse:
    ids = [p for p in people.split(",") if p]
    if not ids:
        raise HTTPException(422, "Pick at least one person.")
    with db.connect(vector=False) as conn:
        return get_availability(conn, ids, datetime.now(UTC))


@app.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def artifact(artifact_id: str) -> ArtifactResponse:
    with db.connect(vector=False) as conn:
        found = get_artifact(conn, artifact_id)
    if found is None:
        raise HTTPException(404, "We couldn't find that thread or PR.")
    return found


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if req.user not in people_by_id():
        raise HTTPException(422, "We don't recognize this account.")
    with db.connect() as conn:
        return handle(conn, req)


@app.post("/actions/{action_id}/approve", response_model=PendingAction)
def approve(action_id: str, body: ApproveRequest | None = None) -> PendingAction:
    payload = body.payload.model_dump(mode="json") if body and body.payload else None
    with db.connect(vector=False) as conn:
        try:
            return actions.approve(conn, action_id, payload)
        except actions.ActionError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:  # payload didn't match the action kind
            raise HTTPException(422, str(e))


@app.post("/actions/{action_id}/reject", response_model=PendingAction)
def reject(action_id: str) -> PendingAction:
    with db.connect(vector=False) as conn:
        try:
            return actions.reject(conn, action_id)
        except actions.ActionError as e:
            raise HTTPException(404, str(e))


@app.post("/actions/{action_id}/rewrite", response_model=PendingAction)
def rewrite(action_id: str, body: RewriteRequest | None = None) -> PendingAction:
    with db.connect() as conn:
        try:
            return actions.rewrite(conn, action_id, (body or RewriteRequest()).style)
        except actions.ActionError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(409, str(e))


@app.get("/graph", response_model=GraphResponse)
def graph() -> GraphResponse:
    with db.connect() as conn:
        return build_graph(conn, datetime.now(UTC))


@app.post("/corrections", response_model=Correction)
def correct(req: CorrectionRequest) -> Correction:
    """"Not the right person?": demotes the expert on this topic for everyone's future searches."""
    people = people_by_id()
    if req.expert_id not in people or req.reported_by not in people:
        raise HTTPException(422, "We don't recognize this person.")
    if req.kind == "redirect" and req.redirect_to not in people:
        raise HTTPException(422, "Pick who to ask instead.")
    if req.topic_id not in TOPICS:
        raise HTTPException(422, "We don't recognize this topic.")
    with db.connect() as conn:
        row = conn.execute(
            """
            insert into corrections (expert_id, topic_id, kind, redirect_to, reported_by, note)
            values (%s, %s, %s, %s, %s, %s)
            returning id, expert_id, topic_id, kind, redirect_to, created_at
            """,
            (req.expert_id, req.topic_id, req.kind, req.redirect_to if req.kind == "redirect" else None,
             req.reported_by, req.note),
        ).fetchone()
    return Correction(id=row[0], expert_id=row[1], topic_id=row[2], kind=row[3], redirect_to=row[4], created_at=row[5])
