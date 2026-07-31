"""
Minimal ANSI color helper. No external dependency (no colorama) --
keeps frame60 stdlib-only. Colors auto-disable when output isn't a real
terminal (piped/redirected, e.g. `> log.txt`) or when NO_COLOR is set,
and self-enable on Windows 10+ via the native virtual-terminal switch
so cmd.exe gets real color without any extra install.
"""
import ctypes
import os
import re
import sys

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _enable_windows_ansi():
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING))
    except Exception:
        return False


def _detect_support():
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FRAME60_FORCE_COLOR"):
        return True
    try:
        if not sys.stdout.isatty():
            return False
    except Exception:
        return False
    if os.name == "nt":
        return _enable_windows_ansi()
    return True


ENABLED = _detect_support()
UNICODE_OK = bool((getattr(sys.stdout, "encoding", "") or "").lower().startswith("utf"))

# Pro-CLI status glyphs -- fall back to plain ASCII on terminals that
# can't render the unicode ones cleanly (older Windows codepages).
CHECK = "\u2713" if UNICODE_OK else "OK"
CROSS = "\u2717" if UNICODE_OK else "X"
WARN = "\u26a0" if UNICODE_OK else "!"

_CODES = {
    "reset": "0", "bold": "1", "dim": "2",
    "red": "31", "green": "32", "yellow": "33", "blue": "34",
    "magenta": "35", "cyan": "36", "white": "37",
}


def set_enabled(value):
    global ENABLED
    ENABLED = bool(value)


def visible_len(s):
    """Length of s as it will actually appear on screen (ANSI codes strip to zero width)."""
    return len(_ANSI_RE.sub("", s))


def _wrap(text, *codes):
    if not ENABLED:
        return str(text)
    seq = ";".join(_CODES[c] for c in codes)
    return f"\033[{seq}m{text}\033[0m"


def bold(t): return _wrap(t, "bold")
def dim(t): return _wrap(t, "dim")
def red(t): return _wrap(t, "red")
def green(t): return _wrap(t, "green")
def yellow(t): return _wrap(t, "yellow")
def blue(t): return _wrap(t, "blue")
def cyan(t): return _wrap(t, "cyan")
def magenta(t): return _wrap(t, "magenta")
def bold_cyan(t): return _wrap(t, "bold", "cyan")
def bold_green(t): return _wrap(t, "bold", "green")
def bold_yellow(t): return _wrap(t, "bold", "yellow")
def bold_red(t): return _wrap(t, "bold", "red")
