import pytest

from org import load_org, people_by_github_login, validate_org
from schema import Org


def test_people_json_is_valid():
    org = load_org()
    assert 20 <= len(org.people) <= 30


def test_demo_personas_are_mapped():
    by_login = people_by_github_login()
    assert by_login["neo773"].id == "dana-okafor"
    assert by_login["charlesbochet"].id == "marcus-lee"
    assert by_login["felixmalfait"].id == "victor-hale"
    assert "coreteamtwenty" not in by_login


def test_priya_is_on_integrations_with_marcus_and_dana():
    org = {p.id: p for p in load_org().people}
    assert org["priya-shah"].team == org["marcus-lee"].team == org["dana-okafor"].team == "Integrations"


def _org(**overrides):
    person = {"id": "a", "name": "A", "team": "T", "role": "r", "manager": None,
              "github_login": None, "slack_handle": "a"}
    return Org(teams=["T"], people=[{**person, **overrides}])


def test_rejects_unknown_manager():
    with pytest.raises(ValueError, match="unknown manager"):
        validate_org(_org(manager="ghost"))


def test_rejects_duplicate_slack_user_id():
    person = {"name": "A", "team": "T", "role": "r", "manager": None, "github_login": None,
              "slack_user_id": "U1"}
    org = Org(teams=["T"], people=[{**person, "id": "a", "slack_handle": "a"},
                                   {**person, "id": "b", "slack_handle": "b"}])
    with pytest.raises(ValueError, match="duplicate slack_user_id"):
        validate_org(org)


def test_rejects_unknown_team():
    with pytest.raises(ValueError, match="unknown team"):
        validate_org(_org(team="Nope"))
