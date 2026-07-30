"""
Non-blocking single-keypress listener for interactive control while a
job is running:

  p  = pause current chunk (SIGSTOP) — "exit" the active encode
  r  = resume (SIGCONT)              — "enter" back in
  q  = quit gracefully after this chunk; session state is saved so
       re-running with --resume continues from here instead of
       starting over

Silently disables itself if stdin isn't a real terminal (e.g. running
under nohup, cron, or with input piped in) so it never breaks headless
runs.
"""
import sys
import threading

try:
    import termios
    import tty
    _POSIX_TTY = True
except ImportError:
    _POSIX_TTY = False


class KeyListener(threading.Thread):
    def __init__(self, progress_run_getter, on_quit, on_event=None):
        super().__init__(daemon=True)
        self.get_run = progress_run_getter
        self.on_quit = on_quit
        self.on_event = on_event or (lambda msg: None)
        self._stop = threading.Event()
        self.enabled = _POSIX_TTY and sys.stdin.isatty()

    def stop(self):
        self._stop.set()

    def run(self):
        if not self.enabled:
            return
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not self._stop.is_set():
                ch = sys.stdin.read(1)
                run = self.get_run()
                if ch == "p" and run:
                    run.pause()
                    self.on_event("paused (press r to resume, q to quit+save)")
                elif ch == "r" and run:
                    run.resume()
                    self.on_event("resumed")
                elif ch == "q":
                    self.on_event("quit requested -- finishing current write and saving session")
                    self.on_quit()
                    break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
