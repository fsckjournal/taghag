# Autonomous Intelligence Engine (Cuecifer) Architecture

## 1. Executive Vision
The Cuecifer intelligence engine operates within the `taghag` repository as a deterministic music-library intelligence system. The core thesis is to computationally sequence setlists and validate metadata better than human intuition by merging structural DSP data, acoustic "vibe" analysis, and local Large Language Model (LLM) reasoning.

Legacy DJ/Rekordbox-centric workflows have been permanently retired. The active path relies on high-fidelity source files and local Apple-native AI/ML workflows.

## 2. The Core Pipeline: Apple Native Intelligence
To achieve a three-dimensional understanding of every track, the pipeline has been rebuilt to rely heavily on Apple Silicon capabilities rather than cloud APIs or third-party DJ software.

### 2.1 The Structural Layer (MusicUnderstanding)
We extract offline structural analysis directly from high-fidelity source files (typically FLAC masters) using a native Swift CLI built on Apple's WWDC26 `MusicUnderstanding` framework. 
*   **Outputs:** This yields precise `StructureResult` segment boundaries (intros, outros, drops), `HarmonicResult` (tonic/mode), `RhythmResult` (BPM/pace), and `LoudnessResult` (ITU-R BS.1770 LUFS).
*   **Concurrency Sandbox:** Since executing native Swift `MusicUnderstanding` analysis across hundreds of concurrent threads triggers `AVFoundation` and Metal memory-lock exhaustion (`kIOGPUCommandBufferCallbackErrorOutOfMemory`), the Swift binary execution is strictly sandboxed. It is managed by a Python `ProcessPoolExecutor` throttled to exactly 4 workers, ensuring total pipeline stability.

### 2.2 The Reasoning Layer (MLX-LM)
Structural DSP data provides the acoustic reality, but an intelligence engine must reason over that data to propose setlists, detect anomalies, or normalize genres.
*   **Native 32B Inference:** We utilize `mlx-community/Qwen2.5-32B-Instruct-4bit` running natively via `mlx-lm` on Apple Silicon Unified Memory.
*   **Hardware Overrides:** The 32B model requires approximately 18GB of memory. On a 24GB Unified Memory system, macOS default safety thresholds normally block this allocation. To bypass Metal Out-of-Memory aborts, the system utilizes an experimental override: `sudo sysctl iogpu.wired_limit_mb=21504`. This allocates 21GB exclusively to the active GPU memory, allowing stable inference at ~3.3 tokens/second. 

## 3. Strict Architectural Boundaries

To ensure the safety of the canonical library, the intelligence engine operates under several strict, non-negotiable boundaries:

1. **ML is never metadata authority:** LLMs may propose, cluster, explain, or flag metadata. However, Taghag's deterministic policy engine decides, audits, and writes. No ML output may directly mutate the underlying audio files (e.g. FLAC metadata tags) without passing the validation gate.
2. **MusicUnderstanding does NOT return genre:** The 6 dimensions of `MusicUnderstanding` (key, rhythm, structure, pace, instrument activity, loudness) are strictly empirical, acoustic measurements. Genre is a cultural taxonomy. Under no circumstances should downstream agents or scripts treat these acoustic dimensions as a direct genre classification.
3. **Hardware Overrides are Experimental:** While the `sysctl` memory expansion is operator-proven for local research and inference, override-dependent workflows must never be placed on an unsupervised, automated metadata-write path.
4. **Cleanroom Adherence:** The codebase must not invoke legacy libraries (`tagslut`, `Rekordbox`, etc.) unless specifically permitted by the `audit_cleanroom.py` script exclusions.
