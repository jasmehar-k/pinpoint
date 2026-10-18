// Mirrors backend/schema.py. API shape changes update schema.py, this file and
// /fixtures together in one commit. Datetimes arrive as ISO 8601 strings.
// Fields with a default in schema.py are optional here: fixtures may omit them.

export type Source = "slack" | "github" | "seed";
export type EventType = "authored" | "reviewed" | "answered" | "asked" | "owns";

export interface Health {
  status: "ok";
  mode: "seeded" | "live";
  db: boolean;
}

export interface Citation {
  id: string;
  title: string;
  url: string;
  source: Source;
}

export interface Evidence {
  type: EventType;
  title: string;
  url: string;
  timestamp: string;
}

export interface Availability {
  person_id: string;
  booked_pct: number; // 0 to 1
  open_reviews: number;
  factor: number; // 0 to 1
}

export interface Expert {
  person_id: string;
  name: string;
  team: string;
  role: string;
  topic: string;
  expertise: number;
  rank_score: number;
  evidence_summary: string;
  evidence: Evidence[]; // at most 3
  availability?: Availability | null;
  badge?: "recommended" | "busy" | null;
  same_team?: boolean;
}

export interface ExpertsResponse {
  query: string;
  experts: Expert[];
}

export interface Slot {
  start: string;
  end: string;
}

export interface AvailabilityResponse {
  window_start: string;
  window_end: string;
  people: Availability[];
  mutual_free_slots: Slot[];
}

export interface SendMessagePayload {
  to: string;
  text: string;
}

export interface ScheduleMeetingPayload {
  title: string;
  attendees: string[];
  slot: Slot;
}

export type ActionStatus = "pending" | "executed" | "rejected" | "failed";

interface PendingActionBase {
  id: string;
  status: ActionStatus;
  requested_by: string;
  created_at: string;
  executed_at?: string | null;
  // e.g. {"delivery": "slack"} or {"delivery": "simulated"}, or the meeting id
  result?: Record<string, unknown> | null;
}

// schema.py types payload as a plain union; `kind` tells them apart.
export type PendingAction =
  | (PendingActionBase & { kind: "send_message"; payload: SendMessagePayload })
  | (PendingActionBase & { kind: "schedule_meeting"; payload: ScheduleMeetingPayload });

export interface ChatReply {
  text: string;
  citations: Citation[];
}

export interface ChatResponse {
  conversation_id: string;
  reply: ChatReply;
  experts?: Expert[];
  pending_actions?: PendingAction[];
  availability?: AvailabilityResponse | null;
}
