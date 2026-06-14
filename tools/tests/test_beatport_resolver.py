import pytest
from taghag_import.beatport_resolver import BeatportResolver, generate_iwebdj_token

def test_generate_iwebdj_token():
    # Test cases from deobfuscated JS scratchpad
    assert generate_iwebdj_token(10983855) == "UTN4MDO5ATM"
    assert generate_iwebdj_token(0) == "AM"
    assert generate_iwebdj_token(12345) == "UDNzITM"
    assert generate_iwebdj_token(987654321) == "xIzM0UjN3gTO"

def test_decode_payload_format_1():
    # BPM >= 145. Let's design parameters to get exactly 150 BPM.
    # a0 = 5.75 * 150 + 818.254 = 1680.754
    # For Format 2: a1 = 25.5811 - 7.25 * 150 = -1061.9189 (which is < 145 BPM selector)
    # But wait, format_selector is based on bpm_a1.
    # bpm_a1 = (25.5811 - a1) / 7.25
    # If a1 = -1061.9189, bpm_a1 = 150.0. Since bpm_a1 >= 145, format_selector = 1
    resolver = BeatportResolver()
    parsed_dict = {
        "a0": "1680.754", # 150 BPM
        "a1": "-1061.9189", # 150 BPM (so selector = 1)
        "a2": "2045.711", # Will yield offset around 65.7 ms
        "a3": "0",
        "db0": "1",
        "db1": "0",
        "length": "10.0", # 10 seconds
        "bm0": "AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQRRSSTTUUVVWWXXYYZZ",
        "bm1": ""
    }
    
    # 150 BPM -> beat period = 400ms.
    # a2_ms = 1000 * (2045.711 - 1894.123) / 2307.2383 = 65.7ms.
    # beat_offset = 65.7 + 1 * 400 = 465.7 ms.
    decoded = resolver.decode_iwebdj_payload(parsed_dict)
    
    assert abs(decoded["bpm"] - 150.0) < 0.01
    assert abs(decoded["beat_period_ms"] - 400.0) < 0.01
    assert abs(decoded["beat_offset_ms"] - 465.7) < 0.5
    assert len(decoded["beat_times_ms"]) > 0
    # First beat should be beat_offset
    assert abs(decoded["beat_times_ms"][0] - 465.7) < 0.5

def test_decode_payload_format_2():
    # BPM < 145. Let's design parameters to get exactly 120 BPM.
    # bpm_a1 = (25.5811 - a1) / 7.25 -> a1 = 25.5811 - 7.25 * 120 = -844.4189
    resolver = BeatportResolver()
    parsed_dict = {
        "a0": "0",
        "a1": "-844.4189", # 120 BPM
        "a2": "0",
        "a3": "6433.327148437", # Yields offset around 119.7 ms
        "db0": "0",
        "db1": "0",
        "length": "20.0", # 20 seconds
        "bm0": "",
        "bm1": "AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQRRSSTTUUVVWWXXYYZZ"
    }
    
    decoded = resolver.decode_iwebdj_payload(parsed_dict)
    
    assert abs(decoded["bpm"] - 120.0) < 0.01
    assert abs(decoded["beat_period_ms"] - 500.0) < 0.01
    assert abs(decoded["beat_offset_ms"] - 119.7) < 0.5

def test_outro_detection_threshold():
    # Test how outro detects threshold >= 20.
    # Base52: Z is 25, a is 26, z is 51.
    # Let's create an energy profile where energies drop below 20 at the end.
    # Value 19 is 'T' (19) or 'U' (20).
    # We want a transition from high energy to low energy.
    resolver = BeatportResolver()
    parsed_dict = {
        "a0": "0",
        "a1": "-844.4189", # 120 BPM (500ms period)
        "a2": "0",
        "a3": "6770.2211", # Offset = 0ms
        "db0": "0",
        "db1": "0",
        "length": "10.0", # 10s -> 20 beats
        # Beat energy list: 10 beats of peak energy ('Z'=25), then 10 beats of low energy ('A'=0)
        # Sliced list length: 20
        # Sweeping backward, index 10 (time 5000ms) has energy 25 (>=20)
        "bm1": "ZZZZZZZZZZAAAAAAAAAA"
    }
    
    decoded = resolver.decode_iwebdj_payload(parsed_dict)
    # The last beat >= 20 is at index 9 (since 10 beats are Z).
    # Beat times: 0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500 (index 9)
    # So outro_raw_ms should be 4500 ms.
    # Formula for outro_ms: duration_ms - floor((duration_ms - outro_raw_ms) / (32 * beat_period)) * beat_period * 32
    # duration_ms = 10000.
    # duration_ms - outro_raw_ms = 5500.
    # 32 * beat_period = 16000.
    # floor(5500 / 16000) = 0.
    # So outro_ms = 10000 - 0 = 10000 ms.
    assert decoded["outro_ms"] == 10000.0

def test_decode_malformed_and_boundaries():
    resolver = BeatportResolver()
    # Missing fields - should fallback to defaults or fail gracefully
    parsed_dict = {}
    decoded = resolver.decode_iwebdj_payload(parsed_dict)
    assert decoded["bpm"] > 0 # Should fallback to float("0") defaults cleanly
    
    # Boundary: length = 0
    parsed_dict_zero = {
        "length": "0.0",
        "bm0": "",
        "bm1": ""
    }
    decoded_zero = resolver.decode_iwebdj_payload(parsed_dict_zero)
    assert len(decoded_zero["beat_times_ms"]) == 0
