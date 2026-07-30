"""
Central configuration: efficiency profiles, defaults, and thermal thresholds.

Each profile is a full set of tuning knobs. --profile picks one; any
individual --threads / --preset / --chunk-minutes / --max-temp flag
overrides just that one field.
"""

# Pick your training split. battery-saver = recovery day, don't be a
# hero. performance = beast mode, plugged in, no distractions.
PROFILES = {
    "battery-saver": {
        "threads": 1,
        "nice": 19,
        "preset": "ultrafast",
        "mode": "blend",
        "max_temp_c": 42,
        "cooldown_s": 45,
        "chunk_minutes": 8,
    },
    "balanced": {
        "threads": 2,
        "nice": 15,
        "preset": "veryfast",
        "mode": "interpolate",
        "max_temp_c": 45,
        "cooldown_s": 30,
        "chunk_minutes": 12,
    },
    "performance": {
        "threads": 4,
        "nice": 0,
        "preset": "fast",
        "mode": "interpolate",
        "max_temp_c": 50,
        "cooldown_s": 20,
        "chunk_minutes": 20,
    },
}

DEFAULT_PROFILE = "balanced"
DEFAULT_TARGET_FPS = 60

# {fps} is substituted at build time.
FILTER_TEMPLATES = {
    # Real motion-compensated interpolation. Best quality, most CPU.
    "interpolate": "minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1",
    # Cheap cross-fade blend between frames. Much lighter than mci.
    "blend": "minterpolate=fps={fps}:mi_mode=blend",
    # Plain frame duplication/drop to hit the target fps. Cheapest, most judder.
    "dupe": "fps={fps}",
}

# Not all devices expose a readable thermal zone without root; we try a
# few common indices and fall back to battery temp (needs termux-api),
# and finally to "no sensor available" if neither works.
THERMAL_ZONE_CANDIDATES = [
    "/sys/class/thermal/thermal_zone0/temp",
    "/sys/class/thermal/thermal_zone1/temp",
    "/sys/class/thermal/thermal_zone2/temp",
]

SESSION_DIR_NAME = ".frame60_sessions"
