import Link from "next/link";
import type { ReactNode } from "react";

import { displayTitle } from "@/lib/titles";
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

const SOURCE_LABEL = { github: "GitHub", slack: "Slack", seed: "Slack" } as const;

export function SourceList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <ol className="mt-3 space-y-1 border-t border-zinc-200 pt-3 text-sm dark:border-zinc-800">
      {citations.map((c) => (
        <li key={c.id} className="flex min-w-0 items-baseline gap-2">
          <span className={chip}>{c.id}</span>
          <SourceLink url={c.url} title={c.title} className="line-clamp-2 min-w-0 text-zinc-700 hover:underline dark:text-zinc-300">
            {displayTitle(c.title)}
          </SourceLink>
          <span className="shrink-0 text-xs text-zinc-500">{SOURCE_LABEL[c.source]}</span>
        </li>
      ))}
    </ol>
  );
}
