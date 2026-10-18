"use client";

import { useState } from "react";

import { firstName, nameFromId } from "@/lib/people";
import { dayKey, formatDay, formatSlot, weekdaysBetween } from "@/lib/time";
import type { AvailabilityResponse, PendingAction, ScheduleMeetingPayload, Slot } from "@/lib/types";

import { ActionButtons, CardShell } from "./ActionCard";
import { useApproval } from "./useApproval";

type MeetingAction = Extract<PendingAction, { kind: "schedule_meeting" }>;

const startOf = (s: Slot) => new Date(s.start).getTime();
const sameSlot = (a: Slot, b: Slot) => startOf(a) === startOf(b);

// Nothing is booked until Approve. Approve books the slot picked in the week view.
export function MeetingApproveCard({ action, availability }: { action: MeetingAction; availability?: AvailabilityResponse | null }) {
  const { title, attendees, slot: suggested } = action.payload;
  const [selected, setSelected] = useState<Slot>(suggested);
  const [taken, setTaken] = useState<number[]>([]); // slot starts the backend said were no longer free

  // Without availability, the suggested slot is the only option.
  const slots = availability?.mutual_free_slots.length ? availability.mutual_free_slots : [suggested];
  const days = availability ? weekdaysBetween(availability.window_start, availability.window_end) : [suggested.start];

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

  function onApprove() {
    // Only send a payload when a different slot was picked; no payload books the suggestion.
    const payload: ScheduleMeetingPayload | undefined = changed ? { title, attendees, slot: selected } : undefined;
    approve({ payload });
  }

  return (
    <CardShell
      label={`Meeting: ${title}`}
      title={title}
      aside="30 min · times in Pacific"
      dismissed={state.phase === "dismissed" ? "Dismissed. No meeting was booked." : null}
    >
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        {attendees.map(nameFromId).join(" and ")}
        {availability && (
          <span className="text-zinc-500">
            {" · "}
            {availability.people.map((p) => `${firstName(p.person_id)} ${Math.round(p.booked_pct * 100)}% booked`).join(", ")}
          </span>
        )}
      </p>

      {state.phase === "done" ? (
        <p role="status" className="mt-3 text-sm font-medium text-emerald-700 dark:text-emerald-400">
          ✓ Booked {formatDay(selected.start)}, {formatSlot(selected)}. Added to {names.map((n) => `${n}'s`).join(" and ")} calendars.
        </p>
      ) : (
        <>
          <WeekView days={days} slots={slots} taken={taken} selected={selected} onSelect={setSelected} disabled={state.phase !== "draft"} />
          <ActionButtons
            state={state}
            approveLabel={`Book ${formatDay(selected.start).split(",")[0]} ${formatSlot(selected)}`}
            workingLabel="Booking…"
            disabled={selectedTaken}
            note={changed ? "Changed from the suggested time" : undefined}
            errorPrefix="Not booked"
            onApprove={onApprove}
            onDismiss={dismiss}
          />
        </>
      )}
    </CardShell>
  );
}

// Mon–Fri of the window. Columns on wider screens, one row per day on phones.
function WeekView({
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
    <div role="group" aria-label="Free times for everyone" className="mt-3 grid gap-2 sm:grid-cols-5">
      {days.map((day) => {
        const daySlots = slots.filter((s) => dayKey(s.start) === dayKey(day));
        return (
          <div
            key={dayKey(day)}
            className="flex items-center gap-3 rounded-lg border border-zinc-200 bg-white p-2 sm:flex-col sm:items-stretch sm:gap-1.5 dark:border-zinc-800 dark:bg-zinc-900"
          >
            <span className="w-20 shrink-0 text-xs font-medium text-zinc-600 sm:w-auto sm:text-center dark:text-zinc-400">{formatDay(day)}</span>
            <div className="flex flex-1 flex-wrap gap-1.5 sm:flex-col">
              {daySlots.length === 0 && <span className="py-1.5 text-xs text-zinc-400 sm:text-center">No shared time</span>}
              {daySlots.map((s) => {
                const isTaken = taken.includes(startOf(s));
                const isSelected = !isTaken && sameSlot(s, selected);
                return (
                  <button
                    key={s.start}
                    onClick={() => onSelect(s)}
                    disabled={disabled || isTaken}
                    aria-pressed={isSelected}
                    title={isTaken ? "No longer free" : undefined}
                    className={`relative rounded-md border px-2 py-1.5 text-xs font-medium whitespace-nowrap disabled:cursor-not-allowed ${
                      isTaken
                        ? "border-zinc-200 text-zinc-400 line-through dark:border-zinc-800"
                        : isSelected
                          ? "border-blue-600 bg-blue-600 text-white"
                          : "border-zinc-300 text-zinc-700 hover:border-blue-400 hover:bg-blue-50 disabled:hover:bg-transparent dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    }`}
                  >
                    {formatSlot(s)}
                    {isTaken && <span className="sr-only"> (taken)</span>}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
