import math
import sqlite3
import re
from pathlib import Path
from taghag_import.apple_music_adapter import analyze_flac

class OfflineAutomixAnalyzer:
    """
    Computes professional DJ transition points entirely offline using 
    Apple Music Understanding ML features (pace, loudness, structure).
    """
    
    def __init__(self, flac_path: str):
        self.flac_path = Path(flac_path)
        self.db_path = "/Users/g/Projects/tag/slut_db/FRESH_2026/music_v3.db"
        
    def _fetch_lexicon_metadata(self) -> dict:
        """Queries the database for MIK key/energy and Rekordbox BPM via the FLAC path."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT lf.musical_key, lf.energy, lf.bpm 
            FROM asset_file af
            JOIN asset_link al ON af.id = al.asset_id
            JOIN lexicon_features lf ON al.identity_id = lf.track_identity_id
            WHERE af.path = ?
            LIMIT 1
        """, (str(self.flac_path),))
        row = c.fetchone()
        conn.close()
        
        if row:
            return {"musical_key": row[0], "energy": row[1], "bpm": row[2]}
        return {}
        
    def _parse_lexicon_key(self, raw_key: str) -> tuple[int, int]:
        """Converts MIK Camelot/Standard strings to Spotify Integer (key, mode). Mode: 0=Minor, 1=Major."""
        if not raw_key:
            return None, None
            
        raw_key = raw_key.strip().upper()
        
        # 1. Check for Camelot formats (e.g., '12A', '1B', '10M', '5D', '12m', '05A')
        camelot_match = re.match(r"^0?([1-9]|1[0-2])([ABMD])$", raw_key)
        if camelot_match:
            num = int(camelot_match.group(1))
            letter = camelot_match.group(2)
            
            # Mode mapping
            is_major = 1 if letter in ["B", "M", "D"] else 0
            
            # Standard Camelot mapping to pitch class
            # Minor (A): 1A=8, 2A=3, 3A=10, 4A=5, 5A=0, 6A=7, 7A=2, 8A=9, 9A=4, 10A=11, 11A=6, 12A=1
            # Major (B): 1B=11, 2B=6, 3B=1, 4B=8, 5B=3, 6B=10, 7B=5, 8B=0, 9B=7, 10B=2, 11B=9, 12B=4
            camelot_minor_map = {1:8, 2:3, 3:10, 4:5, 5:0, 6:7, 7:2, 8:9, 9:4, 10:11, 11:6, 12:1}
            camelot_major_map = {1:11, 2:6, 3:1, 4:8, 5:3, 6:10, 7:5, 8:0, 9:7, 10:2, 11:9, 12:4}
            
            key_num = camelot_major_map[num] if is_major else camelot_minor_map[num]
            return key_num, is_major
            
        # 2. Check for Standard formats (e.g., 'C Minor', 'FSharp major', 'Eb')
        mode = 1 # Default Major
        if " MINOR" in raw_key or "M" in raw_key.split(" ")[-1] and raw_key[-1] == "M":
            mode = 0
            
        # Strip mode words
        clean_key = raw_key.replace(" MINOR", "").replace(" MAJOR", "").replace(" M", "").replace(" D", "").strip()
        
        pitch_map = {
            "C": 0, "C#": 1, "CSHARP": 1, "DB": 1,
            "D": 2, "D#": 3, "DSHARP": 3, "EB": 3,
            "E": 4, 
            "F": 5, "F#": 6, "FSHARP": 6, "GB": 6,
            "G": 7, "G#": 8, "GSHARP": 8, "AB": 8,
            "A": 9, "A#": 10, "ASHARP": 10, "BB": 10,
            "B": 11
        }
        
        key_num = pitch_map.get(clean_key)
        if key_num is not None:
            return key_num, mode
            
        return None, None
        
    def _cmtime_ms(self, value) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, dict):
            return 0.0
        raw_value = value.get("value", 0)
        timescale = value.get("timescale", 1)
        if timescale <= 0:
            return 0.0
        return float(raw_value) / timescale

    def _get_range_ms(self, item) -> tuple[float, float]:
        if not isinstance(item, dict):
            return 0.0, 0.0
        range_data = item.get("range", item)
        if not isinstance(range_data, dict):
            return 0.0, 0.0
        start_sec = self._cmtime_ms(range_data.get("start"))
        duration_sec = self._cmtime_ms(range_data.get("duration"))
        return start_sec, start_sec + duration_sec
        
    def _parse_beats(self, rhythm_data):
        beats = []
        for beat in rhythm_data.get("beats", []):
            time_sec = self._cmtime_ms(beat.get("time") if "time" in beat else beat)
            beats.append({"start": time_sec})
        return beats

    def _parse_bars(self, rhythm_data):
        bars = []
        for bar in rhythm_data.get("bars", []):
            time_sec = self._cmtime_ms(bar.get("time") if "time" in bar else bar)
            bars.append({"start": time_sec})
        return bars

    def extract_payload(self) -> dict:
        """
        Runs Apple Music Understanding on the FLAC and converts the output 
        to an AutomixPayload-compatible dictionary.
        """
        data = analyze_flac(self.flac_path)
        if not data:
            raise RuntimeError(f"Failed to analyze {self.flac_path} with apple_analyzer")
            
        # Fetch Lexicon / MIK data
        lex_meta = self._fetch_lexicon_metadata()
        lex_bpm = lex_meta.get("bpm")
        lex_key, lex_mode = self._parse_lexicon_key(lex_meta.get("musical_key", ""))
        lex_energy = lex_meta.get("energy", 0)
        
        rhythm = data.get("rhythm", {})
        # If Lexicon BPM exists, we use it as the source of truth, otherwise fallback to Apple ML
        tempo = lex_bpm if lex_bpm else rhythm.get("beatsPerMinute", 120.0)
        
        structure = data.get("structure", {})
        sections = structure.get("sections", [])
        phrases = structure.get("phrases", [])
        
        loudness = data.get("loudness", {})
        momentary = loudness.get("momentary", [])
        integrated = loudness.get("integrated")
        if isinstance(integrated, dict):
            integrated = integrated.get("value", -14.0)
            
        key_data = data.get("key", {})
        key_mode = None
        key_tonic = None
        if isinstance(key_data, dict):
            ranges = key_data.get("ranges", [])
            if ranges and isinstance(ranges, list) and isinstance(ranges[0], dict):
                key_value = ranges[0].get("value", {})
                key_mode = key_value.get("mode")
        # Override Apple's Key with MIK's Key if available
        if lex_key is not None:
            key_tonic = lex_key
            key_mode = lex_mode
            
        # ---------------------------------------------------------
        # Heuristic 1: End of Fade-In
        # The end of the first phrase, or fallback to first section.
        # ---------------------------------------------------------
        end_of_fade_in = 0.0
        if phrases:
            start_sec, end_sec = self._get_range_ms(phrases[0])
            end_of_fade_in = end_sec
        elif sections:
            start_sec, end_sec = self._get_range_ms(sections[0])
            end_of_fade_in = end_sec
            
        # ---------------------------------------------------------
        # Heuristic 2: Start of Fade-Out
        # The start of the final section (outro), or fallback to 90% of track.
        # ---------------------------------------------------------
        start_of_fade_out = 0.0
        if sections and len(sections) > 1:
            start_sec, end_sec = self._get_range_ms(sections[-1])
            start_of_fade_out = start_sec
        else:
            # Fallback if no sections
            start_of_fade_out = max(0.0, end_of_fade_in + 30.0) 
            
        # Refine fade-out with pace/drum dropoff if possible
        pace_ranges = data.get("pace", {}).get("ranges", [])
        if pace_ranges:
            # Check the last 10% of pace ranges for a significant drop
            pass # TODO: implement deeper pace analysis if basic sections fail
            
        # Format identical to Spotify payload
        return {
            "track": {
                "tempo": tempo,
                "end_of_fade_in": end_of_fade_in,
                "start_of_fade_out": start_of_fade_out,
                "key": key_tonic,
                "mode": key_mode,
                "energy": lex_energy,
                "duration": data.get("duration", 0.0) 
            },
            "bars": self._parse_bars(rhythm),
            "beats": self._parse_beats(rhythm)
        }

if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) < 2:
        print("Usage: python3 offline_automix_analyzer.py <path_to_flac>")
        sys.exit(1)
        
    analyzer = OfflineAutomixAnalyzer(sys.argv[1])
    try:
        payload = analyzer.extract_payload()
        print(json.dumps(payload, indent=2))
    except Exception as e:
        print(f"Error analyzing track: {e}")
