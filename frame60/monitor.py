"""
Background thermal/lag guard. Polls a temperature source and pauses the
active ffmpeg job (SIGSTOP) when it gets too hot, resuming (SIGCONT)
once it has cooled by a margin. Degrades gracefully to "disabled" if no
sensor is readable on the device (common without root).
"""
import json
import shutil
import subprocess
import threading

from .config import THERMAL_ZONE_CANDIDATES


def read_thermal_zone_c():
    for path in THERMAL_ZONE_CANDIDATES:
        try:
            with open(path) as f:
                raw = int(f.read().strip())
            return raw / 1000 if raw > 1000 else float(raw)
        except (FileNotFoundError, PermissionError, ValueError, OSError):
            continue
    return None


def read_battery_temp_c():
    """Needs the (optional) termux-api package + Termux:API companion app."""
    if shutil.which("termux-battery-status") is None:
        return None
    try:
        out = subprocess.run(
            ["termux-battery-status"], capture_output=True, text=True, timeout=3
        )
        data = json.loads(out.stdout)
        return data.get("temperature")
    except Exception:
        return None


class ThermalGuard(threading.Thread):
    # This is your spotter. It doesn't lift the weight for you -- it just
    # racks it before you hurt yourself, then hands it back once you've
    # shaken it off.
    def __init__(self, progress_run_getter, max_temp_c, cooldown_s,
                 resume_margin_c=3.0, poll_interval_s=5, on_event=None):
        super().__init__(daemon=True)
        self.get_run = progress_run_getter
        self.max_temp_c = max_temp_c
        self.cooldown_s = cooldown_s
        self.resume_margin_c = resume_margin_c
        self.poll_interval_s = poll_interval_s
        self.on_event = on_event or (lambda msg: None)
        self._stop = threading.Event()
        self.last_temp_c = None
        self.available = (
            read_thermal_zone_c() is not None or read_battery_temp_c() is not None
        )

    def current_temp(self):
        return read_thermal_zone_c() or read_battery_temp_c()

    def stop(self):
        self._stop.set()

    def run(self):
        if not self.available:
            return
        while not self._stop.is_set():
            temp = self.current_temp()
            self.last_temp_c = temp
            run = self.get_run()
            if temp is not None and run is not None:
                if temp >= self.max_temp_c and not run.paused:
                    self.on_event(
                        f"temp {temp:.1f}C >= limit {self.max_temp_c}C -> pausing "
                        f"for {self.cooldown_s}s"
                    )
                    run.pause()
                    self._stop.wait(self.cooldown_s)
                    continue
                elif run.paused and temp <= self.max_temp_c - self.resume_margin_c:
                    self.on_event(f"temp {temp:.1f}C cooled down -> resuming")
                    run.resume()
            self._stop.wait(self.poll_interval_s)
