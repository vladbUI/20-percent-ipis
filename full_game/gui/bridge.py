"""Connects the GUI to the C programs.

The GUI never opens a socket. It starts ipis_server (when hosting) and
ipis_client, then exchanges protocol lines with ipis_client through its
standard input and output. The protocol is described in ../README.md.
"""

import atexit
import os
import queue
import shutil
import subprocess
import threading
from dataclasses import dataclass

GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER = os.path.join(GAME_DIR, "ipis_server")
CLIENT = os.path.join(GAME_DIR, "ipis_client")

_running = []


def ensure_built():
    """Build the C programs with make if needed. Returns an error or None."""
    if os.path.exists(SERVER) and os.path.exists(CLIENT):
        return None
    if not shutil.which("make"):
        return "The C programs are not built. Run make in the full_game folder."
    result = subprocess.run(["make", "-C", GAME_DIR], capture_output=True, text=True)
    if result.returncode != 0:
        return "Building the C programs failed:\n" + (result.stderr or result.stdout).strip()
    return None


class Process:
    """A C program whose output lines arrive in a queue; None means it ended."""

    def __init__(self, args, server=False):
        self.server = server
        self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1)
        self.lines = queue.Queue()
        self.errors = []
        self._error_reader = threading.Thread(target=self._read_errors, daemon=True)
        self._error_reader.start()
        threading.Thread(target=self._read, daemon=True).start()
        _running.append(self)

    def _read(self):
        for line in self.proc.stdout:
            self.lines.put(line.rstrip("\r\n"))
        self.lines.put(None)

    def _read_errors(self):
        for line in self.proc.stderr:
            self.errors.append(line.strip())

    def poll(self):
        lines = []
        while True:
            try:
                lines.append(self.lines.get_nowait())
            except queue.Empty:
                return lines

    def error_text(self):
        self._error_reader.join(timeout=0.5)
        return " ".join(self.errors)

    def send(self, text):
        try:
            self.proc.stdin.write(text + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass

    def stop(self):
        """Close input (a client then sends QUIT), then make sure it exits."""
        if self in _running:
            _running.remove(self)
        if self.server:
            self.proc.terminate()
        try:
            self.proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            self.proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def stop_all():
    # Clients first, so they can say goodbye before a hosted server stops.
    for process in sorted(_running, key=lambda p: p.server):
        process.stop()


atexit.register(stop_all)


# Protocol messages ----------------------------------------------------------

@dataclass
class State:
    round: int
    hp: list
    ap: list
    deck: int
    discard: int
    hand: list


@dataclass
class Report:
    round: int
    outcome: int
    cards: list       # cards[player][slot]
    damage: list      # damage TAKEN by each player in each slot
    defended: list
    hp_before: list
    ap_before: list
    hp_after: list
    ap_after: list


def parse_state(values):
    """STATE round hp1 hp2 ap1 ap2 deck discard hand_count hand..."""
    round_, hp1, hp2, ap1, ap2, deck, discard, count = values[:8]
    return State(round_, [hp1, hp2], [ap1, ap2], deck, discard, values[8:8 + count])


def parse_result(values):
    """RESULT round outcome cards[6] damage[6] defended[6] hp/ap before and after."""
    def pairs(start):
        return [values[start:start + 3], values[start + 3:start + 6]]
    return Report(values[0], values[1], pairs(2), pairs(8), pairs(14),
                  values[20:22], values[22:24], values[24:26], values[26:28])
