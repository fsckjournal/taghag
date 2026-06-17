# Multi-Platform DSP Metadata Integration & Canonical Identity Resolution Specification

## 1. Purpose and Scope  
This document defines a vendor-neutral architecture for a **unified music metadata integration gateway**. It addresses the fragmentation of the streaming ecosystem (Spotify, Tidal, Qobuz, Beatport) by standardizing how a backend system retrieves and normalizes entity data (tracks, albums/releases, artists, etc.) from each DSP. The goal is to ensure catalog **data integrity** across platforms: all entity lookups should be deterministic (using IDs/ISRC/UPC rather than fuzzy search), and payload schemas must be mathematically normalized. The integration must be robust against provider differences in authentication, routing, and metadata formats.

## 2. Evidence and Risk Classification  
All claims below are marked by their source:

- **Official (Public API)** – Verified by provider documentation (e.g. Spotify or TIDAL developer sites).  
- **Official (Policy/Terms)** – DSP-imposed rules (Spotify developer terms, etc.).  
- **Third-Party** – Community or vendor libraries (e.g. OAuth middleware, open-source connectors).  
- **Reverse-Engineered (Undocumented)** – Observations from unofficial docs or code (Beatport Gists, Qobuz plugins).  
- **Defensive Recommendation** – Best practices not mandated by API but advised (rate-limits, retries).  
- **Unverified Claim** – Lacking authoritative confirmation (flagged for review).  

All substantive integration details are preserved; uncertain items are explicitly flagged below.

## 3. Provider Access Model  

### Spotify (Official Public API)  
- **Access Model:** OAuth 2.0 Client Credentials flow. The gateway obtains an access token and injects it as `Authorization: Bearer {token}` in all requests. (Official behavior.)  
- **Endpoints:**  
  - **By ID:** GET `https://api.spotify.com/v1/tracks/{id}`, `/albums/{id}` (Official).  
  - **By ISRC/UPC:** Use the search endpoint with filters. For example:  
    - Tracks by ISRC: `GET /v1/search?type=track&q=isrc:{ISRC}` (Official).  
    - Albums by UPC: `GET /v1/search?type=album&q=upc:{UPC}` (Official).  
  - **Market:** All catalog queries must include a `market=ISO3166-1 alpha-2` parameter to ensure regionally available content. (E.g. `market=US`, etc.) This is required for tracks/albums to be returned as playable.  
- **Metadata Features:**  
  - **Release Date:** Spotify returns `release_date` and a `release_date_precision` field (year/month/day), which guides how to interpret partial dates.  
  - **Duration:** Provided as `duration_ms` in milliseconds (no conversion needed for the canonical model).  
  - **Artists:** Array of simplified artist objects with `name`, `id`, etc.  
  - **External IDs:** Spotify exposes `external_ids` with `isrc`, `ean`, `upc`. These map directly to canonical ISRC/UPC.  
  - **Restrictions:** If a track/album is blocked, Spotify includes a `restrictions` object with a `reason` field (values `"market"`, `"product"`, `"explicit"`). The gateway must interpret these to handle geo-blocks and subscription restrictions.  
  - **Relinking:** Spotify may “relink” an unavailable track to another version. In a track GET, the boolean `is_playable` appears; if `false` and a `linked_from` object is present, the original track was replaced. The gateway should detect `is_playable=false` and extract the original `linked_from.id`/`uri` to follow the redirected identity.  
- **Restrictions & Compliance:** Spotify’s Developer Terms explicitly **forbid** using API data or audio previews for AI/ML training or commercial modeling. Preview clips (30-second MP3s) may not be offered as standalone content. Album art must remain unmodified and used only with a Spotify link/logo attribution. These conditions are non-negotiable compliance constraints (Official policy).

