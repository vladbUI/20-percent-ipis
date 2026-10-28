"""What the GUI needs to draw cards and numbers.

This is display data only. The rules run in C (game_logic_demo/game.c inside
ipis_server), which checks every plan. The ids must match enum Card in game.h.
"""

EMPTY, KAGAT, LAYOG_KAGAT, SAGANG, DULAG_SAPAK, ULTI_KAGAT = range(6)
CARD_TYPES = (KAGAT, LAYOG_KAGAT, SAGANG, DULAG_SAPAK, ULTI_KAGAT)

# Same order as enum Outcome in game.h.
ONGOING, PLAYER_ONE_WINS, PLAYER_TWO_WINS, DRAW = range(4)

# Printed on screen; the server enforces the real limits.
START_HP = 50
ROUND_ENERGY = 4
SLOTS = 3
MAX_AP = 2
MOLT_COST = 2

CARD_NAMES = {
    EMPTY: "Empty",
    KAGAT: "Kagat",
    LAYOG_KAGAT: "Layog+Kagat",
    SAGANG: "Sagang",
    DULAG_SAPAK: "Dulag sabay sapak",
    ULTI_KAGAT: "Ulti kagat",
}

CARD_EFFECTS = {
    KAGAT: "5 damage. Cannot be dodged.",
    LAYOG_KAGAT: "10 damage. Can be blocked or dodged.",
    SAGANG: "Blocks Kagat and Layog+Kagat.",
    DULAG_SAPAK: "Dodges Layog+Kagat and counters for 5.",
    ULTI_KAGAT: "5 damage through any defense.",
}

CARD_COSTS = {KAGAT: 1, LAYOG_KAGAT: 2, SAGANG: 1, DULAG_SAPAK: 1, ULTI_KAGAT: 2}


def card_cost(card):
    return CARD_COSTS.get(card, 0)
