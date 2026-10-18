// What the floating bubble knows about the page it sits on: the file and any selected lines.
// Two switch points for when the backend catches up:
//   - getPathExperts: derives "who knows this file" from GET /graph via the path's topic.
//     Swap the body for GET /experts?path= once it exists.
//   - withPageContext: puts the context in the message text. Swap for ChatRequest.context
//     (and send the bare question) once that field exists.

import { getGraph } from "./api";
import { topicForPath, topicName } from "./topics";
import type { GraphPerson } from "./types";

export type PageContext = {
  path: string;
  lines?: { start: number; end: number; text: string }; // 1-based, inclusive
};

export type PathExpert = GraphPerson & { score: number; evidence_summary: string };

export type PathExperts = { topicId: string; topicName: string; people: PathExpert[] };

// Top three people on the file's topic, by expertise score.
export async function getPathExperts(path: string): Promise<PathExperts | null> {
  const topicId = topicForPath(path);
  if (!topicId) return null;
  const graph = await getGraph();
  const people = graph.edges
    .filter((e) => e.topic_id === topicId)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .flatMap((e) => {
      const p = graph.people.find((x) => x.person_id === e.person_id);
      return p ? [{ ...p, score: e.score, evidence_summary: e.evidence_summary }] : [];
    });
  const name = graph.topics.find((t) => t.id === topicId)?.name ?? topicName(topicId);
  return { topicId, topicName: name, people };
}

export const MAX_CONTEXT_LINES = 12;

// "About <path>, lines 80-84:" then the selected code in a fence, a blank line, the question.
// Plain hyphen in the range so the text is easy to copy into demo_questions.py exactly.
export function withPageContext(question: string, ctx?: PageContext | null): string {
  if (!ctx) return question;
  if (!ctx.lines) return `About ${ctx.path}:\n\n${question}`;
  const { start, end, text } = ctx.lines;
  return `About ${ctx.path}, lines ${start}-${end}:\n\`\`\`\n${text}\n\`\`\`\n\n${question}`;
}
