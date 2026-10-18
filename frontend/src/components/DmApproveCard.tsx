"use client";

import { useState } from "react";

import { DEMO_USER } from "@/lib/demo";
import { firstName, nameFromId } from "@/lib/people";
import type { Citation, PendingAction, SendMessagePayload } from "@/lib/types";

import { ActionButtons, CardShell } from "./ActionCard";
import { shortLabel, SourceLink } from "./CitedText";
import { useApproval } from "./useApproval";

type DmAction = Extract<PendingAction, { kind: "send_message" }>;

// The DM never goes out until Approve is clicked. Approve sends the text as edited here.
// `context` is what the draft was written from: the sources of the answer that produced it.
export function DmApproveCard({ action, context = [] }: { action: DmAction; context?: Citation[] }) {
  const draft = action.payload.text;
  const to = action.payload.to;
  const [text, setText] = useState(draft);
  const { state, approve, dismiss } = useApproval(action);
  const edited = text.trim() !== draft.trim();
  const label = `Slack DM to ${nameFromId(to)}`;

  function onApprove() {
    if (!text.trim()) return;
    // Only send a payload when the draft was edited; no payload executes the draft as is.
    const payload: SendMessagePayload | undefined = edited ? { to, text: text.trim() } : undefined;
    approve({ payload });
  }

  return (
    <CardShell
      id={`action-${action.id}`}
      label={label}
      title={
        <>
          <ChatIcon />
          <span className="font-semibold">Slack DM</span>
          <span className="text-zinc-500">to {nameFromId(to)}</span>
        </>
      }
      aside={
        state.phase === "done" ? null : (
          <span className="rounded-md bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700">Needs approval</span>
        )
      }
      dismissed={state.phase === "dismissed" ? "Cancelled. Nothing was sent." : null}
    >
      {state.phase === "done" ? (
        <>
          <p className="rounded-lg border border-zinc-200 px-3 py-2.5 text-[15px] whitespace-pre-wrap">{text.trim()}</p>
          <SentNote to={to} delivery={String(state.action.result?.delivery ?? "")} />
        </>
      ) : (
        <>
          <label htmlFor={`dm-${action.id}`} className="text-xs font-medium text-zinc-600">
            Message
          </label>
          <textarea
            id={`dm-${action.id}`}
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={state.phase !== "draft"}
            aria-label="Message text"
            className="mt-1.5 block w-full resize-y rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-[15px] outline-none [field-sizing:content] focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:text-zinc-500"
          />
          {context.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-zinc-500">
              <span>Context attached:</span>
              {context.map((c) => (
                <SourceLink key={c.id} url={c.url} title={c.title} className="rounded-md bg-blue-50 px-2 py-0.5 font-mono text-blue-800 hover:bg-blue-100">
                  {shortLabel(c)}
                </SourceLink>
              ))}
            </div>
          )}
          <p className="mt-2 text-xs text-zinc-500">Sends as Pinpoint on behalf of {DEMO_USER.name}</p>
          {/* "Rewrite shorter" goes here once POST /actions/{id}/rewrite exists. */}
          <ActionButtons
            state={state}
            approveLabel="Approve and send"
            workingLabel="Sending…"
            disabled={!text.trim()}
            note={edited ? "Edited" : undefined}
            errorPrefix="Not sent"
            onApprove={onApprove}
            onDismiss={dismiss}
            dismissLabel="Cancel"
          />
        </>
      )}
    </CardShell>
  );
}

function SentNote({ to, delivery }: { to: string; delivery: string }) {
  const simulated = delivery === "simulated";
  return (
    <p role="status" className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
      {simulated
        ? `✓ Marked as sent. Simulated: ${firstName(to)} isn't a real Slack user in this demo.`
        : `✓ Sent to ${firstName(to)} on Slack`}
    </p>
  );
}

function ChatIcon() {
  return (
    <svg aria-hidden viewBox="0 0 20 20" className="size-4 text-zinc-500" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M4 4h12a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H8l-4 3V5a1 1 0 0 1 1-1Z" strokeLinejoin="round" />
    </svg>
  );
}
