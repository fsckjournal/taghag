taghag — automated beatmatched FLAC mixer: SAMPLE INPUTS
=========================================================

A canonical, working input set for tools/mixslice/render_transition.py.
This is one transition: outgoing track A -> incoming track B.
(Mike Shannon - Search Party  ->  Mella Dee - Realisation; adjacent in the
playlist, both grid-BPM ~127, so this pair needs no time-stretch.)

FILES
-----
A__mike_shannon__search_party.flac           Outgoing FLAC master (the audio).
A__mike_shannon__search_party.analyzer.json  Its cuecifer_analyzer output (beat grid).
B__mella_dee__realisation.flac               Incoming FLAC master (the audio).
B__mella_dee__realisation.analyzer.json      Its cuecifer_analyzer output (beat grid).
order__minimal-rekordbox.m3u8                The ordered playlist (defines adjacency).

WHAT THE RENDERER READS
-----------------------
FLAC  -> PCM samples; resampled to 44100; sliced into lead-in / 32-beat overlap /
         lead-out and equal-power crossfaded.
JSON  -> rhythm.beats[]      beat onsets in seconds (CMTime value/timescale).
                             USED to find the anchor beat + measure overlap length.
         structure.sections[] 32-beat phrase starts. USED to snap mix points to
                             musical boundaries.
         rhythm.beatsPerMinute  report label only (the declared header is NOT
                             trusted; true BPM = median beat interval of the grid).
m3u8  -> which two tracks are consecutive (you pick the A/B pair from it).

HOW THESE JSONs WERE PRODUCED
-----------------------------
  cuecifer_analyzer "A.flac" > A.analyzer.json
(the built Swift binary at
 tools/cuecifer-analyzer/.build/out/Products/Release/cuecifer_analyzer)

HOW TO RUN THE TRANSITION
-------------------------
  cd tools && source .venv/bin/activate
  python mixslice/render_transition.py \
    A__mike_shannon__search_party.flac  B__mella_dee__realisation.flac \
    A__mike_shannon__search_party.analyzer.json  B__mella_dee__realisation.analyzer.json \
    out.flac --stems --click
