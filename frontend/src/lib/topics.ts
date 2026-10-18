// Display names for topic ids. Mirrors TOPICS in backend/topics.py.
export const TOPIC_NAMES: Record<string, string> = {
  workflow: "Workflow",
  messaging: "Messaging (email sync)",
  calendar: "Calendar sync",
  billing: "Billing",
  auth: "Auth",
  metadata: "Metadata (custom objects)",
  "file-storage": "File storage",
  "message-queue": "Message queue / jobs",
  frontend: "Frontend",
  deploys: "Deploys",
  "on-call": "On-call",
};

export function topicName(id: string): string {
  return TOPIC_NAMES[id] ?? id;
}

// File path -> topic. A copy of PATH_RULES in backend/topics.py (the source of truth; keep
// them in step). Matches whole path segments; first match wins. Used by the /code page until
// GET /experts?path= exists.
const S = "packages/twenty-server/src/";
const CORE = S + "engine/core-modules/";
const F = "packages/twenty-front/src/modules/";
const PATH_RULES: [string, string[]][] = [
  ["messaging", [S + "modules/messaging", CORE + "messaging", S + "modules/connected-account", S + "modules/blocklist", S + "modules/match-participant", S + "modules/emailing", CORE + "imap-smtp-caldav-connection", F + "accounts", F + "settings/accounts"]],
  ["calendar", [S + "modules/calendar", CORE + "calendar"]],
  ["workflow", [S + "modules/workflow", CORE + "workflow", F + "workflow"]],
  ["billing", [CORE + "billing", F + "settings/billing"]],
  ["auth", [CORE + "auth", CORE + "sso", CORE + "two-factor-authentication", CORE + "jwt", F + "auth", F + "settings/security", F + "settings/two-factor-authentication"]],
  ["metadata", [S + "engine/metadata-modules", S + "engine/workspace-manager", S + "database/commands", "packages/twenty-server/test/integration/metadata", F + "object-metadata", F + "metadata-store", F + "settings/data-model"]],
  ["file-storage", [CORE + "file-storage", CORE + "file", F + "file-upload", F + "file"]],
  ["message-queue", [CORE + "message-queue", CORE + "cron"]],
  ["frontend", ["packages/twenty-front"]],
];

export function topicForPath(path: string): string | null {
  const parts = path.split("/");
  for (const [topic, prefixes] of PATH_RULES) {
    if (prefixes.some((p) => p.split("/").every((seg, i) => parts[i] === seg))) return topic;
  }
  return null;
}
