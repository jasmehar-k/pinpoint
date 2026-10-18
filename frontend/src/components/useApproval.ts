"use client";

import { useState } from "react";

import { approveAction, rejectAction } from "@/lib/api";
import type { ApproveRequest, PendingAction } from "@/lib/types";

export type Approval =
  | { phase: "draft"; error?: string; stuck?: boolean }
  | { phase: "working"; dismissing: boolean }
  | { phase: "done"; action: PendingAction }
  | { phase: "dismissed" };

function initial(action: PendingAction): Approval {
  if (action.status === "executed") return { phase: "done", action };
  if (action.status === "rejected") return { phase: "dismissed" };
  if (action.status === "failed") return { phase: "draft", error: errorOf(action) };
  return { phase: "draft" };
}

function errorOf(action: PendingAction): string {
  const error = action.result?.error;
  return typeof error === "string" ? error : `status ${action.status}`;
}

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

// Shared by the DM and meeting cards. Nothing runs until approve(); the buttons lock while a
// request is out. A "failed" result unlocks the card with the backend's error so the user can
// change something and retry.
export function useApproval(action: PendingAction, onFailed?: (result: PendingAction) => void) {
  const [state, setState] = useState<Approval>(() => initial(action));
  const [lastFailure, setLastFailure] = useState<string | null>(action.status === "failed" ? (action.executed_at ?? null) : null);

  async function approve(body: ApproveRequest) {
    if (state.phase !== "draft" || state.stuck) return;
    setState({ phase: "working", dismissing: false });
    try {
      const result = await approveAction(action, body);
      if (result.status === "executed") return setState({ phase: "done", action: result });
      if (result.status === "rejected") return setState({ phase: "dismissed" });
      if (result.status === "failed") {
        // The backend only executes pending actions; a retry of a failed one returns the same row.
        if (lastFailure && result.executed_at === lastFailure) {
          return setState({ phase: "draft", stuck: true, error: "This one can't be retried. Ask in the chat for a new one." });
        }
        setLastFailure(result.executed_at ?? null);
        onFailed?.(result);
        return setState({ phase: "draft", error: errorOf(result) });
      }
      setState({ phase: "draft", error: `status ${result.status}` });
    } catch (e) {
      setState({ phase: "draft", error: message(e) });
    }
  }

  async function dismiss() {
    if (state.phase !== "draft") return;
    setState({ phase: "working", dismissing: true });
    try {
      const result = await rejectAction(action);
      // Already executed elsewhere (another tab, a double click): show what happened.
      setState(result.status === "executed" ? { phase: "done", action: result } : { phase: "dismissed" });
    } catch (e) {
      setState({ phase: "draft", error: message(e) });
    }
  }

  return { state, approve, dismiss };
}
