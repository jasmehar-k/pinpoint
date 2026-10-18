"use client";

import { useState } from "react";

import { approveAction } from "@/lib/api";
import { DEMO_USER } from "@/lib/demo";
import { firstName, nameFromId } from "@/lib/people";
import type { PendingAction, SendMessagePayload } from "@/lib/types";

type DmAction = Extract<PendingAction, { kind: "send_message" }>;

type State =
  | { step: "draft"; error?: string }
  | { step: "sending" }
  | { step: "sent"; text: string; delivery: string };

// The DM never goes out until Approve is clicked. Approve sends the text as edited here.
export function DmApproveCard({ action }: { action: DmAction }) {
  const draft = action.payload.text;
  const to = action.payload.to;
  const [text, setText] = useState(draft);
  const [state, setState] = useState<State>(
    action.status === "executed"
      ? { step: "sent", text: draft, delivery: String(action.result?.delivery ?? "") }
      : { step: "draft" },
  );

  async function approve() {
    if (state.step !== "draft" || !text.trim()) return;
    setState({ step: "sending" }); // locks the button before the request goes out
    const sentText = text.trim();
    // Only send a payload when the draft was edited; no payload executes the draft as is.
    const payload: SendMessagePayload | undefined = sentText === draft.trim() ? undefined : { to, text: sentText };
    try {
      const result = await approveAction(action, { payload });
      if (result.status === "executed") {
        setState({ step: "sent", text: sentText, delivery: String(result.result?.delivery ?? "") });
      } else {
        const reason = typeof result.result?.error === "string" ? result.result.error : `status ${result.status}`;
        setState({ step: "draft", error: `Not sent: ${reason}` });
      }
    } catch (e) {
      // Approve is safe to retry on the backend, so unlock and let the user try again.
      setState({ step: "draft", error: `Not sent: ${e instanceof Error ? e.message : String(e)}` });
    }
  }

  const locked = state.step !== "draft";

  return (
    <article aria-label={`Message to ${nameFromId(to)}`} className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 dark:border-blue-900 dark:bg-blue-950/30">
      <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h4 className="font-semibold">Message to {nameFromId(to)}</h4>
        <span className="text-xs text-zinc-500">Slack DM from Pinpoint, on behalf of {DEMO_USER.name.split(" ")[0]}</span>
      </header>

      {state.step === "sent" ? (
        <p className="mt-3 rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-[15px] whitespace-pre-wrap dark:border-zinc-800 dark:bg-zinc-900">
          {state.text}
        </p>
      ) : (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={locked}
          aria-label="Message text"
          className="mt-3 block w-full resize-y rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-[15px] outline-none [field-sizing:content] focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
        />
      )}

      <footer className="mt-3 flex flex-wrap items-center gap-3">
        {state.step === "sent" ? (
          <SentNote to={to} delivery={state.delivery} />
        ) : (
          <>
            <button
              onClick={approve}
              disabled={locked || !text.trim()}
              className="h-10 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-zinc-300 dark:disabled:bg-zinc-700"
            >
              {state.step === "sending" ? "Sending…" : "Approve and send"}
            </button>
            {state.step === "draft" && text.trim() !== draft.trim() && <span className="text-xs text-zinc-500">Edited</span>}
            {state.step === "draft" && state.error && (
              <span role="alert" className="text-sm text-red-700 dark:text-red-300">
                {state.error}
              </span>
            )}
          </>
        )}
      </footer>
    </article>
  );
}

function SentNote({ to, delivery }: { to: string; delivery: string }) {
  if (delivery === "simulated") {
    return (
      <p role="status" className="text-sm text-zinc-600 dark:text-zinc-400">
        ✓ Marked as sent. Simulated: {firstName(to)} isn&apos;t a real Slack user in this demo.
      </p>
    );
  }
  return (
    <p role="status" className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
      ✓ Sent to {firstName(to)} on Slack
    </p>
  );
}
