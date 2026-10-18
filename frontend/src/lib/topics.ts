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
