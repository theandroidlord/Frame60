"""
Collects per-chunk stats during a run and prints a summary table (and
writes stats.json alongside the output) once the job finishes or stops.
"""
import json
import time


def _human_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


class StatsCollector:
    def __init__(self):
        self.start_time = time.time()
        self.chunks = []

    def add_chunk(self, index, elapsed_s, avg_speed_x, in_size, out_size):
        self.chunks.append({
            "index": index,
            "elapsed_s": round(elapsed_s, 1),
            "avg_speed_x": round(avg_speed_x, 2),
            "input_bytes": in_size,
            "output_bytes": out_size,
        })

    def summary(self):
        total_elapsed = time.time() - self.start_time
        total_in = sum(c["input_bytes"] for c in self.chunks) or 1
        total_out = sum(c["output_bytes"] for c in self.chunks)
        avg_speed = (
            sum(c["avg_speed_x"] for c in self.chunks) / len(self.chunks)
            if self.chunks else 0
        )
        return {
            "chunks_processed": len(self.chunks),
            "total_elapsed_s": round(total_elapsed, 1),
            "avg_speed_x": round(avg_speed, 2),
            "input_bytes": total_in,
            "output_bytes": total_out,
            "size_ratio": round(total_out / total_in, 2),
        }

    def print_summary(self):
        s = self.summary()
        print("\n--- frame60 summary ---")
        print(f"Chunks processed : {s['chunks_processed']}")
        print(f"Total time       : {s['total_elapsed_s'] / 60:.1f} min")
        print(f"Avg encode speed : {s['avg_speed_x']}x realtime")
        print(f"Input size       : {_human_bytes(s['input_bytes'])}")
        print(f"Output size      : {_human_bytes(s['output_bytes'])}")
        print(f"Size ratio       : {s['size_ratio']}x")

    def write_json(self, path):
        with open(path, "w") as f:
            json.dump(self.summary(), f, indent=2)
