import type { ReactNode } from "react";

import type { Approval } from "./useApproval";

// Frame shared by the DM and meeting approve cards: a header strip, then the body.
// A dismissed card collapses to one line.
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
  title: ReactNode;
  aside?: ReactNode;
  dismissed: string | null;
  children: ReactNode;
}) {
  if (dismissed) {
    return (
      <article id={id} aria-label={label} className="rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-500">
        <span className="font-medium text-zinc-700">{title}</span> · <span role="status">{dismissed}</span>
      </article>
    );
  }
  return (
    <article id={id} aria-label={label} className="overflow-hidden rounded-xl border border-zinc-200 bg-white">
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-zinc-100 bg-zinc-50 px-4 py-2.5">
        <h4 className="flex items-center gap-2 text-sm">{title}</h4>
        {aside}
      </header>
      <div className="p-4">{children}</div>
    </article>
  );
}

// Approve + cancel/dismiss, the working label, a note ("Edited") and the error from the last attempt.
export function ActionButtons({
  state,
  approveLabel,
  workingLabel,
  disabled,
  note,
  errorPrefix,
  onApprove,
  onDismiss,
  dismissLabel = "Dismiss",
  extra,
}: {
  state: Approval;
  approveLabel: string;
  workingLabel: string;
  disabled?: boolean;
  note?: string;
  errorPrefix: string;
  onApprove: () => void;
  onDismiss: () => void;
  dismissLabel?: string;
  extra?: ReactNode; // more buttons between approve and dismiss
}) {
  const working = state.phase === "working";
  const draft = state.phase === "draft" ? state : null;
  return (
    <footer className="mt-4 flex flex-wrap items-center gap-3 border-t border-zinc-100 pt-4">
      <button
        onClick={onApprove}
        disabled={!draft || draft.stuck || disabled}
        className="h-10 rounded-lg bg-blue-700 px-4 text-sm font-medium text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
      >
        {working && !state.dismissing ? workingLabel : approveLabel}
      </button>
      {extra}
      {draft && note && <span className="text-xs text-zinc-500">{note}</span>}
      <button
        onClick={onDismiss}
        disabled={!draft}
        className="ml-auto h-10 rounded-lg px-3 text-sm font-medium text-zinc-600 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:text-zinc-400"
      >
        {working && state.dismissing ? `${dismissLabel === "Cancel" ? "Cancelling" : "Dismissing"}…` : dismissLabel}
      </button>
      {draft?.error && (
        <span role="alert" className="basis-full text-sm text-red-700">
          {draft.stuck ? draft.error : `${errorPrefix}: ${draft.error}`}
        </span>
      )}
    </footer>
  );
}
