"use client";

import { useState } from "react";

import { firstName, nameFromId } from "@/lib/people";
import { dayKey, formatDay, formatSlot, formatTime, minutesOfDay, weekdaysBetween } from "@/lib/time";
import type { AvailabilityResponse, Busy, PendingAction, ScheduleMeetingPayload, Slot } from "@/lib/types";

import { ActionButtons, CardShell } from "./ActionCard";
import { useApproval } from "./useApproval";

type MeetingAction = Extract<PendingAction, { kind: "schedule_meeting" }>;

const startOf = (s: Slot) => new Date(s.start).getTime();
const sameSlot = (a: Slot, b: Slot) => startOf(a) === startOf(b);
const weekday = (iso: string) => formatDay(iso).split(",")[0]; // "Wed"

// Nothing is booked until Approve. Approve books the slot picked in the chips or "Other times".
export function MeetingApproveCard({ action, availability }: { action: MeetingAction; availability?: AvailabilityResponse | null }) {
  const { title, attendees, slot: suggested } = action.payload;
  const [selected, setSelected] = useState<Slot>(suggested);
  const [taken, setTaken] = useState<number[]>([]); // slot starts the backend said were no longer free
  const [showAll, setShowAll] = useState(false);

  // Without availability, the suggested slot is the only option.
  const slots = availability?.mutual_free_slots.length ? availability.mutual_free_slots : [suggested];
  const days = availability ? weekdaysBetween(availability.window_start, availability.window_end) : [suggested.start];
  const picks = suggestions(slots, suggested);

  const { state, approve, dismiss } = useApproval(action, (failed) => {
    if (failed.kind !== "schedule_meeting") return;
    // Mark the slot that failed and move the pick to the next free one, so a retry is one click.
    const bad = startOf(failed.payload.slot);
    const nowTaken = [...taken, bad];
    setTaken(nowTaken);
    const next = slots.find((s) => startOf(s) > bad && !nowTaken.includes(startOf(s))) ?? slots.find((s) => !nowTaken.includes(startOf(s)));
    if (next) setSelected(next);
  });

  const changed = !sameSlot(selected, suggested);
  const selectedTaken = taken.includes(startOf(selected));
  const names = attendees.map(firstName);
  const draft = state.phase === "draft";
  const other = attendees.filter((a) => a !== attendees[0]);

  function onApprove() {
    // Only send a payload when a different slot was picked; no payload books the suggestion.
    const payload: ScheduleMeetingPayload | undefined = changed ? { title, attendees, slot: selected } : undefined;
    approve({ payload });
  }

  return (
    <CardShell
      id={`action-${action.id}`}
      label={`Meeting: ${title}`}
      title={
        <>
          <CalendarIcon />
          <span className="font-semibold">Meeting</span>
          {other.length > 0 && <span className="text-zinc-500">with {other.map(nameFromId).join(", ")}</span>}
        </>
      }
      aside={<span className="text-xs text-zinc-500">30 min · times in Pacific</span>}
      dismissed={state.phase === "dismissed" ? "Cancelled. No meeting was booked." : null}
    >
      {state.phase === "done" ? (
        <p role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          ✓ Booked {formatDay(selected.start)}, {formatSlot(selected)}. Added to {names.map((n) => `${n}'s`).join(" and ")} calendars.
        </p>
      ) : (
        <>
          <p className="text-xs font-medium text-zinc-600">Suggested slots · 30 min</p>
          <div role="group" aria-label="Suggested slots" className="mt-2 grid grid-cols-3 gap-2">
            {picks.map((s) => {
              const isTaken = taken.includes(startOf(s));
              const isSelected = !isTaken && sameSlot(s, selected);
              return (
                <button
                  key={s.start}
                  onClick={() => setSelected(s)}
                  disabled={!draft || isTaken}
                  aria-pressed={isSelected}
                  aria-label={`${formatDay(s.start)}, ${formatSlot(s)}${isTaken ? " (taken)" : ""}`}
                  title={isTaken ? "No longer free" : undefined}
                  className={`rounded-lg border px-2 py-2 text-center text-sm disabled:cursor-not-allowed ${
                    isTaken
                      ? "border-zinc-200 text-zinc-400 line-through"
                      : isSelected
                        ? "border-blue-600 bg-blue-50 text-blue-800 ring-1 ring-blue-600"
                        : "border-zinc-300 text-zinc-800 hover:border-blue-400 hover:bg-blue-50 disabled:hover:bg-transparent"
                  }`}
                >
                  <span className="block font-semibold">{weekday(s.start)}</span>
                  <span className="block text-xs">{formatTime(s.start)}</span>
                </button>
              );
            })}
          </div>

          {availability && (
            <WeekGrid days={days} busy={availability.busy ?? []} attendees={attendees} picks={picks} selected={selectedTaken ? null : selected} />
          )}

          {showAll && (
            <FreeTimes days={days} slots={slots} taken={taken} selected={selected} onSelect={setSelected} disabled={!draft} />
          )}

          <ActionButtons
            state={state}
            approveLabel={`Book ${weekday(selected.start)} ${formatTime(selected.start)}`}
            workingLabel="Booking…"
            disabled={selectedTaken}
            note={changed ? "Changed from the suggested time" : undefined}
            errorPrefix="Not booked"
            onApprove={onApprove}
            onDismiss={dismiss}
            dismissLabel="Cancel"
            extra={
              slots.length > picks.length && (
                <button
                  onClick={() => setShowAll(!showAll)}
                  aria-expanded={showAll}
                  disabled={!draft}
                  className="h-10 rounded-lg px-3 text-sm font-medium text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:text-zinc-400"
                >
                  {showAll ? "Fewer times" : "Other times"}
                </button>
              )
            }
          />
        </>
      )}
      <p className="mt-3 text-xs text-zinc-500">
        Title: “{title}” · writes to the Acme calendar for {names.join(" and ")}.
      </p>
    </CardShell>
  );
}

