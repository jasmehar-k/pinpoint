"""Fixed topic list and the file path -> topic map for GitHub artifacts.

Prefixes were checked against twentyhq/twenty. First match wins.
"""

from pathlib import PurePosixPath

TOPICS: dict[str, str] = {
    "workflow": "Workflow",
    "messaging": "Messaging (email sync)",
    "calendar": "Calendar sync",
    "billing": "Billing",
    "auth": "Auth",
    "metadata": "Metadata (custom objects)",
    "file-storage": "File storage",
    "message-queue": "Message queue / jobs",
    "frontend": "Frontend",
    "deploys": "Deploys",
    "on-call": "On-call",
}

_S = "packages/twenty-server/src/"
_CORE = _S + "engine/core-modules/"
# Frontend code for a feature counts toward that feature; the rest falls through to "frontend".
_F = "packages/twenty-front/src/modules/"

PATH_RULES: list[tuple[str, list[str]]] = [
    ("messaging", [
        _S + "modules/messaging",
        _CORE + "messaging",
        _S + "modules/connected-account",
        _S + "modules/blocklist",
        _S + "modules/match-participant",
        _S + "modules/emailing",
        _CORE + "imap-smtp-caldav-connection",
        _F + "accounts",
        _F + "settings/accounts",
    ]),
    ("calendar", [_S + "modules/calendar", _CORE + "calendar"]),
    ("workflow", [_S + "modules/workflow", _CORE + "workflow", _F + "workflow"]),
    ("billing", [_CORE + "billing", _F + "settings/billing"]),
    ("auth", [
        _CORE + "auth", _CORE + "sso", _CORE + "two-factor-authentication", _CORE + "jwt",
        _F + "auth", _F + "settings/security", _F + "settings/two-factor-authentication",
    ]),
    ("metadata", [
        _S + "engine/metadata-modules",
        _S + "engine/workspace-manager",
        _S + "database/commands",  # upgrade commands are mostly workspace schema migrations
        "packages/twenty-server/test/integration/metadata",
        _F + "object-metadata",
        _F + "metadata-store",
        _F + "settings/data-model",
    ]),
    ("file-storage", [_CORE + "file-storage", _CORE + "file", _F + "file-upload", _F + "file"]),
    ("message-queue", [_CORE + "message-queue", _CORE + "cron"]),
    ("frontend", ["packages/twenty-front"]),
]


def topic_for_path(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    for topic_id, prefixes in PATH_RULES:
        for prefix in prefixes:
            prefix_parts = PurePosixPath(prefix).parts
            if parts[: len(prefix_parts)] == prefix_parts:
                return topic_id
    return None


def topics_for_paths(paths: list[str]) -> set[str]:
    return {t for p in paths if (t := topic_for_path(p))}
