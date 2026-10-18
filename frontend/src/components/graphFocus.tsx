"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

export type GraphMode = "experts" | "bus";

// Shared by the graph, the chat and the command palette: the focused topic (from a graph
// click, the latest answer or the palette), the focused person (hovering an expert card, or
// clicking a person in the graph), the graph mode, and a handle to ask the chat a question.
type Focus = {
  topic: string | null;
  person: { id: string; from: "graph" | "chat" } | null;
  mode: GraphMode;
  setTopic: (topic: string | null) => void;
  setPerson: (person: Focus["person"]) => void;
  setMode: (mode: GraphMode) => void;
  registerAsk: (ask: ((question: string) => void) | null) => void; // the chat registers itself
  ask: (question: string) => void; // sends a question to the registered chat
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
};

const GraphFocus = createContext<Focus>({
  topic: null,
  person: null,
  mode: "experts",
  setTopic: () => {},
  setPerson: () => {},
  setMode: () => {},
  registerAsk: () => {},
  ask: () => {},
  paletteOpen: false,
  setPaletteOpen: () => {},
});

export function GraphFocusProvider({ children }: { children: ReactNode }) {
  const [topic, setTopic] = useState<string | null>(null);
  const [person, setPerson] = useState<Focus["person"]>(null);
  const [mode, setMode] = useState<GraphMode>("experts");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const askRef = useRef<((question: string) => void) | null>(null);
  const registerAsk = useCallback((fn: ((question: string) => void) | null) => {
    askRef.current = fn;
  }, []);
  const ask = useCallback((q: string) => askRef.current?.(q), []);
  return (
    <GraphFocus.Provider value={{ topic, person, mode, setTopic, setPerson, setMode, registerAsk, ask, paletteOpen, setPaletteOpen }}>{children}</GraphFocus.Provider>
  );
}

export function useGraphFocus(): Focus {
  return useContext(GraphFocus);
}
