// taghag-server — server-side Supabase handlers via @supabase/server.
//
// withSupabase({ auth }, handler) validates the inbound request and hands your
// handler a context:
//   ctx.supabase       RLS-scoped client (the caller's own permissions)
//   ctx.supabaseAdmin  admin client that BYPASSES RLS (uses SUPABASE_SECRET_KEY)
//   ctx.userClaims     JWT identity (id, email, role) — null for non-"user" auth
//   ctx.jwtClaims      raw JWT payload — null for non-"user" auth
//   ctx.authMode       which mode matched: "user" | "publishable" | "secret" | "none"
//
// Env (loaded from ../.env via the npm scripts):
//   SUPABASE_URL            always
//   SUPABASE_SECRET_KEY     for auth:"secret" or any ctx.supabaseAdmin use
//   SUPABASE_PUBLISHABLE_KEY for auth:"publishable"
//   SUPABASE_JWKS_URL       for auth:"user" (verifies user JWTs)
//
// The bare `withSupabase(...)` result is a standard Web fetch handler
// (req: Request) => Promise<Response>. On Deno / Supabase Edge Functions you'd
// `export default { fetch: handler }`; on Node we serve it with @hono/node-server.
import { serve } from "@hono/node-server"
import { withSupabase } from "@supabase/server"

// Example: an authenticated endpoint. RLS scopes the query to the caller.
const handler = withSupabase({ auth: "user" }, async (_req, ctx) => {
  const { data, error } = await ctx.supabase.from("todos").select()
  if (error) return Response.json({ message: error.message, code: error.code }, { status: 400 })
  return Response.json(data)
})

const port = Number(process.env.PORT ?? 3000)
serve({ fetch: handler, port })
console.log(`taghag-server listening on http://localhost:${port}`)
