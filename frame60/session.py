"""
Persists job state (which chunks are already converted, and where) to a
small JSON file, so a job interrupted by --quit, a crash, low battery,
or Termux getting killed in the background can be picked up again with
--resume instead of starting over from chunk zero.
"""
import hashlib
import json
import os
import time

from .config import SESSION_DIR_NAME


def _session_dir():
    path = os.path.join(os.path.expanduser("~"), SESSION_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def job_id(src_path, target_fps, mode):
    """Identify a job by source file + settings, so changing settings
    doesn't silently resume with the wrong ones."""
    src_stat = os.stat(src_path)
    key = f"{os.path.abspath(src_path)}|{src_stat.st_size}|{target_fps}|{mode}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


class Session:
    def __init__(self, jid):
        self.jid = jid
        self.path = os.path.join(_session_dir(), f"{jid}.json")
        self.data = {"created": time.time(), "chunks_done": [], "settings": {}}
        if os.path.exists(self.path):
            with open(self.path) as f:
                self.data = json.load(f)

    def exists(self):
        return os.path.exists(self.path)

    def mark_chunk_done(self, chunk_index, out_path):
        entry = {"index": chunk_index, "output": out_path}
        self.data["chunks_done"] = [
            c for c in self.data["chunks_done"] if c["index"] != chunk_index
        ] + [entry]
        self.save()

    def done_indices(self):
        return {c["index"] for c in self.data["chunks_done"]}

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)

    def clear(self):
        if os.path.exists(self.path):
            os.remove(self.path)
