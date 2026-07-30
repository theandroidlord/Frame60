"""
Splits the source into fixed-length chunks (stream copy — fast and
lossless, no re-encode) so each chunk can be converted, checkpointed,
and resumed independently instead of losing all progress if the run is
interrupted partway through. Chunks are stitched back together with a
lossless concat at the end.
"""
import math
import os
import subprocess


def plan_chunks(duration_s, chunk_minutes):
    # Break the whole movie into sets instead of one giant unbroken rep --
    # way easier to recover between chunks than to bail halfway through
    # a single huge one.
    chunk_s = chunk_minutes * 60
    n = max(1, math.ceil(duration_s / chunk_s))
    return [
        (i, i * chunk_s, min(chunk_s, duration_s - i * chunk_s))
        for i in range(n)
    ]


def extract_chunk(src, index, start_s, length_s, workdir):
    out = os.path.join(workdir, f"chunk_{index:04d}_src.mp4")
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_s), "-i", src,
        "-t", str(length_s), "-c", "copy", "-avoid_negative_ts", "make_zero", out,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out


def concat_chunks(chunk_paths, dst, workdir):
    list_path = os.path.join(workdir, "concat_list.txt")
    with open(list_path, "w") as f:
        for p in chunk_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
        "-c", "copy", dst,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
