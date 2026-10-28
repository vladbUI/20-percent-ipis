#include "cpu.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

#define MAX_PLANS 256
#define TOP_PLANS 12

typedef struct {
    double score;
    Plan plan;
} Candidate;

/* Learn every one-slot interaction from the real engine, so the CPU can
   never disagree with game_resolve. */
void cpu_init(Cpu *cpu, int index) {
    int mine, theirs;
    memset(cpu, 0, sizeof(*cpu));
    cpu->index = index;
    for (mine = EMPTY; mine < CARD_KINDS; mine++) {
        cpu->seen[mine] = 1.0;
        for (theirs = EMPTY; theirs < CARD_KINDS; theirs++) {
            Game game;
            RoundReport report;
            Plan plans[2] = {{{0, 0, 0}}, {{0, 0, 0}}};
            char error[128];
            game_init(&game);
            if (mine) { game.players[0].hand[0] = mine; plans[0].picks[0] = 1; }
            if (theirs) { game.players[1].hand[0] = theirs; plans[1].picks[0] = 1; }
            game_resolve(&game, plans, &report, error, sizeof(error));
            cpu->damage[mine][theirs][0] = report.damage[0][0];
            cpu->damage[mine][theirs][1] = report.damage[1][0];
            cpu->defended[mine][theirs][0] = report.defended[0][0];
            cpu->defended[mine][theirs][1] = report.defended[1][0];
        }
    }
}

void cpu_observe(Cpu *cpu, const RoundReport *report) {
    int slot;
    for (slot = 0; slot < SLOTS; slot++)
        cpu->seen[report->cards[1 - cpu->index][slot]] += 1.0;
}

/* Expected value of playing one card in one slot against the opponent model. */
static double card_value(const Cpu *cpu, int card, const Player *me, const Player *foe) {
    double total = 0, value = 0;
    /* Hit harder when the opponent is close to KO; defend more when low. */
    double attack_weight = foe->hp <= 15 ? 1.6 : 1.0;
    double guard_weight = me->hp <= 15 ? 1.5 : 1.0;
    double ap_value = me->ap < MAX_AP ? 2.0 : 0.0;
    int theirs;
    for (theirs = EMPTY; theirs < CARD_KINDS; theirs++) total += cpu->seen[theirs];
    for (theirs = EMPTY; theirs < CARD_KINDS; theirs++) {
        value += cpu->seen[theirs] / total *
                 (attack_weight * cpu->damage[card][theirs][1]
                  - guard_weight * cpu->damage[card][theirs][0]
                  + ap_value * cpu->defended[card][theirs][0]);
    }
    return value;
}

int cpu_choose_molt(const Cpu *cpu, const Game *game) {
    const Player *me = &game->players[cpu->index];
    const Player *foe = &game->players[1 - cpu->index];
    double values[HAND_SIZE], sum = 0;
    int i, worst = 0;
    if (me->ap < 2 || me->hand_count == 0) return 0;
    for (i = 0; i < me->hand_count; i++) {
        values[i] = card_value(cpu, me->hand[i], me, foe);
        sum += values[i];
        if (values[i] < values[worst]) worst = i;
    }
    /* Only shed a card that is clearly weaker than the rest of the hand. */
    return values[worst] < sum / me->hand_count - 0.5 ? worst + 1 : 0;
}

static int by_score(const void *a, const void *b) {
    double left = ((const Candidate *)a)->score, right = ((const Candidate *)b)->score;
    return (left < right) - (left > right);
}

void cpu_choose_plan(const Cpu *cpu, const Game *game, Plan *plan) {
    const Player *me = &game->players[cpu->index];
    const Player *foe = &game->players[1 - cpu->index];
    Candidate candidates[MAX_PLANS];
    double values[HAND_SIZE], weights[TOP_PLANS], total = 0, roll;
    int count = 0, top, a, b, c, i;
    for (i = 0; i < me->hand_count; i++) values[i] = card_value(cpu, me->hand[i], me, foe);
    /* Every legal plan, including empty slots and passing. */
    for (a = 0; a <= me->hand_count; a++) {
        for (b = 0; b <= me->hand_count; b++) {
            for (c = 0; c <= me->hand_count; c++) {
                Plan option = {{a, b, c}};
                double score = 0;
                int slot;
                if (!validate_plan(me, &option, NULL, 0)) continue;
                for (slot = 0; slot < SLOTS; slot++) {
                    int pick = option.picks[slot];
                    if (!pick) continue;
                    /* Slight preference for using energy instead of passing. */
                    score += values[pick - 1] + 0.2 * card_cost(me->hand[pick - 1]);
                }
                candidates[count].score = score;
                candidates[count++].plan = option;
            }
        }
    }
    qsort(candidates, (size_t)count, sizeof(Candidate), by_score);
    /* Pick among the best plans, favouring higher scores, so the CPU is
       strong but not predictable. */
    top = count < TOP_PLANS ? count : TOP_PLANS;
    for (i = 0; i < top; i++) {
        weights[i] = exp((candidates[i].score - candidates[0].score) / 1.5);
        total += weights[i];
    }
    roll = (double)rand() / ((double)RAND_MAX + 1.0) * total;
    for (i = 0; i < top - 1 && roll >= weights[i]; i++) roll -= weights[i];
    *plan = candidates[i].plan;
    /* The same cards in a shuffled slot order. */
    for (i = SLOTS - 1; i > 0; i--) {
        int j = rand() % (i + 1);
        int swap = plan->picks[i];
        plan->picks[i] = plan->picks[j];
        plan->picks[j] = swap;
    }
}