### TIDAL (v2 Open API)  
- **Access Model:** OAuth 2.0 Bearer Token (Client Credentials). Include `Authorization: Bearer {token}` and `Accept: application/vnd.tidal.v1+json` headers (as per TIDAL docs).  
- **Endpoints:**  
  - **By ID:** GET `https://api.tidal.com/v2/tracks/{id}`, `/v2/albums/{id}` (Official JSON:API style). The `countryCode={ISO}` query parameter is recommended to scope availability (as shown in examples).  
  - **Search by Identifier:** The Tidal API supports filtering via query parameters (JSON:API). For example:  
    - **Tracks by ISRC:** `GET /v2/tracks?filter[isrc]={ISRC}` (observed in Tidal developer forums; official reference is limited).  
    - **Albums by UPC/EAN:** Possibly `GET /v2/albums?filter[barcodeId]={UPC}` (not officially documented; community sources indicate Tidal supports EAN-13/UPC as `barcodeId`). This should be tested carefully.  
- **Metadata Features:**  
  - **JSON:API Design:** Tidal’s v2 API follows JSON:API conventions. Many relationships (artists, providers, etc.) are returned as links rather than embedded data. The gateway typically needs to follow relationship URLs or use the `include` parameter to hydrate fields.  
  - **Relationships:** Notable relationship routes include (all `GET /v2/*/relationships/*`):  
    - Albums: `/albums/{id}/relationships/artists`, `/coverArt`, `/items` (tracks), `/owners`, `/providers`, `/similarAlbums`.  
    - Tracks: `/tracks/{id}/relationships/albums`, `/artists`, `/owners`, `/providers`, `/radio`, `/similarTracks`, `/sourceFile`, and the **to-one** `/usageRules` for play/subscription rules.  
    These endpoints return minimal objects or IDs, so multiple requests or `include` must be used to build full metadata (JSON:API model).  
- **Notes:** Official Tidal docs confirm Bearer auth and v2 base URL, and JSON:API style. The filter-based search endpoints are community-verified and should be verified in practice (third-party). 

### Qobuz (v0.2 JSON API, Undocumented)  
- **Access Model:** Qobuz’s modern API (often called “v0.2 JSON API”) is **not** OAuth; instead it uses proprietary headers. Every request must include an application ID header `X-App-Id:{app_id}`. A known example App ID (`285473059`, used by XBMC/Kodi) is seen in community code. If user-specific data is needed, an optional header `X-User-Auth-Token:{token}` may also be sent. These observations come from open-source clients (reverse-engineered). (Official Qobuz docs are unavailable; treat this as reverse-engineered behavior.)  
- **Endpoints:**  
  - **Track/Album Data:** 
    - `GET http://www.qobuz.com/api.json/0.2/track/get?track_id={id}` and `GET /album/get?album_id={id}` to retrieve individual records (reverse-engineered/unofficial).  
    - Search by code: `GET /track/search?query={isrc}` and `/album/search?query={upc}` (seen in client code) to find tracks/albums by ISRC or UPC.  
    These endpoints mirror older Qobuz API patterns; reliability may vary.  
  - **File Streaming URL:** To fetch a track’s actual stream URL (sensitive endpoint), use `GET /track/getFileUrl` with parameters `format_id`, `intent` (e.g. “stream”), `track_id`, plus `request_ts` (Unix timestamp) and a cryptographic `request_sig`. The signature is an MD5 hash over the literal concatenated string:  
    ```
    "trackgetFileUrl"
      + "format_id" + {format_id}
      + "intent" + {intent}
      + "track_id" + {track_id}
      + {request_ts}
      + s4
    ```  
    where `s4` is the app-specific secret (derived by base64 XOR with the App ID). This exact logic is documented in a Qobuz client’s code. (This is fully **reverse-engineered**.)  
  - **Telemetry (Streaming Reports):** If streaming endpoints are used, Qobuz requires reporting start/end of playback (Terms of Service enforcement). Call `POST /track/reportStreamingStart` with `user_id` and `track_id`, and upon end call `POST /track/reportStreamingEnd` with `user_id`, `track_id`, and `duration`. The `duration` must be `floor(int(seconds))` per spec, and **do not report durations under 5 seconds** (abort if `<5`). These rules appear in the code comments and logic of known Qobuz clients. (Treat as **reverse-engineered requirement**.)  
