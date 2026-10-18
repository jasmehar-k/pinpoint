from schema import Person
from connectors.github import clean_body, normalize_pr


def _person(id_, login):
    return Person(id=id_, name=id_, team="Integrations", role="r", manager=None,
                  github_login=login, slack_handle=id_)


PEOPLE = {"neo773": _person("dana-okafor", "neo773"), "charlesbochet": _person("marcus-lee", "charlesBochet")}


def _pr(**overrides):
    pr = {
        "number": 26180,
        "title": "Sync message channels from webhooks",
        "body": "Removes the cron hand-off.",
        "url": "https://github.com/twentyhq/twenty/pull/26180",
        "mergedAt": "2026-08-04T14:12:00Z",
        "author": {"login": "neo773"},
        "reviews": {"nodes": [
            {"author": {"login": "charlesBochet"}, "submittedAt": "2026-08-04T12:00:00Z"},
            {"author": {"login": "charlesBochet"}, "submittedAt": "2026-08-03T09:00:00Z"},
            {"author": {"login": "neo773"}, "submittedAt": "2026-08-04T13:00:00Z"},
            {"author": {"login": "CoreTeamTwenty"}, "submittedAt": "2026-08-04T13:00:00Z"},
            {"author": None, "submittedAt": "2026-08-04T13:00:00Z"},
        ]},
        "files": {"nodes": [{"path": "packages/twenty-server/src/modules/messaging/a.ts"}]},
    }
    return {**pr, **overrides}


def test_authored_and_reviewed_events():
    artifact, events = normalize_pr(_pr(), PEOPLE)
    assert artifact.id == "github:pr:26180"
    assert artifact.title == "Sync message channels from webhooks (#26180)"
    assert artifact.text.startswith("Sync message channels from webhooks\n\nRemoves")
    assert sorted((e.type, e.person_id) for e in events) == [
        ("authored", "dana-okafor"), ("reviewed", "marcus-lee"),
    ]


def test_review_uses_first_review_time_and_skips_self_review():
    _, events = normalize_pr(_pr(), PEOPLE)
    review = next(e for e in events if e.type == "reviewed")
    assert review.timestamp.isoformat() == "2026-08-03T09:00:00+00:00"


def test_unmapped_author_keeps_artifact_without_events():
    artifact, events = normalize_pr(_pr(author={"login": "dependabot"}, reviews={"nodes": []}), PEOPLE)
    assert artifact is not None and events == []


def test_deleted_author_account():
    artifact, events = normalize_pr(_pr(author=None), PEOPLE)
    assert artifact is not None
    # No author to exclude, so every mapped reviewer counts
    assert sorted((e.type, e.person_id) for e in events) == [
        ("reviewed", "dana-okafor"), ("reviewed", "marcus-lee"),
    ]


def test_skips_prs_outside_ingested_packages():
    artifact, events = normalize_pr(_pr(files={"nodes": [{"path": "packages/twenty-docs/x.md"}]}), PEOPLE)
    assert artifact is None and events == []


def test_null_body():
    artifact, _ = normalize_pr(_pr(body=None), PEOPLE)
    assert artifact.text == "Sync message channels from webhooks"


def test_clean_body_strips_template_noise():
    body = (
        "## Summary\n<!-- describe your change -->\nFixes sync.\n\n\n\n"
        '<img width="400" src="https://x/y.png" />\n![screenshot](https://x/z.png)\n'
        "<details><summary>Logs</summary>trace</details>"
    )
    assert clean_body(body) == "## Summary\n\nFixes sync.\n\nLogstrace"


def test_clean_body_strips_review_bot_buttons_but_keeps_link_text():
    body = (
        "Fixes the cron.\n\n"
        '<a href="https://cubic.dev/pr/1" target="_blank"><source media="(prefers-color-scheme: dark)" '
        'srcset="https://x/dark.svg"><source srcset="https://x/light.svg"></a>\n\n'
        'See <a href="https://docs/x">the docs</a>.'
    )
    assert clean_body(body) == "Fixes the cron.\n\nSee the docs."
