"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { CODE_FILE } from "@/lib/code/messagingListFetchCron";
import { getPathExperts, MAX_CONTEXT_LINES, type PageContext, type PathExperts } from "@/lib/pageContext";
import { firstName } from "@/lib/people";
import { formatDay } from "@/lib/time";

import { Bubble, type BubbleState, hasTime } from "./Bubble";
import { GraphFocusProvider } from "../graphFocus";

const LINE_H = 22; // px, fixed so a line's offset is (n - 1) * LINE_H
const PAD_TOP = 12;

type Selection = { start: number; end: number };

export function CodeBrowser() {
  const lines = useMemo(() => CODE_FILE.source.replace(/\n$/, "").split("\n"), []);
  const fileName = CODE_FILE.path.split("/").at(-1)!;
  const folder = CODE_FILE.path.split("/").slice(0, -1);
  const [experts, setExperts] = useState<PathExperts | null>(null);
  const [sel, setSel] = useState<Selection | null>(null);
  const anchor = useRef<number | null>(null);
  const [bubble, setBubble] = useState<BubbleState>("collapsed");
  const [focusSignal, setFocusSignal] = useState(0);
  const codeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getPathExperts(CODE_FILE.path)
      .then(setExperts)
      .catch(() => setExperts(null)); // the page works without it; the bubble just says less
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && bubble === "collapsed" && setSel(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [bubble]);

  // At most MAX_CONTEXT_LINES lines go to the chat, so a selection is capped there.
  const pick = (a: number, b: number) => {
    const start = Math.min(a, b);
    setSel({ start, end: Math.min(Math.max(a, b), start + MAX_CONTEXT_LINES - 1) });
  };

  function onLineNumber(n: number, shift: boolean) {
    if (shift && anchor.current !== null) pick(anchor.current, n);
    else {
      anchor.current = n;
      pick(n, n);
    }
  }

  // Highlighting text in the code selects the lines it touches.
  function onMouseUp() {
    const s = window.getSelection();
    if (!s || s.isCollapsed || !codeRef.current) return;
    const lineOf = (node: Node | null) => Number((node instanceof Element ? node : node?.parentElement)?.closest("[data-line]")?.getAttribute("data-line") ?? 0);
    const a = lineOf(s.anchorNode);
    const b = lineOf(s.focusNode);
    if (!a || !b || !codeRef.current.contains(s.anchorNode)) return;
    anchor.current = Math.min(a, b);
    pick(a, b);
    s.removeAllRanges();
  }

  const context: PageContext = {
    path: CODE_FILE.path,
    lines: sel ? { start: sel.start, end: sel.end, text: lines.slice(sel.start - 1, sel.end).join("\n") } : undefined,
  };

  function openBubble() {
    setBubble((b) => (b === "collapsed" ? "open" : b));
    setFocusSignal((n) => n + 1);
  }

  // "Ask Marcus, Dana +1": people with time first.
  const ordered = experts ? [...experts.people].sort((a, b) => Number(hasTime(b)) - Number(hasTime(a))) : [];
  const askLabel = ordered.length ? `Ask ${ordered.slice(0, 2).map((p) => firstName(p.person_id)).join(", ")}${ordered.length > 2 ? ` +${ordered.length - 2}` : ""}` : "Ask Pinpoint";

  return (
    <GraphFocusProvider>
      <div className="min-h-dvh bg-white">
        <header className="sticky top-0 z-20 flex h-12 items-center gap-3 border-b border-zinc-200 bg-zinc-900 px-4 text-sm text-zinc-300">
          <span className="font-semibold text-white">Acme Code</span>
          <span className="min-w-0 truncate font-mono text-xs">
            {CODE_FILE.repo} › {folder.join("/")}
          </span>
          <Link href="/" className="ml-auto shrink-0 rounded-md px-2 py-1 text-xs font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white">
            ← Back to Pinpoint
          </Link>
        </header>

        <div className="flex">
          <FileTree folder={folder} fileName={fileName} />

          <main className="min-w-0 flex-1">
            <div className="sticky top-12 z-10 flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-zinc-200 bg-white px-4 py-2.5">
              <h1 className="font-mono text-sm font-semibold">{fileName}</h1>
              <span className="text-xs text-zinc-500">
                Last changed in{" "}
                <a href={CODE_FILE.lastChange.url} target="_blank" rel="noreferrer" className="text-blue-700 hover:underline">
                  PR #{CODE_FILE.lastChange.pr}
                </a>{" "}
                · {formatDay(CODE_FILE.lastChange.date)}
              </span>
              <button
                onClick={openBubble}
                className="ml-auto flex items-center gap-1.5 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-800 hover:bg-blue-100"
              >
                <PinIcon className="size-3.5" />
                {askLabel}
              </button>
            </div>

            <div className="relative" onMouseUp={onMouseUp}>
              <div ref={codeRef} className="overflow-x-auto pb-28 font-mono text-[13px]" style={{ paddingTop: PAD_TOP }}>
                <div className="min-w-max">
                  {lines.map((text, i) => {
                    const n = i + 1;
                    const on = sel !== null && n >= sel.start && n <= sel.end;
                    return (
                      <div key={n} data-line={n} className={`flex ${on ? "bg-blue-50" : ""}`} style={{ height: LINE_H, lineHeight: `${LINE_H}px` }}>
                        <button
                          onClick={(e) => onLineNumber(n, e.shiftKey)}
                          aria-label={`Line ${n}`}
                          aria-pressed={on}
                          className={`w-14 shrink-0 pr-4 text-right select-none hover:text-zinc-700 ${on ? "font-semibold text-blue-700" : "text-zinc-400"}`}
                        >
                          {n}
                        </button>
                        <code className="pr-8 whitespace-pre text-zinc-800">
                          <Highlighted text={text} />
                        </code>
                      </div>
                    );
                  })}
                </div>
              </div>
              {sel && bubble === "collapsed" && (
                <button
                  onClick={openBubble}
                  className="absolute right-6 flex items-center gap-1.5 rounded-md bg-zinc-900 px-2.5 py-1.5 text-xs font-medium text-white shadow-lg hover:bg-zinc-700"
                  style={{ top: PAD_TOP + (sel.start - 1) * LINE_H - 34 }}
                >
                  <PinIcon className="size-3.5" />
                  Ask Pinpoint about this
                </button>
              )}
            </div>
          </main>
        </div>

        <Bubble
          state={bubble}
          onState={setBubble}
          fileName={fileName}
          experts={experts}
          context={context}
          onClearSelection={() => setSel(null)}
          focusSignal={focusSignal}
        />
      </div>
    </GraphFocusProvider>
  );
}