// Three chips: the suggested slot plus the closest-in-time free slot on the nearest day before
// and after it (two after when it's the first day), in day order.
function suggestions(slots: Slot[], suggested: Slot): Slot[] {
  const target = minutesOfDay(suggested.start);
  const day = dayKey(suggested.start);
  const byDay = new Map<string, Slot[]>();
  for (const s of slots) byDay.set(dayKey(s.start), [...(byDay.get(dayKey(s.start)) ?? []), s]);
  const closest = (d: string) => byDay.get(d)!.reduce((a, b) => (Math.abs(minutesOfDay(b.start) - target) < Math.abs(minutesOfDay(a.start) - target) ? b : a));
  const before = [...byDay.keys()].filter((d) => d < day).sort().reverse();
  const after = [...byDay.keys()].filter((d) => d > day).sort();
  const order = [before[0], after[0], after[1], before[1], after[2], before[2]].filter(Boolean);
  const picks = [suggested, ...order.slice(0, 2).map(closest)];
  return picks.sort((a, b) => startOf(a) - startOf(b));
}

const DAY_START = 9 * 60;
const DAY_END = 17 * 60;
const AXIS = [9, 11, 13, 15, 17];
const COLORS = ["bg-zinc-400", "bg-violet-500", "bg-sky-500"]; // by attendee: requester first
const pos = (startIso: string, endIso: string) => {
  const clamp = (m: number) => Math.min(Math.max(m, DAY_START), DAY_END);
  const top = clamp(minutesOfDay(startIso)) - DAY_START;
  const height = clamp(minutesOfDay(endIso)) - DAY_START - top;
  return { top: `${(top / (DAY_END - DAY_START)) * 100}%`, height: `${(height / (DAY_END - DAY_START)) * 100}%` };
};

