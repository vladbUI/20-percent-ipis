"""End-to-end checks of ipis_server and ipis_client, the C side of the game.

Each test starts the real server and talks to it through real ipis_client
processes, exactly as the GUI does. Run with: make test
"""

import os
import queue
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui"))
import bridge  # noqa: E402

TIMEOUT = 5


class Player:
    def __init__(self, port):
        self.process = bridge.Process([bridge.CLIENT, "127.0.0.1", str(port)])

    def send(self, text):
        self.process.send(text)

    def read(self):
        line = self.process.lines.get(timeout=TIMEOUT)
        if line is None:
            raise EOFError("connection closed")
        return line

    def expect(self, prefix):
        line = self.read()
        if not line.startswith(prefix):
            raise AssertionError(f"expected {prefix!r}, got {line!r}")
        return line

    def both_locked(self):
        # Order depends on which player's plan reached the server first.
        lines = sorted([self.read(), self.read()])
        if lines != ["LOCKED", "OPPONENT_LOCKED"]:
            raise AssertionError(f"expected both lock messages, got {lines!r}")

    def numbers(self, prefix):
        return [int(x) for x in self.expect(prefix).split()[1:]]

    def closed(self):
        try:
            return self.process.lines.get(timeout=TIMEOUT) is None
        except queue.Empty:
            return False

    def quiet(self):
        try:
            self.process.lines.get(timeout=0.3)
            return False
        except queue.Empty:
            return True


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        error = bridge.ensure_built()
        if error:
            raise unittest.SkipTest(error)

    def start_server(self, *flags):
        self.server = bridge.Process([bridge.SERVER, "0", "--local", *flags], server=True)
        line = self.server.lines.get(timeout=TIMEOUT)
        self.assertTrue(line.startswith("IPIS Arena server listening on port"), line)
        self.addCleanup(self.server.stop)
        return int(line.rsplit(" ", 1)[1])

    def join(self, port):
        player = Player(port)
        self.addCleanup(player.process.stop)
        return player

    def start_match(self):
        port = self.start_server()
        one = self.join(port)
        self.assertEqual(one.read(), "WELCOME 0 HUMAN")
        self.assertEqual(one.read(), "WAITING")
        two = self.join(port)
        self.assertEqual(two.read(), "WELCOME 1 HUMAN")
        for player in (one, two):
            self.assertEqual(player.read(), "START")
            self.assertEqual(player.read(), "STATE 1 50 50 0 0 10 0 5 1 2 3 4 5")
        return port, one, two

    def test_invalid_commands_are_rejected(self):
        _, one, _ = self.start_match()
        for command, error in (("PLAN 1 1 0", "ERROR The same hand position cannot be used twice."),
                               ("PLAN 2 5 1", "ERROR That plan costs more than 4 energy."),
                               ("PLAN 6 0 0", "ERROR Choose an existing hand position or 0."),
                               ("PLAN 1 2", "ERROR Use PLAN followed by three hand positions."),
                               ("PLAN 1 2 3 4", "ERROR Use PLAN followed by three hand positions."),
                               ("PLAN -1 0 0", "ERROR Use PLAN followed by three hand positions."),
                               ("MOLT 1", "ERROR Molt requires 2 AP."),
                               ("REMATCH", "ERROR The match is still running."),
                               ("HELLO", "ERROR Unknown command."),
                               ("X" * 300, "ERROR Line too long.")):
            one.send(command)
            self.assertEqual(one.read(), error, command)
        one.send("PLAN 1 0 0")
        self.assertEqual(one.read(), "LOCKED")
        one.send("PLAN 2 0 0")
        self.assertEqual(one.read(), "ERROR Your plan is already locked for this round.")

    def test_presentation_rounds_and_privacy(self):
        # The same two rounds as game_logic_demo/PRESENTATION.md.
        _, one, two = self.start_match()
        one.send("PLAN 2 1 0")
        self.assertEqual(one.read(), "LOCKED")
        # The other player learns only that a plan was locked, not the cards.
        self.assertEqual(two.read(), "OPPONENT_LOCKED")
        self.assertTrue(two.quiet())
        two.send("PLAN 4 3 0")
        self.assertEqual(two.read(), "LOCKED")
        self.assertEqual(one.read(), "OPPONENT_LOCKED")
        for player in (one, two):
            result = player.numbers("RESULT")
            self.assertEqual(result[:2], [1, 0])
            self.assertEqual(result[2:8], [2, 1, 0, 4, 3, 0])      # cards
            self.assertEqual(result[8:14], [5, 0, 0, 0, 0, 0])     # damage taken
            self.assertEqual(result[14:20], [0, 0, 0, 1, 1, 0])    # defended
            self.assertEqual(result[24:28], [45, 50, 0, 2])        # HP and AP after
        self.assertEqual(one.read(), "STATE 2 45 50 0 2 8 2 5 3 4 5 1 2")
        self.assertEqual(two.read(), "STATE 2 45 50 0 2 8 2 5 1 2 5 1 2")

        two.send("MOLT 1")
        self.assertEqual(two.read(), "STATE 2 45 50 0 0 7 3 5 2 5 1 2 3")
        one.send("PLAN 3 5 0")
        two.send("PLAN 5 2 0")
        for player in (one, two):
            player.both_locked()
            self.assertEqual(player.numbers("RESULT")[24:28], [40, 35, 0, 0])

    def test_full_match_rematch_and_leaving(self):
        port, one, two = self.start_match()
        outcome = 0
        while outcome == 0:
            one.send("PLAN 1 2 0")
            two.send("PLAN 0 0 0")
            for player in (one, two):
                player.both_locked()
            outcome = one.numbers("RESULT")[1]
            two.expect("RESULT")
            if outcome == 0:
                one.expect("STATE")
                two.expect("STATE")
        self.assertEqual(outcome, 1)  # Player 1 wins

        extra = self.join(port)
        self.assertEqual(extra.read(), "FULL")
        self.assertTrue(extra.closed())

        one.send("REMATCH")
        self.assertEqual(two.read(), "OPPONENT_REMATCH")
        two.send("REMATCH")
        self.assertEqual(one.read(), "OPPONENT_REMATCH")
        for player in (one, two):
            self.assertEqual(player.read(), "START")
            self.assertEqual(player.read(), "STATE 1 50 50 0 0 10 0 5 1 2 3 4 5")

        two.process.stop()  # Closing the GUI's pipe makes the client send QUIT.
        self.assertEqual(one.read(), "OPPONENT_LEFT")
        self.assertTrue(one.closed())
        self.assertEqual(self.server.proc.wait(timeout=TIMEOUT), 0)

    def test_leaving_before_the_match_frees_the_seat(self):
        port = self.start_server()
        first = self.join(port)
        self.assertEqual(first.read(), "WELCOME 0 HUMAN")
        first.process.stop()
        second = self.join(port)
        self.assertEqual(second.read(), "WELCOME 0 HUMAN")
        self.assertEqual(second.read(), "WAITING")

    def test_cpu_plays_complete_legal_matches(self):
        port = self.start_server("--cpu")
        player = self.join(port)
        self.assertEqual(player.read(), "WELCOME 0 CPU")
        outcomes = []
        for match in range(5):
            self.assertEqual(player.read(), "START")
            outcome = 0
            while outcome == 0:
                state = player.numbers("STATE")
                self.assertEqual(player.read(), "OPPONENT_LOCKED")
                plans = ["PLAN 1 0 0", "PLAN 3 4 0", "PLAN 0 0 0", "PLAN 2 1 0"]
                player.send(plans[state[0] % len(plans)])
                player.expect("LOCKED")
                outcome = player.numbers("RESULT")[1]
            outcomes.append(outcome)
            if match < 4:
                player.send("REMATCH")
        self.assertTrue(all(outcome in (1, 2, 3) for outcome in outcomes))
        self.assertNotIn("CPU plan rejected", self.server.error_text())

    def test_bad_arguments(self):
        for args in ([], ["70000"], ["5001", "--bogus"]):
            result = subprocess.run([bridge.SERVER, *args], capture_output=True, text=True, timeout=TIMEOUT)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Usage", result.stderr)
        result = subprocess.run([bridge.CLIENT, "not-an-ip", "5001"], capture_output=True, text=True,
                                timeout=TIMEOUT)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
