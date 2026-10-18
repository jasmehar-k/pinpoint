// Seeded thread titles look like "#help: how does X work? trying to figure out why a test mailb..."
// (the backend cuts them at 80 chars). These keep the channel and the question, dropping the cut-off tail.

// "#help: how does…" -> { channel: "help", title: "how does…" }. PR titles pass through.
export function splitTitle(raw: string | null): { channel?: string; title: string } {
  const match = raw?.match(/^#([\w-]+):\s+([\s\S]*)$/);
  return match ? { channel: match[1], title: match[2] } : { title: raw ?? "Untitled" };
}

// "how does X work? trying to..." -> "How does X work?"
export function questionOf(title: string): string {
  const q = title.match(/^[^?]*\?/)?.[0] ?? title;
  return q.charAt(0).toUpperCase() + q.slice(1);
}

// For lists of sources: "#help: How does X work?" for threads, PR titles unchanged.
export function displayTitle(raw: string): string {
  const { channel, title } = splitTitle(raw);
  return channel ? `#${channel}: ${questionOf(title)}` : raw;
}
