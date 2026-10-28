"""Drawing helpers for the IPIS Arena GUI: theme, text, cards, fighters.

Shapes are drawn at twice the size and smooth-scaled down, which gives
anti-aliased edges with plain pygame drawing calls. Static pieces such as
cards and buttons are cached.
"""

import math
from functools import lru_cache

import pygame

from cards import (CARD_EFFECTS, CARD_NAMES, DULAG_SAPAK, KAGAT, LAYOG_KAGAT,
                    SAGANG, ULTI_KAGAT, card_cost)

WIDTH, HEIGHT = 1280, 720
SS = 2  # supersampling factor

# Theme -------------------------------------------------------------------

BG_TOP = (24, 18, 14)
BG_BOTTOM = (44, 31, 22)
PANEL = (255, 255, 255, 14)
PANEL_BORDER = (255, 255, 255, 26)
TEXT = (246, 236, 222)
TEXT_DIM = (190, 174, 152)
TEXT_MUTED = (130, 116, 98)
AMBER = (247, 172, 48)
AMBER_DARK = (150, 96, 20)
RED = (240, 82, 70)
GREEN = (92, 214, 120)
BLUE = (88, 160, 255)
TEAL = (40, 196, 170)
PLAYER_COLORS = ((255, 112, 82), (82, 176, 255))

CARD_COLORS = {
    KAGAT: (229, 72, 77),
    LAYOG_KAGAT: (247, 120, 30),
    SAGANG: (62, 123, 250),
    DULAG_SAPAK: (18, 165, 148),
    ULTI_KAGAT: (142, 78, 198),
}
CARD_TAGS = {
    KAGAT: "ATTACK",
    LAYOG_KAGAT: "HEAVY",
    SAGANG: "BLOCK",
    DULAG_SAPAK: "COUNTER",
    ULTI_KAGAT: "PIERCE",
}

CARD_W, CARD_H = 132, 184


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lighten(color, t):
    return mix(color, (255, 255, 255), t)


def darken(color, t):
    return mix(color, (0, 0, 0), t)


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_out_back(t):
    t = max(0.0, min(1.0, t))
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


# Text --------------------------------------------------------------------

_fonts = {}


def font(size, bold=False, display=False):
    key = (size, bold, display)
    if key not in _fonts:
        names = "inter,ubuntu,dejavusans,freesans,arial"
        if display:
            names = "interdisplayblack,interdisplay,ubuntu,dejavusans,freesans,arial"
        _fonts[key] = pygame.font.SysFont(names, size, bold=bold)
    return _fonts[key]


