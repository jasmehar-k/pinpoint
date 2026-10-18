"use client";

import { useState } from "react";

import { DEMO_USER } from "@/lib/demo";
import { firstName, nameFromId } from "@/lib/people";
import type { PendingAction, SendMessagePayload } from "@/lib/types";

import { ActionButtons, CardShell } from "./ActionCard";
import { useApproval } from "./useApproval";

type DmAction = Extract<PendingAction, { kind: "send_message" }>;

// The DM never goes out until Approve is clicked. Approve sends the text as edited here.
export function DmApproveCard({ action }: { action: DmAction }) {
  const draft = action.payload.text;
  const to = action.payload.to;
  const [text, setText] = useState(draft);
  const { state, approve, dismiss } = useApproval(action);
  const edited = text.trim() !== draft.trim();

  function onApprove() {
    if (!text.trim()) return;
    // Only send a payload when the draft was edited; no payload executes the draft as is.
    const payload: SendMessagePayload | undefined = edited ? { to, text: text.trim() } : undefined;
    approve({ payload });
  }

  return (
    <CardShell
      label={`Message to ${nameFromId(to)}`}
      title={`Message to ${nameFromId(to)}`}
      aside={`Slack DM from Pinpoint, on behalf of ${DEMO_USER.name.split(" ")[0]}`}
      dismissed={state.phase === "dismissed" ? "Dismissed. Nothing was sent." : null}
    >
      {state.phase === "done" ? (
        <>
          <p className="mt-3 rounded-lg border border-zinc-200 bg-white px-3 py-2.5 text-[15px] whitespace-pre-wrap dark:border-zinc-800 dark:bg-zinc-900">
            {text.trim()}
          </p>
          <SentNote to={to} delivery={String(state.action.result?.delivery ?? "")} />
        </>
      ) : (
        <>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={state.phase !== "draft"}
            aria-label="Message text"
            className="mt-3 block w-full resize-y rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-[15px] outline-none [field-sizing:content] focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <ActionButtons
            state={state}
            approveLabel="Approve and send"
            workingLabel="Sending…"
            disabled={!text.trim()}
            note={edited ? "Edited" : undefined}
            errorPrefix="Not sent"
            onApprove={onApprove}
            onDismiss={dismiss}
          />
        </>
      )}
    </CardShell>
  );
}

function SentNote({ to, delivery }: { to: string; delivery: string }) {
  if (delivery === "simulated") {
    return (
      <p role="status" className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
        ✓ Marked as sent. Simulated: {firstName(to)} isn&apos;t a real Slack user in this demo.
      </p>
    );
  }
  return (
    <p role="status" className="mt-3 text-sm font-medium text-emerald-700 dark:text-emerald-400">
      ✓ Sent to {firstName(to)} on Slack
    </p>
  );
}
