import type { Metadata } from "next";

import { ArtifactView } from "@/components/ArtifactView";
import { Header } from "@/components/Header";

export const metadata: Metadata = { title: "Thread · Pinpoint" };

// Ids can contain colons (slack:C0…:179…). Decode in case the segment arrives
// percent-encoded; decoding an already-decoded id is a no-op for these ids.
function decodeId(raw: string): string {
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

export default async function ArtifactPage({ params }: PageProps<"/artifacts/[id]">) {
  const { id } = await params;
  return (
    <div className="flex min-h-dvh flex-col">
      <Header />
      <main className="mx-auto w-full max-w-3xl px-4">
        <ArtifactView id={decodeId(id)} />
      </main>
    </div>
  );
}
