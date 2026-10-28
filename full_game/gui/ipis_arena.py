"""IPIS Arena: graphical client for Cock Fight: Ipis Edition.

Python only draws the game and reads the mouse and keyboard. The rules and all
networking are written in C: ipis_server runs game_logic_demo/game.c, and this
GUI talks to it through the ipis_client program (see bridge.py).

Run with: python3 ipis_arena.py
"""

import math
import random
import sys
from collections import deque

import pygame

import bridge
import ui
from cards import (CARD_NAMES, DRAW, DULAG_SAPAK, EMPTY, KAGAT, LAYOG_KAGAT,
                   MAX_AP, MOLT_COST, ONGOING, PLAYER_ONE_WINS, ROUND_ENERGY,
                   SAGANG, SLOTS, START_HP, ULTI_KAGAT, card_cost)
from ui import (AMBER, BLUE, CARD_H, CARD_W, GREEN, HEIGHT, PLAYER_COLORS,
                RED, TEAL, TEXT, TEXT_DIM, TEXT_MUTED, WIDTH, Button, Fighter,
                TextField, draw_text)

FPS = 60
DEFAULT_PORT = 5001
ATTACKS = (KAGAT, LAYOG_KAGAT, ULTI_KAGAT)

# Layout of the match screen. Side 0 (left) is always you.
FIGHTER_Y = 200
FIGHTER_X = (330, 950)
SLOT_Y = 304
HAND_Y = 516
SLOT_GAP = 22
HAND_GAP = 18
LEFT_PANEL = pygame.Rect(40, 304, 350, 184)
RIGHT_PANEL = pygame.Rect(890, 304, 350, 184)

# Reveal timing, in seconds.
REVEAL_START = 0.5
REVEAL_STEP = 1.45
FLIP_TIME = 0.35
CLASH_TIME = 0.45
IMPACT_TIME = 0.65
REVEAL_END = REVEAL_START + (SLOTS - 1) * REVEAL_STEP + 1.1


def slot_rect(i):
    x = WIDTH // 2 - (3 * CARD_W + 2 * SLOT_GAP) // 2 + i * (CARD_W + SLOT_GAP)
    return pygame.Rect(x, SLOT_Y, CARD_W, CARD_H)


def hand_rect(i, count):
    total = count * CARD_W + (count - 1) * HAND_GAP
    return pygame.Rect(WIDTH // 2 - total // 2 + i * (CARD_W + HAND_GAP), HAND_Y, CARD_W, CARD_H)


def gradient_text(text, size, top, bottom):
    image = ui.font(size, True, True).render(text, True, (255, 255, 255))
    fill = ui.gradient(image.get_width(), image.get_height(), top, bottom).convert_alpha()
    fill.blit(image, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return fill


def bolt(surface, rect, color):
    pts = [(0.58, 0.08), (0.22, 0.56), (0.47, 0.56), (0.38, 0.92), (0.78, 0.40), (0.53, 0.40), (0.66, 0.08)]
    big = pygame.Surface((rect.w * 2, rect.h * 2), pygame.SRCALPHA)
    pygame.draw.polygon(big, color, [(x * rect.w * 2, y * rect.h * 2) for x, y in pts])
    surface.blit(pygame.transform.smoothscale(big, rect.size), rect)


def blit_card(surface, card, rect, back=False, alpha=255, shadow=True, scale_x=1.0):
    """Draw a card into rect; scale_x < 1 squeezes it for a flip animation."""
    image = ui.card_back(rect.w, rect.h) if back else ui.card_face(card, rect.w, rect.h)
    if scale_x < 0.999:
        width = max(1, int(rect.w * scale_x))
        image = pygame.transform.smoothscale(image, (width, rect.h))
        rect = image.get_rect(center=rect.center)
    if shadow:
        ui.blit_shadow(surface, rect, 14, 8, int(110 * alpha / 255), (0, 6))
    if alpha < 255:
        image = image.copy()
        image.set_alpha(alpha)
    surface.blit(image, rect)


def spinner(surface, center, clock, color=AMBER):
    big = pygame.Surface((88, 88), pygame.SRCALPHA)
    start = clock * 5
    pygame.draw.arc(big, (255, 255, 255, 30), big.get_rect().inflate(-8, -8), 0, math.tau, 7)
    pygame.draw.arc(big, color, big.get_rect().inflate(-8, -8), start, start + 1.8, 7)
    image = pygame.transform.smoothscale(big, (44, 44))
    surface.blit(image, image.get_rect(center=center))


class Floater:
    def __init__(self, text, pos, color, size=34, delay=0.0):
        self.text, self.color, self.size = text, color, size
        self.pos = pygame.Vector2(pos)
        self.age = -delay
        self.life = 1.3

    def draw(self, surface):
        if self.age < 0:
            return
        t = self.age / self.life
        pop = 0.6 + 0.4 * ui.ease_out_back(min(1, self.age / 0.25))
        alpha = int(255 * (1 - max(0, t - 0.6) / 0.4))
        image = ui.font(int(self.size * pop), True, True).render(self.text, True, self.color)
        outline = ui.font(int(self.size * pop), True, True).render(self.text, True, (20, 12, 8))
        pos = self.pos + (0, -60 * ui.ease_out(t))
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 3)):
            outline.set_alpha(alpha)
            surface.blit(outline, outline.get_rect(center=pos + (dx, dy)))
        image.set_alpha(alpha)
        surface.blit(image, image.get_rect(center=pos))


class Spark:
    def __init__(self, pos, color):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(120, 360)
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(math.cos(angle) * speed, math.sin(angle) * speed - 120)
        self.color = color
        self.life = random.uniform(0.35, 0.7)
        self.age = 0.0

    def update(self, dt):
        self.age += dt
        self.vel.y += 600 * dt
        self.pos += self.vel * dt

    def draw(self, surface):
        t = self.age / self.life
        radius = max(1, int(4 * (1 - t)))
        pygame.draw.circle(surface, ui.lighten(self.color, 0.3 * (1 - t)), self.pos, radius)


# Scenes --------------------------------------------------------------------

class Scene:
    def __init__(self, app):
        self.app = app

    def handle(self, event):
        pass

    def update(self, dt):
        pass

    def draw(self, surface):
        pass


class TitleScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        x = WIDTH // 2 - 170
        self.buttons = [
            (Button((x, 300, 340, 56), "Play vs Computer", "primary", "1", 19), self.play_cpu),
            (Button((x, 368, 340, 50), "Host Online Game", "secondary", "2"), self.host),
            (Button((x, 428, 340, 50), "Join Online Game", "secondary", "3"), self.join),
            (Button((x, 488, 340, 50), "How to Play", "secondary", "4"), self.rules),
            (Button((x, 548, 340, 50), "Quit", "ghost", "Esc"), self.app.quit),
        ]
        self.fighters = [Fighter(0, (250, 440)), Fighter(1, (1030, 440))]
        self.timer = 2.0
        self.turn = 0

    def play_cpu(self):
        self.app.switch(MatchScene(self.app, "cpu"))

    def host(self):
        self.app.switch(ConnectScene(self.app, "host"))

    def join(self):
        self.app.switch(ConnectScene(self.app, "join"))

    def rules(self):
        self.app.switch(RulesScene(self.app, self))

    def handle(self, event):
        for button, action in self.buttons:
            if button.handle(event):
                action()
                return
        if event.type == pygame.KEYDOWN:
            keys = {pygame.K_1: self.play_cpu, pygame.K_2: self.host, pygame.K_3: self.join,
                    pygame.K_4: self.rules, pygame.K_ESCAPE: self.app.quit}
            if event.key in keys:
                keys[event.key]()

    def update(self, dt):
        mouse = self.app.mouse()
        for button, _ in self.buttons:
            button.update(dt, mouse)
        for fighter in self.fighters:
            fighter.update(dt)
        # A little sparring loop in the background.
        self.timer -= dt
        if self.timer <= 0:
            attacker = self.fighters[self.turn]
            defender = self.fighters[1 - self.turn]
            attacker.attack()
            random.choice((defender.guard, defender.dodge))()
            self.turn = 1 - self.turn
            self.timer = 2.6

    def draw(self, surface):
        surface.blit(ui.background(WIDTH, HEIGHT), (0, 0))
        for fighter in self.fighters:
            fighter.draw(surface)
        glow = gradient_text("IPIS ARENA", 104, (255, 214, 120), (232, 120, 40))
        shade = ui.font(104, True, True).render("IPIS ARENA", True, (0, 0, 0))
        shade.set_alpha(120)
        rect = glow.get_rect(center=(WIDTH // 2, 158))
        surface.blit(shade, rect.move(0, 6))
        surface.blit(glow, rect)
        draw_text(surface, "C O C K   F I G H T  :  I P I S   E D I T I O N", (WIDTH // 2, 228), 15,
                  ui.TEXT_DIM, True, "center")
        pygame.draw.line(surface, (120, 86, 52), (WIDTH // 2 - 120, 256), (WIDTH // 2 + 120, 256), 1)
        for button, _ in self.buttons:
            button.draw(surface)
        draw_text(surface, "Plan three moves. Out-guess your rival. Last cockroach standing wins.",
                  (WIDTH // 2, HEIGHT - 40), 15, TEXT_MUTED, False, "center")


class RulesScene(Scene):
    def __init__(self, app, previous):
        super().__init__(app)
        self.previous = previous
        self.back = Button((WIDTH // 2 - 110, HEIGHT - 76, 220, 50), "Back", "primary", "Esc")

    def handle(self, event):
        if self.back.handle(event) or (event.type == pygame.KEYDOWN and
                                       event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_BACKSPACE)):
            self.app.switch(self.previous)

    def update(self, dt):
        self.back.update(dt, self.app.mouse())

    def draw(self, surface):
        surface.blit(ui.background(WIDTH, HEIGHT), (0, 0))
        draw_text(surface, "How to Play", (WIDTH // 2, 30), 40, TEXT, True, "midtop", True, True)
        cards = (KAGAT, LAYOG_KAGAT, SAGANG, DULAG_SAPAK, ULTI_KAGAT)
        total = 5 * CARD_W + 4 * 26
        for i, card in enumerate(cards):
            rect = pygame.Rect(WIDTH // 2 - total // 2 + i * (CARD_W + 26), 96, CARD_W, CARD_H)
            blit_card(surface, card, rect)
        columns = (
            ("EACH ROUND", [
                "Both players secretly fill up to 3 slots from a 5-card hand.",
                "You have 4 energy per round. The dots on a card show its cost.",
                "Plans are revealed together and resolve slot by slot: slot 1 vs slot 1, and so on.",
                "Played cards are discarded; your hand refills to 5 from your deck.",
            ]),
            ("WINNING & RESOURCES", [
                "Everyone starts at 50 HP. Reach 0 and you lose; both at 0 is a draw.",
                "Each successful block or dodge earns 1 Adaptation Point (max 2).",
                "Molt: spend 2 AP before locking in to swap one card for a new draw.",
                "Empty slots are allowed. Passing with no cards is allowed too.",
            ]),
        )
        for c, (title, lines) in enumerate(columns):
            rect = pygame.Rect(90 + c * 560, 306, 540, 312)
            ui.panel(surface, rect)
            draw_text(surface, title, (rect.x + 24, rect.y + 20), 13, AMBER, True)
            y = rect.y + 52
            for line in lines:
                pygame.draw.circle(surface, AMBER, (rect.x + 30, y + 10), 3)
                for part in ui.wrap(line, 17, rect.w - 70):
                    draw_text(surface, part, (rect.x + 44, y), 17, TEXT_DIM)
                    y += 24
                y += 14
        self.back.draw(surface)


class ConnectScene(Scene):
    """Address and port form for hosting or joining an online game."""

    def __init__(self, app, mode):
        super().__init__(app)
        self.mode = mode
        self.panel = pygame.Rect(WIDTH // 2 - 320, 190, 640, 380)
        field_y = self.panel.y + 178
        digits = "0123456789"
        if mode == "join":
            self.fields = [TextField((self.panel.x + 48, field_y, 340, 58), "HOST ADDRESS", "127.0.0.1",
                                     digits + ".", 15),
                           TextField((self.panel.x + 408, field_y, 184, 58), "PORT", str(DEFAULT_PORT), digits, 5)]
        else:
            self.fields = [TextField((self.panel.centerx - 110, field_y, 220, 58), "PORT", str(DEFAULT_PORT),
                                     digits, 5)]
        self.fields[0].focused = True
        self.back = Button((self.panel.x + 48, self.panel.bottom - 82, 200, 52), "Back", "secondary", "Esc")
        label = "Connect" if mode == "join" else "Start Hosting"
        self.go = Button((self.panel.right - 288, self.panel.bottom - 82, 240, 52), label, "primary", "Enter")
        self.error = ""
        self.clock = 0.0
        pygame.key.start_text_input()

    def submit(self):
        port_text = self.fields[-1].value
        if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
            self.error = "The port must be a number from 1 to 65535."
            return
        host = "127.0.0.1"
        if self.mode == "join":
            host = self.fields[0].value
            parts = host.split(".")
            if len(parts) != 4 or not all(p.isdigit() and int(p) <= 255 for p in parts):
                self.error = "Enter an IPv4 address such as 192.168.1.20."
                return
        self.app.switch(MatchScene(self.app, self.mode, host, int(port_text)))

    def handle(self, event):
        for field in self.fields:
            field.handle(event)
        if self.go.handle(event):
            self.submit()
        elif self.back.handle(event):
            self.app.switch(TitleScene(self.app))
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.submit()
            elif event.key == pygame.K_ESCAPE:
                self.app.switch(TitleScene(self.app))
            elif event.key == pygame.K_TAB and len(self.fields) > 1:
                index = next((i for i, f in enumerate(self.fields) if f.focused), -1)
                for i, field in enumerate(self.fields):
                    field.focused = i == (index + 1) % len(self.fields)

    def update(self, dt):
        self.clock += dt
        mouse = self.app.mouse()
        self.go.update(dt, mouse)
        self.back.update(dt, mouse)

    def draw(self, surface):
        surface.blit(ui.background(WIDTH, HEIGHT), (0, 0))
        glow = gradient_text("IPIS ARENA", 56, (255, 214, 120), (232, 120, 40))
        surface.blit(glow, glow.get_rect(center=(WIDTH // 2, 110)))
        ui.blit_shadow(surface, self.panel, 22, 16, 140)
        ui.panel(surface, self.panel, 22, (30, 22, 16, 245))
        title = "Join an Online Game" if self.mode == "join" else "Host an Online Game"
        draw_text(surface, title, (WIDTH // 2, self.panel.y + 30), 30, TEXT, True, "midtop", True)
        if self.mode == "join":
            text = ("Enter the address and port shown on the host's screen. "
                    "Use 127.0.0.1 if the host is on this computer.")
        else:
            text = ("Your computer runs the game server. After you start, "
                    "the screen shows the address your opponent should join.")
        y = self.panel.y + 80
        for line in ui.wrap(text, 16, self.panel.w - 100):
            draw_text(surface, line, (WIDTH // 2, y), 16, TEXT_DIM, False, "midtop")
            y += 22
        for field in self.fields:
            field.draw(surface, self.clock)
        if self.error:
            draw_text(surface, self.error, (WIDTH // 2, self.panel.y + 258), 15, RED, True, "midtop")
        self.back.draw(surface)
        self.go.draw(surface)


class MatchScene(Scene):
    """One match. All game state shown here comes from the C server."""

    def __init__(self, app, mode, host="127.0.0.1", port=0):
        super().__init__(app)
        self.mode = mode  # "cpu", "host" or "join"
        self.host, self.port = host, port
        self.server = self.client = None
        self.addresses = []
        self.status = "Starting"
        self.error = None
        self.error_title = ""
        self.inbox = deque()
        self.me = 0
        self.names = ["Player 1", "CPU" if mode == "cpu" else "Player 2"]
        self.fighters = [Fighter(s, (FIGHTER_X[s], FIGHTER_Y)) for s in (0, 1)]
        self.toast_text, self.toast_age, self.toast_life = "", 99.0, 1.6
        self.paused = False
        self.time = 0.0
        self.phase = "connecting"
        self.hand = []
        self.deck_count = self.discard_count = 0
        self.clear_plan()
        self.reset_match()

        self.lock_button = Button((RIGHT_PANEL.x + 16, RIGHT_PANEL.y + 14, 318, 58), "Lock In", "primary", "Enter", 20)
        self.clear_button = Button((RIGHT_PANEL.x + 16, RIGHT_PANEL.y + 84, 152, 42), "Clear", "secondary", "C", 15)
        self.rules_button = Button((RIGHT_PANEL.x + 182, RIGHT_PANEL.y + 84, 152, 42), "Rules", "secondary", "?", 15)
        self.molt_button = Button((LEFT_PANEL.x + 150, LEFT_PANEL.y + 128, 184, 40), "Molt", "secondary", "M", 15)
        self.menu_button = Button((WIDTH - 124, 10, 104, 34), "Menu", "ghost", None, 14)
        self.continue_button = Button((WIDTH // 2 - 120, 644, 240, 52), "Next Round", "primary", "Enter", 18)
        self.rematch_button = Button((WIDTH // 2 - 230, 560, 220, 54), "Rematch", "primary", "R", 18)
        self.exit_button = Button((WIDTH // 2 + 10, 560, 220, 54), "Main Menu", "secondary", "Esc", 18)
        self.resume_button = Button((WIDTH // 2 - 140, 300, 280, 52), "Resume", "primary", "Esc")
        self.pause_rules_button = Button((WIDTH // 2 - 140, 364, 280, 52), "How to Play", "secondary")
        self.leave_button = Button((WIDTH // 2 - 140, 428, 280, 52), "Leave Match", "danger")
        self.cancel_button = Button((WIDTH // 2 - 110, 0, 220, 50), "Cancel", "secondary", "Esc")
        self.error_button = Button((WIDTH // 2 - 120, 0, 240, 52), "Main Menu", "primary", "Enter")
        self.connect()

    # Players and sides ---------------------------------------------------

    @property
    def opp(self):
        return 1 - self.me

    def player_at(self, side):
        return self.me if side == 0 else self.opp

    def side_of(self, player):
        return 0 if player == self.me else 1

    def label(self, player):
        return "You" if player == self.me else self.names[player]

    # Connection ----------------------------------------------------------

    def connect(self):
        error = bridge.ensure_built()
        if error:
            self.fail(error)
            return
        if self.mode == "join":
            self.start_client(self.host, self.port)
            return
        args = [bridge.SERVER, str(self.port)]
        if self.mode == "cpu":
            args += ["--cpu", "--local"]
        self.server = bridge.Process(args, server=True)
        self.status = "Starting the game server"

    def start_client(self, host, port):
        self.client = bridge.Process([bridge.CLIENT, host, str(port)])
        self.status = f"Connecting to {host} port {port}"

    def leave(self):
        for process in (self.client, self.server):
            if process:
                process.stop()
        self.client = self.server = None
        self.app.switch(TitleScene(self.app))

    def fail(self, message, title="Connection problem"):
        self.error, self.error_title = message, title
        self.paused = False

    def send(self, text):
        if self.client:
            self.client.send(text)

    def poll_processes(self):
        if self.server:
            for line in self.server.poll():
                if line is None:
                    if not self.client and not self.error:
                        self.fail("The game server could not start. " + self.server.error_text())
                elif line.startswith("IPIS Arena server listening on port"):
                    self.port = int(line.rsplit(" ", 1)[1])
                    self.start_client("127.0.0.1", self.port)
                elif line.startswith("Join address:"):
                    self.addresses.append(line.split()[2])
        if self.client:
            self.inbox.extend(self.client.poll())

    def on_message(self, line):
        if line is None:
            if self.opponent_left or self.error:
                return
            if self.phase == "connecting":
                self.fail(self.client.error_text() or "Could not connect to the game.")
            else:
                self.fail("Lost connection to the game server.")
            return
        parts = line.split()
        if not parts:
            return
        kind = parts[0]
        try:
            values = [int(x) for x in parts[1:]] if kind in ("STATE", "RESULT") else None
            if kind == "WELCOME":
                self.me = int(parts[1])
                self.names = ["Player 1", "Player 2"]
                if parts[2] == "CPU":
                    self.names[self.opp] = "CPU"
                for side in (0, 1):
                    self.fighters[side].accent = PLAYER_COLORS[self.player_at(side)]
                self.status = "Connected"
            elif kind == "WAITING":
                self.status = "Waiting for an opponent to join"
            elif kind == "START":
                self.reset_match()
                self.phase = "sync"
            elif kind == "STATE":
                self.on_state(bridge.parse_state(values))
            elif kind == "RESULT":
                self.start_reveal(bridge.parse_result(values))
        except (IndexError, ValueError):
            return
        if kind == "ERROR":
            self.toast(line[6:], 2.4)
            self.pending_molt = None
            if self.phase == "locked":
                self.phase = "plan"
        elif kind == "OPPONENT_LOCKED":
            self.opponent_ready = True
            if self.phase == "plan":
                self.toast(f"{self.names[self.opp]} is ready", 1.6)
        elif kind == "OPPONENT_REMATCH":
            self.opponent_rematch = True
        elif kind == "OPPONENT_LEFT":
            self.opponent_left = True
            if self.phase != "over":
                self.fail(f"{self.names[self.opp]} left the match. No winner was recorded.", "Match ended")
        elif kind == "FULL":
            self.fail("That game already has two players.")

    # Round flow ----------------------------------------------------------

    def reset_match(self):
        self.round = 1
        self.hp = [START_HP, START_HP]
        self.ghost_hp = [START_HP, START_HP]
        self.ghost_wait = [0.0, 0.0]
        self.ap = [0, 0]
        self.stats = {"damage": [0, 0], "defenses": [0, 0]}
        self.report = None
        self.pending_molt = None
        self.opponent_ready = self.opponent_rematch = self.rematch_sent = self.opponent_left = False
        self.floaters, self.sparks = [], []
        for fighter in self.fighters:
            fighter.ko = False

    def clear_plan(self):
        self.slots = [None] * SLOTS        # 0-based hand index per slot
        self.slot_anim = [None] * SLOTS     # (from_rect, age) for fly-in
        self.hover = [0.0] * 5
        self.shake = [-1.0] * 5
        self.fresh_card = None              # (hand index, age) after a Molt
        self.molt_mode = False
        self.drag = None

    def on_state(self, state):
        self.round = state.round
        self.hp, self.ap = list(state.hp), list(state.ap)
        self.hand = list(state.hand)
        self.deck_count, self.discard_count = state.deck, state.discard
        if self.pending_molt is not None and self.phase == "plan":
            # The server removed the shed card and appended the new draw.
            index, self.pending_molt = self.pending_molt, None
            self.slots = [i - 1 if i is not None and i > index else i for i in self.slots]
            self.fresh_card = (len(self.hand) - 1, 0.0)
            self.toast(f"Molted! Drew {CARD_NAMES[self.hand[-1]]}", 1.8)
            return
        self.clear_plan()
        self.pending_molt = None
        self.opponent_ready = False
        self.phase = "plan"
        self.toast(f"Round {self.round}: plan your moves", 1.6)

    def lock_in(self):
        if self.pending_molt is not None:
            return
        picks = [i + 1 if i is not None else 0 for i in self.slots]
        self.send("PLAN %d %d %d" % tuple(picks))
        self.phase = "locked"
        self.slot_anim = [None] * SLOTS
        self.molt_mode = False
        self.drag = None
        self.hover = [0.0] * 5
        self.toast_age = 99.0

    def start_reveal(self, report):
        for p in (0, 1):
            if report.ap_before[p] < self.ap[p]:
                x = FIGHTER_X[self.side_of(p)]
                self.floaters.append(Floater("MOLT!", (x, FIGHTER_Y - 30), AMBER, 28))
        self.report = report
        self.phase = "reveal"
        self.reveal_t = 0.0
        self.hp, self.ap = list(report.hp_before), list(report.ap_before)
        self.events = []
        for slot in range(SLOTS):
            base = REVEAL_START + slot * REVEAL_STEP
            self.events.append([base + CLASH_TIME, self.clash, slot])
            self.events.append([base + IMPACT_TIME, self.impact, slot])
        self.continue_button.label = "Next Round" if report.outcome == ONGOING else "See Result"

    def clash(self, slot):
        rep = self.report
        for p in (0, 1):
            fighter = self.fighters[self.side_of(p)]
            card = rep.cards[p][slot]
            if card in ATTACKS:
                fighter.attack()
            if rep.defended[p][slot]:
                fighter.dodge() if card == DULAG_SAPAK else fighter.guard()

    def impact(self, slot):
        rep = self.report
        for p in (0, 1):
            side = self.side_of(p)
            x = FIGHTER_X[side] + (slot - 1) * 70
            if rep.defended[p][slot]:
                self.stats["defenses"][p] += 1
                word = "DODGE!" if rep.cards[p][slot] == DULAG_SAPAK else "BLOCK!"
                self.floaters.append(Floater(word, (x, FIGHTER_Y - 30), TEAL if word == "DODGE!" else BLUE, 28))
                if self.ap[p] < MAX_AP:
                    self.ap[p] += 1
                    self.floaters.append(Floater("+1 AP", (x, FIGHTER_Y + 10), AMBER, 22, 0.25))
            damage = rep.damage[p][slot]
            if damage:
                self.fighters[side].hit()
                self.stats["damage"][1 - p] += damage
                self.hp[p] = max(0, self.hp[p] - damage)
                self.ghost_wait[p] = 0.5
                self.floaters.append(Floater(f"-{damage}", (x, FIGHTER_Y - 10), RED, 44, 0.1))
                for _ in range(16 if damage >= 10 else 10):
                    self.sparks.append(Spark((FIGHTER_X[side], FIGHTER_Y - 10), (255, 170, 60)))

    def skip_reveal(self):
        for event in self.events:
            event[1](event[2])
        self.events = []
        self.reveal_t = max(self.reveal_t, REVEAL_END)

    def finish_reveal(self):
        rep = self.report
        self.hp, self.ap = list(rep.hp_after), list(rep.ap_after)
        if rep.outcome == ONGOING:
            self.phase = "sync"  # The next STATE is already waiting in the inbox.
            return
        self.phase = "over"
        for p in (0, 1):
            lost = rep.outcome == DRAW or (rep.outcome == PLAYER_ONE_WINS) == (p == 1)
            self.fighters[self.side_of(p)].ko = lost

    def rematch(self):
        if not self.rematch_sent and not self.opponent_left:
            self.send("REMATCH")
            self.rematch_sent = True

    def toast(self, text, duration=1.6):
        self.toast_text, self.toast_age, self.toast_life = text, 0.0, duration

    # Planning helpers ----------------------------------------------------

    def energy_used(self):
        return sum(card_cost(self.hand[i]) for i in self.slots if i is not None)

    def hand_rects(self):
        count = len(self.hand)
        return [hand_rect(i, count).move(0, -int(14 * self.hover[i])) for i in range(count)]

    def place(self, index, slot=None, from_rect=None):
        """Put hand card index into slot (or the first empty slot)."""
        if index in self.slots:
            if slot is None or self.slots[slot] == index:
                self.slots[self.slots.index(index)] = None
                return
            self.slots[self.slots.index(index)] = None
        if slot is None:
            if None not in self.slots:
                self.toast("All three slots are full")
                self.shake[index] = 0.0
                return
            slot = self.slots.index(None)
        replaced = self.slots[slot]
        cost = card_cost(self.hand[index])
        freed = card_cost(self.hand[replaced]) if replaced is not None else 0
        left = ROUND_ENERGY - self.energy_used() + freed
        if cost > left:
            self.toast(f"Not enough energy: needs {cost}, {left} left")
            self.shake[index] = 0.0
            return
        self.slots[slot] = index
        self.slot_anim[slot] = (pygame.Rect(from_rect or hand_rect(index, len(self.hand))), 0.0)

    def unplace_last(self):
        for slot in reversed(range(SLOTS)):
            if self.slots[slot] is not None:
                self.slots[slot] = None
                return

    def toggle_molt(self):
        if self.molt_mode:
            self.molt_mode = False
            self.toast_age = 99.0
        elif self.pending_molt is not None:
            return
        elif self.ap[self.me] >= MOLT_COST:
            self.molt_mode = True
            self.toast("Molt: click a card in your hand to shed it", 99)
        else:
            self.toast(f"Molt needs {MOLT_COST} AP. Block or dodge to earn AP.")

    def molt(self, index):
        if index in self.slots:
            self.toast("Take that card out of its slot first")
            return
        self.send(f"MOLT {index + 1}")
        self.pending_molt = index
        self.molt_mode = False
        self.toast_age = 99.0

    def card_at(self, pos):
        rects = self.hand_rects()
        for i in reversed(range(len(rects))):
            if rects[i].collidepoint(pos):
                return i
        return None

    def slot_at(self, pos):
        for slot in range(SLOTS):
            if slot_rect(slot).inflate(16, 16).collidepoint(pos):
                return slot
        return None

    # Events --------------------------------------------------------------

    def handle(self, event):
        if self.error:
            if self.error_button.handle(event) or (event.type == pygame.KEYDOWN and event.key in
                                                   (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE)):
                self.leave()
            return
        if self.paused:
            self.handle_pause(event)
            return
        if self.phase == "connecting":
            if self.cancel_button.handle(event) or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                self.leave()
            return
        if self.menu_button.handle(event) or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                                              and not self.molt_mode and self.phase != "over"):
            self.paused = True
            return
        handler = getattr(self, f"handle_{self.phase}", None)
        if handler:
            handler(event)

    def handle_pause(self, event):
        if self.resume_button.handle(event) or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            self.paused = False
        elif self.pause_rules_button.handle(event):
            self.app.switch(RulesScene(self.app, self))
        elif self.leave_button.handle(event):
            self.leave()

    def handle_plan(self, event):
        if self.lock_button.handle(event):
            self.lock_in()
            return
        if self.clear_button.handle(event):
            self.slots = [None] * SLOTS
            return
        if self.rules_button.handle(event):
            self.app.switch(RulesScene(self.app, self))
            return
        if self.molt_button.handle(event):
            self.toggle_molt()
            return
        if event.type == pygame.KEYDOWN:
            key = event.key
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.lock_in()
            elif pygame.K_1 <= key <= pygame.K_5 and key - pygame.K_1 < len(self.hand):
                index = key - pygame.K_1
                if self.molt_mode:
                    self.molt(index)
                else:
                    self.place(index)
            elif key == pygame.K_BACKSPACE:
                self.unplace_last()
            elif key == pygame.K_c:
                self.slots = [None] * SLOTS
            elif key == pygame.K_m:
                self.toggle_molt()
            elif key == pygame.K_ESCAPE and self.molt_mode:
                self.toggle_molt()
            elif key in (pygame.K_SLASH, pygame.K_QUESTION):
                self.app.switch(RulesScene(self.app, self))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            index = self.card_at(event.pos)
            if index is not None:
                if self.molt_mode:
                    self.molt(index)
                    return
                rect = self.hand_rects()[index]
                self.drag = {"index": index, "start": event.pos, "moved": False,
                             "offset": (event.pos[0] - rect.x, event.pos[1] - rect.y)}
                return
            slot = self.slot_at(event.pos)
            if slot is not None and self.slots[slot] is not None and not self.molt_mode:
                self.slots[slot] = None
        elif event.type == pygame.MOUSEMOTION and self.drag:
            sx, sy = self.drag["start"]
            if abs(event.pos[0] - sx) + abs(event.pos[1] - sy) > 8:
                self.drag["moved"] = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.drag:
            drag, self.drag = self.drag, None
            if not drag["moved"]:
                self.place(drag["index"])
                return
            slot = self.slot_at(event.pos)
            if slot is not None:
                rect = pygame.Rect(event.pos[0] - drag["offset"][0], event.pos[1] - drag["offset"][1], CARD_W, CARD_H)
                self.place(drag["index"], slot, rect)

    def handle_reveal(self, event):
        done = self.reveal_t >= REVEAL_END
        if done and self.continue_button.handle(event):
            self.finish_reveal()
            return
        pressed = (event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER)) \
            or (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not done)
        if pressed:
            if done:
                self.finish_reveal()
            else:
                self.skip_reveal()

    def handle_over(self, event):
        if self.rematch_button.handle(event) or (event.type == pygame.KEYDOWN and event.key == pygame.K_r):
            self.rematch()
        elif self.exit_button.handle(event) or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            self.leave()

    # Update --------------------------------------------------------------

    def update(self, dt):
        self.time += dt
        self.poll_processes()
        # Messages wait while a reveal animation plays, then apply in order.
        while self.inbox and self.phase != "reveal" and not self.error:
            self.on_message(self.inbox.popleft())
        mouse = self.app.mouse()
        for fighter in self.fighters:
            fighter.update(dt)
        for floater in self.floaters:
            floater.age += dt
        self.floaters = [f for f in self.floaters if f.age < f.life]
        for spark in self.sparks:
            spark.update(dt)
        self.sparks = [s for s in self.sparks if s.age < s.life]
        self.toast_age += dt
        for p in (0, 1):
            self.ghost_wait[p] -= dt
            if self.ghost_hp[p] > self.hp[p] and self.ghost_wait[p] <= 0:
                self.ghost_hp[p] = max(self.hp[p], self.ghost_hp[p] - 30 * dt)
            elif self.ghost_hp[p] < self.hp[p]:
                self.ghost_hp[p] = self.hp[p]

        buttons = [self.menu_button]
        if self.error:
            buttons = [self.error_button]
        elif self.paused:
            buttons = [self.resume_button, self.pause_rules_button, self.leave_button]
        elif self.phase == "connecting":
            buttons = [self.cancel_button]
        elif self.phase == "plan":
            buttons += [self.lock_button, self.clear_button, self.rules_button, self.molt_button]
            self.update_plan(dt, mouse)
        elif self.phase == "reveal":
            self.reveal_t += dt
            while self.events and self.events[0][0] <= self.reveal_t:
                _, action, slot = self.events.pop(0)
                action(slot)
            buttons.append(self.continue_button)
        elif self.phase == "over":
            buttons += [self.rematch_button, self.exit_button]
        for button in buttons:
            button.update(dt, mouse)

    def update_plan(self, dt, mouse):
        empty = all(i is None for i in self.slots)
        self.lock_button.label = "Pass Round" if empty else "Lock In"
        self.lock_button.enabled = self.pending_molt is None
        self.clear_button.enabled = not empty
        self.molt_button.enabled = self.ap[self.me] >= MOLT_COST and self.pending_molt is None
        self.molt_button.label = "Cancel" if self.molt_mode else "Molt"
        hovered = None if self.drag else self.card_at(mouse)
        for i in range(len(self.hover)):
            target = 1.0 if i == hovered else 0.0
            self.hover[i] += (target - self.hover[i]) * min(1.0, dt * 16)
            if self.shake[i] >= 0:
                self.shake[i] = self.shake[i] + dt if self.shake[i] < 0.4 else -1.0
        for slot in range(SLOTS):
            if self.slot_anim[slot]:
                rect, age = self.slot_anim[slot]
                self.slot_anim[slot] = (rect, age + dt) if age < 0.25 else None
        if self.fresh_card:
            index, age = self.fresh_card
            self.fresh_card = (index, age + dt) if age < 1.5 else None

    # Drawing -------------------------------------------------------------

    def draw(self, surface):
        surface.blit(ui.background(WIDTH, HEIGHT), (0, 0))
        self.draw_top_bar(surface)
        self.draw_arena(surface)
        if self.phase in ("plan", "locked"):
            self.draw_plan(surface)
        else:
            getattr(self, f"draw_{self.phase}")(surface)
        for spark in self.sparks:
            spark.draw(surface)
        for floater in self.floaters:
            floater.draw(surface)
        self.draw_toast(surface)
        if self.paused:
            self.draw_pause(surface)
        if self.error:
            self.draw_error(surface)

    def draw_top_bar(self, surface):
        pill = pygame.Rect(20, 10, 124, 34)
        surface.blit(ui.rounded(pill.w, pill.h, 17, (0, 0, 0, 80), (255, 255, 255, 30), 1), pill)
        round_shown = self.report.round if self.report and self.phase in ("reveal", "over") else self.round
        draw_text(surface, f"ROUND {round_shown}", pill.center, 15, AMBER, True, "center")
        mode = {"cpu": "VS COMPUTER", "host": f"ONLINE · HOSTING ON PORT {self.port}",
                "join": f"ONLINE · {self.host}"}[self.mode]
        draw_text(surface, mode, (pill.right + 16, pill.centery), 12, TEXT_MUTED, True, "midleft")
        titles = {
            "connecting": "CONNECTING",
            "sync": "GET READY",
            "plan": "PLAN YOUR MOVES",
            "locked": f"WAITING FOR {self.names[self.opp].upper()}",
            "reveal": "BATTLE!",
            "over": "MATCH OVER",
        }
        color = PLAYER_COLORS[self.me] if self.phase in ("plan", "locked") else TEXT
        rect = draw_text(surface, titles[self.phase], (WIDTH // 2 + 8, 27), 17, color, True, "center")
        if self.phase in ("plan", "locked"):
            pygame.draw.circle(surface, color, (rect.x - 14, rect.centery), 5)
        self.menu_button.draw(surface)

    def draw_arena(self, surface):
        for side in (0, 1):
            p = self.player_at(side)
            rect = pygame.Rect(32 if side == 0 else WIDTH - 32 - 440, 54, 440, 66)
            ui.panel(surface, rect, 14, (0, 0, 0, 70))
            color = PLAYER_COLORS[p]
            name = self.names[p].upper() + ("  ·  YOU" if p == self.me and self.phase != "connecting" else "")
            name_pos = (rect.x + 18, rect.y + 10) if side == 0 else (rect.right - 18, rect.y + 10)
            draw_text(surface, name, name_pos, 16, color, True, "topleft" if side == 0 else "topright")
            hp_text = f"{max(0, round(self.hp[p]))} / {START_HP} HP"
            hp_pos = (rect.x + 344, rect.y + 11) if side == 0 else (rect.right - 344, rect.y + 11)
            draw_text(surface, hp_text, hp_pos, 15, TEXT, True, "topright" if side == 0 else "topleft")
            bar = pygame.Rect(0, rect.y + 36, 326, 18)
            bar.x = rect.x + 18 if side == 0 else rect.right - 18 - bar.w
            ui.hp_bar(surface, bar, self.hp[p], self.ghost_hp[p], START_HP, color)
            ap_x = rect.right - 52 if side == 0 else rect.x + 30
            draw_text(surface, "AP", (ap_x + 11, rect.y + 13), 11, TEXT_MUTED, True, "midtop")
            ui.ap_pips(surface, (ap_x, rect.y + 44), self.ap[p], MAX_AP)
            if side == 1 and self.opponent_ready and self.phase in ("plan", "locked"):
                pill = pygame.Rect(0, 0, 84, 24)
                pill.center = (rect.centerx, rect.bottom)
                surface.blit(ui.rounded(pill.w, pill.h, 12, (34, 90, 52), GREEN, 1), pill)
                draw_text(surface, "READY", pill.center, 12, TEXT, True, "center")

        center = (WIDTH // 2, FIGHTER_Y + 4)
        pygame.draw.circle(surface, (0, 0, 0), (center[0], center[1] + 4), 34)
        surface.blit(ui.rounded(64, 64, 32, (34, 24, 18), (200, 140, 70), 2), (center[0] - 32, center[1] - 32))
        draw_text(surface, "VS", center, 24, AMBER, True, "center", True)
        for fighter in self.fighters:
            fighter.draw(surface)

    def draw_toast(self, surface):
        life = self.toast_life
        if not self.toast_text or self.toast_age > life or self.phase not in ("plan", "locked"):
            return
        alpha = 255 if self.toast_age < life - 0.3 else int(255 * (life - self.toast_age) / 0.3)
        image = ui.font(16, True).render(self.toast_text, True, TEXT)
        rect = image.get_rect(center=(WIDTH // 2, 272)).inflate(36, 16)
        box = ui.rounded(rect.w, rect.h, rect.h // 2, (16, 10, 6, 220), (*AMBER, 140), 1).copy()
        box.set_alpha(alpha)
        surface.blit(box, rect)
        image.set_alpha(alpha)
        surface.blit(image, image.get_rect(center=rect.center))

    def draw_connecting(self, surface):
        rect = pygame.Rect(WIDTH // 2 - 340, 300, 680, 300)
        ui.blit_shadow(surface, rect, 20, 14, 140)
        ui.panel(surface, rect, 20, (30, 22, 16, 245))
        spinner(surface, (rect.x + 56, rect.y + 56), self.time)
        dots = "." * (1 + int(self.time * 3) % 3)
        draw_text(surface, self.status + dots, (rect.x + 92, rect.y + 40), 24, TEXT, True, "topleft", True)
        y = rect.y + 104
        if self.mode == "host" and self.client:
            draw_text(surface, "Ask your opponent to choose Join Online Game and enter:", (rect.x + 40, y),
                      16, TEXT_DIM)
            y += 34
            rows = [(address, "on your network") for address in self.addresses[:3]]
            rows.append(("127.0.0.1", "on this computer"))
            for address, where in rows:
                box = pygame.Rect(rect.x + 40, y, rect.w - 80, 34)
                surface.blit(ui.rounded(box.w, box.h, 10, (0, 0, 0, 80), (255, 255, 255, 30), 1), box)
                draw_text(surface, f"{address}   port {self.port}", (box.x + 16, box.centery), 17, AMBER, True,
                          "midleft")
                draw_text(surface, where, (box.right - 16, box.centery), 13, TEXT_MUTED, True, "midright")
                y += 40
        elif self.mode == "cpu":
            draw_text(surface, "The C game server runs on this computer with a CPU opponent.",
                      (rect.x + 40, y), 16, TEXT_DIM)
        rect.h = max(rect.h, y - rect.y + 84)
        self.cancel_button.rect.y = rect.y + rect.h - 70
        self.cancel_button.draw(surface)

    def draw_sync(self, surface):
        draw_text(surface, "Get ready" + "." * (1 + int(self.time * 3) % 3), (WIDTH // 2, 420), 22,
                  TEXT_DIM, True, "center")

    def draw_plan(self, surface):
        locked = self.phase == "locked"
        used = self.energy_used()
        mouse = self.app.mouse()

        # Energy and AP panel.
        ui.panel(surface, LEFT_PANEL)
        draw_text(surface, "ENERGY", (LEFT_PANEL.x + 18, LEFT_PANEL.y + 14), 12, TEXT_MUTED, True)
        hovered = None if locked or self.molt_mode or self.drag else self.card_at(mouse)
        preview = card_cost(self.hand[hovered]) if hovered is not None and hovered not in self.slots else 0
        fits = used + preview <= ROUND_ENERGY
        for i in range(ROUND_ENERGY):
            rect = pygame.Rect(LEFT_PANEL.x + 18 + i * 60, LEFT_PANEL.y + 36, 50, 50)
            spent = i >= ROUND_ENERGY - used
            pending = not spent and i >= ROUND_ENERGY - used - preview
            if spent:
                fill, icon = (60, 44, 30), (110, 84, 60)
            elif pending:
                fill, icon = ((120, 80, 20) if fits else (120, 40, 34)), ((255, 220, 140) if fits else RED)
            else:
                fill, icon = (247, 172, 48), (60, 34, 6)
            surface.blit(ui.rounded(50, 50, 12, fill, ui.lighten(fill, 0.2), 1), rect)
            bolt(surface, rect.inflate(-14, -14), icon)
        draw_text(surface, str(ROUND_ENERGY - used), (LEFT_PANEL.right - 34, LEFT_PANEL.y + 34), 34, AMBER,
                  True, "midtop", True)
        draw_text(surface, "left", (LEFT_PANEL.right - 34, LEFT_PANEL.y + 72), 12, TEXT_MUTED, True, "midtop")
        pygame.draw.line(surface, (74, 60, 48), (LEFT_PANEL.x + 18, LEFT_PANEL.y + 104),
                         (LEFT_PANEL.right - 18, LEFT_PANEL.y + 104))
        draw_text(surface, "ADAPTATION", (LEFT_PANEL.x + 18, LEFT_PANEL.y + 118), 12, TEXT_MUTED, True)
        my_ap = self.ap[self.me]
        ui.ap_pips(surface, (LEFT_PANEL.x + 30, LEFT_PANEL.y + 152), my_ap, MAX_AP)
        draw_text(surface, f"{my_ap}/{MAX_AP}", (LEFT_PANEL.x + 80, LEFT_PANEL.y + 152), 15, TEXT, True, "midleft")

        # Actions panel.
        ui.panel(surface, RIGHT_PANEL)
        if locked:
            self.lock_button.label, self.lock_button.enabled = "Locked In", False
            self.clear_button.enabled = self.molt_button.enabled = False
            self.molt_button.label = "Molt"
        self.molt_button.draw(surface)
        self.lock_button.draw(surface)
        self.clear_button.draw(surface)
        self.rules_button.draw(surface)
        if locked:
            text = f"Waiting for {self.names[self.opp]} to lock in" + "." * (1 + int(self.time * 3) % 3)
            spinner(surface, (RIGHT_PANEL.x + 34, RIGHT_PANEL.y + 155), self.time, PLAYER_COLORS[self.opp])
            draw_text(surface, text, (RIGHT_PANEL.x + 62, RIGHT_PANEL.y + 155), 14, TEXT_DIM, True, "midleft")
        else:
            help_text = ("Click a card to fill the next slot, or drag it onto a slot. "
                         "Click a slotted card to take it back.")
            y = RIGHT_PANEL.y + 138
            for line in ui.wrap(help_text, 13, RIGHT_PANEL.w - 36):
                draw_text(surface, line, (RIGHT_PANEL.x + 18, y), 13, TEXT_MUTED)
                y += 18

        # Slots.
        for slot in range(SLOTS):
            rect = slot_rect(slot)
            target = self.drag and self.drag["moved"] and self.slot_at(mouse) == slot
            border = (*AMBER, 220) if target else (255, 255, 255, 46)
            surface.blit(ui.rounded(rect.w, rect.h, 14, (0, 0, 0, 60), border, 2 if target else 1), rect)
            draw_text(surface, f"SLOT {slot + 1}", (rect.centerx, rect.y + 16), 12, TEXT_MUTED, True, "midtop")
            draw_text(surface, "+", (rect.centerx, rect.centery + 4), 40, TEXT, False, "center", alpha=50)
            index = self.slots[slot]
            if index is None:
                continue
            draw_rect = rect
            if self.slot_anim[slot]:
                start, age = self.slot_anim[slot]
                t = ui.ease_out(age / 0.25)
                draw_rect = pygame.Rect(start.x + (rect.x - start.x) * t, start.y + (rect.y - start.y) * t,
                                        CARD_W, CARD_H)
            blit_card(surface, self.hand[index], draw_rect)
            if locked:
                badge = pygame.Rect(0, 0, 30, 30)
                badge.center = (rect.right - 6, rect.y + 6)
                surface.blit(ui.rounded(30, 30, 15, (34, 90, 52), GREEN, 2), badge)
                draw_text(surface, "OK", badge.center, 10, TEXT, True, "center")
            elif draw_rect == rect and rect.collidepoint(mouse) and not self.drag and not self.molt_mode:
                surface.blit(ui.rounded(CARD_W, CARD_H, 14, (0, 0, 0, 140)), rect)
                draw_text(surface, "Remove", rect.center, 16, TEXT, True, "center")

        # Hand.
        draw_text(surface, "YOUR HAND", (40, HAND_Y + 6), 12, TEXT_MUTED, True)
        draw_text(surface, f"Deck {self.deck_count}", (40, HAND_Y + 28), 15, TEXT_DIM, True)
        draw_text(surface, f"Discard {self.discard_count}", (40, HAND_Y + 50), 15, TEXT_DIM, True)
        draw_text(surface, "Keys 1-5 pick cards", (WIDTH - 40, HAND_Y + 6), 12, TEXT_MUTED, True, "topright")
        draw_text(surface, "Backspace undo", (WIDTH - 40, HAND_Y + 26), 12, TEXT_MUTED, True, "topright")
        rects = self.hand_rects()
        remaining = ROUND_ENERGY - used
        for i, rect in enumerate(rects):
            card = self.hand[i]
            if self.drag and self.drag["index"] == i and self.drag["moved"]:
                surface.blit(ui.rounded(CARD_W, CARD_H, 14, (255, 255, 255, 10), (255, 255, 255, 40), 1),
                             hand_rect(i, len(rects)))
                continue
            if self.shake[i] >= 0:
                rect = rect.move(int(math.sin(self.shake[i] * 60) * 8 * (1 - self.shake[i] / 0.4)), 0)
            if i in self.slots:
                surface.blit(ui.rounded(CARD_W, CARD_H, 14, (255, 255, 255, 8), (255, 255, 255, 36), 1), rect)
                blit_card(surface, card, rect, alpha=60, shadow=False)
                draw_text(surface, f"IN SLOT {self.slots.index(i) + 1}", rect.center, 14, TEXT, True, "center",
                          shadow=True)
                continue
            if self.fresh_card and self.fresh_card[0] == i:
                pulse = 1 - self.fresh_card[1] / 1.5
                glow = rect.inflate(16, 16)
                surface.blit(ui.rounded(glow.w, glow.h, 20, (*AMBER, int(120 * pulse))), glow)
            if self.molt_mode:
                glow = rect.inflate(8, 8)
                surface.blit(ui.rounded(glow.w, glow.h, 18, (*TEAL, int(90 + 60 * math.sin(self.time * 6)))), glow)
            blit_card(surface, card, rect, alpha=110 if locked else 255)
            if not locked and card_cost(card) > remaining and not self.molt_mode:
                surface.blit(ui.rounded(CARD_W, CARD_H, 14, (0, 0, 0, 130)), rect)
            draw_text(surface, str(i + 1), (rect.centerx, rect.y - 3), 12, TEXT_MUTED, True, "midbottom")
        if self.drag and self.drag["moved"]:
            x, y = mouse[0] - self.drag["offset"][0], mouse[1] - self.drag["offset"][1]
            rect = pygame.Rect(x, y, CARD_W, CARD_H)
            ui.blit_shadow(surface, rect, 14, 14, 160, (6, 16))
            blit_card(surface, self.hand[self.drag["index"]], rect, shadow=False)

    def draw_reveal(self, surface):
        rep = self.report
        t = self.reveal_t
        card_w, card_h = int(CARD_W * 0.8), int(CARD_H * 0.8)
        for slot in range(SLOTS):
            cx = WIDTH // 2 + (slot - 1) * 410
            column = pygame.Rect(cx - 195, 268, 390, 360)
            base = REVEAL_START + slot * REVEAL_STEP
            active = base <= t < base + REVEAL_STEP or (slot == SLOTS - 1 and t >= base)
            border = (*AMBER, 120) if active and t < REVEAL_END else (255, 255, 255, 26)
            ui.panel(surface, column, 18, (0, 0, 0, 70), border)
            draw_text(surface, f"SLOT {slot + 1}", (cx, column.y + 14), 12, TEXT_MUTED, True, "midtop")
            progress = (t - base) / FLIP_TIME
            for side in (0, 1):
                p = self.player_at(side)
                rect = pygame.Rect(0, column.y + 42, card_w, card_h)
                rect.centerx = cx - 84 if side == 0 else cx + 84
                pygame.draw.circle(surface, PLAYER_COLORS[p], (rect.centerx, rect.bottom + 14), 4)
                card = rep.cards[p][slot]
                if progress < 0.5:
                    blit_card(surface, card, rect, back=True, scale_x=max(0.02, 1 - max(0.0, progress) * 2))
                elif card == EMPTY:
                    surface.blit(ui.rounded(rect.w, rect.h, 12, (255, 255, 255, 8), (255, 255, 255, 40), 1), rect)
                    draw_text(surface, "EMPTY", rect.center, 14, TEXT_MUTED, True, "center")
                else:
                    blit_card(surface, card, rect, scale_x=max(0.02, min(1.0, (progress - 0.5) * 2)))
            draw_text(surface, "vs", (cx, column.y + 42 + card_h // 2), 18, TEXT_MUTED, True, "center")
            if t >= base + CLASH_TIME:
                self.draw_slot_result(surface, slot, cx, column.y + 248, min(1.0, (t - base - CLASH_TIME) / 0.25))

        if t >= REVEAL_END:
            self.continue_button.draw(surface)
            for side in (0, 1):
                p = self.player_at(side)
                text = f"{self.label(p)} dealt {sum(rep.damage[1 - p])}"
                x = self.continue_button.rect.x - 30 if side == 0 else self.continue_button.rect.right + 30
                draw_text(surface, text, (x, self.continue_button.rect.centery), 16, PLAYER_COLORS[p], True,
                          "midright" if side == 0 else "midleft")
        else:
            draw_text(surface, "Click or press Space to skip", (WIDTH // 2, 668), 13, TEXT_MUTED, True, "center")

    def draw_slot_result(self, surface, slot, cx, y, appear):
        rep = self.report
        cards = [rep.cards[p][slot] for p in (0, 1)]
        damage = [rep.damage[p][slot] for p in (0, 1)]
        defended = [rep.defended[p][slot] for p in (0, 1)]
        if any(defended) and DULAG_SAPAK in cards and LAYOG_KAGAT in cards and damage != [0, 0]:
            headline, color = "DODGE & COUNTER", TEAL
        elif any(defended):
            headline, color = "BLOCKED", BLUE
        elif all(damage):
            headline, color = "TRADE", AMBER
        elif any(damage):
            pierce = ULTI_KAGAT in cards and (SAGANG in cards or DULAG_SAPAK in cards)
            headline, color = ("PIERCED", (200, 140, 255)) if pierce else ("HIT", RED)
        elif cards == [EMPTY, EMPTY]:
            headline, color = "NO ACTION", TEXT_MUTED
        else:
            headline, color = "NO CONTACT", TEXT_DIM
        alpha = int(255 * appear)
        draw_text(surface, headline, (cx, y), int(26 + 6 * (1 - appear)), color, True, "center", True, True, alpha)
        for side in (0, 1):
            p = self.player_at(side)
            x = cx - 84 if side == 0 else cx + 84
            if damage[p]:
                draw_text(surface, f"-{damage[p]} HP", (x, y + 46), 18, RED, True, "center", alpha=alpha)
            elif defended[p]:
                draw_text(surface, "+1 AP", (x, y + 46), 18, AMBER, True, "center", alpha=alpha)
            else:
                draw_text(surface, "—", (x, y + 46), 18, TEXT_MUTED, True, "center", alpha=alpha)

    def draw_over(self, surface):
        rep = self.report
        if rep.outcome == DRAW:
            title, color = "DRAW!", AMBER
        else:
            winner = 0 if rep.outcome == PLAYER_ONE_WINS else 1
            color = PLAYER_COLORS[winner]
            title = "YOU WIN!" if winner == self.me else f"{self.names[winner].upper()} WINS"
        rect = pygame.Rect(WIDTH // 2 - 330, 280, 660, 380)
        ui.blit_shadow(surface, rect, 22, 16, 160)
        ui.panel(surface, rect, 22, (28, 20, 15, 245), (*color, 140))
        image = gradient_text(title, 64, ui.lighten(color, 0.35), ui.darken(color, 0.1))
        surface.blit(image, image.get_rect(midtop=(WIDTH // 2, rect.y + 24)))
        rounds = rep.round
        subtitle = "Both cockroaches fell in the same round." if rep.outcome == DRAW \
            else f"Last cockroach standing after {rounds} round{'s' if rounds != 1 else ''}."
        draw_text(surface, subtitle, (WIDTH // 2, rect.y + 104), 16, TEXT_DIM, False, "midtop")
        rows = (("Damage dealt", self.stats["damage"]), ("Blocks & dodges", self.stats["defenses"]),
                ("HP left", rep.hp_after))
        y = rect.y + 146
        for side in (0, 1):
            p = self.player_at(side)
            draw_text(surface, self.label(p).upper(), (WIDTH // 2 + (-90 if side == 0 else 90), y), 13,
                      PLAYER_COLORS[p], True, "center")
        for label, values in rows:
            y += 30
            draw_text(surface, label, (WIDTH // 2, y), 14, TEXT_MUTED, True, "center")
            draw_text(surface, str(values[self.me]), (WIDTH // 2 - 90, y), 18, TEXT, True, "center")
            draw_text(surface, str(values[self.opp]), (WIDTH // 2 + 90, y), 18, TEXT, True, "center")
        opponent = self.names[self.opp]
        if self.opponent_left:
            note, note_color = f"{opponent} left, so a rematch is not possible.", RED
        elif self.rematch_sent:
            note, note_color = f"Waiting for {opponent} to accept the rematch...", TEXT_DIM
        elif self.opponent_rematch:
            note, note_color = f"{opponent} wants a rematch!", GREEN
        else:
            note, note_color = "", TEXT_DIM
        draw_text(surface, note, (WIDTH // 2, rect.bottom - 106), 14, note_color, True, "center")
        self.rematch_button.enabled = not (self.rematch_sent or self.opponent_left)
        self.rematch_button.label = "Waiting..." if self.rematch_sent else "Rematch"
        self.rematch_button.rect.y = self.exit_button.rect.y = rect.bottom - 80
        self.rematch_button.draw(surface)
        self.exit_button.draw(surface)

    def draw_pause(self, surface):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        rect = pygame.Rect(WIDTH // 2 - 180, 210, 360, 300)
        ui.blit_shadow(surface, rect, 20, 14, 160)
        ui.panel(surface, rect, 20, (30, 22, 16, 250))
        draw_text(surface, "Paused", (WIDTH // 2, rect.y + 28), 30, TEXT, True, "midtop", True)
        note = "The match keeps running while paused." if self.mode != "cpu" else "Leaving ends the match."
        draw_text(surface, note, (WIDTH // 2, rect.bottom - 18), 12, TEXT_MUTED, False, "midbottom")
        for button in (self.resume_button, self.pause_rules_button, self.leave_button):
            button.draw(surface)

    def draw_error(self, surface):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))
        lines = []
        for paragraph in self.error.split("\n"):
            lines += ui.wrap(paragraph, 16, 520) or [""]
        lines = lines[:8]
        rect = pygame.Rect(WIDTH // 2 - 300, 0, 600, 190 + 24 * len(lines))
        rect.centery = HEIGHT // 2
        ui.blit_shadow(surface, rect, 20, 14, 160)
        ui.panel(surface, rect, 20, (30, 22, 16, 250), (*RED, 120))
        draw_text(surface, self.error_title, (WIDTH // 2, rect.y + 28), 28, TEXT, True, "midtop", True)
        y = rect.y + 82
        for line in lines:
            draw_text(surface, line, (WIDTH // 2, y), 16, TEXT_DIM, False, "midtop")
            y += 24
        self.error_button.rect.y = rect.bottom - 76
        self.error_button.draw(surface)


# Application ---------------------------------------------------------------

class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("IPIS Arena")
        icon = pygame.Surface((64, 64), pygame.SRCALPHA)
        ui.draw_roach_icon(icon, 32, 38, 20, (214, 140, 60))
        pygame.display.set_icon(icon)
        try:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.RESIZABLE)
        except pygame.error:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene = TitleScene(self)

    def mouse(self):
        return pygame.mouse.get_pos()

    def switch(self, scene):
        self.scene = scene

    def quit(self):
        self.running = False

    def step(self, dt, events):
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
            else:
                self.scene.handle(event)
        self.scene.update(dt)
        self.scene.draw(self.screen)

    def run(self):
        try:
            while self.running:
                dt = min(self.clock.tick(FPS) / 1000, 0.05)
                self.step(dt, pygame.event.get())
                pygame.display.flip()
        finally:
            bridge.stop_all()
            pygame.quit()


def main():
    App().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
