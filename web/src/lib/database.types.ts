export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

type Table<Row, Insert = Row, Update = Partial<Insert>> = {
  Row: Row;
  Insert: Insert;
  Update: Update;
  Relationships: never[];
};

export type Database = {
  public: {
    Tables: {
      import_run: Table<{
        id: string;
        owner_user_id: string;
        run_name: string | null;
        source_root: string | null;
        status: "pending" | "running" | "completed" | "failed" | "cancelled";
        started_at: string;
        completed_at: string | null;
        tool_versions_json: Json;
        summary_json: Json;
        created_at: string;
        updated_at: string;
      }>;
      audio_file: Table<{
        id: string;
        owner_user_id: string;
        file_key: string;
        path: string;
        filename: string;
        size_bytes: number | null;
        mtime_ns: number | null;
        duration_s: number | null;
        bitrate_kbps: number | null;
        codec: "flac" | "mp3";
        checksum_sha256: string | null;
        checksum_prefix: string | null;
        identity_source: string | null;
        identity_confidence: number | null;
        first_seen_at: string;
        last_seen_at: string;
        created_at: string;
        updated_at: string;
      }>;
      audio_observation: Table<{
        id: string;
        owner_user_id: string;
        import_run_id: string;
        audio_file_id: string | null;
        observed_path: string;
        observed_size_bytes: number | null;
        observed_mtime_ns: number | null;
        observed_checksum_sha256: string | null;
        status: "observed" | "imported" | "skipped" | "out_of_scope" | "failed";
        issue_json: Json;
        created_at: string;
        updated_at: string;
      }>;
      dj_tag: Table<{
        id: string;
        owner_user_id: string;
        audio_file_id: string;
        artist: string | null;
        title: string | null;
        album: string | null;
        label: string | null;
        catalog_number: string | null;
        release_date: string | null;
        year: number | null;
        bpm: number | null;
        musical_key: string | null;
        canonical_genre: string | null;
        canonical_subgenre: string | null;
        isrc: string | null;
        compilation: boolean | null;
        rating: number | null;
        energy: string | null;
        role: string | null;
        notes: string | null;
        tag_source: string | null;
        manual_override: boolean;
        created_at: string;
        updated_at: string;
      }>;
      tag_evidence: Table<{
        id: string;
        owner_user_id: string;
        audio_file_id: string;
        provider: string;
        lookup_type: string;
        lookup_key: string;
        provider_track_id: string | null;
        status: "matched" | "no_match" | "ambiguous" | "error" | "malformed" | "duplicate";
        confidence: number | null;
        winning_fields_json: Json;
        candidates_json: Json;
        raw_marker_json: Json;
        fetched_at: string;
        created_at: string;
        updated_at: string;
      }>;
      quality_check: Table<{
        id: string;
        owner_user_id: string;
        import_run_id: string | null;
        audio_file_id: string;
        decode_ok: boolean | null;
        duration_ok: boolean | null;
        bitrate_ok: boolean | null;
        missing_tag_flags_json: Json;
        duplicate_flags_json: Json;
        issue_codes_json: Json;
        tool_name: string | null;
        tool_version: string | null;
        checked_at: string;
        created_at: string;
        updated_at: string;
      }>;
      crate: Table<{
        id: string;
        owner_user_id: string;
        name: string;
        description: string | null;
        sort_order: number;
        created_at: string;
        updated_at: string;
      }>;
      crate_track: Table<{
        id: string;
        owner_user_id: string;
        crate_id: string;
        audio_file_id: string;
        position: number;
        notes: string | null;
        created_at: string;
        updated_at: string;
      }>;
      saved_view: Table<{
        id: string;
        owner_user_id: string;
        name: string;
        route: string;
        filters_json: Json;
        sort_json: Json;
        chart_state_json: Json;
        created_at: string;
        updated_at: string;
      }>;
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
};

