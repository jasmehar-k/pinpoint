// Every backend call goes through here. In fixture mode (the default) responses come
// from /fixtures, served via the public/fixtures symlink, so the UI never waits on the
// backend. Set NEXT_PUBLIC_USE_FIXTURES=0 in frontend/.env.local to hit the real API.

import type { ExpertsResponse, Health } from "./types";

// Read as literal process.env.NEXT_PUBLIC_* so Next inlines them at build time.
export const USE_FIXTURES = process.env.NEXT_PUBLIC_USE_FIXTURES !== "0";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    throw new ApiError(`Can't reach ${url}`, 0);
  }
  if (!res.ok) {
    // FastAPI errors look like {"detail": "..."} or {"detail": [{msg, ...}]}.
    let message = `${res.status} ${res.statusText}`;
    try {
      const { detail } = await res.json();
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail) && detail[0]?.msg) message = detail[0].msg;
    } catch {}
    throw new ApiError(message, res.status);
  }
  return res.json() as Promise<T>;
}

function fixture<T>(name: string): Promise<T> {
  return request<T>(`/fixtures/${name}.json`);
}

function api<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const url = new URL(path, API_URL);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined) url.searchParams.set(key, value);
  }
  return request<T>(url.toString());
}

export function getHealth(): Promise<Health> {
  return USE_FIXTURES ? fixture("health") : api("/health");
}

// `user` is the asker's person id; the backend uses it to prefer same-team experts.
export function getExperts(q: string, user?: string): Promise<ExpertsResponse> {
  return USE_FIXTURES ? fixture("experts") : api("/experts", { q, user });
}
