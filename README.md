# editor-eye

Agent skills for reading short-form video the way an editor does.

An agent cannot watch or hear a video. These skills turn a video into things it can read (every shot,
the words spoken with their times, the text on screen, camera moves, loudness) and tell it how to
explain why each picture sits under each line, with the story behind the video checked against its
sources.

## Skills

| Skill | Use it when |
|---|---|
| [`breaking-down-short-videos`](skills/breaking-down-short-videos/SKILL.md) | studying how a TikTok, Reel or Short is edited, or turning a reference into an editing style |

## Install

Claude Code reads personal skills from `~/.claude/skills/`. Link the skill folder there:

```bash
ln -s "$(pwd)/skills/breaking-down-short-videos" ~/.claude/skills/breaking-down-short-videos
```

On Windows, copy the folder instead, or use `mklink /D` from an elevated prompt.

## Requirements

- [`uv`](https://docs.astral.sh/uv/): the script declares its own Python dependencies (faster-whisper,
  OpenCV, RapidOCR, yt-dlp) and `uv run` installs them in an isolated environment.
- `ffmpeg` and `ffprobe` on `PATH`. On Windows, run the script inside WSL.
- The first run downloads the faster-whisper model (`large-v3-turbo`, about 1.6 GB) unless
  `--whisper-model` points at a local copy.

Everything runs locally. Only a URL download reaches the network.

## How the skill was tested

The skill was written test-first, as the
[writing-skills](https://github.com/obra/superpowers) method asks: an agent analysed a reference Short
without the skill, and the gaps it left became the skill's steps. See
[`docs/testing.md`](docs/testing.md).

## License

Copyright 2026 FaallAI. Licensed under the [Apache License 2.0](LICENSE).
