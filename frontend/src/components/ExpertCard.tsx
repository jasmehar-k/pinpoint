"use client";

import { useEffect, useRef, useState } from "react";

import { timeAgo } from "@/lib/time";
import { displayTitle } from "@/lib/titles";
import type { Availability, EventType, Expert } from "@/lib/types";

import { SourceLink } from "./CitedText";
import { useGraphFocus } from "./graphFocus";

const TEAM_COLOR: Record<string, string> = {
  Integrations: "bg-violet-600",
  Platform: "bg-teal-600",
  Product: "bg-orange-600",
  Core: "bg-slate-600",
};

const EVIDENCE_VERB: Record<EventType, string> = {
  authored: "Authored",
  reviewed: "Reviewed",
  answered: "Answered",
  asked: "Asked",
  owns: "Owns",
};

// Full cards for the first FULL_CARDS experts; the rest start as a one-line row.
const FULL_CARDS = 2;

type Actions = {
  onDraft: (expert: Expert) => void;
  onBook: (expert: Expert) => void;
  disabled?: boolean;
};

export function ExpertList({ experts, ...actions }: { experts: Expert[] } & Actions) {
  if (experts.length === 0) return null;
  return (
    <section aria-label="Who to ask" className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">Who to ask</h3>
      {experts.map((e, i) => (
        <ExpertCard key={e.person_id} expert={e} compact={i >= FULL_CARDS} {...actions} />
      ))}
    </section>
  );
}

function initialsOf(name: string): string {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2);
}

