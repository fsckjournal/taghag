from __future__ import annotations

from taghag_import.postman_evidence import (
    evidence_to_row,
    merge_tag_evidence,
    parse_tag_evidence,
    resolve_tag_evidence,
)

# Captured verbatim from a real Postman run against Beatport/Spotify (ISRC
# DEM091100068, "Soda" by Pitchben) in
# artifacts/apple_poc_rbx_161/provider_evidence_test/provider_evidence.log.
REAL_BEATPORT_MATCHED_MARKER = (
    '[Tag Evidence JSON] {"candidate_count": 1, "candidates": [{"album": "Pitchslap", '
    '"artist": "Pitchben", "bpm": 121, "catalog_number": "CPT3802", "disc_number": "", '
    '"explicit": false, "external_id": "3002744", "field_candidates": ['
    '{"confidence": 0.98, "field_name": "canonical_title", "normalized_value": "Soda", '
    '"rationale": {"external_id": "3002744", "match_confidence": "exact", "provider": "beatport"}}, '
    '{"confidence": 0.94, "field_name": "canonical_label", "normalized_value": "Compost", '
    '"rationale": {"external_id": "3002744", "match_confidence": "exact", "provider": "beatport"}}, '
    '{"confidence": 0.94, "field_name": "canonical_genre", "normalized_value": "Indie Dance", '
    '"rationale": {"external_id": "3002744", "match_confidence": "exact", "provider": "beatport"}}, '
    '{"confidence": 0.99, "field_name": "isrc", "normalized_value": "DEM091100068", '
    '"rationale": {"external_id": "3002744", "match_confidence": "exact", "provider": "beatport"}}, '
    '{"confidence": 0.96, "field_name": "bpm", "normalized_value": 121, '
    '"rationale": {"external_id": "3002744", "match_confidence": "exact", "provider": "beatport"}}, '
    '{"confidence": 0.96, "field_name": "canonical_bpm", "normalized_value": 121, '
    '"rationale": {"external_id": "3002744", "match_confidence": "exact", "provider": "beatport"}}, '
    '{"confidence": 0.96, "field_name": "musical_key", "normalized_value": "2B", '
    '"rationale": {"external_id": "3002744", "match_confidence": "exact", "provider": "beatport"}}, '
    '{"confidence": 0.96, "field_name": "canonical_key", "normalized_value": "2B", '
    '"rationale": {"external_id": "3002744", "match_confidence": "exact", "provider": "beatport"}}], '
    '"genre": "Indie Dance", "isrc": "DEM091100068", "key": "2B", "label": "Compost", '
    '"match_confidence": "exact", "match_score": 100, "provider": "beatport", '
    '"provider_track_id": "3002744", "release_date": "2011-11-04", "title": "Soda"}], '
    '"ingestion_confidence": "high", "lookup_isrc": "DEM091100068", "provider": "beatport", '
    '"schema": "tagslut.postman.tag_evidence.v1", "source": "beatport_search_by_isrc", "status": "matched"}'
)


def test_parse_and_resolve_matched_result() -> None:
    stdout = """
noise
[Tag Evidence JSON] {"schema":"tagslut.postman.tag_evidence.v1","provider":"spotify","status":"matched","lookup_isrc":"USABC1234567","candidates":[{"album":"Album Cut","field_candidates":[{"field_name":"canonical_album","normalized_value":"Album Cut","confidence":0.91}]}]}
[Tag Evidence JSON] {"schema":"tagslut.postman.tag_evidence.v1","provider":"tidal","status":"matched","lookup_isrc":"USABC1234567","candidates":[{"release_date":"2024-02-03","field_candidates":[{"field_name":"canonical_title","normalized_value":"Title Cut","confidence":0.92},{"field_name":"canonical_artist_credit","normalized_value":"Artist Cut","confidence":0.88}]}]}
[Tag Evidence JSON] {"schema":"tagslut.postman.tag_evidence.v1","provider":"beatport","status":"matched","lookup_isrc":"USABC1234567","candidates":[{"catalog_number":"CAT-001","genre":"House","field_candidates":[{"field_name":"canonical_genre","normalized_value":"House","confidence":0.82},{"field_name":"canonical_label","normalized_value":"Label Cut","confidence":0.75}]}]}
""".strip()

    evidences = parse_tag_evidence(stdout)
    resolved = resolve_tag_evidence(stdout)

    assert len(evidences) == 3
    assert resolved is not None
    assert resolved.isrc == "USABC1234567"
    assert resolved.title == "Title Cut"
    assert resolved.artist == "Artist Cut"
    assert resolved.album == "Album Cut"
    assert resolved.label == "Label Cut"
    assert resolved.genre == "House"
    assert resolved.catalog_number == "CAT-001"
    assert resolved.release_date == "2024-02-03"
    assert resolved.year == "2024"
    assert resolved.providers_matched == ["spotify", "tidal", "beatport"]
    assert resolved.raw_status == {
        "spotify": "matched",
        "tidal": "matched",
        "beatport": "matched",
    }


