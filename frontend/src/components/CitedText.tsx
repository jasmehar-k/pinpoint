import Link from "next/link";
import type { ReactNode } from "react";

import { displayTitle, splitTitle } from "@/lib/titles";
import type { Citation } from "@/lib/types";

// Seeded threads link to /artifacts/{id} in this app; everything else is external.
// Both open in a new tab: the chat lives in page state, so navigating away would lose it.
export function isInternal(url: string): boolean {
  return url.startsWith("/");
}

type LinkProps = { url: string; title: string; className?: string; children: ReactNode };

export function SourceLink({ url, title, className, children }: LinkProps) {
  if (isInternal(url)) {
    return (
      <Link href={url} target="_blank" className={className} title={title}>
        {children}
      </Link>
    );
  }
  return (
    <a href={url} target="_blank" rel="noreferrer" className={className} title={title}>
      {children}
    </a>
  );
}

const chip =
  "mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-blue-100 px-1 align-[1px] text-[11px] font-semibold text-blue-800 no-underline hover:bg-blue-200 dark:bg-blue-950 dark:text-blue-200 dark:hover:bg-blue-900";

// Renders reply text, turning [n] markers into chips that link to citation n.
// Markers without a matching citation stay as plain text.
export function CitedText({ text, citations }: { text: string; citations: Citation[] }) {
  const byId = new Map(citations.map((c) => [c.id, c]));
  return (
    <>
      {text.split(/\n{2,}/).map((para, i) => (
        <p key={i} className="mb-3 last:mb-0">
          {para.split(/(\[\d+\])/).map((part, j) => {
            const citation = byId.get(part.match(/^\[(\d+)\]$/)?.[1] ?? "");
            if (!citation) return part;
            return (
              <SourceLink key={j} url={citation.url} title={citation.title} className={chip}>
                {citation.id}
              </SourceLink>
            );
          })}
        </p>
      ))}
    </>
  );
}

// Short chip label: "PR #26180" for GitHub, "#help thread" for Slack threads.
export function shortLabel(c: Citation): string {
  const pr = c.title.match(/\(#(\d+)\)\s*$/);
  if (c.source === "github" && pr) return `PR #${pr[1]}`;
  const { channel } = splitTitle(c.title);
  if (channel) return `#${channel} thread`;
  return c.title.length > 32 ? `${c.title.slice(0, 30)}…` : c.title;
}

// The answer's sources as a row of chips under the text, numbered like the inline markers.
export function SourceChips({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <ul aria-label="Sources" className="mt-3 flex flex-wrap gap-1.5">
      {citations.map((c) => (
        <li key={c.id}>
          <SourceLink
            url={c.url}
            title={displayTitle(c.title)}
            className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-2 py-1 font-mono text-xs text-blue-800 hover:bg-blue-100"
          >
            <span className="font-semibold">{c.id}</span>
            {shortLabel(c)}
          </SourceLink>
        </li>
      ))}
    </ul>
  );
}
