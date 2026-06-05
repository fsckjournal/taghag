import { createClient } from "@supabase/supabase-js";
import type { Database } from "./database.types";

let client: ReturnType<typeof createClient<Database>> | null = null;

export function getSupabaseClient() {
  const url = import.meta.env.VITE_SUPABASE_URL;
  const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

  if (!url) {
    throw new Error("VITE_SUPABASE_URL is required for the Taghag web app.");
  }
  if (!publishableKey) {
    throw new Error("VITE_SUPABASE_PUBLISHABLE_KEY is required for the Taghag web app.");
  }

  client ??= createClient<Database>(url, publishableKey);
  return client;
}

