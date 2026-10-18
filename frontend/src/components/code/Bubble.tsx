"use client";

import { useEffect, useRef } from "react";

import type { PageContext, PathExpert, PathExperts } from "@/lib/pageContext";
import { firstName } from "@/lib/people";

import { Chat } from "../Chat";
import { GraphPanel } from "../GraphPanel";
import { useGraphFocus } from "../graphFocus";

export type BubbleState = "collapsed" | "open" | "expanded";

const BUSY_AT = 0.7; // same line as the expert cards' Busy badge
export const hasTime = (p: PathExpert) => p.booked_pct < BUSY_AT;

// Pinpoint on someone else's page. One Chat instance for all three states (it's hidden, not
// unmounted, while collapsed), so the conversation survives opening, expanding and collapsing.
export function Bubble({
  state,
  onState,
  fileName,
  experts,
  context,
  onClearSelection,
  focusSignal,
}: {
  state: BubbleState;
  onState: (s: BubbleState) => void;
  fileName: string;
  experts: PathExperts | null;
  context: PageContext;
  onClearSelection: () => void;
  focusSignal: number;
}) {
  const askRef = useRef<((q: string) => void) | null>(null);
  const { setTopic, setPerson } = useGraphFocus();
  const free = experts?.people.find(hasTime);
  const topicShort = experts?.topicName.replace(/\s*\(.*\)$/, "");

  function expand() {
    if (experts) setTopic(experts.topicId);
    setPerson(null);
    onState("expanded");
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (state === "expanded") onState("open");
      else if (state === "open") onState("collapsed");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state, onState]);

  const iconButton = "flex size-8 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900";
  const actions = (
    <div className="flex items-center gap-1">
      {state === "expanded" ? (
        <button onClick={() => onState("open")} className="h-8 rounded-md border border-zinc-200 px-2.5 text-xs font-medium hover:bg-zinc-50">
          Collapse
        </button>
      ) : (
        <button onClick={expand} aria-label="Expand to graph" title="Expand to graph" className={iconButton}>
          <svg aria-hidden viewBox="0 0 20 20" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.7">
            <path d="M12 3h5v5M8 17H3v-5M17 3l-6 6M3 17l6-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}
      <button onClick={() => onState("collapsed")} aria-label="Close Pinpoint" title="Close" className={iconButton}>
        <svg aria-hidden viewBox="0 0 20 20" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.7">
          <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  );

  // "Show in graph" expands; the other is a question. Tried against the real backend: it cites
  // PR #26180 and routes to Messaging (vaguer file questions drifted to other topics).
  const chips = ["How does this cron fit into inbound email sync?", ...(state === "open" ? ["Show in graph"] : [])];

  const composerTop = (
    <div className="flex flex-col gap-2">
      {context.lines && (
        <span className="flex w-fit items-center gap-1.5 rounded-md bg-blue-50 px-2 py-1 font-mono text-xs text-blue-800">
          Lines {context.lines.start}–{context.lines.end}
          <button onClick={onClearSelection} aria-label="Clear selected lines" className="text-blue-500 hover:text-blue-900">
            ×
          </button>
        </span>
      )}
      <div role="group" aria-label="Suggestions" className="flex flex-wrap gap-1.5">
        {chips.map((label) => (
          <button key={label} type="button" onClick={() => (label === "Show in graph" ? expand() : askRef.current?.(label))} className="rounded-full border border-zinc-200 px-2.5 py-1 text-xs text-zinc-700 hover:border-blue-400 hover:bg-blue-50">
            {label}
          </button>
        ))}
      </div>
    </div>
  );

  const intro = (
    <div className="flex flex-col gap-3 text-sm">
      <p className="text-zinc-500">
        Viewing <span className="font-mono text-xs text-zinc-700">{fileName}</span>
        {context.lines && ` · lines ${context.lines.start}–${context.lines.end}`}
      </p>
      {experts && experts.people.length > 0 && (
        <section aria-label="Who knows this file" className="rounded-xl border border-zinc-200 p-3">
          <h3 className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">Who knows this file · {topicShort}</h3>
          <ul className="mt-2 flex flex-col gap-2.5">
            {experts.people.map((p) => (
              <li key={p.person_id} className="flex items-start gap-2.5">
                <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-zinc-700 text-[11px] font-semibold text-white">
                  {p.name
                    .split(" ")
                    .map((w) => w[0])
                    .join("")}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-medium">{p.name}</span>
                    <span className={`rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${hasTime(p) ? "bg-teal-50 text-teal-700" : "bg-orange-50 text-orange-700"}`}>
                      {hasTime(p) ? "Has time" : "Busy"}
                    </span>
                  </span>
                  <span className="block truncate text-xs text-zinc-500" title={p.evidence_summary}>
                    {p.evidence_summary} · {Math.round(p.booked_pct * 100)}% booked
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="text-zinc-500">Ask about this file, or highlight lines in the code to ask about them.</p>
    </div>
  );

  const box =
    state === "collapsed"
      ? "hidden"
      : state === "open"
        ? "fixed inset-0 z-40 flex flex-col sm:inset-auto sm:right-6 sm:bottom-24 sm:h-[min(640px,calc(100dvh-8rem))] sm:w-[400px] [&>section]:flex-1 [&>section]:shadow-2xl"
        : "fixed inset-0 z-40 grid grid-cols-[minmax(0,1fr)] gap-4 bg-zinc-100 p-3 sm:inset-4 sm:rounded-2xl sm:p-4 sm:shadow-2xl lg:grid-cols-[minmax(0,1fr)_minmax(380px,440px)]";

  return (
    <>
      {state === "expanded" && <div aria-hidden className="fixed inset-0 z-30 bg-zinc-900/40" onClick={() => onState("open")} />}
      <div className={box} role={state === "collapsed" ? undefined : "dialog"} aria-label="Pinpoint">
        {state === "expanded" ? <GraphPanel /> : null}
        <Chat
          title={state === "expanded" && topicShort ? `Pinpoint · ${topicShort}` : "Pinpoint"}
          actions={actions}
          intro={intro}
          composerTop={composerTop}
          placeholder={context.lines ? `Ask about lines ${context.lines.start}–${context.lines.end}` : "Ask about this page"}
          pageContext={context}
          askRef={askRef}
          focusSignal={focusSignal}
        />
      </div>

      {state === "collapsed" && (
        <div className="fixed right-6 bottom-6 z-40 flex items-center gap-3">
          {experts && experts.people.length > 0 && (
            <button onClick={() => onState("open")} className="rounded-xl border border-zinc-200 bg-white px-3 py-2 text-left shadow-lg hover:border-blue-300">
              <span className="block text-sm font-semibold">
                {experts.people.length} {experts.people.length === 1 ? "person knows" : "people know"} this file
              </span>
              <span className="block text-xs text-zinc-500">{free ? `${firstName(free.person_id)} has time this week` : `Everyone on ${topicShort} is busy this week`}</span>
            </button>
          )}
          <button
            onClick={() => onState("open")}
            aria-label="Open Pinpoint"
            className="relative flex size-14 items-center justify-center rounded-full bg-blue-700 text-white shadow-xl hover:bg-blue-800"
          >
            <svg aria-hidden viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z" strokeLinejoin="round" />
              <circle cx="12" cy="10" r="2.3" />
            </svg>
            {experts && experts.people.length > 0 && (
              <span className="absolute -top-1 -right-1 flex size-5 items-center justify-center rounded-full bg-orange-500 text-[11px] font-semibold">
                {experts.people.length}
              </span>
            )}
          </button>
        </div>
      )}
    </>
  );
}
