from __future__ import annotations

from taghag_import.postman_evidence import (
    evidence_to_row,
    parse_tag_evidence,
    resolve_tag_evidence,
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
