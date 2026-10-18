"use client";

import { useState } from "react";

import { timeAgo } from "@/lib/time";
import type { Availability, EventType, Expert } from "@/lib/types";

import { SourceLink } from "./CitedText";

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

export function ExpertList({ experts }: { experts: Expert[] }) {
  if (experts.length === 0) return null;
  return (
    <section aria-label="Who to ask" className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">Who to ask</h3>
      {experts.map((e) => (
        <ExpertCard key={e.person_id} expert={e} />
      ))}
    </section>
  );
}

export function ExpertCard({ expert }: { expert: Expert }) {
  const recommended = expert.badge === "recommended";
  const initials = expert.name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2);

  return (
    <article
      className={`rounded-xl border bg-white p-4 dark:bg-zinc-900 ${
        recommended ? "border-emerald-400 ring-1 ring-emerald-400/40 dark:border-emerald-600" : "border-zinc-200 dark:border-zinc-800"
      }`}
    >
      <header className="flex items-start gap-3">
        <span
          aria-hidden
          className={`flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white ${TEAM_COLOR[expert.team] ?? "bg-zinc-500"}`}
        >
          {initials}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <h4 className="font-semibold">{expert.name}</h4>
            <Badge badge={expert.badge} />
          </div>
          <p className="text-sm text-zinc-500">
            {expert.role} · {expert.team}
            {expert.same_team && <span className="text-zinc-700 dark:text-zinc-300"> · Your team</span>}
          </p>
        </div>
      </header>

      <p className="mt-3 text-sm">{expert.evidence_summary}</p>

      {expert.availability && <AvailabilityBar availability={expert.availability} />}

      {expert.evidence.length > 0 && (
        <ul className="mt-3 space-y-1.5 text-sm">
          {expert.evidence.map((ev) => (
            // Columns on wider screens; on phones the title gets its own line.
            <li key={ev.url + ev.type} className="flex min-w-0 flex-col sm:flex-row sm:items-baseline sm:gap-2">
              <span className="hidden w-[4.5rem] shrink-0 text-xs text-zinc-500 sm:block">{EVIDENCE_VERB[ev.type]}</span>
              <SourceLink
                url={ev.url}
                title={ev.title}
                className="line-clamp-2 min-w-0 text-zinc-700 hover:underline sm:flex-1 dark:text-zinc-300"
              >
                {ev.title}
              </SourceLink>
              <span className="shrink-0 text-xs text-zinc-500">
                <span className="sm:hidden">{EVIDENCE_VERB[ev.type]} · </span>
                {timeAgo(ev.timestamp)}
              </span>
            </li>
          ))}
        </ul>
      )}

      <NotTheRightPerson />
    </article>
  );
}

function Badge({ badge }: { badge: Expert["badge"] }) {
  if (badge === "recommended") {
    return (
      <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
        Recommended
      </span>
    );
  }
  if (badge === "busy") {
    return (
      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-200">
        Busy
      </span>
    );
  }
  return null;
}

function AvailabilityBar({ availability }: { availability: Availability }) {
  const pct = Math.round(availability.booked_pct * 100);
  const color = pct >= 75 ? "bg-red-500" : pct >= 50 ? "bg-amber-500" : "bg-emerald-500";
  const reviews = availability.open_reviews;
  return (
    <div className="mt-3">
      <div className="flex justify-between text-xs text-zinc-500">
        <span>{pct}% booked this week</span>
        <span>
          {reviews} open review{reviews === 1 ? "" : "s"}
        </span>
      </div>
      <div
        role="meter"
        aria-label="Booked this week"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800"
      >
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// Corrections aren't wired to the backend yet, so this only acknowledges.
function NotTheRightPerson() {
  const [sent, setSent] = useState(false);
  if (sent) {
    return <p className="mt-3 text-xs text-zinc-500">Thanks. We&apos;ll use this to improve who we suggest for this topic.</p>;
  }
  return (
    <button onClick={() => setSent(true)} className="mt-3 text-xs text-zinc-500 underline hover:text-zinc-800 dark:hover:text-zinc-200">
      Not the right person?
    </button>
  );
}
