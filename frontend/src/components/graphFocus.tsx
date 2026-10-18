"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

// What the graph and the chat both highlight: a topic (from a graph click or the latest
// answer) and a person (hovering an expert card, or clicking a person in the graph).
type Focus = {
  topic: string | null;
  person: { id: string; from: "graph" | "chat" } | null;
  setTopic: (topic: string | null) => void;
  setPerson: (person: Focus["person"]) => void;
};

const GraphFocus = createContext<Focus>({ topic: null, person: null, setTopic: () => {}, setPerson: () => {} });

export function GraphFocusProvider({ children }: { children: ReactNode }) {
  const [topic, setTopic] = useState<string | null>(null);
  const [person, setPerson] = useState<Focus["person"]>(null);
  return <GraphFocus.Provider value={{ topic, person, setTopic, setPerson }}>{children}</GraphFocus.Provider>;
}

export function useGraphFocus(): Focus {
  return useContext(GraphFocus);
}
