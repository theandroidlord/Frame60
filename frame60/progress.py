"""
Runs one ffmpeg command as a subprocess, parses its machine-readable
`-progress pipe:1` output, and renders a single-line progress bar with
percent, encode speed, elapsed time, and ETA. Also exposes pause()/
resume()/kill() on the live process so the thermal guard and the
keyboard listener can control it mid-run.
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import time


def _fmt_time(seconds):
    if seconds is None or seconds < 0 or seconds == float("inf"):
        return "--:--:--"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _bar(fraction, width=26):
    fraction = max(0.0, min(1.0, fraction))
    filled = int(width * fraction)
    return "#" * filled + "-" * (width - filled)


class ProgressRun:
    """One ffmpeg invocation with a live progress bar and pause/resume."""

    def __init__(self, cmd, total_duration_s, label=""):
        self.cmd = cmd
        self.total_duration_s = max(total_duration_s, 0.001)
        self.label = label
        self.process = None
        self.paused = False
        self._start_time = None
        self._last_out_time = 0.0
        self._last_speed = 0.0

    def start(self):
        self._start_time = time.time()
        self.process = subprocess.Popen(
            self.cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
        )
        return self.process

    def pause(self):
        # Rack it. SIGSTOP freezes ffmpeg mid-rep -- no work lost, it's
        # just standing there holding the position until we say go.
        if self.process and not self.paused:
            try:
                os.kill(self.process.pid, signal.SIGSTOP)
                self.paused = True
            except ProcessLookupError:
                pass

    def resume(self):
        # Back under the bar. SIGCONT and it picks up exactly where it left off.
        if self.process and self.paused:
            try:
                os.kill(self.process.pid, signal.SIGCONT)
                self.paused = False
            except ProcessLookupError:
                pass

    def kill(self):
        if self.process:
            self.process.kill()

    def run(self):
        self.start()
        term_width = shutil.get_terminal_size((80, 20)).columns
        for line in self.process.stdout:
            line = line.strip()
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key == "out_time_ms":
                try:
                    self._last_out_time = max(int(value), 0) / 1_000_000
                except ValueError:
                    pass
            elif key == "speed":
                m = re.match(r"([\d.]+)x", value)
                if m:
                    self._last_speed = float(m.group(1))
            elif key == "progress":
                self._render(term_width)
                if value == "end":
                    break
        self.process.wait()
        sys.stdout.write("\n")
        sys.stdout.flush()
        return self.process.returncode

    def snapshot(self):
        elapsed = time.time() - self._start_time if self._start_time else 0.0
        fraction = min(self._last_out_time / self.total_duration_s, 1.0)
        remaining_media_s = max(self.total_duration_s - self._last_out_time, 0)
        eta_s = remaining_media_s / self._last_speed if self._last_speed > 0 else None
        return {
            "fraction": fraction,
            "elapsed_s": elapsed,
            "eta_s": eta_s,
            "speed_x": self._last_speed,
            "out_time_s": self._last_out_time,
        }

    def _render(self, term_width):
        snap = self.snapshot()
        pct = snap["fraction"] * 100
        state = "PAUSED" if self.paused else ""
        line = (
            f"\r{self.label} [{_bar(snap['fraction'])}] {pct:5.1f}%  "
            f"speed {snap['speed_x']:.2f}x  "
            f"elapsed {_fmt_time(snap['elapsed_s'])}  "
            f"ETA {_fmt_time(snap['eta_s'])}  {state}"
        )
        sys.stdout.write(line[:term_width].ljust(min(term_width, len(line))))
        sys.stdout.flush()
