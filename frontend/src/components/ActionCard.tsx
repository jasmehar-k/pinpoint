import type { ReactNode } from "react";

import type { Approval } from "./useApproval";

// Frame shared by the DM and meeting approve cards. A dismissed card collapses to one line.
export function CardShell({
  id,
  label,
  title,
  aside,
  dismissed,
  children,
}: {
  id?: string;
  label: string;
  title: string;
  aside: string;
  dismissed: string | null;
  children: ReactNode;
}) {
  if (dismissed) {
    return (
      <article id={id} aria-label={label} className="rounded-xl border border-zinc-200 px-4 py-3 text-sm text-zinc-500 dark:border-zinc-800">
        <span className="font-medium text-zinc-700 dark:text-zinc-300">{title}</span> · <span role="status">{dismissed}</span>
      </article>
    );
  }
  return (
    <article id={id} aria-label={label} className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 dark:border-blue-900 dark:bg-blue-950/30">
      <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h4 className="font-semibold">{title}</h4>
        <span className="text-xs text-zinc-500">{aside}</span>
      </header>
      {children}
    </article>
  );
}

// Approve + Dismiss, the working label, a note ("Edited") and the error from the last attempt.
export function ActionButtons({
  state,
  approveLabel,
  workingLabel,
  disabled,
  note,
  errorPrefix,
  onApprove,
  onDismiss,
}: {
  state: Approval;
  approveLabel: string;
  workingLabel: string;
  disabled?: boolean;
  note?: string;
  errorPrefix: string;
  onApprove: () => void;
  onDismiss: () => void;
}) {
  const working = state.phase === "working";
  const draft = state.phase === "draft" ? state : null;
  return (
    <footer className="mt-3 flex flex-wrap items-center gap-3">
      <button
        onClick={onApprove}
        disabled={!draft || draft.stuck || disabled}
        className="h-10 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-zinc-300 dark:disabled:bg-zinc-700"
      >
        {working && !state.dismissing ? workingLabel : approveLabel}
      </button>
      <button
        onClick={onDismiss}
        disabled={!draft}
        className="h-10 rounded-lg px-3 text-sm font-medium text-zinc-600 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:text-zinc-400 dark:text-zinc-400 dark:hover:bg-zinc-800"
      >
        {working && state.dismissing ? "Dismissing…" : "Dismiss"}
      </button>
      {draft && note && <span className="text-xs text-zinc-500">{note}</span>}
      {draft?.error && (
        <span role="alert" className="basis-full text-sm text-red-700 dark:text-red-300">
          {draft.stuck ? draft.error : `${errorPrefix}: ${draft.error}`}
        </span>
      )}
    </footer>
  );
}
