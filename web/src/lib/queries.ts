import { getSupabaseClient } from "./supabase";
import type { Database, Json } from "./database.types";

type Tables = Database["public"]["Tables"];
export type ImportRun = Tables["import_run"]["Row"];
export type Mp3File = Tables["mp3_file"]["Row"];
export type DjTag = Tables["dj_tag"]["Row"];
export type QualityCheck = Tables["quality_check"]["Row"];
export type TagEvidence = Tables["tag_evidence"]["Row"];
export type Crate = Tables["crate"]["Row"];

export type LibraryFilters = {
  genre?: string | null;
  key?: string | null;
  quality?: string | null;
  providerStatus?: string | null;
  bpmMin?: number | null;
  bpmMax?: number | null;
};

export type LibraryTrack = {
  file: Mp3File;
  tag: DjTag | null;
  latestQuality: QualityCheck | null;
  latestEvidence: TagEvidence | null;
};

export type DashboardCounts = {
  totalMp3s: number;
  missingArtistTitle: number;
  missingBpmKey: number;
  missingGenreSubgenre: number;
  missingLabel: number;
  duplicateChecksumCandidates: number;
  evidenceStatuses: Record<string, number>;
};

function asArray(value: Json): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

export async function listImportRuns(): Promise<ImportRun[]> {
  const supabase = getSupabaseClient();
  const { data, error } = await supabase
    .from("import_run")
    .select("*")
    .order("started_at", { ascending: false })
    .limit(50);
  if (error) throw error;
  return data ?? [];
}

export async function listLibraryTracks(filters: LibraryFilters = {}): Promise<LibraryTrack[]> {
  const supabase = getSupabaseClient();
  const { data: files, error: fileError } = await supabase
    .from("mp3_file")
    .select("*")
    .order("filename", { ascending: true })
    .limit(200);
  if (fileError) throw fileError;

  const fileIds = (files ?? []).map((file) => file.id);
  if (fileIds.length === 0) return [];

  const [{ data: tags, error: tagError }, { data: quality, error: qualityError }, { data: evidence, error: evidenceError }] =
    await Promise.all([
      supabase.from("dj_tag").select("*").in("mp3_file_id", fileIds),
      supabase
        .from("quality_check")
        .select("*")
        .in("mp3_file_id", fileIds)
        .order("checked_at", { ascending: false }),
      supabase
        .from("tag_evidence")
        .select("*")
        .in("mp3_file_id", fileIds)
        .order("fetched_at", { ascending: false }),
    ]);
  if (tagError) throw tagError;
  if (qualityError) throw qualityError;
  if (evidenceError) throw evidenceError;

  const tagsByFile = new Map((tags ?? []).map((tag) => [tag.mp3_file_id, tag]));
  const qualityByFile = new Map<string, QualityCheck>();
  for (const row of quality ?? []) {
    if (!qualityByFile.has(row.mp3_file_id)) qualityByFile.set(row.mp3_file_id, row);
  }
  const evidenceByFile = new Map<string, TagEvidence>();
  for (const row of evidence ?? []) {
    if (!evidenceByFile.has(row.mp3_file_id)) evidenceByFile.set(row.mp3_file_id, row);
  }

  return (files ?? [])
    .map((file) => ({
      file,
      tag: tagsByFile.get(file.id) ?? null,
      latestQuality: qualityByFile.get(file.id) ?? null,
      latestEvidence: evidenceByFile.get(file.id) ?? null,
    }))
    .filter((track) => {
      if (filters.genre && track.tag?.canonical_genre !== filters.genre) return false;
      if (filters.key && track.tag?.musical_key !== filters.key) return false;
      if (filters.bpmMin && (track.tag?.bpm ?? 0) < filters.bpmMin) return false;
      if (filters.bpmMax && (track.tag?.bpm ?? Number.MAX_SAFE_INTEGER) > filters.bpmMax) return false;
      if (filters.providerStatus && track.latestEvidence?.status !== filters.providerStatus) return false;
      if (filters.quality && !asArray(track.latestQuality?.issue_codes_json ?? []).includes(filters.quality)) {
        return false;
      }
      return true;
    });
}

export async function getTrackDetail(id: string): Promise<LibraryTrack | null> {
  const tracks = await listLibraryTracks();
  return tracks.find((track) => track.file.id === id) ?? null;
}

export async function listCrates(): Promise<Crate[]> {
  const supabase = getSupabaseClient();
  const { data, error } = await supabase.from("crate").select("*").order("sort_order", { ascending: true });
  if (error) throw error;
  return data ?? [];
}

export async function getDashboardCounts(): Promise<DashboardCounts> {
  const tracks = await listLibraryTracks();
  const evidenceStatuses: Record<string, number> = {};
  let duplicateChecksumCandidates = 0;

  for (const track of tracks) {
    const evidenceStatus = track.latestEvidence?.status ?? "none";
    evidenceStatuses[evidenceStatus] = (evidenceStatuses[evidenceStatus] ?? 0) + 1;
    if (asArray(track.latestQuality?.duplicate_flags_json ?? []).length > 0) {
      duplicateChecksumCandidates += 1;
    }
  }

  return {
    totalMp3s: tracks.length,
    missingArtistTitle: tracks.filter((track) => !track.tag?.artist || !track.tag?.title).length,
    missingBpmKey: tracks.filter((track) => !track.tag?.bpm || !track.tag?.musical_key).length,
    missingGenreSubgenre: tracks.filter(
      (track) => !track.tag?.canonical_genre || !track.tag?.canonical_subgenre,
    ).length,
    missingLabel: tracks.filter((track) => !track.tag?.label).length,
    duplicateChecksumCandidates,
    evidenceStatuses,
  };
}

