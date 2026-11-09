---
name: breaking-down-short-videos
description: Use when asked how a short-form video (TikTok, Reels, YouTube Shorts) is edited, to study a reference video's style, to reverse-engineer why its scenes, cuts, text or zooms were chosen, or to turn a reference into a reusable editing style or template.
---

# Breaking down short videos

## Overview

You cannot watch or hear a video. You can read frames and text. An editor's reading needs four
things you only get by measuring: every shot, the words spoken over it with their times, the text on
screen, and the story behind the video. A description of what the video looks like is not a breakdown;
the breakdown explains why each picture sits under each line.

## Step 1: measure

```bash
uv run <this skill's folder>/scripts/breakdown.py <file or URL> --out <dir> [--language id] [--whisper-model PATH]
```

Needs `uv`, `ffmpeg` and `ffprobe`. On Windows run it inside WSL, with paths under `/mnt/<drive>/`:
`MSYS_NO_PATHCONV=1 wsl -e bash -lc 'uv run /mnt/c/.../scripts/breakdown.py /mnt/d/v.mp4 --out /mnt/d/out'`.
The first run downloads a 1.6 GB speech model unless `--whisper-model` points at a local copy.

It writes `breakdown.md` (one row per shot: time, the word the cut lands on, words, on-screen text,
camera move, loudness, audio peaks), `breakdown.json` (plus every word with its time, and the post's
metadata for a URL) and `sheet-NN.jpg` (first, middle and last frame of each shot). `--help` lists the
options.

Read `breakdown.md` and every sheet. Do not sample.

## Step 2: get the story

Collect the names, accounts, events, places, numbers and claims from the words and the on-screen
text. A video can hold several stories (a "3 cases" compilation); give each its own pass. For each
story, find the context in this order:

1. **What the video shows as proof:** posts, handles, replies, articles, notes on screen.
2. **Those sources themselves:** open the posts or articles it shows.
3. **Web search with dates,** for the claims the first two leave open. Small online dramas are rarely
   in the news; large events are.

Search until each central claim is confirmed, contradicted, or not found after two different
queries. Write down which is which. For names and handles, compare the transcript, the on-screen text
and the sheet itself: speech recognition mishears handles and OCR runs words together.

## Step 3: write the reading

Write it in exactly this shape:

1. **The video:** account, length, shots, average shot, date and counts if known, and the style family
   in a few words.
2. **The story:** what happened and who is involved, per story, with sources. Mark every unconfirmed
   claim the video makes.
3. **The beats:** one table row per shot or group of shots: `Time | Beat | Said | Shown | Role | Why it
   fits`.
   - Role is one of: hook, setup, claim, reference, evidence, counter-evidence, payoff, humour, reaction,
     social proof, question, close, callback.
   - Why it fits names the link: the picture shows what the line names, proves it, contrasts with it,
     or reacts to it. Take the timing from the `Cut on` column: the word and how long after its start
     the cut lands.
4. **The rules:** the editing rules the whole video follows, each with two or more shots as evidence.
   For example: every new name gets that person's face within half a second.
5. **The look:** text styles (size as a share of frame width, place, colour, box, how it is revealed),
   framing (blur-fill, cards, picture in picture), camera moves, transitions, sound.
6. **Limits:** what you inferred rather than measured.

## Reading the measurements

| Signal | Trust it when | Watch out for |
|---|---|---|
| Cuts | Each shot's three frames show one picture | Rows marked "check: may hold a cut", and any shot whose frames show two pictures, hold a missed cut; rerun with `--centre 0.6` or `--scene 0.2` (shot numbers change) or place the cut from the sheet and the words |
| Cut on | The cut is a hard cut | The lag is from the start of the word being spoken or last begun; under 0.3 s is a cut on the word, over 1 s a cut in a pause |
| Camera move | The three frames show the same picture | Over about 40% is nearly always a hidden cut or motion inside the picture, not a zoom |
| Words | Most of the time | Names and handles; no punctuation; repeated words |
| On-screen text | As a hint of what to look for | Words run together and repeat; read captions, quotes and other languages from the sheets |
| Audio peaks | They are hits, whooshes or stings above the voice | They are not labelled; music and voice tone are not measured; say unknown |

A dark first or last frame in a sheet is a fade or a darkened overlay, not an empty shot. Text sizes
and colours are your estimates from the sheets; say so. For a local file there is no metadata: write
"unknown", or find the post. Give `--whisper-model` an absolute path (inside WSL, a `/mnt/` path).

## Common mistakes

- Describing the look and stopping there, without saying why each picture is under each line.
- Writing a recreation recipe from a few frames instead of reading every shot.
- Repeating the video's claims as facts.
- Guessing at audio you never measured. Say it is unknown.
- Copying private people's details out of the analysis notes. Keep them in the reading only.
