import json

import pytest

import config
from org import people_by_id
from schema import (ArtifactResponse, AvailabilityResponse, ChatResponse, Correction, ExpertsResponse,
                    GraphResponse, Health, PendingAction)

FIXTURES = {
    "health.json": Health,
    "experts.json": ExpertsResponse,
    "chat.json": ChatResponse,
    "chat_schedule.json": ChatResponse,
    "availability.json": AvailabilityResponse,
    "action_approve_message.json": PendingAction,
    "action_approve_meeting.json": PendingAction,
    "artifact.json": ArtifactResponse,
    "graph.json": GraphResponse,
    "correction.json": Correction,
}


@pytest.mark.parametrize("name,model", FIXTURES.items())
def test_fixture_matches_model(name, model):
    model.model_validate_json((config.FIXTURES_DIR / name).read_text())


def test_every_fixture_is_covered():
    on_disk = {p.name for p in config.FIXTURES_DIR.glob("*.json")}
    assert on_disk == set(FIXTURES)


def _person_ids(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("person_id", "to", "requested_by") and isinstance(v, str):
                yield v
            elif k == "attendees":
                yield from v
            else:
                yield from _person_ids(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _person_ids(v)


@pytest.mark.parametrize("name", FIXTURES)
def test_fixtures_only_name_real_personas(name):
    data = json.loads((config.FIXTURES_DIR / name).read_text())
    unknown = set(_person_ids(data)) - set(people_by_id())
    assert not unknown
