"""Trusted geometric animation, synchronized to each scene's measured audio duration."""
import math
import os
import subprocess
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT, FPS = 1280, 720, 24
BG, INK, MUTED = "#101821", "#eef3ed", "#aab7ba"
COLORS = ["#74d8c6", "#f7cb74", "#a2b8ff", "#ee9bba", "#9de0a3", "#ccaff1"]


@lru_cache
def font(size):
    paths = [os.environ.get("CHALKCAST_FONT", ""),
             "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/System/Library/Fonts/Supplemental/Arial.ttf"]
    for path in paths:
        if path and Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def fit_font(draw, text, size, width):
    while size > 12 and draw.textlength(text, font=font(size)) > width:
        size -= 1
    return font(size)


def centered(draw, xy, text, size=24, fill=INK, width=1100):
    text = " ".join(text.split())
    f = fit_font(draw, text, size, width)
    draw.text(xy, text, font=f, fill=fill, anchor="mm")


def ease(t):
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


def frame(scene, progress, subtitle="", index=0, total=1):
    im = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(im)
    for x in range(70, WIDTH, 50):
        for y in range(170, 550, 50):
            d.ellipse((x, y, x + 2, y + 2), fill="#27343d")
    d.text((64, 35), "CHALKCAST / AN IDEA IN MOTION", font=font(15), fill=MUTED)
    d.text((1216, 35), f"{index + 1:02} / {total:02}", font=font(16), fill=MUTED, anchor="ra")
    centered(d, (WIDTH / 2, 108), scene.title, 40)
    v = scene.visual
    p = ease(progress * 3)
    left, right, top, bottom = 160, 1120, 230, 500
    if v.kind in {"bars", "chart"}:
        # Include zero so negative-valued charts retain the correct sign.
        low, high = min(0, min(v.values)), max(0, max(v.values))
        span = high - low or 1
        baseline = bottom - (0 - low) / span * (bottom - top)
        d.line((left, baseline, right, baseline), fill=MUTED, width=2)
        d.line((left, top - 20, left, bottom), fill=MUTED, width=2)
        n = len(v.values)
        points = []
        for i, value in enumerate(v.values):
            x = left + (i + 0.5) * (right - left) / n
            y = baseline - value / span * (bottom - top) * p
            if v.kind == "bars":
                w = min(100, (right - left) / n * 0.55)
                d.rounded_rectangle((x - w / 2, min(y, baseline), x + w / 2,
                                     max(y, baseline) + 1), radius=4, fill=COLORS[i])
            points.append((x, y))
            centered(d, (x, max(195, min(530, y - (23 if value >= 0 else -23)))), f"{value:g}", 23,
                     fill=COLORS[i], width=150)
            centered(d, (x, 550), v.labels[i], 21, width=(right - left) / n - 16)
        if v.kind == "chart":
            if len(points) > 1:
                d.line(points, fill=COLORS[0], width=5)
            for x, y in points:
                d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=COLORS[0])
    elif v.kind == "flow":
        n = len(v.labels)
        available = right - left
        w = min(220, available / n - 28)
        for i, label in enumerate(v.labels):
            x = left + (i + 0.5) * available / n
            active = progress * (n + 1) >= i
            color = COLORS[i] if active else "#36444c"
            d.rounded_rectangle((x - w / 2, 305, x + w / 2, 425), radius=16, outline=color, width=3)
            centered(d, (x, 365), label, 27, fill=color, width=w - 22)
            if i < n - 1:
                a, b = x + w / 2 + 6, x + available / n - w / 2 - 6
                d.line((a, 365, b, 365), fill=MUTED, width=3)
                d.polygon([(b, 365), (b - 9, 359), (b - 9, 371)], fill=MUTED)
    elif v.kind == "equation":
        centered(d, (640, 345), v.formula, int(48 + 8 * p), fill=COLORS[0])
        d.line((340, 412, 340 + 600 * p, 412), fill=COLORS[1], width=3)
    if v.caption:
        centered(d, (640, 587), v.caption, 23, fill=MUTED)
    d.rounded_rectangle((50, 618, 1230, 692), radius=12, fill="#1c2731")
    if subtitle:
        centered(d, (640, 654), subtitle, 27, width=1120)
    d.rectangle((0, 714, WIDTH * (index + progress) / total, 720), fill=COLORS[0])
    return im


def render_video(storyboard, segments, destination: Path, progress_callback=lambda x: None):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    silent = destination / "visuals.mp4"
    error_path = destination / "encoder.log"
    with error_path.open("wb") as error_log:
        command = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-vcodec", "rawvideo",
                   "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
                   "-an", "-vcodec", "libx264", "-preset", "veryfast", "-crf", "22",
                   "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(silent)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=error_log)
        try:
            for index, (scene, segment) in enumerate(zip(storyboard.scenes, segments, strict=True)):
                count = math.ceil(segment["seconds"] * FPS)
                segment["render_seconds"] = count / FPS
                for num in range(count):
                    sec = num / FPS
                    cue = next((c["text"] for c in segment["captions"] if c["start"] <= sec < c["end"]), "")
                    im = frame(scene, num / max(1, count - 1), cue, index, len(segments))
                    process.stdin.write(im.tobytes())
                progress_callback(f"Rendered scene {index + 1}/{len(segments)}")
            process.stdin.close()
            if process.wait(timeout=120) != 0:
                raise ValueError("Video encoding failed. See the local encoder.log.")
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.wait()
            raise
    # Decode each scene, pad only to its frame boundary, then concatenate.
    audio_inputs, filters = [], []
    for i, segment in enumerate(segments):
        audio_inputs += ["-i", segment["path"]]
        filters.append(f"[{i}:a]aresample=44100,apad,atrim=duration={segment['render_seconds']:.8f},"
                       f"asetpts=PTS-STARTPTS[a{i}]")
    filters.append("".join(f"[a{i}]" for i in range(len(segments)))
                   + f"concat=n={len(segments)}:v=0:a=1[out]")
    narration_path = destination / "narration.m4a"
    audio_cmd = [ffmpeg, "-y", "-loglevel", "error", *audio_inputs, "-filter_complex", ";".join(filters),
                 "-map", "[out]", "-c:a", "aac", "-b:a", "128k", str(narration_path)]
    with error_path.open("ab") as error_log:
        subprocess.run(audio_cmd, check=True, stderr=error_log, timeout=120)
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(narration_path),
                        "-c", "copy", "-shortest", "-movflags", "+faststart", str(destination / "video.mp4")],
                       check=True, stderr=error_log, timeout=120)
    silent.unlink()
    return destination / "video.mp4"
