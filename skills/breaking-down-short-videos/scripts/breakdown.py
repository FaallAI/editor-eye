# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "faster-whisper>=1.1",
#   "numpy>=1.26",
#   "opencv-python-headless>=4.9",
#   "rapidocr-onnxruntime>=1.3",
#   "yt-dlp>=2025.1.1",
# ]
# ///
"""Break a short video into what an editor notices, as files an agent can read.

    uv run breakdown.py <video file or URL> --out <dir> [--whisper-model PATH_OR_NAME] [--language id]

Writes to <dir>:
  breakdown.md    one row per shot: time, words spoken, text on screen, camera move, loudness
  breakdown.json  the same, plus every word with its time and the source metadata
  sheet-NN.jpg    four shots per image, each as its first, middle and last frame
Needs ffmpeg and ffprobe on PATH. Nothing leaves the machine except a URL download.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

STRIP_W, STRIP_H = 180, 320


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def fetch(url: str, out: Path) -> tuple[Path, dict]:
    """Download a public post once, with its metadata (title, account, date, counts)."""
    import yt_dlp

    options = {"outtmpl": str(out / "source.%(ext)s"), "format": "b[height<=1280]/b", "noplaylist": True,
               "quiet": True, "writeinfojson": False}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))
    keep = ("title", "description", "uploader", "channel", "upload_date", "duration", "view_count",
            "like_count", "comment_count", "repost_count", "track", "artist", "webpage_url")
    return path, {k: info.get(k) for k in keep if info.get(k) is not None}


def centre_histogram(frame: np.ndarray) -> np.ndarray:
    """Colour histogram of the middle of the picture, where the sharp clip sits on a blur-fill."""
    h, w = frame.shape[:2]
    middle = frame[int(h * 0.3):int(h * 0.7), int(w * 0.15):int(w * 0.85)]
    hsv = cv2.cvtColor(np.ascontiguousarray(middle), cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [16, 8, 8], [0, 180, 0, 256, 0, 256])
    return cv2.normalize(hist, hist).flatten()


def centre_cuts(frames: np.ndarray, rate: float, limit: float) -> list[float]:
    """Cuts seen in the middle of the picture. Blur-fill keeps the borders alike across a cut, which hides
    it from a whole-frame detector; the sharp clip in the middle changes."""
    hists = [centre_histogram(f) for f in frames]
    return [round(i / rate, 2) for i in range(1, len(hists))
            if cv2.compareHist(hists[i - 1], hists[i], cv2.HISTCMP_CORREL) < limit]


def cuts(video: Path, frames: np.ndarray, rate: float, threshold: float, centre: float,
         duration: float) -> list[tuple[float, float]]:
    info = run("ffmpeg", "-hide_banner", "-i", str(video), "-vf", f"select='gt(scene,{threshold})',showinfo",
               "-f", "null", "-").stderr
    times = sorted([float(t) for t in re.findall(r"pts_time:([0-9.]+)", info)] + centre_cuts(frames, rate, centre))
    merged: list[float] = []
    for t in times:
        if 0.2 < t < duration - 0.2 and (not merged or t - merged[-1] >= 0.4):
            merged.append(t)
    edges = [0.0] + merged + [duration]
    return [(a, b) for a, b in zip(edges, edges[1:]) if b - a > 0.15]


def decode(video: Path, rate: float) -> np.ndarray:
    """Every frame at `rate` fps, 360 px wide. ffmpeg decodes, so AV1 and HEVC work too."""
    probe = run("ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                "-of", "csv=p=0", str(video)).stdout.strip().split(",")
    w, h = int(probe[0]), int(probe[1])
    width = 360
    height = int(round(h * width / w / 2)) * 2
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={rate},scale={width}:{height}",
                          "-pix_fmt", "bgr24", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, height, width, 3)


def transcribe(video: Path, model_name: str, language: str | None) -> tuple[str | None, list[dict]]:
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-f",
                          "f32le", "-"], capture_output=True, check=False).stdout
    if not pcm:
        return None, []
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, meta = model.transcribe(np.frombuffer(pcm, np.float32), word_timestamps=True, vad_filter=True,
                                      language=language)
    words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)}
             for seg in segments for w in (seg.words or [])]
    return meta.language, words


def loudness(video: Path) -> tuple[list[tuple[float, float]], list[float]]:
    """Momentary loudness every 0.1 s, and the moments well above the bed (hits, whooshes, stings)."""
    text = run("ffmpeg", "-hide_banner", "-i", str(video), "-af", "ebur128", "-f", "null", "-").stderr
    series = [(float(t), float(m)) for t, m in re.findall(r"t:\s*([0-9.]+)\s+TARGET.*?M:\s*(-?[0-9.]+)", text)]
    values = [m for _, m in series if m > -70]
    if not values:
        return series, []
    bed = statistics.median(values)
    peaks, last = [], -1.0
    for i in range(1, len(series) - 1):
        t, m = series[i]
        if m > bed + 4 and m >= series[i - 1][1] and m >= series[i + 1][1] and t - last > 0.5:
            peaks.append(round(t, 1))
            last = t
    return series, peaks


def motion(frames: np.ndarray, rate: float, a: float, b: float) -> dict:
    """Zoom and pan across a shot from tracked corners. It also counts motion inside the picture."""
    first, last = int(np.ceil(a * rate)), int(np.floor(b * rate)) - 1
    scale, tx, ty, steps = 1.0, 0.0, 0.0, 0
    for i in range(max(first, 0), min(last, len(frames) - 1)):
        g0 = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
        g1 = cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY)
        pts = cv2.goodFeaturesToTrack(g0, 200, 0.01, 8)
        if pts is None or len(pts) < 8:
            continue
        nxt, ok, _ = cv2.calcOpticalFlowPyrLK(g0, g1, pts, None)
        good = ok.reshape(-1) == 1
        if good.sum() < 8:
            continue
        m, _ = cv2.estimateAffinePartial2D(pts[good], nxt[good])
        if m is None:
            continue
        scale *= float(np.hypot(m[0, 0], m[1, 0]))
        tx, ty, steps = tx + float(m[0, 2]), ty + float(m[1, 2]), steps + 1
    width = frames.shape[2]
    return {"zoom_pct": round((scale - 1) * 100, 1), "pan_x_pct": round(tx / width * 100, 1),
            "pan_y_pct": round(ty / width * 100, 1), "samples": steps}


def describe_motion(m: dict) -> str:
    parts = []
    if abs(m["zoom_pct"]) >= 4:
        parts.append(f"zoom {'in' if m['zoom_pct'] > 0 else 'out'} {abs(m['zoom_pct']):.0f}%")
    if abs(m["pan_x_pct"]) >= 8:
        parts.append(f"pan {'left' if m['pan_x_pct'] < 0 else 'right'} {abs(m['pan_x_pct']):.0f}%")
    if abs(m["pan_y_pct"]) >= 8:
        parts.append(f"move {'up' if m['pan_y_pct'] < 0 else 'down'} {abs(m['pan_y_pct']):.0f}%")
    return ", ".join(parts) or "still"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="a video file, or a public post URL yt-dlp understands")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--scene", type=float, default=0.3, help="whole-frame cut threshold; lower finds more")
    parser.add_argument("--centre", type=float, default=0.5,
                        help="centre-of-picture cut threshold (histogram correlation); higher finds more")
    parser.add_argument("--whisper-model", default="large-v3-turbo", help="a faster-whisper model name or path")
    parser.add_argument("--language", default=None, help="speech language code; detected when left out")
    parser.add_argument("--no-ocr", action="store_true")
    args = parser.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            sys.exit(f"{tool} is required on PATH")
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    metadata: dict = {}
    if re.match(r"https?://", args.source):
        video, metadata = fetch(args.source, out)
    else:
        video = Path(args.source)

    duration = float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                         str(video)).stdout)
    rate = 5.0 if duration <= 180 else 2.0
    frames = decode(video, rate)
    shots = cuts(video, frames, rate, args.scene, args.centre, duration)
    language, words = transcribe(video, args.whisper_model, args.language)
    series, peaks = loudness(video)
    ocr = None
    if not args.no_ocr:
        from rapidocr_onnxruntime import RapidOCR

        ocr = RapidOCR()

    def frame_at(t: float) -> np.ndarray:
        return frames[min(len(frames) - 1, max(0, int(round(t * rate))))]

    def read_text(t: float) -> list[str]:
        if ocr is None:
            return []
        result, _ = ocr(frame_at(t))
        return [line[1] for line in (result or []) if line[2] >= 0.6 and len(line[1].strip()) >= 3]

    rows, strips = [], []
    for n, (a, b) in enumerate(shots, start=1):
        times = (a + 0.1, (a + b) / 2, b - 0.1)
        seen: list[str] = []
        for t in times:
            for line in read_text(t):
                if line not in seen:
                    seen.append(line)
        m = motion(frames, rate, a, b)
        inside = [v for t, v in series if a <= t < b and v > -70]
        # The word being spoken, or last begun, when this shot starts: how a cut sits against the voice.
        before = [w for w in words if w["s"] <= a + 0.05]
        cut_word = None
        if n > 1 and before:
            w = before[-1]
            cut_word = {"word": w["w"], "word_start": w["s"], "lag": round(a - w["s"], 2),
                        "during_word": bool(w["s"] <= a <= w["e"])}
        # A long shot whose first and last pictures differ probably holds a cut the detectors missed.
        alike = float(cv2.compareHist(centre_histogram(frame_at(times[0])), centre_histogram(frame_at(times[2])),
                                      cv2.HISTCMP_CORREL))
        row = {
            "shot": n, "start": round(a, 2), "end": round(b, 2), "seconds": round(b - a, 2),
            "check_for_cut": bool(b - a > 1.0 and alike < 0.6),
            "cut_on_word": cut_word,
            "said": " ".join(w["w"] for w in words if a - 0.1 <= w["s"] < b),
            "on_screen": seen[:30], "motion": m, "motion_text": describe_motion(m),
            "lufs": round(sum(inside) / len(inside), 1) if inside else None,
            "audio_peaks": [p for p in peaks if a <= p < b],
        }
        rows.append(row)
        tiles = [cv2.resize(frame_at(t), (STRIP_W, STRIP_H)) for t in times]
        strip = np.hstack(tiles)
        cv2.rectangle(strip, (0, 0), (170, 22), (0, 0, 0), -1)
        cv2.putText(strip, f"#{n} {a:.1f}-{b:.1f}s", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        strips.append(strip)

    for i in range(0, len(strips), 4):
        group = strips[i:i + 4] + [np.zeros_like(strips[0])] * (4 - len(strips[i:i + 4]))
        cv2.imwrite(str(out / f"sheet-{i // 4 + 1:02d}.jpg"), np.vstack(group), [cv2.IMWRITE_JPEG_QUALITY, 85])

    lengths = [r["seconds"] for r in rows]
    summary = {"source": str(args.source), "duration": round(duration, 2), "shots": len(rows),
               "average_shot": round(statistics.mean(lengths), 2) if lengths else None,
               "language": language, "words": len(words), "metadata": metadata}
    (out / "breakdown.json").write_text(json.dumps({**summary, "rows": rows, "transcript": words},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")

    def cell(text: str) -> str:
        return text.replace("|", "/").replace("\n", " ")

    lines = [f"# Breakdown: {args.source}", "",
             f"{duration:.1f} s, {len(rows)} shots, average {summary['average_shot']} s, speech {language}, "
             f"{len(words)} words.", ""]
    if metadata:
        lines += ["Metadata: " + "; ".join(f"{k}: {cell(str(v))[:200]}" for k, v in metadata.items()), ""]
    lines += ["Camera moves are estimates and include motion inside the picture. Audio peaks are moments "
              "4 LU above the median loudness: hits, whooshes or stings, not labelled.", "",
              "Cut on: the word spoken or last begun when the shot starts, and how long after that word's "
              "start the cut lands.", "",
              "| # | Time | s | Cut on | Said | On screen | Camera | LUFS | Peaks |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        c = r["cut_on_word"]
        cut_on = f"{cell(c['word'])} {c['lag']:+.2f}s" if c else ""
        mark = " (check: may hold a cut)" if r["check_for_cut"] else ""
        lines.append(f"| {r['shot']}{mark} | {r['start']:.1f}-{r['end']:.1f} | {r['seconds']:.1f} | {cut_on} | "
                     f"{cell(r['said'])} | "
                     f"{cell(' / '.join(r['on_screen']))} | {r['motion_text']} | {r['lufs']} | "
                     f"{', '.join(str(p) for p in r['audio_peaks'])} |")
    (out / "breakdown.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} shots, {len(words)} words, {len(strips)} strips in {(len(strips) + 3) // 4} sheets -> {out}")


if __name__ == "__main__":
    main()
