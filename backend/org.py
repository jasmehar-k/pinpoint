"""Loads and validates people.json, the hand-written identity map."""

from functools import cache

import config
from schema import Org, Person


def load_org(path=config.PEOPLE_PATH) -> Org:
    org = Org.model_validate_json(path.read_text())
    validate_org(org)
    return org


def validate_org(org: Org) -> None:
    ids = [p.id for p in org.people]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate person ids: {sorted(dupes)}")
    for field in ("github_login", "slack_handle", "slack_user_id"):
        values = [getattr(p, field) for p in org.people if getattr(p, field)]
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {field} in people.json")
    known = set(ids)
    for p in org.people:
        if p.team not in org.teams:
            raise ValueError(f"{p.id}: unknown team {p.team!r}")
        if p.manager and p.manager not in known:
            raise ValueError(f"{p.id}: unknown manager {p.manager!r}")


@cache
def people_by_github_login() -> dict[str, Person]:
    return {p.github_login.lower(): p for p in load_org().people if p.github_login}


@cache
def people_by_slack_user_id() -> dict[str, Person]:
    return {p.slack_user_id: p for p in load_org().people if p.slack_user_id}


@cache
def people_by_id() -> dict[str, Person]:
    return {p.id: p for p in load_org().people}
