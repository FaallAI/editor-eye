# How `breaking-down-short-videos` was tested

Written test-first (the writing-skills method): an agent analysed a reference Short without the
skill, the gaps it left became the skill, and agents with the skill were run against it.

## Baseline, without the skill (2026-11-09)

Task: "analyse how this reference Short is edited", one Indonesian YouTube Short (101 s, AV1).

What the agent did: one contact sheet at a frame every 4 s, four full frames, ffmpeg scene cuts,
loudness and silence. What it left out:

- **No transcript.** It never learnt what was said, so "cuts land on sentence boundaries" was a guess.
- **Sparse frames.** Most of the content was inferred from 25 tiles.
- **No context.** No search; the stories were never checked against a source.
- **No link between line and picture.** It described the look and wrote a generic recreation recipe,
  with no reason for any picture's place.

## With the skill, first version

Same video. The agent ran the script, read every sheet, searched once and found the real case behind
the first story with three sources, marked the parts it could not confirm, and filled the beats table
with roles and reasons. Its feedback changed the skill and the script:

- Cuts were far too coarse (11 shots where there are about 30 clips): blur-fill keeps the borders
  alike across a cut. The script now also detects cuts in the centre of the picture (11 -> 27).
- "How soon after the word the cut lands" could not be read from the output. Each row now names the
  word the cut lands on and the lag.
- Multi-story videos, how many searches are enough, cross-checking names between speech and OCR, and
  a Windows command line were added to the skill.

## With the skill, second version

A fresh agent on a different Short (Sybh8vKbzkg, 65 s). It followed the whole shape: every sheet read,
one search that confirmed the central story with five sources and named two figures the sources
disagree on, a beats table whose reasons cite the cut lags, seven rules with shot evidence, and the
limits. Its feedback added:

- a per-shot "check: may hold a cut" flag when a long shot's first and last pictures differ; on this
  video it marks 10 shots, 7 of the 12 the agent found by eye;
- how to read the cut lag, large camera readings, noisy on-screen text, dark frames, other languages,
  local files without metadata, and absolute model paths.

Not done yet: labelling music and sound effects, and measuring text boxes (size, position, colour).