- **Pagination:** Qobuz list/search calls use standard `limit` and `offset` parameters.  
- **Notes:** All above details are drawn from community reverse-engineering (e.g. Qobuz API clients). Official Qobuz support for v0.2 is unclear and not documented; use carefully.

### Beatport (v4 Public and Internal API)  
- **Access Model:** Beatport v4 has **two tiers**: Public OAuth2 PKCE (third-party) and an internal SSR API.  
  - **Public (api.beatport.com/v4):** Uses OAuth 2.0 with PKCE. A client ID must be obtained (often scraped from dev portal). The authorization flow exchanges a code for a Bearer token. All calls use `Authorization: Bearer {token}` and `Accept: application/json`.  
  - **Internal SSR (api-internal.beatportprod.com):** Beatport’s website uses a Next.js frontend to fetch data via session cookies (Direct Login). POST `/auth/login/` with user credentials returns cookies. These are private APIs meant for the frontend; using them in production is **undocumented and ToS-sensitive**. (Mentioned here only for reference; production code should treat them as potential violation unless explicitly allowed.)  
- **Endpoints:**  
  - **Tracks/Releases:** Beatport v4 uses “release” instead of “album”. Public endpoints (authenticated) include:  
    - `GET /catalog/tracks/{id}/` – get track details (Official).  
    - `GET /catalog/releases/{id}/` – get release details (Official, analogous to album).  
    - Search: `GET /catalog/search/?q={query}&type={type}` with type=`tracks` or `releases` (officially supported). For example, to find a track by ISRC, use `type=tracks`; by UPC, use `type=releases`. (Or use `type=tracks` and include ISRC in query, as search covers all fields.)  
    - **Releases vs Albums:** The older term “Album” is deprecated in Beatport v4; use the **Release** entity. (Verified by API docs.)  
  - **Genre/Taxonomy (Internal):** Beatport’s genre catalog is fixed. Official v4 endpoints include `GET /catalog/genres/` and `/genres/{id}/`. Known genre IDs (internal taxonomy) are listed below. Similarly, sub-genres are at `/catalog/sub-genres/{id}/`, charts at `/catalog/charts/` and `/charts/{id}/`, keys at `/catalog/keys/{id}/`, and chord-types at `/catalog/chord-types/{id}/`. These were documented in a community gist (Reverse-engineered) but appear consistent with Beatport’s web API.  
  - **Search Types:** The catalog search supports multiple types (`tracks`, `artists`, `labels`, `releases`, `charts`).  
- **Metadata Features:**  
  - **Sample/Preview:** Beatport provides sample clip URLs: a static domain `https://geo-samples.beatport.com/track/{uuid}.LOFI.mp3`. Playback is bounded by `sample_start_ms` and `sample_end_ms` fields (usually a 2-minute window).  
  - **Images:** Beatport serves artwork via `https://geo-media.beatport.com/image_size/{width}x{height}/{uuid}.jpg`. Static sizes include `100x100`, `250x250`, `500x500`, `590x404`, `1400x1400`.  
  - **Duration:** Beatport’s track JSON has `length_ms` (milliseconds), matching Spotify’s unit.  
  - **Genre Mapping:** Beatport’s catalog objects include genre IDs. The known mapping of genre ID to name is provided; integration should map these IDs to descriptive names accordingly.  
