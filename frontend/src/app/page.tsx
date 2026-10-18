import { Chat } from "@/components/Chat";
import { Header } from "@/components/Header";

export default function Home() {
  return (
    <div className="flex h-dvh flex-col">
      <Header />
      <Chat />
    </div>
  );
}
