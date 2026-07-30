"""
Thin wrappers around ffprobe/ffmpeg: probing the source video and
building the actual conversion command. No subprocess is spawned here
long-running — that's progress.py's job.
"""
import json
import shutil
import subprocess
from dataclasses import dataclass


class FFmpegNotFoundError(RuntimeError):
    pass


def check_binaries():
    missing = [b for b in ("ffmpeg", "ffprobe") if shutil.which(b) is None]
    if missing:
        raise FFmpegNotFoundError(
            f"missing required binaries: {', '.join(missing)}. "
            f"Install with: pkg install ffmpeg"
        )


@dataclass
class VideoInfo:
    duration_s: float
    fps: float
    width: int
    height: int
    codec: str


def probe(path):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,width,height,codec_name",
        "-show_entries", "format=duration",
        "-of", "json", path,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    stream = data["streams"][0]
    num, den = stream["r_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) else float(num)
    duration = float(data["format"]["duration"])
    return VideoInfo(
        duration_s=duration,
        fps=round(fps, 3),
        width=int(stream["width"]),
        height=int(stream["height"]),
        codec=stream["codec_name"],
    )


def build_filter(mode, target_fps, filter_templates):
    template = filter_templates.get(mode)
    if template is None:
        raise ValueError(f"unknown mode: {mode!r} (choices: {list(filter_templates)})")
    return template.format(fps=target_fps)


def build_command(src, dst, *, target_fps, mode, threads, preset,
                   filter_templates, extra_args=None, progress_pipe=True):
    """Build the ffmpeg argv list for converting one file/chunk."""
    vf = build_filter(mode, target_fps, filter_templates)
    cmd = ["ffmpeg", "-y", "-i", src]
    if progress_pipe:
        cmd += ["-progress", "pipe:1", "-nostats"]
    cmd += [
        "-threads", str(threads),
        "-filter:v", vf,
        "-c:v", "libx264",
        "-preset", preset,
        "-c:a", "copy",
    ]
    if extra_args:
        cmd += extra_args
    cmd.append(dst)
    return cmd
