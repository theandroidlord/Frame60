"""
frame60 command-line interface.

  python -m frame60 IN.mp4 OUT.mp4 [options]

See README.md for full documentation, profile details, and hotkeys.
"""
import argparse
import os
import shutil
import sys
import tempfile
import time

from . import chunker, ffmpeg_utils, keyboard_control, monitor, progress, session, stats
from .config import DEFAULT_PROFILE, DEFAULT_TARGET_FPS, FILTER_TEMPLATES, PROFILES


def build_parser():
    p = argparse.ArgumentParser(
        prog="frame60",
        description=(
            "Convert a video's frame rate (e.g. 24fps -> 60fps) with efficiency "
            "profiles, chunked resumable processing, and thermal-aware lag "
            "protection. Designed to run comfortably on a phone under Termux, "
            "or on desktop."
        ),
    )
    p.add_argument("input", nargs="?", default=None,
                    help="source video file (omit both input/output to launch the guided menu)")
    p.add_argument("output", nargs="?", default=None,
                    help="destination video file (omit both input/output to launch the guided menu)")
    p.add_argument("--wizard", action="store_true",
                    help="force the guided menu (plain-language prompts, no flags needed)")
    p.add_argument("--fps", type=int, default=DEFAULT_TARGET_FPS,
                    help=f"target frame rate (default: {DEFAULT_TARGET_FPS})")
    p.add_argument("--mode", choices=["interpolate", "blend", "dupe"], default=None,
                    help="frame generation method (default: from --profile). "
                         "interpolate = motion-compensated, best quality, slowest. "
                         "blend = cheap cross-fade, much lighter. "
                         "dupe = plain frame duplication, cheapest, most judder.")
    p.add_argument("--profile", choices=list(PROFILES), default=DEFAULT_PROFILE,
                    help="efficiency profile: threads/preset/thermal limits "
                         f"(default: {DEFAULT_PROFILE})")
    p.add_argument("--threads", type=int, default=None, help="override profile thread count")
    p.add_argument("--preset", default=None, help="override x264 preset")
    p.add_argument("--chunk-minutes", type=int, default=None,
                    help="override chunk length in minutes")
    p.add_argument("--max-temp", type=float, default=None,
                    help="override thermal auto-pause threshold, Celsius")
    p.add_argument("--no-thermal-guard", action="store_true",
                    help="disable temperature-based auto-pause (lag protection)")
    p.add_argument("--no-hotkeys", action="store_true",
                    help="disable interactive p/r/q keyboard control")
    p.add_argument("--resume", action="store_true",
                    help="resume a previously interrupted job on the same input/settings")
    p.add_argument("--fresh", action="store_true",
                    help="ignore any saved session for this job and start over")
    p.add_argument("--dry-run", action="store_true",
                    help="print the plan and ffmpeg commands without running anything")
    p.add_argument("--keep-chunks", action="store_true",
                    help="keep intermediate chunk files instead of deleting them")
    return p


def resolve_settings(args):
    profile = PROFILES[args.profile].copy()
    return {
        "mode": args.mode or profile["mode"],
        "threads": args.threads or profile["threads"],
        "preset": args.preset or profile["preset"],
        "chunk_minutes": args.chunk_minutes or profile["chunk_minutes"],
        "max_temp_c": args.max_temp or profile["max_temp_c"],
        "cooldown_s": profile["cooldown_s"],
        "nice": profile["nice"],
    }


def _apply_nice(target_nice):
    try:
        current = os.nice(0)
        delta = target_nice - current
        if delta:
            os.nice(delta)
    except (AttributeError, PermissionError, OSError):
        pass  # not available on this platform, or not permitted -- fine


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.wizard or (args.input is None and args.output is None):
        from . import menu
        args = menu.collect_args()
        if args is None:
            return 0
    elif args.input is None or args.output is None:
        print("error: need both input and output, or neither (to launch the guided menu). "
              "Try: python -m frame60", file=sys.stderr)
        return 1

    return run_job(args)


