#ifndef IPIS_CPU_H
#define IPIS_CPU_H

#include "game.h"

#define CARD_KINDS (ULTI_KAGAT + 1) /* Card ids 0..5, including EMPTY. */

/* Computer opponent. It never looks at the other player's hand or plan: it
   uses its own hand, both HP/AP values and the cards the other player has
   revealed in earlier rounds. */
typedef struct {
    int index;                  /* Seat the CPU plays: 0 or 1. */
    double seen[CARD_KINDS];    /* Smoothed counts of the opponent's cards. */
    /* One slot of combat, CPU card vs opponent card: [0] = CPU, [1] = foe. */
    int damage[CARD_KINDS][CARD_KINDS][2];
    int defended[CARD_KINDS][CARD_KINDS][2];
} Cpu;

void cpu_init(Cpu *cpu, int index);
void cpu_observe(Cpu *cpu, const RoundReport *report);
/* Returns a hand position (1..5) to Molt, or 0 to keep the hand. */
int cpu_choose_molt(const Cpu *cpu, const Game *game);
void cpu_choose_plan(const Cpu *cpu, const Game *game, Plan *plan);

#endif
