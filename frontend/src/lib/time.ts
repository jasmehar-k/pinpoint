// Times show in the org timezone (Pacific), not the browser's, so the demo reads the
// same on any laptop.

export const ORG_TZ = "America/Los_Angeles";

const timeFmt = new Intl.DateTimeFormat("en-US", { timeZone: ORG_TZ, hour: "numeric", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat("en-US", { timeZone: ORG_TZ, weekday: "short", month: "short", day: "numeric" });
const dayKeyFmt = new Intl.DateTimeFormat("en-CA", { timeZone: ORG_TZ, year: "numeric", month: "2-digit", day: "2-digit" });

// "10:30 AM"
export function formatTime(iso: string): string {
  return timeFmt.format(new Date(iso));
}

// "Wed, Oct 21"
export function formatDay(iso: string): string {
  return dayFmt.format(new Date(iso));
}

// "2026-10-21", the Pacific calendar day; use it to group slots by day.
export function dayKey(iso: string): string {
  return dayKeyFmt.format(new Date(iso));
}

// "2 days ago", for evidence timestamps.
export function timeAgo(iso: string, now: Date = new Date()): string {
  const days = Math.floor((now.getTime() - new Date(iso).getTime()) / 86_400_000);
  if (days < 1) return "today";
  if (days === 1) return "yesterday";
  if (days < 60) return `${days} days ago`;
  return `${Math.floor(days / 30)} months ago`;
}

const weekdayFmt = new Intl.DateTimeFormat("en-US", { timeZone: ORG_TZ, weekday: "short" });

// "10:30 – 11:00 AM", or "11:30 AM – 12:00 PM" when the slot crosses noon.
export function formatSlot(slot: { start: string; end: string }): string {
  const start = formatTime(slot.start);
  const end = formatTime(slot.end);
  const sameHalf = start.slice(-2) === end.slice(-2);
  return `${sameHalf ? start.slice(0, -3) : start} – ${end}`;
}

// Pacific weekdays from start to end, inclusive, one ISO timestamp per day; pass them to
// dayKey/formatDay. Steps 24h from the window start (9 AM), so a DST shift moves the
// hour, never the day.
export function weekdaysBetween(startIso: string, endIso: string): string[] {
  const last = dayKey(endIso);
  const days: string[] = [];
  for (let t = new Date(startIso).getTime(); dayKey(new Date(t).toISOString()) <= last; t += 86_400_000) {
    const iso = new Date(t).toISOString();
    if (!["Sat", "Sun"].includes(weekdayFmt.format(new Date(iso)))) days.push(iso);
    if (days.length > 14) break; // a window is a week; guard against bad input
  }
  return days;
}
