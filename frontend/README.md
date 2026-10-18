# Pinpoint frontend

Next.js 16 chat UI. Next 16 has breaking changes, so read `AGENTS.md` and the docs in `node_modules/next/dist/docs/` before writing code.

## Run

```
npm install
npm run dev        # http://localhost:3000
npm run lint
npm run typecheck  # next typegen + tsc; plain tsc fails on a clean checkout
npm run build
```

Create `frontend/.env.local` (Next doesn't read the repo-root `.env`):

```
NEXT_PUBLIC_USE_FIXTURES=1
NEXT_PUBLIC_API_URL=http://localhost:8000
```

`1` serves every response from `/fixtures` (via the `public/fixtures` symlink), so no backend is needed. Set `0` to call the API at `NEXT_PUBLIC_API_URL`, then restart `npm run dev`.

## Layout

- `src/lib/api.ts`: every backend call, in fixture or real mode
- `src/lib/types.ts`: mirrors `backend/schema.py`. Change it together with the model and the fixture.
- `src/lib/time.ts`: formats times in Pacific, the org timezone
