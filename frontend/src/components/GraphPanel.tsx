// Left panel. Holds the expertise graph once GET /graph exists; until then, an empty frame
// with the same title so the two-panel layout is in place.
export function GraphPanel() {
  return (
    <section aria-label="Expertise graph" className="hidden min-h-0 flex-col rounded-xl border border-zinc-200 bg-white lg:flex">
      <header className="border-b border-zinc-100 px-5 py-4">
        <h2 className="font-semibold">Expertise graph</h2>
        <p className="text-sm text-zinc-500">Who knows what across Acme</p>
      </header>
      <div className="m-4 flex flex-1 items-center justify-center rounded-lg border border-dashed border-zinc-200 bg-zinc-50 text-sm text-zinc-400">
        Topics and experts will show here.
      </div>
    </section>
  );
}
