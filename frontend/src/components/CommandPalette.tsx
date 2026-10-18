"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { SUGGESTED_QUESTIONS } from "@/lib/demo";
import { TOPIC_NAMES } from "@/lib/topics";

import { useGraphFocus } from "./graphFocus";

type Command = { id: string; group: string; label: string; run: () => void };

const short = (name: string) => name.replace(/\s*\(.*\)$/, "");

// Cmd+K (Ctrl+K): jump to a topic in the graph, switch graph mode, ask a demo question, open
// the code page. A combobox over a filtered listbox; arrows move, Enter runs, Esc closes.
export function CommandPalette() {
  const { paletteOpen: open, setPaletteOpen: setOpen } = useGraphFocus();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  // Mounted only while open, so every opening starts with an empty query.
  return open ? <PaletteDialog onClose={() => setOpen(false)} /> : null;
}

function PaletteDialog({ onClose }: { onClose: () => void }) {
  const { setTopic, setPerson, setMode, ask } = useGraphFocus();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  const commands = useMemo<Command[]>(
    () => [
      ...Object.entries(TOPIC_NAMES).map(([id, name]) => ({
        id: `topic-${id}`,
        group: "Graph",
        label: `Focus ${short(name)}`,
        run: () => {
          setMode("experts");
          setPerson(null);
          setTopic(id);
        },
      })),
      { id: "mode-bus", group: "Graph", label: "Show bus factor", run: () => setMode("bus") },
      { id: "mode-experts", group: "Graph", label: "Show experts", run: () => setMode("experts") },
      ...SUGGESTED_QUESTIONS.map((q, i) => ({ id: `ask-${i}`, group: "Ask", label: q, run: () => ask(q) })),
    ],
    [setTopic, setPerson, setMode, ask],
  );

  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const shown = commands.filter((c) => words.every((w) => `${c.group} ${c.label}`.toLowerCase().includes(w)));
  const current = Math.min(active, Math.max(shown.length - 1, 0));

  useEffect(() => {
    listRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  }, [current]);

  function run(c: Command | undefined) {
    if (!c) return;
    onClose();
    c.run();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-zinc-900/30 px-4 pt-[12vh]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-label="Command palette" aria-modal="true" className="w-full max-w-lg overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-2xl">
        <input
          autoFocus
          role="combobox"
          aria-expanded="true"
          aria-controls="palette-list"
          aria-activedescendant={shown[current] ? `palette-${shown[current].id}` : undefined}
          aria-label="Type a command or a topic"
          placeholder="Type a command or a topic…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((current + 1) % Math.max(shown.length, 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((current - 1 + shown.length) % Math.max(shown.length, 1));
            } else if (e.key === "Enter") {
              e.preventDefault();
              run(shown[current]);
            } else if (e.key === "Escape") {
              e.preventDefault();
              onClose();
            }
          }}
          className="w-full border-b border-zinc-100 px-4 py-3.5 text-[15px] outline-none placeholder:text-zinc-400"
        />
        <ul ref={listRef} id="palette-list" role="listbox" aria-label="Commands" className="max-h-[50vh] overflow-y-auto p-1.5">
          {shown.length === 0 && <li className="px-3 py-6 text-center text-sm text-zinc-500">No matching command</li>}
          {shown.map((c, i) => (
            <li
              key={c.id}
              id={`palette-${c.id}`}
              role="option"
              aria-selected={i === current}
              onMouseMove={() => setActive(i)}
              onClick={() => run(c)}
              className={`flex cursor-pointer items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm ${i === current ? "bg-blue-50 text-blue-900" : "text-zinc-700"}`}
            >
              <span className="min-w-0 truncate">{c.label}</span>
              <span className="shrink-0 text-xs text-zinc-400">{c.group}</span>
            </li>
          ))}
        </ul>
        <p className="flex gap-4 border-t border-zinc-100 px-4 py-2 text-xs text-zinc-400">
          <span>↑↓ to move</span>
          <span>Enter to run</span>
          <span>Esc to close</span>
        </p>
      </div>
    </div>
  );
}

// Header button for people who don't know the shortcut.
export function PaletteButton() {
  const { setPaletteOpen } = useGraphFocus();
  return (
    <button
      onClick={() => setPaletteOpen(true)}
      aria-label="Open command palette"
      title="Command palette (⌘K)"
      className="hidden items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 font-mono text-xs text-zinc-500 hover:bg-zinc-50 lg:flex"
    >
      ⌘K
    </button>
  );
}