def run_job(args):
    try:
        ffmpeg_utils.check_binaries()
    except ffmpeg_utils.FFmpegNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not os.path.exists(args.input):
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 1

    settings = resolve_settings(args)

    try:
        info = ffmpeg_utils.probe(args.input)
    except Exception as e:
        print(f"error: could not read source video: {e}", file=sys.stderr)
        return 1

    print(f"Source   : {args.input}  ({info.width}x{info.height}, "
          f"{info.fps}fps, {info.duration_s / 60:.1f} min, {info.codec})")
    print(f"Target   : {args.output}  ({args.fps}fps, mode={settings['mode']})")
    print(f"Profile  : {args.profile}  (threads={settings['threads']}, "
          f"preset={settings['preset']}, chunk={settings['chunk_minutes']}min, "
          f"max_temp={settings['max_temp_c']}C)")

    plan = chunker.plan_chunks(info.duration_s, settings["chunk_minutes"])
    print(f"Chunks   : {len(plan)}")

    jid = session.job_id(args.input, args.fps, settings["mode"])
    if args.fresh:
        session.Session(jid).clear()
    sess = session.Session(jid)
    done = sess.done_indices()
    if done:
        print(f"Resuming : {len(done)}/{len(plan)} chunks already done (job {jid})")
    elif not args.resume:
        pass  # fresh job, nothing to resume

    if args.dry_run:
        print(f"Job ID   : {jid}")
        for index, start_s, length_s in plan:
            cmd = ffmpeg_utils.build_command(
                f"<chunk_{index}_src.mp4>", f"<chunk_{index}_out.mp4>",
                target_fps=args.fps, mode=settings["mode"],
                threads=settings["threads"], preset=settings["preset"],
                filter_templates=FILTER_TEMPLATES,
            )
            tag = "skip (done)" if index in done else "run "
            print(f"  [{tag}] chunk {index} ({length_s / 60:.1f}min): {' '.join(cmd)}")
        return 0

    workdir = tempfile.mkdtemp(prefix="frame60_")
    collector = stats.StatsCollector()
    current_run = {"run": None}
    quit_requested = {"flag": False}

    def get_run():
        return current_run["run"]

    def request_quit():
        quit_requested["flag"] = True

    def log_event(msg):
        print(f"\n[frame60] {msg}")

    guard = None
    if not args.no_thermal_guard:
        guard = monitor.ThermalGuard(
            get_run, settings["max_temp_c"], settings["cooldown_s"], on_event=log_event,
        )
        guard.start()
        if not guard.available:
            print("[frame60] note: no readable temperature sensor on this device -- "
                  "lag protection is inactive. Stay conservative with --threads/--profile.")

    # Let 'em tap out mid-set if they need to -- p/r/q only works on a
    # real POSIX terminal, so this quietly no-ops on Windows cmd.
    listener = None
    if not args.no_hotkeys:
        listener = keyboard_control.KeyListener(get_run, request_quit, on_event=log_event)
        listener.start()
        if listener.enabled:
            print("[frame60] hotkeys: p = pause, r = resume, q = quit & save progress")

    _apply_nice(settings["nice"])

    completed_all = False
    try:
        for index, start_s, length_s in plan:
            if index in done:
                continue
            if quit_requested["flag"]:
                break

            src_chunk = chunker.extract_chunk(args.input, index, start_s, length_s, workdir)
            out_chunk = os.path.join(workdir, f"chunk_{index:04d}_out.mp4")
            in_size = os.path.getsize(src_chunk)

            cmd = ffmpeg_utils.build_command(
                src_chunk, out_chunk, target_fps=args.fps, mode=settings["mode"],
                threads=settings["threads"], preset=settings["preset"],
                filter_templates=FILTER_TEMPLATES,
            )
            run = progress.ProgressRun(cmd, length_s, label=f"chunk {index + 1}/{len(plan)}")
            current_run["run"] = run
            t0 = time.time()
            rc = run.run()
            elapsed = time.time() - t0
            current_run["run"] = None

            if rc != 0:
                print(f"\n[frame60] chunk {index} failed (ffmpeg exit {rc}); stopping. "
                      f"Re-run with --resume once fixed (job {jid}).")
                break

            out_size = os.path.getsize(out_chunk)
            collector.add_chunk(index, elapsed, length_s / max(elapsed, 0.001), in_size, out_size)
            sess.mark_chunk_done(index, out_chunk)
            if not args.keep_chunks:
                os.remove(src_chunk)

            if quit_requested["flag"]:
                print(f"\n[frame60] stopping after this chunk as requested. "
                      f"Re-run with --resume to continue (job {jid}).")
                break
        else:
            ordered = [
                c["output"] for c in sorted(sess.data["chunks_done"], key=lambda c: c["index"])
            ]
            print("\n[frame60] all chunks done -- merging final file...")
            chunker.concat_chunks(ordered, args.output, workdir)
            sess.clear()
            completed_all = True
            print(f"[frame60] done: {args.output}")
    finally:
        if guard:
            guard.stop()
        if listener:
            listener.stop()
        collector.print_summary()
        if completed_all and not args.keep_chunks:
            shutil.rmtree(workdir, ignore_errors=True)
        elif not completed_all:
            print(f"[frame60] intermediate files kept in: {workdir}")

    return 0 if completed_all or quit_requested["flag"] else 1


if __name__ == "__main__":
    sys.exit(main())