- **Pagination & Errors:**  
  - Beatport list endpoints default to 25 items and cap at 100 per page. Use `page` and `per_page`. Results include standard pagination fields (`count`, `page`, `per_page`, `next`, `previous`).  
  - Rate limits are undocumented, but community guidance suggests **adding ~500ms delay between requests** to avoid 429s. On receiving HTTP 429, respect the `Retry-After` header (if any) or implement exponential backoff.  
  - Common HTTP statuses include: 200 (OK), 302 (redirect to login if unauthorized), 400, 401, 403, 404, 429 (rate limit). Code should handle 401/403 by refreshing credentials or falling back, and retry 429 after delay.  

## 4. Authentication and Token Management  
Implement a **modular auth layer** for each DSP:

- **Spotify/Tidal:** Both use standard OAuth2 Client Credentials. Code should cache access tokens and refresh them on expiry (expires_in given in token response). Insert the `Authorization: Bearer` header in each request. 
- **Beatport (Public):** Implement PKCE flow. A third-party OAuth library may be used; example PHP middleware exists (requires PHP 7.1+, Guzzle 6.x, Beatport Consumer Key/Secret). Store the PKCE verifier to exchange code. Cache tokens and use refresh tokens as per spec. For session login, support an optional code path to POST `/auth/login/` (internal) to obtain cookies, if truly needed (with caution about ToS). 
- **Qobuz:** Insert `X-App-Id` (and `X-User-Auth-Token` if available) headers per request. No token exchange is documented; the app ID is static (embedding it implies acceptance of Qobuz API terms).  

**Token Refresh & Expiration:** Implement expiration checks and refresh tokens before they expire. For OAuth2, use the provided `expires_in` and `refresh_token`. For Qobuz, no refresh logic (static app ID). 

**Error Recovery:** On HTTP 401/403, attempt re-authentication (refresh token or re-login). On 429, pause as directed. All auth credentials (client secrets, tokens) must be secured and not leaked in logs.

## 5. Identifier Resolution Strategy  
To match entities across catalogs:

- **Provider IDs:** Always preserve the original provider’s internal IDs (Spotify track/album ID, Tidal track/album ID, Qobuz track/album ID, Beatport track/release ID) in the canonical record for back-reference.  
- **ISRC (Track-level):** Primary key for tracks. Query each DSP by ISRC where supported (Spotify, Tidal, Qobuz, Beatport) to find the authoritative track record. Spotify and Beatport support ISRC filtering natively; Tidal uses `filter[isrc]` (community-confirmed); Qobuz’s search can match ISRC via `/track/search?query=...`.  
- **UPC/EAN (Release-level):** Primary key for releases. Use each DSP’s UPC search. Spotify supports `q=upc:{UPC}`; Tidal likely via `filter[barcodeId]` (expected EAN-13); Beatport with search type `releases`; Qobuz via `/album/search?query={UPC}`.  
- **Catalog Number / Label:** If available, use label+catalog number as tertiary match (some providers include this). This is a fallback if ISRC/UPC not present.  
- **Fallback Fuzzy Matching:** Only if deterministic keys fail, one may use title/artist fuzzy matching, but tag conflict risk is high. (Design should **favor strict ID queries**.)  

At each step, **record provenance**: tag data by source (e.g. “Spotify external_ids.isrc”) and confidence. Match conflicts (e.g. two ISRCs returned) must be flagged for manual review.

## 6. Provider Route Registry  
Below is a summary of key API routes by provider. Official routes are marked (Official), whereas unsupported/internal routes are noted as (Undocumented/Reverse). Routes not found should be tested and not assumed.

- **Spotify:**  
  - `GET /v1/tracks/{id}`, `/v1/albums/{id}` – Official.  
  - `GET /v1/search?type=track&q=isrc:{isrc}` – Official.  
  - `GET /v1/search?type=album&q=upc:{upc}` – Official.  
- **TIDAL:**  
  - `GET /v2/tracks/{id}`, `/v2/albums/{id}` – Official.  
  - `GET /v2/tracks?filter[isrc]={isrc}` – Unofficial (community source).  
  - `GET /v2/albums?filter[barcodeId]={upc_or_ean}` – Unverified (expected behavior).  
  - `/v2/albums/{id}/relationships/*`, `/v2/tracks/{id}/relationships/*` – Official (JSON:API).  
