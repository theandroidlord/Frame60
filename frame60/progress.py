"""
Runs one ffmpeg command as a subprocess, parses its machine-readable
`-progress pipe:1` output, and renders a single-line colored progress
bar with percent, encode speed, elapsed time, and ETA. Also exposes
pause()/resume()/kill() on the live process so the thermal guard and
the keyboard listener can control it mid-run.
"""
import os
import re
import signal
import subprocess
import sys
import time

from . import colors

_SPEED_RE = re.compile(r"([\d.]+)x")

# Real block characters look far more "pro" than plain # / - -- but
# fall back cleanly on terminals that can't render them.
_FILL_CHAR = "\u2588" if colors.UNICODE_OK else "#"
_EMPTY_CHAR = "\u2591" if colors.UNICODE_OK else "-"


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
    return colors.green(_FILL_CHAR * filled) + colors.dim(_EMPTY_CHAR * (width - filled))


class ProgressRun:
    """One ffmpeg invocation with a live colored progress bar and pause/resume."""

    def __init__(self, cmd, total_duration_s, label=""):
        self.cmd = cmd
        self.total_duration_s = max(total_duration_s, 0.001)
        self.label = label
        self.process = None
        self.paused = False
        self._start_time = None
        self._last_out_time = 0.0
        self._last_speed = 0.0
        self._last_visible_len = 0

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
                m = _SPEED_RE.match(value)
                if m:
                    self._last_speed = float(m.group(1))
            elif key == "progress":
                self._render()
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

    def _render(self):
        snap = self.snapshot()
        pct = snap["fraction"] * 100
        state = colors.bold_yellow("PAUSED") if self.paused else ""
        label = colors.bold_cyan(self.label)
        pct_str = colors.bold(f"{pct:5.1f}%")
        speed_str = colors.cyan(f"{snap['speed_x']:.2f}x")
        elapsed_str = colors.dim(_fmt_time(snap["elapsed_s"]))
        eta_str = colors.yellow(_fmt_time(snap["eta_s"]))

        line = (
            f"\r{label} [{_bar(snap['fraction'])}] {pct_str}  "
            f"speed {speed_str}  elapsed {elapsed_str}  ETA {eta_str}  {state}"
        )
        # Pad (never truncate) based on *visible* length so we clear any
        # leftover characters from a longer previous line without ever
        # slicing through an ANSI escape sequence and corrupting color state.
        visible = colors.visible_len(line)
        pad = max(0, self._last_visible_len - visible)
        self._last_visible_len = visible
        sys.stdout.write(line + (" " * pad))
        sys.stdout.flush()