def draw_text(surface, text, pos, size=18, color=TEXT, bold=False,
              anchor="topleft", display=False, shadow=False, alpha=255):
    image = font(size, bold, display).render(text, True, color)
    rect = image.get_rect(**{anchor: pos})
    if shadow:
        shade = font(size, bold, display).render(text, True, (0, 0, 0))
        shade.set_alpha(int(110 * alpha / 255))
        surface.blit(shade, rect.move(0, max(2, size // 16)))
    if alpha < 255:
        image.set_alpha(alpha)
    surface.blit(image, rect)
    return rect


def wrap(text, size, width, bold=False):
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if font(size, bold).size(trial)[0] <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# Surfaces ----------------------------------------------------------------

def gradient(w, h, top, bottom):
    strip = pygame.Surface((1, 2))
    strip.set_at((0, 0), top[:3])
    strip.set_at((0, 1), bottom[:3])
    return pygame.transform.smoothscale(strip, (w, h))


@lru_cache(maxsize=256)
def rounded(w, h, radius, fill, border=None, border_width=0):
    """An anti-aliased rounded rectangle with optional border."""
    big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    rect = big.get_rect()
    if border and border_width:
        pygame.draw.rect(big, border, rect, border_radius=radius * SS)
        inset = border_width * SS
        pygame.draw.rect(big, fill, rect.inflate(-2 * inset, -2 * inset),
                         border_radius=max(0, (radius - border_width) * SS))
    else:
        pygame.draw.rect(big, fill, rect, border_radius=radius * SS)
    return pygame.transform.smoothscale(big, (w, h))


@lru_cache(maxsize=64)
def shadow(w, h, radius, spread=10, alpha=120):
    """A soft drop shadow, made by blurring a dark rounded rectangle."""
    pad = spread * 2
    base = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    base.blit(rounded(w, h, radius, (0, 0, 0, alpha)), (pad, pad))
    small = pygame.transform.smoothscale(base, (max(1, base.get_width() // 8),
                                                max(1, base.get_height() // 8)))
    return pygame.transform.smoothscale(small, base.get_size())


def blit_shadow(surface, rect, radius, spread=10, alpha=120, offset=(0, 6)):
    image = shadow(rect.w, rect.h, radius, spread, alpha)
    surface.blit(image, (rect.x - spread * 2 + offset[0], rect.y - spread * 2 + offset[1]))


def panel(surface, rect, radius=16, fill=PANEL, border=PANEL_BORDER):
    surface.blit(rounded(rect.w, rect.h, radius, fill, border, 1), rect)


@lru_cache(maxsize=4)
def background(w, h):
    surface = gradient(w, h, BG_TOP, BG_BOTTOM).convert()
    glow = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(14):
        r = int(w * 0.55 * (1 - i / 14))
        pygame.draw.ellipse(glow, (255, 170, 80, 3),
                            pygame.Rect(0, 0, r * 2, int(r * 0.8)).move(w // 2 - r, int(h * 0.36 - r * 0.4)))
    surface.blit(glow, (0, 0))
    vignette = pygame.Surface((w // 8, h // 8), pygame.SRCALPHA)
    cx, cy = vignette.get_width() / 2, vignette.get_height() / 2
    for y in range(vignette.get_height()):
        for x in range(vignette.get_width()):
            d = math.hypot((x - cx) / cx, (y - cy) / cy)
            vignette.set_at((x, y), (0, 0, 0, int(min(1, max(0, d - 0.55)) * 220)))
    surface.blit(pygame.transform.smoothscale(vignette, (w, h)), (0, 0))
    return surface


# Card icons --------------------------------------------------------------

def _fang(surface, x, y, s, color):
    pygame.draw.polygon(surface, color, [(x - s * 0.5, y), (x + s * 0.5, y),
                                         (x + s * 0.12, y + s * 1.25), (x - s * 0.05, y + s * 1.35)])


def draw_icon(surface, card, cx, cy, s, color=(255, 255, 255)):
    """Draw a card symbol of roughly size s centred on (cx, cy)."""
    if card in (KAGAT, LAYOG_KAGAT):
        offset = s * 0.12 if card == LAYOG_KAGAT else 0
        pygame.draw.rect(surface, color, (cx - s * 0.62 + offset, cy - s * 0.5, s * 1.24, s * 0.3),
                         border_radius=int(s * 0.15))
        _fang(surface, cx - s * 0.3 + offset, cy - s * 0.25, s * 0.42, color)
        _fang(surface, cx + s * 0.3 + offset, cy - s * 0.25, s * 0.42, color)
        if card == LAYOG_KAGAT:
            for i, length in enumerate((0.55, 0.8, 0.55)):
                y = cy - s * 0.35 + i * s * 0.32
                pygame.draw.line(surface, color, (cx - s * 1.05, y), (cx - s * (1.05 - length), y),
                                 max(2, int(s * 0.1)))
    elif card == SAGANG:
        points = [(cx, cy - s * 0.8), (cx + s * 0.68, cy - s * 0.52), (cx + s * 0.6, cy + s * 0.2),
                  (cx, cy + s * 0.85), (cx - s * 0.6, cy + s * 0.2), (cx - s * 0.68, cy - s * 0.52)]
        pygame.draw.polygon(surface, color, points)
        inner = [(cx + (x - cx) * 0.62, cy + (y - cy) * 0.62 + s * 0.02) for x, y in points]
        pygame.draw.polygon(surface, darken(CARD_COLORS[SAGANG], 0.25), inner)
        pygame.draw.line(surface, color, (cx, cy - s * 0.45), (cx, cy + s * 0.5), max(2, int(s * 0.1)))
    elif card == DULAG_SAPAK:
        rect = pygame.Rect(0, 0, s * 1.5, s * 1.5)
        rect.center = (cx, cy + s * 0.05)
        pygame.draw.arc(surface, color, rect, math.radians(200), math.radians(500),
                        max(3, int(s * 0.18)))
        tip = (cx - s * 0.68, cy - s * 0.18)
        pygame.draw.polygon(surface, color, [(tip[0] - s * 0.32, tip[1] - s * 0.05),
                                             (tip[0] + s * 0.3, tip[1] - s * 0.12),
                                             (tip[0] - s * 0.02, tip[1] + s * 0.38)])
        pygame.draw.circle(surface, color, (cx + s * 0.05, cy + s * 0.05), s * 0.2)
    elif card == ULTI_KAGAT:
        points = []
        for i in range(16):
            r = s * (0.95 if i % 2 == 0 else 0.42)
            a = math.pi * 2 * i / 16 - math.pi / 2
            points.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        pygame.draw.polygon(surface, (255, 214, 102), points)
        _fang(surface, cx - s * 0.17, cy - s * 0.32, s * 0.3, color)
        _fang(surface, cx + s * 0.17, cy - s * 0.32, s * 0.3, color)


@lru_cache(maxsize=32)
def card_face(card, w=CARD_W, h=CARD_H):
    color = CARD_COLORS[card]
    W, H = CARD_W * SS, CARD_H * SS
    big = pygame.Surface((W, H), pygame.SRCALPHA)
    radius = 14 * SS
    border = (255, 214, 102) if card == ULTI_KAGAT else lighten(color, 0.25)
    pygame.draw.rect(big, border, big.get_rect(), border_radius=radius)
    inner = big.get_rect().inflate(-5 * SS, -5 * SS)
    pygame.draw.rect(big, (30, 24, 20), inner, border_radius=radius - 3 * SS)

    # Art window with a vertical gradient.
    art = pygame.Rect(inner.x + 5 * SS, inner.y + 5 * SS, inner.w - 10 * SS, int(H * 0.46))
    grad = gradient(art.w, art.h, lighten(color, 0.15), darken(color, 0.45)).convert_alpha()
    mask = pygame.Surface(art.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=10 * SS)
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    big.blit(grad, art)
    glow = pygame.Surface(art.size, pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 255, 255, 34), (art.w // 2, art.h // 2 + 4 * SS), art.h * 0.42)
    big.blit(glow, art)
    draw_icon(big, card, art.centerx, art.centery + 6 * SS, art.h * 0.3)

    # Energy pips and type tag.
    for i in range(card_cost(card)):
        center = (art.x + 13 * SS + i * 17 * SS, art.y + 13 * SS)
        pygame.draw.circle(big, (20, 14, 8), center, 7.5 * SS)
        pygame.draw.circle(big, AMBER, center, 5.5 * SS)
    tag = font(9 * SS, True).render(CARD_TAGS[card], True, (255, 255, 255))
    tag_rect = tag.get_rect(topright=(art.right - 8 * SS, art.y + 7 * SS)).inflate(10 * SS, 6 * SS)
    pygame.draw.rect(big, (0, 0, 0, 90), tag_rect, border_radius=tag_rect.h // 2)
    big.blit(tag, tag.get_rect(center=tag_rect.center))

    # Name and effect text.
    y = art.bottom + 9 * SS
    name_size = 15 * SS if len(CARD_NAMES[card]) < 12 else 13 * SS
    for line in wrap(CARD_NAMES[card], name_size, inner.w - 14 * SS, True):
        image = font(name_size, True).render(line, True, TEXT)
        big.blit(image, image.get_rect(midtop=(W // 2, y)))
        y += image.get_height() - 2 * SS
    y += 5 * SS
    pygame.draw.line(big, darken(color, 0.1), (W * 0.3, y), (W * 0.7, y), SS)
    y += 7 * SS
    for line in wrap(CARD_EFFECTS[card], 11 * SS, inner.w - 18 * SS):
        image = font(11 * SS).render(line, True, TEXT_DIM)
        big.blit(image, image.get_rect(midtop=(W // 2, y)))
        y += image.get_height()
    return pygame.transform.smoothscale(big, (w, h))


@lru_cache(maxsize=8)
def card_back(w=CARD_W, h=CARD_H):
    W, H = CARD_W * SS, CARD_H * SS
    big = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.rect(big, (120, 78, 40), big.get_rect(), border_radius=14 * SS)
    inner = big.get_rect().inflate(-6 * SS, -6 * SS)
    grad = gradient(inner.w, inner.h, (70, 42, 22), (34, 22, 14)).convert_alpha()
    mask = pygame.Surface(inner.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=11 * SS)
    grad.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    big.blit(grad, inner)
    for i in range(-H, W, 14 * SS):
        pygame.draw.line(big, (255, 200, 120, 14), (i, inner.y), (i + H, inner.y + H), 3 * SS)
    pygame.draw.rect(big, (200, 140, 70), inner.inflate(-14 * SS, -14 * SS), 2 * SS, border_radius=8 * SS)
    draw_roach_icon(big, W // 2, H // 2, 26 * SS, (214, 156, 86))
    label = font(12 * SS, True).render("IPIS", True, (214, 156, 86))
    big.blit(label, label.get_rect(midtop=(W // 2, H // 2 + 36 * SS)))
    return pygame.transform.smoothscale(big, (w, h))


def draw_roach_icon(surface, cx, cy, s, color):
    """A simple top-down cockroach silhouette."""
    for side in (-1, 1):
        for i, dy in enumerate((-0.25, 0.1, 0.45)):
            start = (cx + side * s * 0.3, cy + dy * s)
            knee = (cx + side * s * 0.75, cy + dy * s - s * 0.2 + i * s * 0.12)
            foot = (cx + side * s * 0.95, cy + dy * s + s * 0.25)
            pygame.draw.lines(surface, color, False, [start, knee, foot], max(2, int(s * 0.08)))
        pygame.draw.lines(surface, color, False, [(cx + side * s * 0.1, cy - s * 0.85),
                                                 (cx + side * s * 0.35, cy - s * 1.25),
                                                 (cx + side * s * 0.7, cy - s * 1.4)], max(2, int(s * 0.06)))
    pygame.draw.ellipse(surface, color, (cx - s * 0.42, cy - s * 0.55, s * 0.84, s * 1.45))
    pygame.draw.ellipse(surface, color, (cx - s * 0.32, cy - s * 0.92, s * 0.64, s * 0.5))


def scaled_card(card, scale, back=False):
    w, h = int(CARD_W * scale), int(CARD_H * scale)
    return card_back(w, h) if back else card_face(card, w, h)


# Fighter -----------------------------------------------------------------

def _bezier(p0, p1, p2, steps=14):
    points = []
    for i in range(steps + 1):
        t = i / steps
        points.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                       (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    return points


def roach_surface(accent, t, scale=1.0, walking=1.0):
    """Side view of a cockroach facing right, with a bandana in its colour."""
    w, h = int(250 * scale), int(150 * scale)
    W, H = w * SS, h * SS
    s = scale * SS
    big = pygame.Surface((W, H), pygame.SRCALPHA)
    leg = (52, 30, 16)
    body = (104, 56, 26)
    cx, cy = W * 0.46, H * 0.5

    # Far-side legs first, then body, then near-side legs on top.
    def legs(phase_shift, color, width):
        for i, base_x in enumerate((-22, 6, 30)):
            swing = math.sin(t * 9 * walking + i * 2.1 + phase_shift) * 7 * walking
            hip = (cx + base_x * s, cy + 14 * s)
            knee = (hip[0] + (-26 + i * 20 + swing) * s, hip[1] + 14 * s - abs(swing) * 0.4 * s)
            foot = (knee[0] + (-14 + i * 12 + swing * 0.5) * s, cy + 46 * s)
            pygame.draw.lines(big, color, False, [hip, knee, foot], int(5 * s))
            pygame.draw.circle(big, color, knee, 3 * s)

    legs(math.pi, darken(leg, 0.3), 4)

    # Rear cerci.
    for dy in (-3, 4):
        pygame.draw.line(big, leg, (cx - 70 * s, cy + dy * s), (cx - 88 * s, cy + (dy * 2 - 4) * s), int(3 * s))

    # Abdomen and wings with a glossy highlight.
    pygame.draw.ellipse(big, darken(body, 0.35), (cx - 78 * s, cy - 20 * s, 128 * s, 46 * s))
    pygame.draw.ellipse(big, body, (cx - 76 * s, cy - 26 * s, 124 * s, 44 * s))
    pygame.draw.ellipse(big, lighten(body, 0.18), (cx - 64 * s, cy - 23 * s, 92 * s, 16 * s))
    pygame.draw.ellipse(big, (255, 236, 210, 70), (cx - 50 * s, cy - 21 * s, 52 * s, 7 * s))
    pygame.draw.arc(big, darken(body, 0.4), (cx - 76 * s, cy - 26 * s, 124 * s, 44 * s),
                    math.radians(185), math.radians(355), int(2 * s))
    for i in range(3):
        x = cx - 50 * s + i * 22 * s
        pygame.draw.arc(big, darken(body, 0.25), (x, cy - 6 * s, 26 * s, 26 * s),
                        math.radians(200), math.radians(340), int(2 * s))

    # Pronotum shield with pale rim, then head.
    pro = pygame.Rect(cx + 30 * s, cy - 25 * s, 40 * s, 38 * s)
    pygame.draw.ellipse(big, (200, 150, 92), pro)
    pygame.draw.ellipse(big, (86, 44, 20), pro.inflate(-9 * s, -9 * s))
    head = pygame.Rect(cx + 58 * s, cy - 6 * s, 24 * s, 22 * s)
    pygame.draw.ellipse(big, (70, 38, 18), head)
    pygame.draw.circle(big, (18, 10, 6), (head.centerx + 4 * s, head.centery - 2 * s), 4.5 * s)
    pygame.draw.circle(big, (255, 255, 255), (head.centerx + 5.5 * s, head.centery - 3.5 * s), 1.6 * s)
    pygame.draw.line(big, (40, 20, 10), (head.right - 3 * s, head.bottom - 5 * s),
                     (head.right + 4 * s, head.bottom), int(3 * s))

    # Bandana: band across the shield and two fluttering tails.
    band = pygame.Rect(pro.x + 2 * s, pro.y + 7 * s, pro.w - 4 * s, 10 * s)
    pygame.draw.ellipse(big, accent, band)
    flutter = math.sin(t * 6) * 4 * s
    knot = (pro.x + 6 * s, band.centery)
    for dy in (-1, 1):
        tail = [knot, (knot[0] - 22 * s, knot[1] + dy * 6 * s + flutter),
                (knot[0] - 18 * s, knot[1] + dy * 13 * s + flutter * 1.3)]
        pygame.draw.polygon(big, darken(accent, 0.15), tail)

    # Antennae sway.
    sway = math.sin(t * 2.4) * 6 * s
    root = (head.centerx + 6 * s, head.y + 3 * s)
    for k, (reach, lift) in enumerate(((95, 58), (78, 38))):
        tip = (root[0] + reach * s, root[1] - lift * s + sway * (1 + k * 0.5))
        ctrl = (root[0] + reach * 0.35 * s, root[1] - lift * 1.3 * s)
        pygame.draw.lines(big, (60, 34, 16), False, _bezier(root, ctrl, tip), int(2.4 * s))

    legs(0, leg, 5)
    return pygame.transform.smoothscale(big, (w, h))


class Fighter:
    """Animation state for one cockroach in the arena."""

    def __init__(self, index, center, accent=None):
        self.index = index
        self.home = pygame.Vector2(center)
        self.accent = accent or PLAYER_COLORS[index]
        self.lunge = 0.0      # 0..1, towards the opponent
        self.lunge_time = -1.0
        self.hop_time = -1.0
        self.hit_time = -1.0
        self.guard_time = -1.0
        self.ko = False
        self.clock = index * 1.3

    def attack(self):
        self.lunge_time = 0.0

    def dodge(self):
        self.hop_time = 0.0

    def hit(self):
        self.hit_time = 0.0

    def guard(self):
        self.guard_time = 0.0

    def update(self, dt):
        self.clock += dt
        for name in ("lunge_time", "hop_time", "hit_time", "guard_time"):
            value = getattr(self, name)
            if value >= 0:
                value += dt
                setattr(self, name, value if value < 1.2 else -1.0)

    def draw(self, surface):
        facing = 1 if self.index == 0 else -1
        offset = pygame.Vector2(0, math.sin(self.clock * 2.2) * 2.5)
        walking = 0.35
        if self.lunge_time >= 0:
            t = self.lunge_time
            push = math.sin(min(1.0, t / 0.45) * math.pi)
            offset.x += facing * 120 * push
            walking = 1.6
        if self.hop_time >= 0:
            t = min(1.0, self.hop_time / 0.5)
            offset.x -= facing * 50 * math.sin(t * math.pi)
            offset.y -= 40 * math.sin(t * math.pi)
        if self.hit_time >= 0 and self.hit_time < 0.4:
            offset.x += math.sin(self.hit_time * 70) * 8 * (1 - self.hit_time / 0.4)
        if self.ko:
            walking = 1.2

        # Coloured floor glow and shadow.
        floor = pygame.Rect(0, 0, 210, 34)
        floor.center = (self.home.x + offset.x * 0.6, self.home.y + 58)
        glow = pygame.Surface((floor.w + 80, floor.h + 40), pygame.SRCALPHA)
        for i in range(8):
            pygame.draw.ellipse(glow, (*self.accent, 10), glow.get_rect().inflate(-i * 12, -i * 5))
        surface.blit(glow, glow.get_rect(center=floor.center))
        dark = pygame.Surface(floor.size, pygame.SRCALPHA)
        pygame.draw.ellipse(dark, (0, 0, 0, 110), dark.get_rect())
        surface.blit(dark, floor)

        image = roach_surface(self.accent, self.clock, 1.0, walking)
        if facing < 0:
            image = pygame.transform.flip(image, True, False)
        if self.ko:
            image = pygame.transform.flip(image, False, True)
            offset.y += 22
        if self.hit_time >= 0 and self.hit_time < 0.35:
            flash = image.copy()
            flash.fill((255, 70, 50, 0), special_flags=pygame.BLEND_RGBA_MAX)
            flash.set_alpha(int(170 * (1 - self.hit_time / 0.35)))
            image = image.copy()
            image.blit(flash, (0, 0))
        rect = image.get_rect(center=self.home + offset)
        surface.blit(image, rect)

        if self.guard_time >= 0 and self.guard_time < 0.8:
            t = self.guard_time / 0.8
            ring = pygame.Surface((220, 220), pygame.SRCALPHA)
            alpha = int(200 * (1 - t))
            radius = 70 + 30 * ease_out(t)
            start = -60 if facing > 0 else 120
            pygame.draw.arc(ring, (*BLUE, alpha), ring.get_rect().inflate(-(220 - radius * 2), -(220 - radius * 2)),
                            math.radians(start), math.radians(start + 120), 7)
            surface.blit(ring, ring.get_rect(center=(rect.centerx + facing * 40, rect.centery)))


# Widgets -----------------------------------------------------------------

class Button:
    STYLES = {
        "primary": ((247, 172, 48), (255, 196, 92), (40, 24, 6)),
        "secondary": ((70, 54, 42), (92, 72, 56), TEXT),
        "ghost": ((255, 255, 255, 12), (255, 255, 255, 30), TEXT_DIM),
        "danger": ((200, 64, 56), (226, 88, 78), TEXT),
    }

    def __init__(self, rect, label, style="secondary", hint=None, size=17):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.style = style
        self.hint = hint
        self.size = size
        self.enabled = True
        self.visible = True
        self.hover = 0.0
        self.pressed = False

    def handle(self, event):
        """Return True when the button was clicked."""
        if not (self.visible and self.enabled):
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self.pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            clicked = self.pressed and self.rect.collidepoint(event.pos)
            self.pressed = False
            return clicked
        return False

    def update(self, dt, mouse):
        target = 1.0 if self.visible and self.enabled and self.rect.collidepoint(mouse) else 0.0
        self.hover += (target - self.hover) * min(1.0, dt * 14)

    def draw(self, surface):
        if not self.visible:
            return
        base, hover, text_color = self.STYLES[self.style]
        if len(base) == 3:
            fill = mix(base, hover, self.hover) if self.enabled else mix(base, (60, 52, 46), 0.75)
        else:
            fill = tuple(int(base[i] + (hover[i] - base[i]) * self.hover) for i in range(4))
        rect = self.rect.move(0, 2 if self.pressed else 0)
        if self.style in ("primary", "danger") and self.enabled:
            blit_shadow(surface, rect, rect.h // 2, 8, 90, (0, 5))
        border = lighten(fill[:3], 0.25) if len(fill) == 3 else (255, 255, 255, 40)
        surface.blit(rounded(rect.w, rect.h, min(14, rect.h // 2), fill, border, 1), rect)
        color = text_color if self.enabled else TEXT_MUTED
        if self.hint:
            label_rect = draw_text(surface, self.label, (rect.centerx - 14, rect.centery), self.size,
                                   color, True, "center")
            hint_image = font(12, True).render(self.hint, True, color)
            hint_rect = hint_image.get_rect(midleft=(label_rect.right + 10, rect.centery)).inflate(10, 4)
            surface.blit(rounded(hint_rect.w, hint_rect.h, 5, (0, 0, 0, 50)), hint_rect)
            surface.blit(hint_image, hint_image.get_rect(center=hint_rect.center))
        else:
            draw_text(surface, self.label, rect.center, self.size, color, True, "center")


class TextField:
    """A one-line text box for addresses and port numbers."""

    def __init__(self, rect, label, value, allowed, max_length):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.value = value
        self.allowed = allowed
        self.max_length = max_length
        self.focused = False

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
        elif self.focused and event.type == pygame.TEXTINPUT:
            for ch in event.text:
                if ch in self.allowed and len(self.value) < self.max_length:
                    self.value += ch
        elif self.focused and event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE:
            self.value = self.value[:-1]

    def draw(self, surface, clock):
        draw_text(surface, self.label, (self.rect.x + 4, self.rect.y - 24), 13, TEXT_MUTED, True)
        border = (*AMBER, 220) if self.focused else (255, 255, 255, 50)
        surface.blit(rounded(self.rect.w, self.rect.h, 12, (0, 0, 0, 90), border, 2 if self.focused else 1),
                     self.rect)
        text_rect = draw_text(surface, self.value, (self.rect.x + 18, self.rect.centery), 22, TEXT, True, "midleft")
        if self.focused and int(clock * 2) % 2 == 0:
            x = text_rect.right + 3 if self.value else self.rect.x + 18
            pygame.draw.line(surface, AMBER, (x, self.rect.y + 14), (x, self.rect.bottom - 14), 2)


def hp_bar(surface, rect, hp, ghost_hp, max_hp, color):
    surface.blit(rounded(rect.w, rect.h, rect.h // 2, (0, 0, 0, 120), (255, 255, 255, 30), 1), rect)
    inner = rect.inflate(-6, -6)
    ghost_w = int(inner.w * max(0, ghost_hp) / max_hp)
    if ghost_w > inner.h:
        surface.blit(rounded(ghost_w, inner.h, inner.h // 2, (255, 236, 210)), inner.topleft)
    fill_w = int(inner.w * max(0, hp) / max_hp)
    if fill_w > inner.h:
        ratio = hp / max_hp
        bar_color = GREEN if ratio > 0.5 else AMBER if ratio > 0.25 else RED
        bar = gradient(fill_w, inner.h, lighten(bar_color, 0.25), darken(bar_color, 0.15)).convert_alpha()
        mask = rounded(fill_w, inner.h, inner.h // 2, (255, 255, 255, 255))
        bar.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(bar, inner.topleft)
        sheen = rounded(max(1, fill_w - 8), max(1, inner.h // 3), inner.h // 6, (255, 255, 255, 50))
        surface.blit(sheen, (inner.x + 4, inner.y + 2))


def ap_pips(surface, pos, ap, max_ap, anchor_right=False):
    x, y = pos
    step = 22
    if anchor_right:
        x -= step * (max_ap - 1)
    for i in range(max_ap):
        center = (x + i * step, y)
        points = [(center[0], center[1] - 8), (center[0] + 8, center[1]),
                  (center[0], center[1] + 8), (center[0] - 8, center[1])]
        big = pygame.Surface((40, 40), pygame.SRCALPHA)
        local = [(px - center[0] + 10, py - center[1] + 10) for px, py in points]
        local = [(px * SS, py * SS) for px, py in local]
        if i < ap:
            pygame.draw.polygon(big, AMBER, local)
            pygame.draw.polygon(big, (255, 226, 150), [local[0], local[1], local[3]])
        else:
            pygame.draw.polygon(big, (255, 255, 255, 50), local, 2 * SS)
        small = pygame.transform.smoothscale(big, (20, 20))
        surface.blit(small, (center[0] - 10, center[1] - 10))
