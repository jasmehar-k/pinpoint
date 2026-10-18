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
  RewriteRequest,
} from "./types";

export const USE_FIXTURES = process.env.NEXT_PUBLIC_USE_FIXTURES !== "0";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// status 0 = the request never got a response (backend down, network, CORS).
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    console.error(`request failed: ${url}`);
    throw new ApiError("Pinpoint can't connect right now. Try again in a moment.", 0);
  }
  if (!res.ok) {
    // The backend writes its 4xx `detail` strings for users ("That time was just taken. ...").
    // Anything else (5xx, validation lists) gets a plain message; the technical detail goes to the console.
    let message = "Something went wrong. Try again in a moment.";
    let detail: unknown;
    try {
      ({ detail } = await res.json());
    } catch {}
    if (res.status < 500 && typeof detail === "string") message = detail;
    console.error(`${url.replace(API_URL, "")} returned ${res.status}`, detail);
    throw new ApiError(message, res.status);
  }
  return res.json();
}

function fixture<T>(name: string): Promise<T> {
  return request(`/fixtures/${name}`);
}

function call<T>(path: string, init?: RequestInit): Promise<T> {
  return request(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
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

// POST /actions/{id}/rewrite: the backend rewrites the pending DM's stored text and returns
// the updated action. Fixture mode keeps the first two sentences.
export function rewriteAction(action: PendingAction, style: RewriteRequest["style"] = "shorter"): Promise<PendingAction> {
  if (USE_FIXTURES) {
    if (action.kind !== "send_message") return Promise.resolve(action);
    const shorter = action.payload.text.match(/[^.!?]+[.!?]+/g)?.slice(0, 2).join("").trim() ?? action.payload.text;
    return Promise.resolve({ ...action, payload: { ...action.payload, text: shorter } });
  }
  return call(`/actions/${action.id}/rewrite`, { method: "POST", body: JSON.stringify({ style }) });
}

// POST /actions/{id}/reject, no body. Takes the action like approveAction so fixture mode
// can answer without a fixture file.
export function rejectAction(action: PendingAction): Promise<PendingAction> {
  if (USE_FIXTURES) return Promise.resolve({ ...action, status: "rejected" });
  return call(`/actions/${action.id}/reject`, { method: "POST" });
}

export function getArtifact(id: string): Promise<ArtifactResponse> {
  // Fixture mode has one example artifact; every id gets it
  return USE_FIXTURES ? fixture("artifact.json") : call(`/artifacts/${encodeURIComponent(id)}`);
}
