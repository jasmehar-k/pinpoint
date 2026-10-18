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
from org import people_by_id
from schema import (ApproveRequest, ArtifactResponse, AvailabilityResponse, ChatRequest, ChatResponse,
                    ExpertsResponse, Health, PendingAction)


@asynccontextmanager
async def lifespan(app: FastAPI):
    embed_query("warm up")  # load the embedding model now, not on the first question
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
    return Health(status="ok", mode=config.MODE, db=db.ping())


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
        raise HTTPException(422, "people is empty")
    with db.connect(vector=False) as conn:
        return get_availability(conn, ids, datetime.now(UTC))


@app.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
def artifact(artifact_id: str) -> ArtifactResponse:
    with db.connect(vector=False) as conn:
        found = get_artifact(conn, artifact_id)
    if found is None:
        raise HTTPException(404, "no such artifact")
    return found


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if req.user not in people_by_id():
        raise HTTPException(422, f"unknown user {req.user!r}")
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
