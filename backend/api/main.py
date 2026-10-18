from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

import config
import db
from embeddings import embed_query
from graph.experts import find_experts
from schema import ExpertsResponse, Health


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
        return ExpertsResponse(query=q, experts=find_experts(conn, q, asker_id=user))
