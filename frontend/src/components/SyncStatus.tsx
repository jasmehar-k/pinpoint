"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";
import { minutesAgo } from "@/lib/time";

// "Synced: Slack · GitHub · 3 min ago" from /health's synced_at; no time if it's missing.
export function SyncStatus() {
  const [syncedAt, setSyncedAt] = useState<string | null>(null);
  useEffect(() => {
    getHealth().then((h) => setSyncedAt(h.synced_at ?? null), () => {});
  }, []);
  return (
    <span className="hidden font-mono text-xs text-zinc-500 md:inline">
      Synced: Slack · GitHub{syncedAt && ` · ${minutesAgo(syncedAt)}`}
    </span>
  );
}
