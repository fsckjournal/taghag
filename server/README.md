# taghag-server

Server-side Supabase handlers via [`@supabase/server`](https://github.com/supabase/server).
Holds the **secret key** and an admin (RLS-bypassing) client — this directory must
**never** be bundled to the browser (that's `web/`, which only gets `VITE_*` / publishable values).

## Install

> The agent could not run `npm install` (auto-mode blocks session-added packages).
> Run it yourself — the package is the official `@supabase/server` (npm scope
> `@supabase`, repo `github.com/supabase/server`, no install scripts):

```bash
cd server
npm install
```

## Configure

Real values go in the repo-root `.env` (gitignored). Template is in `.env.example`:

```env
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...          # server-side only — never commit
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
SUPABASE_JWKS_URL=https://<ref>.supabase.co/auth/v1/.well-known/jwks.json
```

The SDK reads the plural forms (`SUPABASE_SECRET_KEYS={"default":...}`) first, then
these singular fallbacks. Only set the keys for the auth modes you use.

## Run

```bash
npm run dev    # node --env-file=../.env --watch index.js
npm start
```

`index.js` is a template — one `auth: "user"` endpoint served on `:3000` via
`@hono/node-server`. Swap in your routes / framework adapter as needed.

## Auth modes

`withSupabase({ auth }, handler)` — `"user"` (valid JWT), `"publishable"`,
`"secret"`, or `"none"`. The handler runs only on successful auth; `ctx` exposes
`supabase` (RLS-scoped), `supabaseAdmin` (bypasses RLS), `userClaims`, `jwtClaims`,
`authMode`.

## Supabase Edge Functions instead?

If you deploy as an Edge Function rather than this Node server, the env vars are
injected automatically and you use the `export default { fetch: handler }` form.
For `auth` other than `"user"`, disable the platform JWT check in
`supabase/config.toml`:

```toml
[functions.<name>]
verify_jwt = false
```
