import Link from "next/link";

import { USE_FIXTURES } from "@/lib/api";
import { DEMO_USER } from "@/lib/demo";

import { PaletteButton } from "./CommandPalette";
import { SyncStatus } from "./SyncStatus";

// palette: show the ⌘K button (only where a CommandPalette is mounted, i.e. the main page).
export function Header({ palette = false }: { palette?: boolean }) {
  const initials = DEMO_USER.name
    .split(" ")
    .map((w) => w[0])
    .join("");
  return (
    <header className="border-b border-zinc-200 bg-white">
      <div className="flex items-center justify-between gap-3 px-4 py-3 lg:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/" className="flex items-center gap-2 text-lg font-semibold">
            <PinIcon />
            Pinpoint
          </Link>
          <span className="hidden border-l border-zinc-200 pl-3 text-sm text-zinc-500 sm:inline">{DEMO_USER.org}</span>
        </div>
        <div className="flex items-center gap-4">
          {USE_FIXTURES && (
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">Fixtures</span>
          )}
          {palette && <PaletteButton />}
          <SyncStatus />
          <div className="flex items-center gap-2">
            <span aria-hidden className="flex size-8 items-center justify-center rounded-full bg-zinc-800 text-xs font-semibold text-white">
              {initials}
            </span>
            <div className="leading-tight">
              <div className="text-sm font-semibold">{DEMO_USER.name}</div>
              <div className="text-xs text-zinc-500">New hire · day {DEMO_USER.day}</div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

function PinIcon() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className="size-7 text-blue-700">
      <circle cx="12" cy="12" r="11" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 6.5a3.8 3.8 0 0 0-3.8 3.8c0 2.8 3.8 7.2 3.8 7.2s3.8-4.4 3.8-7.2A3.8 3.8 0 0 0 12 6.5Z" fill="currentColor" />
      <circle cx="12" cy="10.3" r="1.4" fill="white" />
    </svg>
  );
}
