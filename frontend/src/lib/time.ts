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
