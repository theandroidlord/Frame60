# frame60 💪

**Bulk your video from 24fps up to 60fps without blowing up your phone.**

This thing takes a 24fps movie and grinds out extra frames so it plays
smooth at 60fps — like turning a stiff, choppy set into buttery reps.
Runs on Termux (phone) or cmd/PowerShell (PC/laptop). Built with
efficiency profiles, thermal auto-pause, resumable chunks, and a live
progress bar, so it works hard without gassing out your device.

Tested end-to-end for real: a 24fps clip converted, verified 60fps with
ffprobe, chunk splitting, checkpoint/resume, and the no-sensor fallback
all confirmed working before this ever shipped to you.

## Never touched a terminal? Start here 🔰

You do **not** need to learn any commands or copy-paste anything. After
the one-time install below:

- **Termux (phone):** run `bash start.sh`
- **Windows:** double-click `start.bat`

Either one drops you straight into a guided menu — pick your video from a
numbered list, answer a few plain questions (or just hit Enter to accept
the sensible default each time), confirm, done. No flags, no syntax to
remember. Everything below this point (`--profile`, `--mode`, etc.) is
for people who want to skip the menu and drive it directly — totally
optional.

## Real talk before you load the bar 🏋️

`--mode interpolate` (the good-looking mode, real motion-compensated frame
generation) is a **heavy lift for a CPU**. Phone chips are not desktop
chips — no shortcuts around that. A full movie in interpolate mode can
realistically take **hours** even in efficiency mode. Efficiency mode
doesn't make the work lighter, it makes the *device* handle the work
without overheating or locking up — same total reps, just paced so you
don't tear something. If raw speed matters more than looks to you, drop
down to `--mode blend` or `--mode dupe`. And if it's a whole movie: doing
the conversion on a PC once and just watching the file on your phone will
always out-lift doing the grind on-device.

---

## Install day 1: Termux (phone)

```bash
bash install.sh
```

That pulls `python` and `ffmpeg` via `pkg`. Optional accessory work:
`pkg install termux-api` (+ the Termux:API app) so the thermal guard has
a battery-temp fallback on phones that don't expose a readable sensor.

## Install day 1: cmd shell (Windows PC/laptop)

Two ways in, pick one:

**Option A — let the script do it:**
```cmd
install.bat
```
Uses `winget` to grab Python and ffmpeg if they're not already on your
system, then checks both are on PATH.

**Option B — do it yourself, old-school:**
1. Install Python from python.org (check "Add to PATH" during setup)
2. Install ffmpeg: `winget install ffmpeg` (or grab a build and add it to PATH manually)
3. Confirm both landed correctly:
```cmd
python --version
ffmpeg -version
```

macOS/Linux desktop: same deal as Termux basically — `ffmpeg`/`python3`
installed and on PATH, and you're good, no script needed.

---

## Leg day: running a set

**Easiest way — the guided menu, no flags at all:**

```bash
# Termux
bash start.sh
```
```cmd
:: Windows (or just double-click start.bat)
start.bat
```

That's `python -m frame60` with no arguments under the hood — it notices
nothing was given and opens the guided menu automatically. Works the same
either way: pick your file from a numbered list, answer a handful of
plain questions, confirm, and it runs.

**Power-user way — flags, if you know what you want:**

Same command everywhere, just swap the input/output names:

```bash
# Termux
python -m frame60 input.mp4 output.mp4 --profile battery-saver
```

```cmd
:: cmd shell
python -m frame60 input.mp4 output.mp4 --profile battery-saver
```

Full move list:

```
python -m frame60 IN OUT [--fps 60] [--mode interpolate|blend|dupe]
                          [--profile battery-saver|balanced|performance]
                          [--threads N] [--preset PRESET]
                          [--chunk-minutes N] [--max-temp C]
                          [--no-thermal-guard] [--no-hotkeys]
                          [--resume] [--fresh] [--dry-run] [--keep-chunks]
                          [--wizard]
```

`--wizard` forces the guided menu even if you're the type who normally
uses flags — good for a one-off run where you don't feel like thinking.

`python -m frame60 --help` for the whole menu.

### Warm up first

`--dry-run` prints the whole workout plan (chunk breakdown + exact ffmpeg
commands) without touching a single frame. Check your form before you
load real weight on the bar.

---

## Training programs (efficiency profiles)

| Profile        | Threads | Preset    | Default mode | Max temp | Chunk length | Vibe |
|----------------|:-------:|-----------|---------------|:--------:|:------------:|------|
| battery-saver  | 1       | ultrafast | blend         | 42°C     | 8 min        | recovery day, don't push it |
| balanced       | 2       | veryfast  | interpolate   | 45°C     | 12 min       | normal training day |
| performance    | 4       | fast      | interpolate   | 50°C     | 20 min       | beast mode, plugged in only |