export function ExpertCard({ expert, compact = false, onDraft, onBook, disabled }: { expert: Expert; compact?: boolean } & Actions) {
  const [expanded, setExpanded] = useState(!compact);
  const recommended = expert.badge === "recommended";
  // Linked with the graph: hovering the card lights the person there; clicking the person in
  // the graph rings this card and scrolls the latest one into view.
  const { person, setPerson } = useGraphFocus();
  const ref = useRef<HTMLElement>(null);
  const highlighted = person?.id === expert.person_id;
  const fromGraph = highlighted && person.from === "graph";
  useEffect(() => {
    if (fromGraph) ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [fromGraph]);
  const link = {
    ref,
    "data-highlighted": highlighted || undefined,
    onMouseEnter: () => setPerson({ id: expert.person_id, from: "chat" }),
    onMouseLeave: () => person?.from === "chat" && setPerson(null),
  };
  const ring = fromGraph ? " shadow-[0_0_0_3px_rgba(37,99,235,0.35)]" : "";
  const avatar = (size: string) => (
    <span
      aria-hidden
      className={`flex ${size} shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white ${TEAM_COLOR[expert.team] ?? "bg-zinc-500"}`}
    >
      {initialsOf(expert.name)}
    </span>
  );

  if (!expanded) {
    const booked = expert.availability ? `${Math.round(expert.availability.booked_pct * 100)}% booked` : null;
    return (
      <article aria-label={expert.name} {...link} className={`rounded-xl border border-zinc-200 bg-white${ring}`}>
        <button onClick={() => setExpanded(true)} aria-expanded={false} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-zinc-50">
          {avatar("size-9")}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h4 className="font-semibold">{expert.name}</h4>
              <Badge badge={expert.badge} />
            </div>
            <p className="truncate text-sm text-zinc-500">
              {expert.evidence_summary}
              {booked && ` · ${booked}`}
            </p>
          </div>
        </button>
      </article>
    );
  }

  return (
    <article
      aria-label={expert.name}
      {...link}
      className={`rounded-xl border bg-white p-4 ${recommended ? "border-blue-600 ring-1 ring-blue-600" : "border-zinc-200"}${ring}`}
    >
      <header className="flex items-start gap-3">
        {avatar("size-10")}
        <div className="min-w-0 flex-1">
          <h4 className="font-semibold">{expert.name}</h4>
          <p className="text-sm text-zinc-500">
            {expert.role} · {expert.team}
            {expert.same_team && <span className="text-zinc-700"> · Your team</span>}
          </p>
        </div>
        <Badge badge={expert.badge} />
      </header>

      <p className="mt-3 text-sm">{expert.evidence_summary}</p>

      {expert.availability && <AvailabilityBar availability={expert.availability} />}

      {recommended && (
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={() => onDraft(expert)}
            disabled={disabled}
            className="h-10 rounded-lg bg-blue-700 px-4 text-sm font-medium text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
          >
            Draft a message
          </button>
          <button
            onClick={() => onBook(expert)}
            disabled={disabled}
            className="h-10 rounded-lg border border-zinc-300 bg-white px-4 text-sm font-medium hover:bg-zinc-50 disabled:cursor-not-allowed disabled:text-zinc-400"
          >
            Book 30 min
          </button>
        </div>
      )}

      <Footer expert={expert} />
    </article>
  );
}

// "Show evidence" toggle on the left, "Not the right person?" on the right; evidence opens below.
function Footer({ expert }: { expert: Expert }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const [corrected, setCorrected] = useState(false);
  const hasEvidence = expert.evidence.length > 0;
  return (
    <>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
        {hasEvidence ? (
          <button onClick={() => setShowEvidence((v) => !v)} aria-expanded={showEvidence} className="font-medium text-zinc-600 hover:text-zinc-900">
            {showEvidence ? "Hide evidence" : "Show evidence"}
          </button>
        ) : (
          <span />
        )}
        {/* Corrections aren't wired to the backend yet, so this only acknowledges. */}
        {corrected ? (
          <span className="text-zinc-500">Thanks. We&apos;ll use this to improve who we suggest for this topic.</span>
        ) : (
          <button onClick={() => setCorrected(true)} className="text-blue-700 underline hover:text-blue-900">
            Not the right person?
          </button>
        )}
      </div>
      {showEvidence && (
        <ul aria-label="Evidence" className="mt-2 space-y-1.5 border-t border-zinc-100 pt-2 text-sm">
          {expert.evidence.map((ev) => (
            // Columns on wider screens; on phones the title gets its own line.
            <li key={ev.url + ev.type} className="flex min-w-0 flex-col sm:flex-row sm:items-baseline sm:gap-2">
              <span className="hidden w-[4.5rem] shrink-0 text-xs text-zinc-500 sm:block">{EVIDENCE_VERB[ev.type]}</span>
              <SourceLink url={ev.url} title={ev.title} className="line-clamp-2 min-w-0 text-zinc-700 hover:underline sm:flex-1">
                {displayTitle(ev.title)}
              </SourceLink>
              <span className="shrink-0 text-xs text-zinc-500">
                <span className="sm:hidden">{EVIDENCE_VERB[ev.type]} · </span>
                {timeAgo(ev.timestamp)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Badge({ badge }: { badge: Expert["badge"] }) {
  if (badge === "recommended") {
    return <span className="shrink-0 rounded-md bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700">Recommended</span>;
  }
  if (badge === "busy") {
    return <span className="shrink-0 rounded-md bg-orange-50 px-2 py-0.5 text-xs font-semibold text-orange-700">Busy</span>;
  }
  return null;
}

function AvailabilityBar({ availability }: { availability: Availability }) {
  const pct = Math.round(availability.booked_pct * 100);
  const color = pct >= 70 ? "bg-orange-600" : pct >= 50 ? "bg-amber-500" : "bg-teal-600";
  const reviews = availability.open_reviews;
  return (
    <div className="mt-3 flex items-center gap-3">
      <div
        role="meter"
        aria-label="Booked this week"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-200"
      >
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="shrink-0 text-xs text-zinc-600">
        {pct}% booked · {reviews} open review{reviews === 1 ? "" : "s"}
      </span>
    </div>
  );
}
