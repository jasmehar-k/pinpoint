import { Chat } from "@/components/Chat";
import { GraphPanel } from "@/components/GraphPanel";
import { Header } from "@/components/Header";

// Graph on the left, chat on the right. Below lg the graph is hidden and the chat fills the screen.
export default function Home() {
  return (
    <div className="flex h-dvh flex-col">
      <Header />
      <main className="grid min-h-0 flex-1 gap-5 p-3 sm:p-4 lg:grid-cols-[minmax(0,1fr)_minmax(400px,470px)] lg:p-6">
        <GraphPanel />
        <Chat />
      </main>
    </div>
  );
}