- **Qobuz (v0.2):**  
  - `GET /track/get?track_id={id}`, `GET /album/get?album_id={id}` – Reverse-engineered.  
  - `GET /track/search?query={isrc}`, `GET /album/search?query={upc}` – Reverse-engineered.  
  - `GET /track/getFileUrl?format_id=...&intent=...&track_id=...&request_ts=...&request_sig=...` – Reverse-engineered (signature required).  
  - `POST /track/reportStreamingStart`, `/track/reportStreamingEnd` – Reverse-engineered telemetry.  
- **Beatport (Public v4):**  
  - `GET /catalog/tracks/{id}/`, `GET /catalog/releases/{id}/` – Official (see Beatport docs).  
  - `GET /catalog/search/?type=tracks&q={query}`, `?type=releases&q={query}` – Official (documented for search).  
- **Beatport (Internal SSR):** *(use with extreme caution – likely against TOS)*  
  - `GET /catalog/genres/`, `/genres/{id}/`, `/sub-genres/{id}/`, `/charts/`, `/charts/{id}/`, `/keys/{id}/`, `/chord-types/{id}/` – Documented in community guides.  
  - These provide controlled vocabularies (genre and taxonomy) not exposed in public API.  

Any route marked Undocumented/Reverse **should not be relied upon long-term** without official support – they may break if Beatport/Qobuz change their frontends.

## 7. Canonical Entity Model  
Define unified entities and relationships that cover all DSP schemas. Key entities and their canonical fields include:

- **Track (Recording):** title, ISRC, duration (ms), track number, explicit flag, preview URL & window, associated release ID, contributing artists (with roles), key/chord (if provided), genre IDs.  
- **Release (Album/EP):** title, UPC/EAN, release date, release date precision, label, catalog number, list of track IDs, artists, price info (Beatport only), and whether streamable.  
- **Artist:** name, provider-specific ID(s), aliases.  
- **Label:** name, provider-specific ID(s).  
- **Genre/Subgenre:** Use Beatport genre IDs or provider genre strings. Map to canonical genre taxonomy as needed (Beatport provides a fixed list).  
- **Musical Key/Chord:** as provided by Beatport (`/keys/`, `/chord-types/`).  
- **Artwork:** Cover image URLs (maintaining dimensions, no cropping).  
- **Preview/Media:** Sample clip URL (Beatport Lofi URLs; Spotify preview_url; Qobuz/file URL from `getFileUrl`).  
- **Rights/Availability:** Regions (markets), restriction reasons (Spotify “restrictions.reason”), subscription requirements, expiration.  

Each canonical record should log which provider it came from for each field (e.g. Spotify.track.duration_ms, Tidal.track.duration, etc.) to allow audit and conflict resolution.

## 8. Field Normalization Matrix  