def test_merge_tag_evidence_resolves_provider_bpm_and_key_under_distinct_names() -> None:
    evidences = parse_tag_evidence(REAL_BEATPORT_MATCHED_MARKER)
    resolved = merge_tag_evidence(evidences)

    assert resolved.title == "Soda"
    assert resolved.label == "Compost"
    assert resolved.genre == "Indie Dance"
    # Provider bpm/key land under provider_* names, never under bpm/musical_key
    # -- those names are reserved for the measured/local signal elsewhere in
    # the pipeline (dj_tag, Butter Flow's cost terms).
    assert resolved.provider_bpm == "121"
    assert resolved.provider_musical_key == "2B"
    assert not hasattr(resolved, "bpm")
    assert not hasattr(resolved, "musical_key")


def test_merge_tag_evidence_applies_beatport_authority_bonus_for_key() -> None:
    competing = """
[Tag Evidence JSON] {"schema":"tagslut.postman.tag_evidence.v1","provider":"tidal","status":"matched","lookup_isrc":"DEM091100068","candidates":[{"field_candidates":[{"field_name":"musical_key","normalized_value":"9A","confidence":0.96}]}]}
""".strip() + "\n" + REAL_BEATPORT_MATCHED_MARKER

    resolved = merge_tag_evidence(parse_tag_evidence(competing))

    # Beatport's authority bonus (+0.05) should win over TIDAL's equal raw
    # confidence (0.96) for musical_key.
    assert resolved.provider_musical_key == "2B"
    assert resolved.field_sources["provider_musical_key"].startswith("beatport:")


def test_resolve_no_match_result_returns_none() -> None:
    stdout = """
[Tag Evidence JSON] {"schema":"tagslut.postman.tag_evidence.v1","provider":"spotify","status":"no_match","lookup_isrc":"USABC1234567","candidates":[]}
""".strip()

    assert resolve_tag_evidence(stdout) is None


def test_resolve_ambiguous_result_returns_none() -> None:
    stdout = """
[Tag Evidence JSON] {"schema":"tagslut.postman.tag_evidence.v1","provider":"spotify","status":"ambiguous","lookup_isrc":"USABC1234567","candidates":[{"field_candidates":[{"field_name":"canonical_title","normalized_value":"Wrong Winner","confidence":0.1}]}]}
""".strip()

    assert resolve_tag_evidence(stdout) is None


def test_resolve_error_result_returns_none() -> None:
    stdout = """
[Tag Evidence JSON] {"schema":"tagslut.postman.tag_evidence.v1","provider":"spotify","status":"error","lookup_isrc":"USABC1234567","candidates":[]}
""".strip()

    assert resolve_tag_evidence(stdout) is None


def test_parse_malformed_json_as_evidence_warning() -> None:
    evidences = parse_tag_evidence("[Tag Evidence JSON] not json")

    assert evidences == [{"status": "malformed", "raw_line": "[Tag Evidence JSON] not json"}]


def test_parse_wrapped_postman_console_marker() -> None:
    stdout = """
  | [Tag Evidence JSON] {"schema":"tagslut.postman.tag_evidence.v1",
  | "provider":"tidal","status":"error","lookup_isrc":"GBEYE0100042",
  | "candidates":[]}
""".strip()

    evidences = parse_tag_evidence(stdout)

    assert len(evidences) == 1
    assert evidences[0]["provider"] == "tidal"
    assert evidences[0]["status"] == "error"
    assert evidences[0]["lookup_isrc"] == "GBEYE0100042"


def test_evidence_to_row_preserves_raw_marker() -> None:
    marker = {
        "schema": "tagslut.postman.tag_evidence.v1",
        "provider": "beatport",
        "status": "matched",
        "lookup_isrc": "USABC2400001",
        "candidates": [
            {
                "provider_track_id": "123",
                "field_candidates": [
                    {
                        "field_name": "canonical_label",
                        "normalized_value": "Label",
                        "confidence": 0.88,
                    }
                ],
            }
        ],
    }

    row = evidence_to_row(marker)

    assert row["provider"] == "beatport"
    assert row["lookup_type"] == "isrc"
    assert row["lookup_key"] == "USABC2400001"
    assert row["status"] == "matched"
    assert row["confidence"] == 0.88
    assert row["winning_fields_json"] == {"canonical_label": "Label"}
    assert row["raw_marker_json"] == marker
