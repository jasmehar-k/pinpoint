import Link from "next/link";

import { USE_FIXTURES } from "@/lib/api";
import { DEMO_USER } from "@/lib/demo";

export function Header() {
  return (
    <header className="border-b border-zinc-200 dark:border-zinc-800">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="text-lg font-semibold">
          Pinpoint
        </Link>
        <div className="flex items-center gap-2 text-sm text-zinc-500">
          {USE_FIXTURES && (
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-200">
              Fixtures
            </span>
          )}
          <span className="truncate">
            {DEMO_USER.name} · {DEMO_USER.team}
          </span>
        </div>
      </div>
    </header>
  );
}