| Canonical Field       | Spotify JSON Key           | Tidal (v2) Key/Logic      | Qobuz Key/Logic         | Beatport Key          |
|-----------------------|----------------------------|---------------------------|-------------------------|-----------------------|
| **Provider Track ID** | `id`                       | `id`                      | `track_id`              | `id`                  |
| **Provider Release ID** | `id` (on album)         | `id` (on album)           | `album_id`              | `id` (on release)     |
| **ISRC**              | `external_ids.isrc` | `isrc` (filter)           | `isrc` (in track object) | `isrc` (in JSON)      |
| **UPC/EAN**           | `external_ids.upc` | `release.barcodeId`? (filter) | `upc` (in album object)  | `upc` (in release JSON) |
| **Title**             | `name`                     | `title`                   | `title`                 | `title`               |
| **Artists**           | `artists[].name`           | Relationship `artists` (links) | `performer[]` (array)   | `artists[].name`      |
| **Contributors**      | (Track rel. artists)       | (Use album/track rel. to fetch artists) | `performer` roles      | `artists[].name` (flat) |
| **Release Title**     | `album.name`               | `album.title`             | `album.title`           | `name` (on release)   |
| **Release Date**      | `release_date` (ISO date)  | `releaseDate` (ISO date)  | `released_at` (Unix epoch) | `publish_date` (ISO) |
| **Release Date Precision** | `release_date_precision` | —                       | —                       | —                     |
| **Duration (ms)**     | `duration_ms` | `duration * 1000`       | `duration * 1000`        | `length_ms`           |
| **Label**             | `album.label.name`         | `label.name`              | `label.name`            | `label.name`          |
| **Catalog Number**    | `album.external_ids.upc`?  | `album.catalogNumber`?    | (none)                  | `catalog_number`      |
| **Genre/Subgenre**    | Spotify genres not exposed | (use providers’ genre fields) | (none)                | `genre_id` (see table)|
| **Key/Chord**         | (none)                     | (none)                    | (none)                  | `/keys/{id}`, `/chord-types/{id}` |
| **Artwork URL**       | `images[]` (various sizes) | (album cover via relationship) | `image.url`            | via `geo-media.beatport.com` sizes |
| **Preview URL**       | `preview_url` (Spotify 30s MP3) | (none)                | (stream URL from getFileUrl) | Sample URL (Beatport Lofi) |
| **Sample Window (ms)**| (30s clip)                 | —                         | —                       | `sample_start_ms` / `sample_end_ms` |
| **Availability**      | `is_playable` / `restrictions.reason` | `availability` fields (via `/usageRules`) | (none)            | `is_available_for_streaming` (boolean) |
  
Notes on normalization:
- **Duration:** Tidal and Qobuz return seconds; convert to ms (`duration_ms = duration * 1000`).  
- **Artists/Performers:** Qobuz returns a `performer` array with roles. Flatten into canonical track-artist list, preserving role (e.g. “Main Artist”, “Remixer”). Tidal returns relationships for artists (join via the API). Spotify and Beatport return embedded name arrays.  
- **Dates:** Qobuz’s `released_at` is Unix epoch; convert to ISO8601. Spotify’s `release_date_precision` (year/month/day) may require setting the date string to the first day of the month/year if less precise.  
- **Identifiers:** Always store raw provider IDs (e.g. Spotify URIs), even if canonical entity uses ISRC/UPC for lookup.  

## 9. Provider-Specific Parsing Rules  

- **Spotify:**  
  - *Market Restrictions:* If Spotify returns an album/track, check its `restrictions.reason`. `"market"` implies country block, `"product"` implies subscriber level block, `"explicit"` implies parental block. The integration should surface these as availability flags.  
  - *Track Relinking:* When `is_playable=false` and a `linked_from` object is present, extract `linked_from.id` and `uri` as the canonical track ID (since the requested track was replaced). This ensures continuity of identity. If `is_playable=true`, no relinking needed.  
  - *Local Flag:* Spotify’s `is_local` boolean indicates a user’s local file. Treat `is_local=true` as not fetchable via API (likely skip such records).  
- **TIDAL:**  
  - *JSON:API Hydration:* Tidal’s data often requires extra calls. For example, to get track artist names, you may need to GET `/tracks/{id}?include=artists` or call `/tracks/{id}/relationships/artists`. The integration should plan to fetch any nested data by using the `include` parameter or sequential calls.  
- **Qobuz:**  
  - *Signature:* For `/track/getFileUrl`, compute `request_sig` exactly as per the algorithm. The concatenation order and MD5 hashing must match the code above.  
  - *Timestamps:* Always include `request_ts` as a seconds-since-epoch. The `request_sig` uses this same timestamp.  
  - *Time-based Reporting:* Only post streaming events (`reportStreamingStart/End`) when actually streaming file endpoints, not for metadata fetch. (Otherwise, skip.)  
