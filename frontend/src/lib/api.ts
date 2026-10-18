// Fixture mode (NEXT_PUBLIC_USE_FIXTURES=1) serves /fixtures via the public/fixtures symlink.
// Flip it off once the matching backend route exists.

import type {
  ApproveRequest,
  ArtifactResponse,
  ChatRequest,
  ChatResponse,
  ExpertsResponse,
  Health,
  PendingAction,
} from "./types";

const USE_FIXTURES = process.env.NEXT_PUBLIC_USE_FIXTURES !== "0";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fixture<T>(name: string): Promise<T> {
  const res = await fetch(`/fixtures/${name}`);
  if (!res.ok) throw new Error(`fixture ${name}: ${res.status}`);
  return res.json();
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

export function getHealth(): Promise<Health> {
  return USE_FIXTURES ? fixture("health.json") : call("/health");
}

export function getExperts(q: string, user?: string): Promise<ExpertsResponse> {
  if (USE_FIXTURES) return fixture("experts.json");
  const params = new URLSearchParams({ q, ...(user ? { user } : {}) });
  return call(`/experts?${params}`);
}

export function sendChat(req: ChatRequest): Promise<ChatResponse> {
  if (USE_FIXTURES) {
    return fixture(req.conversation_id ? "chat_schedule.json" : "chat.json");
  }
  return call("/chat", { method: "POST", body: JSON.stringify(req) });
}

export function approveAction(action: PendingAction, body: ApproveRequest = {}): Promise<PendingAction> {
  if (USE_FIXTURES) {
    return fixture(action.kind === "send_message" ? "action_approve_message.json" : "action_approve_meeting.json");
  }
  return call(`/actions/${action.id}/approve`, { method: "POST", body: JSON.stringify(body) });
}

export function getArtifact(id: string): Promise<ArtifactResponse> {
  // Fixture mode has one example artifact; every id gets it
  return USE_FIXTURES ? fixture("artifact.json") : call(`/artifacts/${encodeURIComponent(id)}`);
}
