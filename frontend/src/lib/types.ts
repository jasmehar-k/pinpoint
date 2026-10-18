// Mirrors backend/schema.py. Keep the two in sync.

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
  booked_pct: number;
  open_reviews: number;
  factor: number;
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
  evidence: Evidence[];
  availability: Availability | null;
  badge: "recommended" | "busy" | null;
  same_team: boolean;
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

interface PendingActionBase {
  id: string;
  status: "pending" | "executed" | "rejected" | "failed";
  requested_by: string;
  created_at: string;
  executed_at?: string | null;
  result?: Record<string, unknown> | null;
}

export type PendingAction =
  | (PendingActionBase & { kind: "send_message"; payload: SendMessagePayload })
  | (PendingActionBase & { kind: "schedule_meeting"; payload: ScheduleMeetingPayload });

export interface ChatResponse {
  conversation_id: string;
  reply: { text: string; citations: Citation[] };
  experts: Expert[];
  pending_actions: PendingAction[];
  availability?: AvailabilityResponse | null;
}

// ---- request bodies ----

export interface ChatRequest {
  message: string;
  conversation_id?: string; // omit on the first message; reuse the one from the response
  user: string; // person id of whoever is asking, e.g. "priya-shah"
}

export interface ApproveRequest {
  // the user's edits (DM text, chosen slot); omit to execute the draft unchanged
  payload?: SendMessagePayload | ScheduleMeetingPayload;
}

// ---- GET /artifacts/{id} ----

export interface ThreadMessage {
  person_id: string | null;
  name: string;
  text: string;
}

export interface ArtifactPerson {
  person_id: string;
  name: string;
  type: EventType;
}

export interface ArtifactResponse {
  id: string;
  source: Source;
  kind: "pr" | "thread" | "file" | "answer";
  title: string | null;
  url: string;
  timestamp: string;
  topics: string[];
  text: string;
  messages?: ThreadMessage[] | null; // threads only, in order
  people: ArtifactPerson[];
}
