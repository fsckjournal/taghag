from taghag_import.key_normalize import to_camelot


def test_spelled_minor_and_major():
    assert to_camelot("A Minor") == ("8A", "spelled")
    assert to_camelot("G Major") == ("9B", "spelled")


def test_unicode_flats_and_sharps():
    assert to_camelot("B♭ Minor") == ("3A", "spelled")  # B-flat minor
    assert to_camelot("F♯ Major") == ("2B", "spelled")  # F-sharp major


def test_compact_forms():
    assert to_camelot("Am") == ("8A", "compact")
    assert to_camelot("Bbm") == ("3A", "compact")
    assert to_camelot("C") == ("8B", "compact")
    assert to_camelot("CSharp") == ("3B", "compact")


def test_already_camelot_passthrough():
    assert to_camelot("8A") == ("8A", "already_camelot")
    assert to_camelot("6b") == ("6B", "already_camelot")


def test_enharmonic_equivalence():
    # Gb and F# minor are the same Camelot slot.
    assert to_camelot("Gbm")[0] == to_camelot("F#m")[0] == "11A"


def test_unmappable_inputs_are_classified_not_dropped():
    assert to_camelot("1M") == (None, "openkey_ambiguous")
    assert to_camelot("UNKNOWN") == (None, "unknown_sentinel")
    assert to_camelot(None) == (None, "unknown_sentinel")
    assert to_camelot("") == (None, "unknown_sentinel")
    assert to_camelot("garbage") == (None, "unrecognized")
