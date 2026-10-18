"use client";

import { useEffect, useMemo, useState } from "react";

import { getGraph } from "@/lib/api";
import { firstName } from "@/lib/people";
import type { GraphEdge, GraphPerson, GraphResponse, GraphTopic } from "@/lib/types";

import { useGraphFocus } from "./graphFocus";

type Mode = "experts" | "bus";

// Team colours match the expert card avatars.
const TEAM_FILL: Record<string, string> = {
  Integrations: "#7c3aed",
  Platform: "#0d9488",
  Product: "#ea580c",
  Core: "#475569",
};

// Bus factor: 1 expert = red, 2 = amber, 3+ = green.
const RISK = {
  1: { stroke: "#b91c1c", fill: "#fef2f2", text: "#991b1b", label: "1 person" },
  2: { stroke: "#b45309", fill: "#fffbeb", text: "#92400e", label: "2 people" },
  3: { stroke: "#15803d", fill: "#f0fdf4", text: "#166534", label: "3 or more" },
} as const;
const riskOf = (t: GraphTopic) => RISK[Math.min(Math.max(t.bus_factor, 1), 3) as 1 | 2 | 3];

const W = 800;
const H = 560;
const short = (name: string) => name.replace(/\s*\(.*\)$/, ""); // "Messaging (email sync)" -> "Messaging"
const pillWidth = (name: string, withCount: boolean) => short(name).length * 7.4 + (withCount ? 52 : 30);

