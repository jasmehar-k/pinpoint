"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { sendChat } from "@/lib/api";
import { DEMO_USER, SUGGESTED_QUESTIONS } from "@/lib/demo";
import { firstName } from "@/lib/people";
import type { ChatResponse, Expert } from "@/lib/types";

import { CitedText, SourceChips } from "./CitedText";
import { DmApproveCard } from "./DmApproveCard";
import { ExpertList } from "./ExpertCard";
import { MeetingApproveCard } from "./MeetingApproveCard";

type Message =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; response: ChatResponse }
  | { id: number; role: "error"; text: string; retry: string };

// Omit that keeps the union: Omit<Message, "id"> would merge the variants.
type NewMessage = Message extends infer M ? (M extends Message ? Omit<M, "id"> : never) : never;

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string>();
  const nextId = useRef(0);
  const bottom = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  useEffect(() => {
    if (!loading) inputRef.current?.focus();
  }, [loading]);

  async function ask(text: string) {
    const question = text.trim();
    if (!question || loading) return;
    const add = (m: NewMessage) => setMessages((ms) => [...ms, { ...m, id: nextId.current++ }]);

    add({ role: "user", text: question });
    setInput("");
    setLoading(true);
    try {
      const response = await sendChat({ message: question, conversation_id: conversationId, user: DEMO_USER.id });
      setConversationId(response.conversation_id);
      add({ role: "assistant", response });
    } catch (e) {
      add({ role: "error", text: e instanceof Error ? e.message : String(e), retry: question });
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    ask(input);
  }

  return (
    <section aria-label="Ask Pinpoint" className="flex min-h-0 flex-col rounded-xl border border-zinc-200 bg-white">
      <header className="border-b border-zinc-100 px-5 py-4">
        <h2 className="font-semibold">Ask Pinpoint</h2>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="flex flex-col gap-4 px-4 py-5 sm:px-5">
          {messages.length === 0 && <EmptyState onPick={ask} />}
          {messages.map((m, i) => (
            <MessageView key={m.id} message={m} onAsk={ask} busy={loading} shownBefore={expertsShownBefore(messages, i)} />
          ))}
          {loading && <Thinking />}
          <div ref={bottom} />
        </div>
      </div>

      <form onSubmit={onSubmit} className="border-t border-zinc-100">
        <div className="flex items-end gap-2 px-4 py-3 sm:px-5">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                ask(input);
              }
            }}
            disabled={loading}
            rows={1}
            placeholder={loading ? "Waiting for the answer…" : messages.length ? "Ask a follow-up" : "Ask how something works"}
            aria-label="Your question"
            className="max-h-40 min-h-11 flex-1 resize-none [field-sizing:content] rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-[15px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:bg-zinc-100 disabled:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:disabled:bg-zinc-800"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="h-11 shrink-0 rounded-lg bg-zinc-900 px-4 text-sm font-medium text-white hover:bg-zinc-700 disabled:cursor-not-allowed disabled:bg-zinc-300"
          >
            Ask
          </button>
        </div>
      </form>
    </section>
  );
}

// Person ids that appeared on expert cards in replies before index i.
function expertsShownBefore(messages: Message[], i: number): Set<string> {
  const ids = new Set<string>();
  for (const m of messages.slice(0, i)) {
    if (m.role === "assistant") for (const e of m.response.experts ?? []) ids.add(e.person_id);
  }
  return ids;
}

