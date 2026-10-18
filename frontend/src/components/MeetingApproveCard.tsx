"use client";

import { useState } from "react";

import { approveAction } from "@/lib/api";
import { firstName, nameFromId } from "@/lib/people";
import { dayKey, formatDay, formatSlot, weekdaysBetween } from "@/lib/time";
import type { AvailabilityResponse, PendingAction, ScheduleMeetingPayload, Slot } from "@/lib/types";

type MeetingAction = Extract<PendingAction, { kind: "schedule_meeting" }>;

type State = { step: "draft"; error?: string } | { step: "booking" } | { step: "booked"; slot: Slot };

const sameSlot = (a: Slot, b: Slot) => new Date(a.start).getTime() === new Date(b.start).getTime();

// Nothing is booked until Approve. Approve books the slot picked in the week view.
export function MeetingApproveCard({ action, availability }: { action: MeetingAction; availability?: AvailabilityResponse | null }) {
  const { title, attendees, slot: suggested } = action.payload;
  const [selected, setSelected] = useState<Slot>(suggested);
  const [state, setState] = useState<State>(action.status === "executed" ? { step: "booked", slot: suggested } : { step: "draft" });

  // Without availability, the suggested slot is the only option.
  const slots = availability?.mutual_free_slots.length ? availability.mutual_free_slots : [suggested];
  const days = availability ? weekdaysBetween(availability.window_start, availability.window_end) : [suggested.start];
  const changed = !sameSlot(selected, suggested);
  const names = attendees.map(firstName);

  async function approve() {
    if (state.step !== "draft") return;
    setState({ step: "booking" }); // locks the card before the request goes out
    // Only send a payload when a different slot was picked; no payload books the suggestion.
    const payload: ScheduleMeetingPayload | undefined = changed ? { title, attendees, slot: selected } : undefined;
    try {
      const result = await approveAction(action, { payload });
      if (result.status === "executed") {
        setState({ step: "booked", slot: selected });
      } else {
        const reason = typeof result.result?.error === "string" ? result.result.error : `status ${result.status}`;
        setState({ step: "draft", error: `Not booked: ${reason}` });
      }
    } catch (e) {
      setState({ step: "draft", error: `Not booked: ${e instanceof Error ? e.message : String(e)}` });
    }
  }

  const locked = state.step !== "draft";

  return (
    <article aria-label={`Meeting: ${title}`} className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 dark:border-blue-900 dark:bg-blue-950/30">
      <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h4 className="font-semibold">{title}</h4>
        <span className="text-xs text-zinc-500">30 min · times in Pacific</span>
      </header>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        {attendees.map(nameFromId).join(" and ")}
        {availability && (
          <span className="text-zinc-500">
            {" · "}
            {availability.people.map((p) => `${firstName(p.person_id)} ${Math.round(p.booked_pct * 100)}% booked`).join(", ")}
          </span>
        )}
      </p>

      {state.step === "booked" ? (
        <p role="status" className="mt-3 text-sm font-medium text-emerald-700 dark:text-emerald-400">
          ✓ Booked {formatDay(state.slot.start)}, {formatSlot(state.slot)}. Added to {names.map((n) => `${n}'s`).join(" and ")} calendars.
        </p>
      ) : (
        <>
          <WeekView days={days} slots={slots} selected={selected} onSelect={setSelected} disabled={locked} />
          <footer className="mt-3 flex flex-wrap items-center gap-3">
            <button
              onClick={approve}
              disabled={locked}
              className="h-10 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-zinc-300 dark:disabled:bg-zinc-700"
            >
              {state.step === "booking" ? "Booking…" : `Book ${formatDay(selected.start).split(",")[0]} ${formatSlot(selected)}`}
            </button>
            {state.step === "draft" && changed && <span className="text-xs text-zinc-500">Changed from the suggested time</span>}
            {state.step === "draft" && state.error && (
              <span role="alert" className="text-sm text-red-700 dark:text-red-300">
                {state.error}
              </span>
            )}
          </footer>
        </>
      )}
    </article>
  );
}

// Mon–Fri of the window. Columns on wider screens, one row per day on phones.
function WeekView({
  days,
  slots,
  selected,
  onSelect,
  disabled,
}: {
  days: string[];
  slots: Slot[];
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
                const isSelected = sameSlot(s, selected);
                return (
                  <button
                    key={s.start}
                    onClick={() => onSelect(s)}
                    disabled={disabled}
                    aria-pressed={isSelected}
                    className={`rounded-md border px-2 py-1.5 text-xs font-medium whitespace-nowrap disabled:cursor-not-allowed ${
                      isSelected
                        ? "border-blue-600 bg-blue-600 text-white"
                        : "border-zinc-300 text-zinc-700 hover:border-blue-400 hover:bg-blue-50 disabled:hover:bg-transparent dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    }`}
                  >
                    {formatSlot(s)}
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