// Mon–Fri, 9 AM–5 PM: each attendee's busy blocks side by side, the suggested slots dashed and
// the picked one solid. Visual only; the chips and "Other times" are the controls.
function WeekGrid({ days, busy, attendees, picks, selected }: { days: string[]; busy: Busy[]; attendees: string[]; picks: Slot[]; selected: Slot | null }) {
  const lane = (person: string) => attendees.indexOf(person);
  return (
    <div className="mt-4">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-600">
        {attendees.map((a, i) => (
          <li key={a} className="flex items-center gap-1.5">
            <span className={`size-2.5 rounded-sm ${COLORS[i] ?? COLORS[2]}`} />
            {firstName(a)} busy
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm border border-dashed border-blue-500" />
          Open slot
        </li>
      </ul>
      <div aria-hidden className="mt-2 flex gap-1.5">
        <div className="relative mt-5 w-6 shrink-0 text-[10px] text-zinc-400">
          {AXIS.map((h) => (
            <span key={h} className="absolute -translate-y-1/2" style={{ top: `${((h * 60 - DAY_START) / (DAY_END - DAY_START)) * 100}%` }}>
              {h > 12 ? h - 12 : h}
              {h >= 12 ? "p" : "a"}
            </span>
          ))}
          <div className="h-48" />
        </div>
        {days.map((day) => {
          const key = dayKey(day);
          const isSelectedDay = selected !== null && dayKey(selected.start) === key;
          return (
            <div key={key} className="min-w-0 flex-1">
              <p className={`h-5 text-center text-xs ${isSelectedDay ? "font-semibold text-blue-700" : "text-zinc-500"}`}>{weekday(day)}</p>
              <div className={`relative h-48 rounded-md bg-zinc-50 ${isSelectedDay ? "ring-1 ring-blue-600" : ""}`}>
                {busy
                  .filter((b) => dayKey(b.start) === key && lane(b.person_id) >= 0)
                  .map((b) => (
                    <span
                      key={`${b.person_id}-${b.start}`}
                      className={`absolute w-[42%] rounded-sm ${COLORS[lane(b.person_id)] ?? COLORS[2]} ${lane(b.person_id) === 0 ? "left-[6%]" : "right-[6%]"}`}
                      style={pos(b.start, b.end)}
                    />
                  ))}
                {picks
                  .filter((s) => dayKey(s.start) === key && !(selected && sameSlot(s, selected)))
                  .map((s) => (
                    <span key={s.start} className="absolute inset-x-[6%] rounded-sm border border-dashed border-blue-500 bg-white/60" style={pos(s.start, s.end)} />
                  ))}
                {selected && isSelectedDay && <span className="absolute inset-x-[4%] rounded-sm bg-blue-600 shadow-sm" style={pos(selected.start, selected.end)} />}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Every mutual free slot, one row per day (five columns when the card is wide; a container
// query, since the chat panel is narrow even on a big screen).
function FreeTimes({
  days,
  slots,
  taken,
  selected,
  onSelect,
  disabled,
}: {
  days: string[];
  slots: Slot[];
  taken: number[];
  selected: Slot;
  onSelect: (s: Slot) => void;
  disabled: boolean;
}) {
  return (
    <div className="@container">
      <div role="group" aria-label="Free times for everyone" className="mt-4 grid gap-2 @xl:grid-cols-5">
        {days.map((day) => {
          const daySlots = slots.filter((s) => dayKey(s.start) === dayKey(day));
          return (
            <div key={dayKey(day)} className="flex items-center gap-3 rounded-lg border border-zinc-200 bg-white p-2 @xl:flex-col @xl:items-stretch @xl:gap-1.5">
              <span className="w-20 shrink-0 text-xs font-medium text-zinc-600 @xl:w-auto @xl:text-center">{formatDay(day)}</span>
              <div className="flex flex-1 flex-wrap gap-1.5 @xl:flex-col">
                {daySlots.length === 0 && <span className="py-1.5 text-xs text-zinc-400 @xl:text-center">No shared time</span>}
                {daySlots.map((s) => {
                  const isTaken = taken.includes(startOf(s));
                  const isSelected = !isTaken && sameSlot(s, selected);
                  return (
                    <button
                      key={s.start}
                      onClick={() => onSelect(s)}
                      disabled={disabled || isTaken}
                      aria-pressed={isSelected}
                      // Every slot is 30 min, so the button shows the start; the name keeps the range.
                      aria-label={`${formatSlot(s)}${isTaken ? " (taken)" : ""}`}
                      title={isTaken ? "No longer free" : undefined}
                      className={`rounded-md border px-2 py-1.5 text-xs font-medium whitespace-nowrap disabled:cursor-not-allowed ${
                        isTaken
                          ? "border-zinc-200 text-zinc-400 line-through"
                          : isSelected
                            ? "border-blue-600 bg-blue-600 text-white"
                            : "border-zinc-300 text-zinc-700 hover:border-blue-400 hover:bg-blue-50 disabled:hover:bg-transparent"
                      }`}
                    >
                      {formatTime(s.start)}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CalendarIcon() {
  return (
    <svg aria-hidden viewBox="0 0 20 20" className="size-4 text-zinc-500" fill="none" stroke="currentColor" strokeWidth="1.6">
      <rect x="3" y="4.5" width="14" height="12" rx="1.5" />
      <path d="M3 8.5h14M7 3v3M13 3v3" strokeLinecap="round" />
    </svg>
  );
}