Any single knob overrides the profile default:
`--profile battery-saver --mode interpolate --threads 2`.

## Modes (how the reps get done)

- **interpolate** — real motion-compensated frame generation. Best gains,
  most effort.
- **blend** — cheap cross-fade between frames. Way less strain, softer
  look on fast motion.
- **dupe** — straight frame duplication. Cheapest set in the gym, but it
  shows — looks juddery.

## Spotter (thermal / lag protection)

A background thread checks device temp every few seconds
(`/sys/class/thermal`, falling back to `termux-battery-status` if you've
got termux-api). Cross `--max-temp` and it **racks the weight**
(`SIGSTOP`s ffmpeg, no progress lost) until it cools off, then hands it
back to you (`SIGCONT`). No sensor on your device? It tells you up front
and just skips this — never blocks the workout. Skip the spotter
entirely with `--no-thermal-guard`.

**Heads up on platforms:** the auto-pause spotter and the p/r/q hotkeys
below both rely on Linux/POSIX stuff (`/sys/class/thermal`, `SIGSTOP`,
`termios`). That means:
- **Termux / Linux / macOS** — hotkeys work; thermal auto-pause works if
  your device exposes a sensor (most Linux boxes do, phones vary by
  model/OEM).
- **Windows cmd** — neither is available (no POSIX signals or sensor
  path), so both auto-disable cleanly — the conversion, chunking, resume,
  and stats all still run at full strength either way. Use
  `--profile battery-saver` for the load-management, and Ctrl+C +
  `--resume` as your manual "rack it" move.
- **iPhone/iOS** — no dice, there's no way to run this at all (no
  Termux-equivalent, Apple doesn't allow it).

## Hotkeys mid-set (Termux/Linux/macOS)

- `p` — rack it (pause the current chunk)
- `r` — back under the bar (resume)
- `q` — finish this rep, save your progress, walk away clean

`--no-hotkeys` turns these off. Also auto-disables itself if there's no
real terminal attached (like running under `nohup`).

## Resuming after a rest day

Progress checkpoints **per chunk** (a chunk only counts once it's fully
done), saved to `~/.frame60_sessions/<job-id>.json` on Termux/Linux/macOS
or `%USERPROFILE%\.frame60_sessions\<job-id>.json` on Windows — keyed to
the source file, target fps, and mode. Same command later just continues:

```bash
python -m frame60 input.mp4 output.mp4 --profile battery-saver
# ... interrupted, phone died, closed the terminal, whatever ...
python -m frame60 input.mp4 output.mp4 --profile battery-saver --resume
```

`--fresh` wipes a saved session for that job and starts clean.

## Stats (post-workout numbers)

Every run ends with a summary: chunks processed, total time, average
encode speed (as a multiple of realtime), input/output size, size ratio.
Live progress lines show percent, current speed, elapsed time, and ETA
while it's grinding.

---

## Project structure

```
frame60-project/
├── frame60/
│   ├── __init__.py
│   ├── __main__.py          entry point (python -m frame60)
│   ├── cli.py                argument parsing + orchestration
│   ├── menu.py                 guided menu (no flags, plain-language prompts)
│   ├── config.py              training programs (efficiency profiles), filter templates
│   ├── ffmpeg_utils.py         ffprobe/ffmpeg command building
│   ├── chunker.py               split source into chunks (sets), concat output
│   ├── progress.py               live progress bar/ETA, pause/resume/kill
│   ├── monitor.py                 the spotter (thermal guard)
│   ├── keyboard_control.py        p/r/q hotkeys
│   ├── session.py                  resumable job state
│   └── stats.py                     post-workout stats
├── start.sh                  Termux one-command launcher -> guided menu
├── start.bat                 Windows double-click launcher -> guided menu
├── install.sh                Termux setup
├── install.bat                Windows cmd setup
├── requirements.txt          (stdlib only — documents that)
└── README.md
```

## Troubleshooting (when a rep goes wrong)

- `missing required binaries: ffmpeg, ffprobe` — run `install.sh` (Termux)
  or `install.bat` / manual steps (Windows).
- `start.sh: Permission denied` on Termux — run `chmod +x start.sh` once,
  or just use `bash start.sh` (works either way, no chmod needed).
- Double-clicking `start.bat` flashes and closes — that means Python or
  ffmpeg isn't installed/on PATH yet; run `install.bat` first.
- Footage looks stuttery in `blend`/`dupe` — expected, that's the
  lightweight-set trade-off. Switch to `--mode interpolate` if your
  device can carry the extra load.
- No `[frame60] hotkeys:` line shows up — you're not on a real terminal
  (or you're on Windows, see above). Job still runs fine, you just don't
  get manual pause — `--resume` after a hard kill still works.
- On Windows and nothing's auto-pausing when it gets hot — that's
  expected, not broken. Manage load with `--profile battery-saver` /
  `--threads` instead, and keep an eye on the device yourself.
