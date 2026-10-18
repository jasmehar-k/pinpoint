"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";
import type { Health } from "@/lib/types";

// Placeholder until the chat UI lands. Confirms fixtures (or the API) are reachable.
export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth().then(setHealth, (e: Error) => setError(e.message));
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-2 px-4">
      <h1 className="text-2xl font-semibold">Pinpoint</h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        {error ? `Backend unreachable: ${error}` : health ? `Backend ${health.status}, mode ${health.mode}` : "Checking backend"}
      </p>
    </main>
  );
}
