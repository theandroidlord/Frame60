"""
Guided menu -- zero flags, zero copy-paste. Launch with no arguments
(`python -m frame60`, or double-click start.bat / run start.sh) and
answer plain-language prompts instead of remembering command syntax.

collect_args() returns an argparse.Namespace shaped exactly like what
build_parser() would produce, so it plugs straight into cli.run_job() --
the guided menu and the flag-based CLI share the exact same conversion
engine underneath, just a different front door.
"""
import argparse
import os

from . import colors
from . import session as session_mod
from .config import DEFAULT_TARGET_FPS, PROFILES

VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".ts")

PROFILE_ORDER = ["battery-saver", "balanced", "performance"]
PROFILE_BLURBS = {
    "battery-saver": "Gentlest on the device. Best on a phone, or for a long unattended run.",
    "balanced": "Reasonable middle ground. Good default for most laptops/desktops.",
    "performance": "Fastest, most demanding. Best when plugged in on a real PC.",
}

MODE_ORDER = ["interpolate", "blend", "dupe"]
MODE_BLURBS = {
    "interpolate": "Best-looking result (real motion smoothing). Slowest.",
    "blend": "Softer look, much lighter on the device.",
    "dupe": "Fastest by far. Noticeably choppier.",
}


def is_termux():
    return "com.termux" in os.environ.get("PREFIX", "") or os.path.exists("/data/data/com.termux")


def _ask(prompt, default=None):
    suffix = colors.dim(f" [{default}]") if default not in (None, "") else ""
    try:
        raw = input(f"{colors.bold(prompt)}{suffix}: ").strip()
    except EOFError:
        raw = ""
    return raw if raw else default


def _ask_yes_no(prompt, default=True):
    default_label = "Y/n" if default else "y/N"
    while True:
        raw = _ask(f"{prompt} ({default_label})", "")
        if raw == "":
            return default
        if raw.lower() in ("y", "yes"):
            return True
        if raw.lower() in ("n", "no"):
            return False
        print(colors.dim("  Just y or n, whichever's closer."))


def _ask_choice(prompt, items, blurbs, default_index=0):
    print(colors.bold(prompt))
    for i, key in enumerate(items, 1):
        marker = colors.green("  <- default") if (i - 1) == default_index else ""
        print(f"  {colors.cyan(f'{i}.')} {colors.bold(key)}{marker}")
        print(f"     {colors.dim(blurbs.get(key, ''))}")
    while True:
        raw = _ask("Pick a number", str(default_index + 1))
        if raw is not None and raw.isdigit() and 1 <= int(raw) <= len(items):
            return items[int(raw) - 1]
        print(colors.dim(f"  Enter a number from 1 to {len(items)}."))


def _find_video_files():
    try:
        names = os.listdir(".")
    except OSError:
        return []
    return sorted(n for n in names if n.lower().endswith(VIDEO_EXTENSIONS))


def _ask_input_file():
    found = _find_video_files()
    while True:
        if found:
            print(colors.bold("\nVideo files found in this folder:"))
            for i, name in enumerate(found, 1):
                print(f"  {colors.cyan(f'{i}.')} {name}")
            print(f"  {colors.cyan(f'{len(found) + 1}.')} "
                  f"{colors.dim('Type/paste a different path instead')}")
            raw = _ask("Pick a number, or paste a path")
            if raw and raw.isdigit() and 1 <= int(raw) <= len(found):
                return found[int(raw) - 1]
            path = raw
        else:
            path = _ask("No video files spotted in this folder -- paste the path to your file")
        if path and os.path.exists(path):
            return path
        print(colors.red(f"  Can't find that file: {path!r}. Try again."))


def _print_banner():
    if colors.UNICODE_OK:
        title = " frame60 -- guided setup (no commands needed) ".center(48)
        print(colors.bold_cyan("\u250c" + "\u2500" * 48 + "\u2510"))
        print(colors.bold_cyan("\u2502") + colors.bold(title) + colors.bold_cyan("\u2502"))
        print(colors.bold_cyan("\u2514" + "\u2500" * 48 + "\u2518"))
    else:
        print(colors.bold_cyan("=" * 50))
        print(colors.bold(" frame60 -- guided setup (no commands needed)"))
        print(colors.bold_cyan("=" * 50))


