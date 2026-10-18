import pytest

from topics import TOPICS, PATH_RULES, topic_for_path, topics_for_paths

S = "packages/twenty-server/src/"


@pytest.mark.parametrize("path,topic", [
    (S + "modules/messaging/message-import-manager/services/foo.ts", "messaging"),
    (S + "engine/core-modules/imap-smtp-caldav-connection/x.ts", "messaging"),
    (S + "modules/calendar/x.ts", "calendar"),
    (S + "engine/core-modules/file-storage/x.ts", "file-storage"),
    (S + "engine/core-modules/file/x.ts", "file-storage"),
    (S + "engine/core-modules/sso/x.ts", "auth"),
    (S + "engine/metadata-modules/field-metadata/x.ts", "metadata"),
    (S + "engine/core-modules/cron/x.ts", "message-queue"),
    ("packages/twenty-front/src/modules/ui/Button.tsx", "frontend"),
])
def test_known_paths(path, topic):
    assert topic_for_path(path) == topic


def test_prefix_matches_whole_segments():
    # "file" must not swallow "file-storage-v2" style siblings or "filesystem"
    assert topic_for_path(S + "engine/core-modules/filesystem/x.ts") is None
    assert topic_for_path(S + "modules/messaging-webhooks/x.ts") is None


def test_unmapped_paths():
    assert topic_for_path(S + "utils/x.ts") is None
    assert topic_for_path("packages/twenty-docs/x.md") is None


def test_topics_for_paths_dedupes():
    paths = [S + "modules/messaging/a.ts", S + "modules/messaging/b.ts", "packages/twenty-front/c.tsx"]
    assert topics_for_paths(paths) == {"messaging", "frontend"}


def test_rule_topics_exist():
    assert {t for t, _ in PATH_RULES} <= set(TOPICS)
