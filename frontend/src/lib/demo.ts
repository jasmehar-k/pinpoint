// Demo persona and starter questions. The questions are worded exactly as in
// backend/tests/test_demo.py, so the demo asks what the golden tests check.

export const DEMO_USER = { id: "priya-shah", name: "Priya Shah", team: "Integrations", org: "Acme Engineering", day: 3 };

// "How does inbound email sync work?" is left out on purpose: the demo video types it.
export const SUGGESTED_QUESTIONS = [
  "How are subscriptions and plan upgrades billed?",
  "How do workflow triggers and actions run?",
  "Why does my Gmail mailbox import keep failing?",
];