// Left panel: people and topics only (artifacts never become nodes). Experts mode: click a
// topic to rank its people. Bus factor mode: topics coloured by how many experts they have,
// plus the at-risk list.
export function GraphPanel() {
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("experts");
  const [attempt, setAttempt] = useState(0);
  const { topic, setTopic } = useGraphFocus();

  useEffect(() => {
    let live = true;
    getGraph()
      .then((g) => live && (setGraph(g), setError(null)))
      .catch((e) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [attempt]);

  const focused = graph?.topics.find((t) => t.id === topic) ?? null;
  const withEvidence = focused ? graph!.edges.filter((e) => e.topic_id === focused.id).length : 0;
  const subtitle =
    mode === "bus"
      ? "Bus factor: people above the expertise threshold per topic"
      : focused
        ? `${short(focused.name)} selected · ${withEvidence} people with evidence`
        : "Who knows what across Acme · click a topic to focus";

  return (
    <section aria-label="Expertise graph" className="hidden min-h-0 flex-col rounded-xl border border-zinc-200 bg-white lg:flex">
      <header className="flex items-start justify-between gap-4 border-b border-zinc-100 px-5 py-4">
        <div>
          <h2 className="font-semibold">Expertise graph</h2>
          <p className="text-sm text-zinc-500">{subtitle}</p>
        </div>
        <div role="tablist" aria-label="Graph mode" className="flex shrink-0 rounded-lg bg-zinc-100 p-1 text-sm">
          {(
            [
              ["experts", "Experts"],
              ["bus", "Bus factor"],
            ] as const
          ).map(([m, label]) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={`rounded-md px-3 py-1.5 font-medium ${mode === m ? "bg-white text-zinc-900 shadow-sm" : "text-zinc-500 hover:text-zinc-800"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      {!graph ? (
        <div className="m-4 flex flex-1 items-center justify-center rounded-lg bg-zinc-50 text-sm text-zinc-500">
          {error ? (
            <span role="alert">
              Couldn&apos;t load the graph: {error}.{" "}
              <button onClick={() => setAttempt(attempt + 1)} className="font-medium underline">
                Try again
              </button>
            </span>
          ) : (
            "Loading the graph…"
          )}
        </div>
      ) : (
        // The graph shrinks to the panel's height (the SVG keeps its aspect ratio). In bus factor
        // mode the at-risk list sits beside it when there's room, else below (and the panel scrolls).
        <div className="@container flex min-h-0 flex-1 flex-col overflow-y-auto p-4">
          <div className="flex min-h-0 flex-1 flex-col gap-4 @3xl:flex-row">
            <div className="flex min-h-[440px] min-w-0 flex-1 flex-col">
              <Graph graph={graph} mode={mode} />
              <Legend mode={mode} threshold={graph.threshold} />
            </div>
            {mode === "bus" && (
              <div className="shrink-0 @3xl:w-64 @3xl:overflow-y-auto">
                <AtRisk graph={graph} onPick={(id) => setTopic(topic === id ? null : id)} selected={topic} />
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

type Point = { x: number; y: number };

// Fixed positions, computed once from the data (no physics running in the browser): topics on
// an ellipse; each person starts at the score-weighted middle of their topics, pulled inward,
// then a few rounds of pushing apart so nodes and labels don't overlap. Same data, same picture.
function layout(graph: GraphResponse) {
  const topicPos = new Map<string, Point>();
  graph.topics.forEach((t, i) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / graph.topics.length;
    topicPos.set(t.id, { x: W / 2 + 320 * Math.cos(a), y: H / 2 + 225 * Math.sin(a) });
  });

  const top = new Map<string, number>();
  for (const e of graph.edges) top.set(e.topic_id, Math.max(top.get(e.topic_id) ?? 0, e.score));
  const rel = (e: GraphEdge) => e.score / (top.get(e.topic_id) || 1);

  const people = graph.people.map((p) => {
    const edges = graph.edges.filter((e) => e.person_id === p.person_id && topicPos.has(e.topic_id));
    let x = 0;
    let y = 0;
    let w = 0;
    for (const e of edges) {
      const t = topicPos.get(e.topic_id)!;
      const k = rel(e) ** 4;
      x += t.x * k;
      y += t.y * k;
      w += k;
    }
    const mid = w ? { x: x / w, y: y / w } : { x: W / 2, y: H / 2 };
    return { id: p.person_id, x: W / 2 + (mid.x - W / 2) * 0.78, y: H / 2 + (mid.y - H / 2) * 0.78 };
  });

  // Push apart: people from each other (room for a name label below) and from topic pills.
  for (let round = 0; round < 300; round++) {
    for (let i = 0; i < people.length; i++) {
      const a = people[i];
      for (let j = i + 1; j < people.length; j++) {
        const b = people[j];
        const dx = b.x - a.x || 0.01 * (j - i);
        const dy = b.y - a.y || 0.01;
        // Names are wider than tall, so horizontal distance counts for less.
        const d = Math.hypot(dx / 1.35, dy);
        const min = 54;
        if (d < min) {
          const push = (min - d) / 2 / d;
          a.x -= dx * push;
          a.y -= dy * push;
          b.x += dx * push;
          b.y += dy * push;
        }
      }
      // Keep the node and its name label (about 84 x 50, label below) clear of every pill.
      for (const t of graph.topics) {
        const c = topicPos.get(t.id)!;
        const half = pillWidth(t.name, false) / 2 + 46;
        const ox = half - Math.abs(a.x - c.x);
        const oy = a.y < c.y ? 44 - (c.y - a.y) : 36 - (a.y - c.y);
        if (ox > 0 && oy > 0) {
          if (ox < oy) a.x += Math.sign(a.x - c.x || 1) * ox * 0.5;
          else a.y += (a.y < c.y ? -1 : 1) * oy * 0.5;
        }
      }
      a.x = Math.min(Math.max(a.x, 40), W - 40);
      a.y = Math.min(Math.max(a.y, 28), H - 40);
    }
  }

  const personPos = new Map(people.map((p) => [p.id, { x: p.x, y: p.y }]));
  const size = new Map<string, number>();
  for (const e of graph.edges) size.set(e.person_id, Math.max(size.get(e.person_id) ?? 0, rel(e)));
  return { topicPos, personPos, rel, size };
}

function initials(name: string) {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2);
}

function Graph({ graph, mode }: { graph: GraphResponse; mode: Mode }) {
  const { topic, person, setTopic, setPerson } = useGraphFocus();
  const { topicPos, personPos, rel, size } = useMemo(() => layout(graph), [graph]);
  const experts = useMemo(() => new Set(graph.topics.flatMap((t) => t.experts.map((p) => `${p}|${t.id}`))), [graph]);
  const focusTopic = graph.topics.some((t) => t.id === topic) ? topic : null;
  const focusPerson = person && personPos.has(person.id) ? person.id : null;

  // Unfocused, only expert edges (at or above the threshold) are drawn, so it isn't a hairball;
  // a focused topic or person shows all of its evidence. Bus factor mode: expert edges only.
  const isExpert = (e: GraphEdge) => experts.has(`${e.person_id}|${e.topic_id}`);
  const edges = graph.edges.filter((e) => isExpert(e) || (mode === "experts" && (focusTopic ? e.topic_id === focusTopic : e.person_id === focusPerson)));
  const lit = (e: GraphEdge) => (focusTopic ? e.topic_id === focusTopic : focusPerson ? e.person_id === focusPerson : false);
  const anyFocus = focusTopic !== null || focusPerson !== null;

  // Ranks shown next to names when a topic is focused: "1 · Dana Okafor".
  const rank = new Map<string, number>();
  if (focusTopic)
    graph.edges
      .filter((e) => e.topic_id === focusTopic)
      .sort((a, b) => b.score - a.score)
      .forEach((e, i) => rank.set(e.person_id, i + 1));
  const personLit = (p: GraphPerson) =>
    focusTopic ? rank.has(p.person_id) : focusPerson ? p.person_id === focusPerson : true;
  const topicLit = (t: GraphTopic) =>
    focusTopic ? t.id === focusTopic : focusPerson ? graph.edges.some((e) => e.person_id === focusPerson && e.topic_id === t.id) : true;
  const isExpertAnywhere = (id: string) => graph.topics.some((t) => t.experts.includes(id));

  // A click in the graph shows that person's topics; hovering a chat card only rings the node.
  const togglePerson = (id: string) => {
    setTopic(null);
    setPerson(focusPerson === id ? null : { id, from: "graph" });
  };
  const toggleTopic = (id: string) => {
    setPerson(null);
    setTopic(focusTopic === id ? null : id);
  };

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="group"
      aria-label={mode === "bus" ? "Bus factor graph" : "Expertise graph of people and topics"}
      className="block min-h-0 w-full flex-1 rounded-lg bg-zinc-50 select-none"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          setTopic(null);
          setPerson(null);
        }
      }}
    >
      <g>
        {edges.map((e) => {
          const a = personPos.get(e.person_id);
          const b = topicPos.get(e.topic_id);
          if (!a || !b) return null;
          const on = lit(e);
          return (
            <line
              key={`${e.person_id}|${e.topic_id}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={on ? "#1d4ed8" : "#a1a1aa"}
              strokeWidth={on ? 1 + 3.5 * rel(e) : 0.6 + 1.6 * rel(e)}
              strokeOpacity={on ? 0.9 : anyFocus ? 0.12 : 0.35}
            />
          );
        })}
      </g>

      {[...graph.people].sort((a, b) => Number(personLit(a)) - Number(personLit(b))).map((p) => {
        const pos = personPos.get(p.person_id)!;
        const r = 9 + 11 * (size.get(p.person_id) ?? 0);
        const dim = !personLit(p) || (mode === "bus" && !focusTopic && !focusPerson && !isExpertAnywhere(p.person_id));
        const n = rank.get(p.person_id);
        const selected = focusPerson === p.person_id;
        const edge = focusTopic ? graph.edges.find((e) => e.person_id === p.person_id && e.topic_id === focusTopic) : null;
        return (
          <g
            key={p.person_id}
            data-person={p.person_id}
            role="button"
            tabIndex={0}
            aria-label={`${p.name}, ${p.team}, ${Math.round(p.booked_pct * 100)}% booked`}
            aria-pressed={selected}
            opacity={dim ? 0.3 : 1}
            className="cursor-pointer outline-none"
            onClick={() => togglePerson(p.person_id)}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), togglePerson(p.person_id))}
          >
            <title>{edge ? `${p.name}: ${edge.evidence_summary}` : `${p.name} · ${p.team} · ${Math.round(p.booked_pct * 100)}% booked`}</title>
            {(n !== undefined || selected) && <circle cx={pos.x} cy={pos.y} r={r + 4} fill="white" stroke="#1d4ed8" strokeWidth={2} />}
            <circle cx={pos.x} cy={pos.y} r={r} fill={TEAM_FILL[p.team] ?? "#71717a"} />
            <text x={pos.x} y={pos.y} dy="0.35em" textAnchor="middle" fontSize={Math.max(9, r * 0.75)} fontWeight={600} fill="white">
              {initials(p.name)}
            </text>
            <text
              x={pos.x}
              y={pos.y + r + 13}
              textAnchor="middle"
              fontSize={11}
              fill={n !== undefined || selected ? "#18181b" : "#71717a"}
              fontWeight={n !== undefined || selected ? 500 : 400}
              stroke="#fafafa"
              strokeWidth={3}
              paintOrder="stroke"
            >
              {n !== undefined ? `${n} · ${p.name}` : p.name}
            </text>
          </g>
        );
      })}

      {graph.topics.map((t) => {
        const pos = topicPos.get(t.id)!;
        const label = short(t.name);
        const risk = riskOf(t);
        const bus = mode === "bus";
        const w = pillWidth(t.name, bus);
        const selected = focusTopic === t.id;
        const dim = !topicLit(t);
        return (
          <g
            key={t.id}
            data-topic={t.id}
            role="button"
            tabIndex={0}
            aria-label={`${t.name}, ${t.bus_factor} expert${t.bus_factor === 1 ? "" : "s"}`}
            aria-pressed={selected}
            opacity={dim ? 0.45 : 1}
            className="cursor-pointer outline-none"
            onClick={() => toggleTopic(t.id)}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), toggleTopic(t.id))}
          >
            {bus && selected && <rect x={pos.x - w / 2 - 4} y={pos.y - 19} width={w + 8} height={38} rx={19} fill="none" stroke="#1d4ed8" strokeWidth={2} />}
            <rect
              x={pos.x - w / 2}
              y={pos.y - 15}
              width={w}
              height={30}
              rx={15}
              fill={bus ? risk.fill : selected ? "#eff6ff" : "white"}
              stroke={bus ? risk.stroke : selected ? "#1d4ed8" : "#d4d4d8"}
              strokeWidth={selected ? 2.5 : bus ? 1.75 : 1.25}
            />
            <text
              x={bus ? pos.x - 11 : pos.x}
              y={pos.y}
              dy="0.35em"
              textAnchor="middle"
              fontSize={13}
              fontWeight={600}
              fill={bus ? risk.text : selected ? "#1e3a8a" : "#3f3f46"}
            >
              {label}
            </text>
            {bus && (
              <>
                <circle cx={pos.x + w / 2 - 17} cy={pos.y} r={9} fill="white" />
                <text x={pos.x + w / 2 - 17} y={pos.y} dy="0.35em" textAnchor="middle" fontSize={11} fontWeight={600} fill={risk.text}>
                  {t.bus_factor}
                </text>
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}

function Legend({ mode, threshold }: { mode: Mode; threshold: number }) {
  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 text-xs text-zinc-600">
      <ul className="flex flex-wrap gap-x-4 gap-y-1">
        {mode === "experts"
          ? Object.entries(TEAM_FILL).map(([team, fill]) => (
              <li key={team} className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-full" style={{ background: fill }} />
                {team}
              </li>
            ))
          : Object.values(RISK).map((r) => (
              <li key={r.label} className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-full" style={{ background: r.stroke }} />
                {r.label}
              </li>
            ))}
      </ul>
      <p className="text-zinc-500">
        {mode === "experts"
          ? "Node size = expertise score · line weight = evidence strength · click a topic to focus"
          : `Expert = at least ${Math.round(threshold * 100)}% of the topic's top score · click a topic to focus`}
      </p>
    </div>
  );
}

// Topics with one or two experts, single-expert topics first.
function AtRisk({ graph, onPick, selected }: { graph: GraphResponse; onPick: (topicId: string) => void; selected: string | null }) {
  const person = (id: string) => graph.people.find((p) => p.person_id === id);
  const nameOf = (id: string) => person(id)?.name ?? id;
  const risky = graph.topics.filter((t) => t.bus_factor <= 2).sort((a, b) => a.bus_factor - b.bus_factor);
  return (
    <section aria-label="At risk" className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">At risk</h3>
      {risky.length === 0 && <p className="text-sm text-zinc-500">Every topic has three or more experts.</p>}
      <div className="grid gap-2 @xl:grid-cols-2 @3xl:grid-cols-1">
        {risky.map((t) => {
          const risk = riskOf(t);
          const only = t.experts[0];
          const busy = only ? person(only) : undefined;
          const next = t.next_closest ? graph.edges.find((e) => e.person_id === t.next_closest && e.topic_id === t.id) : undefined;
          return (
            <button
              key={t.id}
              onClick={() => onPick(t.id)}
              aria-pressed={selected === t.id}
              aria-label={`${short(t.name)}: ${t.bus_factor} expert${t.bus_factor === 1 ? "" : "s"}`}
              className={`rounded-xl border bg-white p-3.5 text-left text-sm hover:shadow-sm ${selected === t.id ? "ring-2 ring-blue-600" : ""}`}
              style={{ borderColor: risk.stroke }}
            >
              <span className="flex items-baseline justify-between gap-3">
                <span className="font-semibold">{short(t.name)}</span>
                <span className="shrink-0 text-xs font-semibold" style={{ color: risk.text }}>
                  {t.bus_factor} expert{t.bus_factor === 1 ? "" : "s"}
                </span>
              </span>
              {t.bus_factor === 1 && only ? (
                <>
                  <span className="mt-1 block text-zinc-700">
                    Only {nameOf(only)}.
                    {busy && busy.booked_pct >= 0.7 && ` ${firstName(only)} is also ${Math.round(busy.booked_pct * 100)}% booked this week.`}
                  </span>
                  {t.next_closest && (
                    <span className="mt-1 block text-xs text-zinc-500">
                      Next closest: {nameOf(t.next_closest)}
                      {next && ` (${next.evidence_summary.split(", ").slice(0, 2).join(", ")})`}
                    </span>
                  )}
                </>
              ) : (
                <span className="mt-1 block text-zinc-700">{t.experts.map(nameOf).join(", ")}</span>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}
