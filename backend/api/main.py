from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
import db
from schema import Health

app = FastAPI(title="Pinpoint")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="ok", mode=config.MODE, db=db.ping())
