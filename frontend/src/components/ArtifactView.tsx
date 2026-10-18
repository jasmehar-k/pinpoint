"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { ApiError, getArtifact } from "@/lib/api";
import { formatDay } from "@/lib/time";
import { questionOf, splitTitle } from "@/lib/titles";
import { topicName } from "@/lib/topics";
import type { ArtifactPerson, ArtifactResponse, EventType, ThreadMessage } from "@/lib/types";

const PR_BASE = "https://github.com/twentyhq/twenty/pull/";

const ROLE: Record<EventType, string> = {
  asked: "Asked",
  answered: "Answered",
  authored: "Authored",
  reviewed: "Reviewed",
  owns: "Owns",
};

type State = { step: "loading" } | { step: "loaded"; artifact: ArtifactResponse } | { step: "error"; notFound: boolean; message: string };

export function ArtifactView({ id }: { id: string }) {
  const [state, setState] = useState<State>({ step: "loading" });

  useEffect(() => {
    let cancelled = false;
    getArtifact(id).then(
      (artifact) => !cancelled && setState({ step: "loaded", artifact }),
      (e) =>
        !cancelled &&
        setState({
          step: "error",
          notFound: e instanceof ApiError && e.status === 404,
          message: e instanceof Error ? e.message : String(e),
        }),
    );
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (state.step === "loading") return <Skeleton />;
  if (state.step === "error") {
    return (
      <div className="py-10">
        <h1 className="text-xl font-semibold">{state.notFound ? "We couldn't find that thread or PR" : "Couldn't load this page"}</h1>
        <p className="mt-1 text-sm text-zinc-500">{state.notFound ? "It may have been removed." : state.message}</p>
        <Link href="/" className="mt-4 inline-block text-sm font-medium text-blue-700 hover:underline dark:text-blue-400">
          Back to Pinpoint
        </Link>
      </div>
    );
  }
  return <Artifact artifact={state.artifact} />;
}

function Artifact({ artifact }: { artifact: ArtifactResponse }) {
  const { channel, title } = splitTitle(artifact.title);
  const isThread = artifact.kind === "thread";
  const heading = isThread ? questionOf(title) : title;
  const body = isThread ? artifact.text : withoutTitleLine(artifact.text, title);
  const external = artifact.url.startsWith("http");
  const sourceLabel = artifact.source === "github" ? "GitHub PR" : isThread ? "Slack thread" : "Saved answer";

  return (
    <article className="py-6">
      <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
        <span className="font-medium text-zinc-700 dark:text-zinc-300">{sourceLabel}</span>
        {channel && <span>#{channel}</span>}
        <span>· {formatDay(artifact.timestamp)}</span>
      </div>
      <h1 className="mt-1 text-xl font-semibold text-balance">{heading}</h1>

      {artifact.topics.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {artifact.topics.map((t) => (
            <span key={t} className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
              {topicName(t)}
            </span>
          ))}
        </div>
      )}

      <People people={artifact.people} />

      {isThread && artifact.messages?.length ? (
        <ol aria-label="Thread" className="mt-6 flex flex-col gap-4">
          {artifact.messages.map((m, i) => (
            <Message key={i} message={m} role={roleOf(m, artifact.people, i)} />
          ))}
        </ol>
      ) : (
        <div className="mt-6 rounded-xl border border-zinc-200 bg-white p-4 text-[15px] leading-relaxed whitespace-pre-wrap dark:border-zinc-800 dark:bg-zinc-900">
          {linkPrRefs(body)}
        </div>
      )}

      {external && (
        <a
          href={artifact.url}
          target="_blank"
          rel="noreferrer"
          className="mt-6 inline-block text-sm font-medium text-blue-700 hover:underline dark:text-blue-400"
        >
          {artifact.source === "github" ? "View on GitHub" : "Open in Slack"} ↗
        </a>
      )}
    </article>
  );
}

// Who is attached and how, grouped: "Asked: Aisha Bello · Answered: Dana Okafor, Marcus Lee".
function People({ people }: { people: ArtifactPerson[] }) {
  if (people.length === 0) return null;
  const groups = new Map<EventType, string[]>();
  for (const p of people) {
    const names = groups.get(p.type) ?? [];
    if (!names.includes(p.name)) names.push(p.name);
    groups.set(p.type, names);
  }
  return (
    <dl className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-sm">
      {[...groups].map(([type, names]) => (
        <div key={type} className="flex gap-1.5">
          <dt className="text-zinc-500">{ROLE[type]}</dt>
          <dd>{names.join(", ")}</dd>
        </div>
      ))}
    </dl>
  );
}

function Message({ message, role }: { message: ThreadMessage; role?: string }) {
  const initials = message.name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2);
  return (
    <li className="flex gap-3">
      <span aria-hidden className="flex size-9 shrink-0 items-center justify-center rounded-full bg-zinc-200 text-xs font-semibold text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
        {initials}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="font-semibold">{message.name}</span>
          {role && <span className="text-xs text-zinc-500">{role}</span>}
        </div>
        <p className="text-[15px] leading-relaxed break-words whitespace-pre-wrap">{linkPrRefs(message.text)}</p>
      </div>
    </li>
  );
}

// The first message is the question; later messages by someone who answered are answers.
function roleOf(m: ThreadMessage, people: ArtifactPerson[], index: number): string | undefined {
  if (index === 0) return ROLE.asked;
  if (m.person_id && people.some((p) => p.person_id === m.person_id && p.type === "answered")) return ROLE.answered;
  return undefined;
}

// PR text is stored as "title\n\nbody"; the heading already shows the title.
function withoutTitleLine(text: string, title: string): string {
  const [first, ...rest] = text.split("\n");
  return title.startsWith(first.trim()) && rest.length ? rest.join("\n").trim() : text;
}

// Turns "#26180" into a link to that Twenty PR. Channel names like #help don't match.
function linkPrRefs(text: string): ReactNode[] {
  return text.split(/(#\d{3,6}\b)/).map((part, i) =>
    /^#\d{3,6}$/.test(part) ? (
      <a key={i} href={PR_BASE + part.slice(1)} target="_blank" rel="noreferrer" className="font-medium text-blue-700 hover:underline dark:text-blue-400">
        {part}
      </a>
    ) : (
      part
    ),
  );
}

function Skeleton() {
  return (
    <div role="status" aria-label="Loading" className="animate-pulse py-6">
      <div className="h-3 w-40 rounded bg-zinc-200 dark:bg-zinc-800" />
      <div className="mt-3 h-6 w-3/4 rounded bg-zinc-200 dark:bg-zinc-800" />
      <div className="mt-8 space-y-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex gap-3">
            <div className="size-9 rounded-full bg-zinc-200 dark:bg-zinc-800" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-32 rounded bg-zinc-200 dark:bg-zinc-800" />
              <div className="h-3 w-full rounded bg-zinc-200 dark:bg-zinc-800" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