// The messaging module's folders, opened down to the file. Only the current file is real.
function FileTree({ folder, fileName }: { folder: string[]; fileName: string }) {
  const at = folder.indexOf("messaging");
  const path = folder.slice(at); // messaging / message-import-manager / crons / jobs
  const others: Record<string, string[]> = {
    messaging: ["blocklist-manager", "common", "message-cleaner", "message-folder-manager", "message-outbound-manager", "message-participant-manager", "monitoring"],
    "message-import-manager": ["commands", "constants", "drivers", "jobs", "services", "types", "utils"],
    crons: ["commands"],
  };
  return (
    <nav aria-label="Files" className="sticky top-12 hidden h-[calc(100dvh-3rem)] w-64 shrink-0 overflow-y-auto border-r border-zinc-200 bg-zinc-50 py-3 font-mono text-xs text-zinc-600 md:block">
      <p className="px-4 pb-2 text-[11px] tracking-wide text-zinc-400 uppercase">…/src/modules</p>
      <ul>
        {path.map((dir, depth) => (
          <li key={dir}>
            <span className="block truncate py-1 font-semibold text-zinc-800" style={{ paddingLeft: 16 + depth * 12 }}>
              ▾ {dir}/
            </span>
            {depth === path.length - 1 && (
              <ul>
                {[fileName, ...CODE_FILE.siblings].sort().map((f) => (
                  <li
                    key={f}
                    aria-current={f === fileName ? "page" : undefined}
                    className={`truncate py-1 ${f === fileName ? "bg-blue-100 font-semibold text-blue-900" : ""}`}
                    style={{ paddingLeft: 28 + depth * 12 }}
                    title={f}
                  >
                    {f}
                  </li>
                ))}
              </ul>
            )}
            {(others[dir] ?? []).map((o) => (
              <span key={o} className="block truncate py-1 text-zinc-400" style={{ paddingLeft: 28 + depth * 12 }}>
                ▸ {o}/
              </span>
            ))}
          </li>
        ))}
      </ul>
    </nav>
  );
}

// Just enough colour to read as code: comments, strings, decorators, keywords.
const TOKEN = /(\/\/.*$)|('(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`|"(?:[^"\\]|\\.)*")|(@\w+)|\b(import|from|export|const|class|private|readonly|async|await|for|of|if|continue|try|catch|return|new|type|constructor|void|true|false)\b/g;

function Highlighted({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN)) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const cls = m[1] ? "text-zinc-400 italic" : m[2] ? "text-emerald-700" : m[3] ? "text-amber-700" : "text-violet-700";
    parts.push(
      <span key={m.index} className={cls}>
        {m[0]}
      </span>,
    );
    last = m.index + m[0].length;
  }
  parts.push(text.slice(last));
  return <>{parts}</>;
}

export function PinIcon({ className = "size-4" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z" strokeLinejoin="round" />
      <circle cx="12" cy="10" r="2.3" />
    </svg>
  );
}