function MessageView({
  message,
  onAsk,
  busy,
  shownBefore,
}: {
  message: Message;
  onAsk: (q: string) => void;
  busy: boolean;
  shownBefore: Set<string>;
}) {
  if (message.role === "user") {
    return (
      <div className="ml-auto max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-blue-600 px-4 py-2.5 text-[15px] text-white">
        {message.text}
      </div>
    );
  }
  if (message.role === "error") {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
        Couldn&apos;t get an answer: {message.text}{" "}
        <button onClick={() => onAsk(message.retry)} className="font-medium underline">
          Try again
        </button>
      </div>
    );
  }
  const { reply, pending_actions = [], availability } = message.response;
  // A follow-up reply (no citations, e.g. "Here's a draft to Marcus instead.") repeats the
  // expert it's about; skip cards for people already shown. New answers keep their full list.
  const isFollowUp = reply.citations.length === 0;
  const experts = (message.response.experts ?? []).filter((e) => !(isFollowUp && shownBefore.has(e.person_id)));
  // With experts, the backend's last paragraph is its code-written routing line ("Dana knows
  // this best but…"). It reads better after the cards, as in the mockup.
  const paragraphs = reply.text.split(/\n{2,}/);
  const routing = experts.length > 0 && paragraphs.length > 1 ? paragraphs.pop() : null;

  // Expert card buttons become follow-up questions the backend already understands. If a draft
  // to that person is still open in this reply, jump to it instead of asking for another.
  function draft(expert: Expert) {
    const open = pending_actions.find((a) => a.kind === "send_message" && a.payload.to === expert.person_id);
    const box = open && document.querySelector<HTMLTextAreaElement>(`#action-${open.id} textarea`);
    if (box) {
      box.scrollIntoView({ behavior: "smooth", block: "center" });
      box.focus({ preventScroll: true });
      return;
    }
    onAsk(`Draft a message to ${firstName(expert.person_id)}`);
  }
  const book = (expert: Expert) => onAsk(`Book time with ${firstName(expert.person_id)} this week`);
  return (
    <div className="flex flex-col gap-3">
      <div data-answer className="text-[15px] leading-relaxed">
        <CitedText text={paragraphs.join("\n\n")} citations={reply.citations} />
        <SourceChips citations={reply.citations} />
      </div>
      <ExpertList experts={experts} onDraft={draft} onBook={book} disabled={busy} />
      {routing && <p className="text-[15px] leading-relaxed">{routing}</p>}
      {pending_actions.map((a) =>
        a.kind === "send_message" ? (
          <DmApproveCard key={a.id} action={a} context={reply.citations} />
        ) : (
          <MeetingApproveCard key={a.id} action={a} availability={availability} />
        ),
      )}
    </div>
  );
}

// Uncached answers take ~30s on the free model, so show that something is happening. Past
// SLOW_AFTER seconds a ticking counter stops reassuring anyone, so it gives way to a softer line.
const SLOW_AFTER = 30;

function Thinking() {
  // Elapsed time from a start stamp, not a tick count: browsers slow timers in background
  // tabs (e.g. while a cited PR is open), and a tick count would fall behind.
  const [start] = useState(() => Date.now());
  const [now, setNow] = useState(start);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const seconds = Math.floor((now - start) / 1000);
  return (
    <div role="status" className="flex items-center gap-3 text-sm text-zinc-500">
      <span className="flex gap-1">
        {[0, 150, 300].map((d) => (
          <span key={d} className="size-1.5 animate-bounce rounded-full bg-zinc-400" style={{ animationDelay: `${d}ms` }} />
        ))}
      </span>
      {seconds >= SLOW_AFTER
        ? "Still digging through PRs and threads…"
        : `Searching PRs and Slack threads${seconds >= 3 ? ` · ${seconds}s` : "…"}`}
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="py-4">
      <h2 className="text-lg font-semibold">Hi {DEMO_USER.name.split(" ")[0]}, what are you trying to figure out?</h2>
      <p className="mt-1 text-sm text-zinc-500">
        Answers come from your team&apos;s PRs and Slack threads, with a link for every claim, plus who to ask.
      </p>
      <div className="mt-5 grid gap-2">
        {SUGGESTED_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            className="rounded-lg border border-zinc-200 px-3 py-2.5 text-left text-sm hover:border-blue-400 hover:bg-blue-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
