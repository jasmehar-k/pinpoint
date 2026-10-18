"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { sendChat } from "@/lib/api";
import { DEMO_USER, SUGGESTED_QUESTIONS } from "@/lib/demo";
import type { ChatResponse } from "@/lib/types";

import { CitedText, SourceList } from "./CitedText";

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
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
          {messages.length === 0 && <EmptyState onPick={ask} />}
          {messages.map((m) => (
            <MessageView key={m.id} message={m} onRetry={ask} />
          ))}
          {loading && <Thinking />}
          <div ref={bottom} />
        </div>
      </div>

      <form onSubmit={onSubmit} className="border-t border-zinc-200 bg-background dark:border-zinc-800">
        <div className="mx-auto flex max-w-3xl items-end gap-2 px-4 py-3">
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
            placeholder={loading ? "Waiting for the answer…" : "Ask how something works"}
            aria-label="Your question"
            className="max-h-40 min-h-11 flex-1 resize-none [field-sizing:content] rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-[15px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:bg-zinc-100 disabled:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:disabled:bg-zinc-800"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="h-11 shrink-0 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-zinc-300 dark:disabled:bg-zinc-700"
          >
            Ask
          </button>
        </div>
      </form>
    </div>
  );
}

function MessageView({ message, onRetry }: { message: Message; onRetry: (q: string) => void }) {
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
        <button onClick={() => onRetry(message.retry)} className="font-medium underline">
          Try again
        </button>
      </div>
    );
  }
  const { reply } = message.response;
  return (
    <div className="max-w-full rounded-2xl rounded-bl-sm border border-zinc-200 bg-white px-4 py-3 text-[15px] leading-relaxed dark:border-zinc-800 dark:bg-zinc-900">
      <CitedText text={reply.text} citations={reply.citations} />
      <SourceList citations={reply.citations} />
    </div>
  );
}

// Real answers can take 15s+, so show that something is happening and for how long.
function Thinking() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div role="status" className="flex items-center gap-3 text-sm text-zinc-500">
      <span className="flex gap-1">
        {[0, 150, 300].map((d) => (
          <span key={d} className="size-1.5 animate-bounce rounded-full bg-zinc-400" style={{ animationDelay: `${d}ms` }} />
        ))}
      </span>
      Searching PRs and Slack threads{seconds >= 3 ? ` · ${seconds}s` : "…"}
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="py-8">
      <h2 className="text-xl font-semibold">Hi {DEMO_USER.name.split(" ")[0]}, what are you trying to figure out?</h2>
      <p className="mt-1 text-sm text-zinc-500">
        Answers come from your team&apos;s PRs and Slack threads, with a link for every claim, plus who to ask.
      </p>
      <div className="mt-5 grid gap-2 sm:grid-cols-2">
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