def _suggest_output_name(input_path, fps):
    stem, ext = os.path.splitext(input_path)
    return f"{stem}_{fps}fps{ext or '.mp4'}"


def collect_args():
    """Walk the user through every setting in plain language. Returns
    None if they bail out at any point (nothing gets touched either way)."""
    _print_banner()

    try:
        input_path = _ask_input_file()

        fps_raw = _ask("\nTarget frame rate", str(DEFAULT_TARGET_FPS))
        fps = int(fps_raw) if str(fps_raw).isdigit() else DEFAULT_TARGET_FPS

        output_path = _ask("Save result as", _suggest_output_name(input_path, fps))

        default_profile_index = PROFILE_ORDER.index("battery-saver" if is_termux() else "balanced")
        profile = _ask_choice(
            "\nHow gentle should this be on your device?",
            PROFILE_ORDER, PROFILE_BLURBS, default_profile_index,
        )

        mode = None
        if _ask_yes_no("\nWant to pick the quality mode yourself? (default just uses "
                        "whatever the profile above recommends)", False):
            mode = _ask_choice("\nQuality mode:", MODE_ORDER, MODE_BLURBS, 0)

        threads = preset = chunk_minutes = max_temp = None
        no_thermal_guard = no_hotkeys = keep_chunks = False
        if _ask_yes_no("\nShow advanced options (threads, chunk size, temp limit)?", False):
            t = _ask("CPU threads to use (blank = use profile default)", "")
            threads = int(t) if t.isdigit() else None
            pr = _ask("x264 preset override, e.g. ultrafast/veryfast/fast (blank = profile default)", "")
            preset = pr or None
            c = _ask("Chunk length in minutes (blank = use profile default)", "")
            chunk_minutes = int(c) if c.isdigit() else None
            mt = _ask("Auto-pause temperature in Celsius (blank = use profile default)", "")
            max_temp = float(mt) if mt.replace(".", "", 1).isdigit() else None
            no_thermal_guard = not _ask_yes_no("Keep the thermal auto-pause on?", True)
            no_hotkeys = not _ask_yes_no("Keep p/r/q pause hotkeys on?", True)
            keep_chunks = _ask_yes_no("Keep the intermediate chunk files afterward?", False)

        resume = fresh = False
        mode_for_id = mode or PROFILES[profile]["mode"]
        jid = session_mod.job_id(input_path, fps, mode_for_id)
        sess = session_mod.Session(jid)
        if sess.exists() and sess.done_indices():
            if _ask_yes_no(
                f"\nFound an unfinished job for this file "
                f"({len(sess.done_indices())} chunk(s) already done). Resume it?",
                True,
            ):
                resume = True
            else:
                fresh = True

        mode_line = mode_for_id if mode else f"{mode_for_id} {colors.dim('(from profile)')}"
        print(colors.bold_cyan("\n--- summary ---"))
        print(f"{colors.dim('Input')}    : {input_path}")
        print(f"{colors.dim('Output')}   : {output_path}")
        print(f"{colors.dim('FPS')}      : {colors.bold_green(str(fps))}")
        print(f"{colors.dim('Profile')}  : {colors.yellow(profile)}")
        print(f"{colors.dim('Mode')}     : {mode_line}")
        if resume:
            print(colors.yellow("Resuming : yes, previous progress will be reused"))
        print(colors.bold_cyan("---------------"))

        if not _ask_yes_no("\nStart converting now?", True):
            print(colors.yellow("No problem -- nothing was touched. Run it again whenever you're ready."))
            return None

    except KeyboardInterrupt:
        print(colors.yellow("\nCancelled -- nothing was touched."))
        return None

    return argparse.Namespace(
        input=input_path, output=output_path, fps=fps, mode=mode, profile=profile,
        threads=threads, preset=preset, chunk_minutes=chunk_minutes, max_temp=max_temp,
        no_thermal_guard=no_thermal_guard, no_hotkeys=no_hotkeys,
        resume=resume, fresh=fresh, dry_run=False, keep_chunks=keep_chunks,
    )
