import json
import time
from pathlib import Path

def extract_reduced_metadata(raw_json: dict) -> dict | None:
    """Ultra-compresses the JSON so 172 tracks easily fit in the LLM's context window."""
    try:
        # 1. Parse Key (tonic/mode)
        key_name = "Unknown"
        key_ranges = raw_json.get("key", {}).get("ranges", [])
        if key_ranges:
            kv = key_ranges[0].get("value", {})
            tonic = kv.get("tonic", -1)
            mode = kv.get("mode", -1)
            pitch_class = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
            mode_class = ["Major", "Minor"]
            try:
                t = int(tonic)
                m = int(mode)
                if 0 <= t < 12 and 0 <= m < 2:
                    key_name = f"{pitch_class[t]} {mode_class[m]}"
            except (ValueError, TypeError):
                pass

        # 2. Parse BPM
        bpm = raw_json.get("rhythm", {}).get("beatsPerMinute", 0.0)

        # 3. Parse Loudness
        loudness = raw_json.get("loudness", {}).get("integrated", {}).get("value", 0.0)
        
        # 4. Extract ultra-minimal segments (structural shift timestamps)
        segments = raw_json.get("structure", {}).get("segments", [])
        simple_segments = []
        for seg in segments:
            start_dict = seg.get("start", {})
            val = start_dict.get("value", 0)
            timescale = start_dict.get("timescale", 44100)
            time_sec = (val / timescale) if timescale > 0 else 0
            simple_segments.append(f"{time_sec:.0f}s")

        return {
            "key": key_name,
            "bpm": round(bpm, 1) if bpm else 0,
            "loudness": round(loudness, 1) if loudness else 0,
            "shifts": simple_segments
        }
    except Exception as e:
        print(f"Error parsing reduced metadata: {e}")
        return None

def analyze_setlist_with_mlx(playlist_data: list[dict], model_id: str = "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit"):
    print(f"\n--- Running MLX-LM ({model_id}) ---")
    try:
        from mlx_lm import load, generate
    except ImportError:
        print("mlx-lm not installed. Run: pip install mlx-lm")
        return None

    prompt = f"""You are a musical analysis AI. Here is the structural audio data (Key, BPM, Loudness, and structural segments like intros/outros) extracted from a playlist of tracks:
{json.dumps(playlist_data, indent=2)}

Analyze this DJ setlist snippet. Describe the overall flow, the tempo progression, and any harmonic key transitions or structural overlap opportunities between the tracks."""
    system_prompt = "You are an expert DJ and music analyst. Your goal is to analyze playlist audio structure and provide rich, useful insights about the set's flow, energy, and mixing opportunities based on intro/outro durations and harmonic key matching. Be highly analytical but avoid unnecessary verbosity or fluff."

    start_load = time.time()
    model, tokenizer = load(model_id)
    print(f"Model loaded in {time.time() - start_load:.2f}s")
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        formatted_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        formatted_prompt = prompt

    print("Generating response...")
    start_time = time.time()
    
    response = generate(
        model, 
        tokenizer, 
        prompt=formatted_prompt, 
        max_tokens=400, 
        verbose=True
    )
    
    end_time = time.time()
    duration = end_time - start_time
    approx_tokens = len(tokenizer.encode(response))
    tokens_per_sec = approx_tokens / duration if duration > 0 else 0
    print(f"\n[MLX-LM Stats] Time: {duration:.2f}s | Speed: ~{tokens_per_sec:.2f} tokens/sec")
    
    return response
