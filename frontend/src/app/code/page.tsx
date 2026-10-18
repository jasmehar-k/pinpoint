import type { Metadata } from "next";

import { CodeBrowser } from "@/components/code/CodeBrowser";

export const metadata: Metadata = { title: "Acme Code · Pinpoint" };

// A stand-in code browser with Pinpoint's floating bubble on it: one frozen, real file.
export default function CodePage() {
  return <CodeBrowser />;
}
