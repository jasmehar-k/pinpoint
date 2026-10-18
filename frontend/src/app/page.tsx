import { Chat } from "@/components/Chat";
import { GraphFocusProvider } from "@/components/graphFocus";
import { GraphPanel } from "@/components/GraphPanel";
import { Header } from "@/components/Header";

// Off shows the chat alone, centered.
const SHOW_GRAPH = true;

// With the graph: graph on the left, chat on the right (below lg, chat only).
// Without it: the chat panel centered at a readable width.
export default function Home() {
  return (
    <div className="flex h-dvh flex-col">
      <Header />
      {SHOW_GRAPH ? (
        <main className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] gap-5 p-3 sm:p-4 lg:grid-cols-[minmax(0,1fr)_minmax(400px,470px)] lg:p-6">
          <GraphFocusProvider>
            <GraphPanel />
            <Chat />
          </GraphFocusProvider>
        </main>
      ) : (
        <main className="flex min-h-0 flex-1 justify-center p-3 sm:p-4 lg:p-6">
          <div className="flex min-h-0 w-full max-w-3xl flex-col [&>section]:flex-1">
            <Chat />
          </div>
        </main>
      )}
    </div>
  );
}