- **Beatport:**  
  - *Release vs Album:* Treat Beatport “Releases” as albums. Do not attempt to call any `/catalog/albums/` endpoint – use `/releases/` instead.  
  - *Genre Taxonomy:* Map Beatport’s numeric genre IDs to names using the table. This is the definitive mapping.  
  - *Preview Clips:* Use `sample_start_ms` and `sample_end_ms` to determine allowed preview window. Do not attempt to obtain full-track streams.  
  - *Images:* Beatport provides base image URIs; append dimensions to URLs as needed (sizes 100×100 up to 1400×1400 are supported).  
  - *SSR Data:* If using internal SSR API endpoints, be aware they may reveal additional data (e.g. genre top charts) not in public docs. Use this only if permissible.

## 10. Pagination, Rate Limits, Retry, and Backoff  
- **Beatport:** All list endpoints use `page`/`per_page` (default 25, max 100). To be polite, insert a 500 ms delay between Beatport API requests. Check for HTTP 429 and respect `Retry-After` (if given).  
- **Spotify:** Handle HTTP 429 by reading the `Retry-After` header and pausing requests accordingly. Spotify does not document a fixed rate limit, so dynamic backoff is required.  
- **Tidal:** Not officially documented; assume moderate rate limits. Apply exponential backoff on 429 or 500 errors.  
- **Qobuz:** Not documented; since v0.2 is unofficial, use conservative request rates.  
- **Pagination:** Always traverse paginated results to completion (using next page URLs or page params) when enumerating lists (e.g. Beatport catalog/tracks list or Qobuz search).  

## 11. Compliance and Terms-of-Service Safeguards  
- **No Unpermitted Use:** Do *not* use any provider’s content for AI/ML training or commercial data products if forbidden by their terms. Spotify explicitly bans using metadata/previews for ML or standalone services. Qobuz’s terms require agreement on use of file endpoints (the plugin code notes acceptance of Qobuz TOS).  
- **Attribution and Branding:** Where required, always link back to the DSP (e.g. Spotify logo/link for Spotify data). Do not modify album art or overlay branding.  
- **Legal Jurisdiction:** Respect geo-restrictions. For example, Spotify’s `market` parameter must reflect where content is playable. Query only content licensed for the target market.  
- **Separation of Metadata vs Streaming:** Metadata ingestion should not automatically trigger streaming requests. e.g. do not call `/track/getFileUrl` or streaming telemetry endpoints unless explicitly performing a playback. Similarly, do not scrape or emulate streaming from internal endpoints without user consent and legal clearance.  
- **Separation of Concerns:** Treat metadata-only ingestion separately from any file or playback integration. For compliance, metadata code should not carry session cookies used in SSR calls.  

## 12. Provenance, Auditability, and Conflict Resolution  
- **Provenance Tracking:** Store source identifiers and timestamps for every imported field (e.g. `duration_ms (Spotify)`, `duration (TIDAL)`). Include provider name and endpoint.  
- **Source Priority:** If multiple DSPs provide the same data (e.g. duration, release date), decide a priority (e.g. prefer Spotify’s or tag as equivalent). Flag conflicts for review.  
- **Confidence Scoring:** Assign confidence levels to fields. For example, official API values (Spotify, Tidal) get high confidence, whereas reverse-engineered fields (Beatport SSR, Qobuz signature) get lower confidence.  
- **Caching:** Cache each DSP’s responses by a compound key (provider + endpoint + query). Invalidate caches on token refresh or policy changes.  
- **Audit Logs:** Log every failed lookup or unusual response. Maintain an audit trail of reconciliations (e.g. if two ISRC matches conflict, record the decision).  

