import json
import math
import os
import urllib.request
import urllib.error

class AutomixEngine:
    """
    Experimental Intelligence Engine: Calculates professional DJ transitions 
    by analyzing raw Spotify audio-attributes metadata.
    """
    
    def __init__(self, track_a_analysis: dict, track_b_analysis: dict):
        self.track_a = track_a_analysis
        self.track_b = track_b_analysis

    @classmethod
    def fetch_audio_analysis(cls, track_id: str, access_token: str) -> dict:
        """
        Fetches the raw audio analysis JSON block via the SPClient gateway.
        This contains the bars, beats, segments, and fade timestamps required for Automix.
        """
        # Ensure track_id is Base62 (e.g. 14Kv8xn6Cx3PnlcnHiBw4U)
        url = f"https://spclient.wg.spotify.com/audio-attributes/v1/audio-analysis/{track_id}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        })
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Failed to fetch audio analysis: {e.code} {e.reason}")

    @classmethod
    def fetch_local_analysis(cls, track_id: str, cache_dir: str) -> dict:
        """
        Fetches the raw audio analysis JSON block from a local cache directory.
        Looks for {track_id}.json in the given directory.
        """
        file_path = os.path.join(cache_dir, f"{track_id}.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Local analysis not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def generate_pure_offline_analysis(cls, flac_path: str) -> dict:
        """
        Generates the transition payload dynamically and entirely offline 
        using Apple Music Understanding and heuristics.
        """
        from .offline_automix_analyzer import OfflineAutomixAnalyzer
        analyzer = OfflineAutomixAnalyzer(flac_path)
        return analyzer.extract_payload()

    def _get_nearest_bar(self, track_data, target_time):
        """Finds the bar (downbeat) boundary closest to the target timestamp."""
        best_bar = None
        min_diff = float("inf")
        for bar in track_data.get("bars", []):
            diff = abs(bar["start"] - target_time)
            if diff < min_diff:
                min_diff = diff
                best_bar = bar
        return best_bar

    def _get_duration_for_bars(self, track_data, start_time, num_bars=4):
        """Calculates the exact duration of the next N bars to ensure musical timing."""
        bars = track_data.get("bars", [])
        start_idx = -1
        for i, bar in enumerate(bars):
            if bar["start"] >= start_time - 0.05: # Allow small float variance
                start_idx = i
                break
        
        if start_idx == -1 or start_idx + num_bars >= len(bars):
            # Fallback to pure BPM-based duration if we run out of mapped bars
            tempo = track_data.get("track", {}).get("tempo", 120.0)
            return (60.0 / tempo) * 4 * num_bars
            
        end_time = bars[start_idx + num_bars]["start"]
        return end_time - start_time

    def compute_transition(self):
        """
        Calculates the optimal transition start points and exponential fade curves.
        Returns a dictionary containing the start_point, end_point, and fade_curve arrays.
        """
        # --- Track A (Outro) ---
        track_a_meta = self.track_a.get("track", {})
        fade_out_target = track_a_meta.get("start_of_fade_out", 0)
        
        # Snap to nearest downbeat (bar)
        outro_bar = self._get_nearest_bar(self.track_a, fade_out_target)
        start_point_a = outro_bar["start"] if outro_bar else fade_out_target
        
        # Determine transition duration (default 4 bars of Track A's tempo)
        transition_duration_a = self._get_duration_for_bars(self.track_a, start_point_a, num_bars=4)
        end_point_a = start_point_a + transition_duration_a

        # --- Track B (Intro) ---
        track_b_meta = self.track_b.get("track", {})
        fade_in_target = track_b_meta.get("end_of_fade_in", 0)
        
        intro_bar = self._get_nearest_bar(self.track_b, fade_in_target)
        start_point_b = intro_bar["start"] if intro_bar else 0.0
        
        transition_duration_b = self._get_duration_for_bars(self.track_b, start_point_b, num_bars=4)
        
        # --- Generate Equal-Power Fade Curves ---
        points = 20 # Generate 20 volume points for smooth interpolation
        fade_curve_a = []
        fade_curve_b = []
        
        for i in range(points + 1):
            progress = i / points
            time_offset_a = progress * transition_duration_a
            time_offset_b = progress * transition_duration_b
            
            # Track A fades OUT (cos curve from 1 to 0)
            vol_a = math.cos(progress * (math.pi / 2))
            fade_curve_a.append({
                "time_offset": round(time_offset_a, 3),
                "volume": round(vol_a, 4)
            })
            
            # Track B fades IN (sin curve from 0 to 1)
            vol_b = math.sin(progress * (math.pi / 2))
            fade_curve_b.append({
                "time_offset": round(time_offset_b, 3),
                "volume": round(vol_b, 4)
            })

        return {
            "track_a": {
                "tempo": track_a_meta.get("tempo", 120.0),
                "start_point": round(start_point_a, 3),
                "end_point": round(end_point_a, 3),
                "fade_curve": fade_curve_a
            },
            "track_b": {
                "tempo": track_b_meta.get("tempo", 120.0),
                "start_point": round(start_point_b, 3),
                "end_point": round(start_point_b + transition_duration_b, 3),
                "fade_curve": fade_curve_b
            },
            "transition_duration_a": round(transition_duration_a, 3),
            "transition_duration_b": round(transition_duration_b, 3)
        }

if __name__ == "__main__":
    # Example usage
    # analysis_a = AutomixEngine.fetch_audio_analysis("14Kv8xn6Cx3PnlcnHiBw4U", "YOUR_ACCESS_TOKEN")
    # engine = AutomixEngine(analysis_a, analysis_a)
    # print(json.dumps(engine.compute_transition(), indent=2))
    pass