## 13. Implementation Checklist  
- [ ] **Authentication:** Implement OAuth2 (Spotify, Tidal, Beatport PKCE) and Qobuz headers. Test token flows and refresh.  
- [ ] **Identifier Queries:** Code lookup routines for each DSP: by internal ID, by ISRC, by UPC. Verify searches return correct records.  
- [ ] **Routing Layer:** Build an abstraction layer mapping canonical queries to provider-specific endpoints (e.g. a function `lookup_track(isrc, provider)`).  
- [ ] **JSON Parsing:** Implement parsers for each provider’s JSON schema, extracting required fields and renaming into canonical fields (using the normalization matrix above).  
- [ ] **Rate Limiting:** Add global throttling per provider (Beatport 500 ms min delay). Implement 429/Retry-After handling.  
- [ ] **Error Handling:** Wrap API calls to catch HTTP 401/403 (re-auth), 302 (login redirect on Beatport), 404 (not found), 429 (rate limit).  
- [ ] **Telemetry:** (Qobuz) Integrate conditional calls to `/track/reportStreamingStart/End` only in streaming scenarios, applying duration flooring and abort rules.  
- [ ] **Normalization:** Apply unit conversions (sec→ms), date format conversions, flatten nested artist/performer lists, etc.  
- [ ] **Testing:** Validate against known ISRC/UPC pairs. Unit-test each route and edge case (e.g. Spotify relinking, Qobuz signature errors).  
- [ ] **Compliance Audit:** Ensure terms-of-service rules (Section 11) are not violated in code or usage. Document compliance constraints in developer guidelines.  

## 14. Verification Gaps and Claims Requiring Follow-Up  
- **TIDAL UPC Search:** The filter name for album UPC is uncertain. Community posts suggest `filter[barcodeId]` (EAN-13), but official docs don’t list it. This should be validated with test calls. (Marked *Unverified*.)  
- **Beatport OAuth PKCE:** Official docs exist (developer portal) but obtaining credentials may require an account. The middleware `iammordaty/beatport-oauth-middleware` simplifies this (third-party code). Its exact behavior (e.g. scopes) should be confirmed.  
- **Beatport Internal SSR:** All internal endpoints (`/genres`, `/keys`, etc.) are not public. Using them may breach Beatport’s Terms. Our spec mentions them for completeness (Reverse-engineered), but production integration should avoid or get explicit approval.  
- **Qobuz API Access:** Since Qobuz’s v0.2 is undocumented, obtaining a valid `X-App-Id` and understanding its lifecycle is a risk. The known App ID (285473059) may be specific to XBMC and could be revoked. If Qobuz offers a new official API (v2.0+), migration will be needed. (Reverse-engineered, high risk.)  
- **Spotify Terms:** Developer Policy changes (e.g. 2026 Dev Mode) may impose new constraints. Keep current with Spotify’s legal updates.  
- **Others:** Verify Tidal’s JSON:API header usage (the example requires `Content-Type: application/vnd.tidal.v1+json`). Also confirm if Tidal’s search endpoints require countryCode or authentication on all calls.  

## 15. References  

- Spotify for Developers – *Web API Reference (Get Track/Album, Authentication)*.  
- Spotify for Developers – *Client Credentials Flow Tutorial*.  
- Spotify Developer Terms – *Metadata and Visual Content Guidelines*.  
- TIDAL Developer – *Authentication Guide*.  
- TIDAL Open API (v2) – *Quickstart & JSON:API compliance*.  
- TIDAL Developer Q&A – *Discussion: /tracks filter[isrc]*.  
- Qobuz API Clients (third-party) – *API v0.2 Endpoints and Signing Logic*.  
- Qobuz API Clients – *Streaming Report Endpoints*.  
- Beatport API Community Docs – *Public and Internal v4 API Endpoints*.  
- Beatport API Community Docs – *Genre IDs and Media URLs*.  
- Beatport API Community Docs – *Error Codes and Rate-Limit Advice*.  

**Unverified / Reverse-Engineered Claims:** All Qobuz v0.2 details, Beatport internal SSR routes, and Tidal UPC filtering are **unofficial**. They are included for completeness but should be verified in a testing environment.
