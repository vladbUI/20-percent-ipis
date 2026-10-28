/* IPIS Arena match server.

   Runs the C combat engine (game_logic_demo/game.c) for two players who
   connect over TCP, or for one player against the computer.

     ./ipis_server 5001           two networked players
     ./ipis_server 5001 --cpu     one player against the CPU

   Port 0 lets the system choose a free port. --local accepts connections from
   this computer only. The text protocol is described in README.md. */

#define _DEFAULT_SOURCE
#include "game.h"
#include "cpu.h"
#include "socket_io.h"
#include <stdarg.h>
#include <time.h>
#ifndef _WIN32
#include <ifaddrs.h>
#endif

#define LINE_SIZE 128
#define NO_SEAT (-1)

typedef struct {
    socket_handle sock;
    char line[LINE_SIZE]; // Partial line received so far.
    int used;
    int too_long;
} Seat;

static Seat seats[2];
static int cpu_seat = NO_SEAT;
static Cpu cpu;
static Game game;
static Plan plans[2];
static int locked[2];
static int rematch[2];
static int match_started = 0;
static int match_over = 0; // Set when a player leaves a started match.

static int is_human(int p) { return p != cpu_seat; }
static int connected(int p) { return seats[p].sock != BAD_SOCKET; }

static void drop(int p) {
    if (!connected(p)) return;
    close_socket(seats[p].sock);
    seats[p].sock = BAD_SOCKET;
    printf("Player %d left.\n", p + 1);
    fflush(stdout);
    if (match_started) {
        // The other player cannot continue alone, so the session ends.
        if (is_human(1 - p) && connected(1 - p))
            send_text(seats[1 - p].sock, "OPPONENT_LEFT\n");
        match_over = 1;
    }
}

// Send one protocol line to a connected human player.
static void sendf(int p, const char *format, ...) {
    char text[512];
    va_list args;
    if (!is_human(p) || !connected(p)) return;
    va_start(args, format);
    vsnprintf(text, sizeof(text), format, args);
    va_end(args);
    if (send_text(seats[p].sock, text) < 0) drop(p);
}

// STATE round hp1 hp2 ap1 ap2 deck discard hand_count hand...
// Only the receiving player's own hand is included.
static void send_state(int p) {
    const Player *player = &game.players[p];
    char text[256];
    int length, i;
    length = snprintf(text, sizeof(text), "STATE %d %d %d %d %d %d %d %d", game.round,
                      game.players[0].hp, game.players[1].hp,
                      game.players[0].ap, game.players[1].ap,
                      player->deck_count, player->discard_count, player->hand_count);
    for (i = 0; i < player->hand_count; i++)
        length += snprintf(text + length, sizeof(text) - (size_t)length, " %d", player->hand[i]);
    sendf(p, "%s\n", text);
}

static void begin_round(void) {
    int p;
    locked[0] = locked[1] = 0;
    if (cpu_seat != NO_SEAT) {
        // The CPU decides before seeing anything from this round.
        char error[128];
        int position = cpu_choose_molt(&cpu, &game);
        if (position) game_molt(&game, cpu_seat, position, error, sizeof(error));
        cpu_choose_plan(&cpu, &game, &plans[cpu_seat]);
        if (!validate_plan(&game.players[cpu_seat], &plans[cpu_seat], error, sizeof(error))) {
            fprintf(stderr, "CPU plan rejected: %s\n", error);
            memset(&plans[cpu_seat], 0, sizeof(Plan));
        }
        locked[cpu_seat] = 1;
    }
    for (p = 0; p < 2; p++) {
        send_state(p);
        if (locked[1 - p]) sendf(p, "OPPONENT_LOCKED\n");
    }
}

static void start_match(void) {
    int p;
    game_init(&game);
    if (cpu_seat != NO_SEAT) cpu_init(&cpu, cpu_seat);
    rematch[0] = rematch[1] = 0;
    match_started = 1;
    printf("Match started.\n");
    fflush(stdout);
    for (p = 0; p < 2; p++) sendf(p, "START\n");
    begin_round();
}

// RESULT round outcome, then cards[6] damage[6] defended[6]
// hp_before[2] ap_before[2] hp[2] ap[2]. Player 1's values come first.
static void resolve_round(void) {
    RoundReport report;
    char text[512], error[128];
    int length, p, slot, round = game.round;
    if (!game_resolve(&game, plans, &report, error, sizeof(error))) {
        fprintf(stderr, "Could not resolve round: %s\n", error);
        return;
    }
    length = snprintf(text, sizeof(text), "RESULT %d %d", round, game.outcome);
    for (p = 0; p < 2; p++)
        for (slot = 0; slot < SLOTS; slot++)
            length += snprintf(text + length, sizeof(text) - (size_t)length, " %d", report.cards[p][slot]);
    for (p = 0; p < 2; p++)
        for (slot = 0; slot < SLOTS; slot++)
            length += snprintf(text + length, sizeof(text) - (size_t)length, " %d", report.damage[p][slot]);
    for (p = 0; p < 2; p++)
        for (slot = 0; slot < SLOTS; slot++)
            length += snprintf(text + length, sizeof(text) - (size_t)length, " %d", report.defended[p][slot]);
    snprintf(text + length, sizeof(text) - (size_t)length, " %d %d %d %d %d %d %d %d\n",
             report.hp_before[0], report.hp_before[1], report.ap_before[0], report.ap_before[1],
             game.players[0].hp, game.players[1].hp, game.players[0].ap, game.players[1].ap);
    printf("Round %d: P1 HP %d -> %d | P2 HP %d -> %d\n", round,
           report.hp_before[0], game.players[0].hp, report.hp_before[1], game.players[1].hp);
    for (p = 0; p < 2; p++) sendf(p, "%s", text);
    if (cpu_seat != NO_SEAT) cpu_observe(&cpu, &report);
    if (game.outcome == ONGOING) {
        begin_round();
    } else {
        printf("%s\n", game.outcome == DRAW ? "Match over: draw." :
               game.outcome == PLAYER_ONE_WINS ? "Match over: Player 1 wins." : "Match over: Player 2 wins.");
    }
    fflush(stdout);
}

// Read exactly count small non-negative numbers, each preceded by spaces.
static int parse_values(const char *text, int values[], int count) {
    int i;
    for (i = 0; i < count; i++) {
        char *end;
        long value;
        if (*text != ' ') return 0;
        while (*text == ' ') text++;
        if (*text < '0' || *text > '9') return 0;
        value = strtol(text, &end, 10);
        if (value > 99) return 0;
        values[i] = (int)value;
        text = end;
    }
    while (*text == ' ') text++;
    return *text == '\0';
}

// Returns -1 when the player asked to leave.
static int handle_line(int p, const char *line) {
    char error[128];
    int values[SLOTS], i;
    if (strcmp(line, "QUIT") == 0) return -1;
    if (strncmp(line, "PLAN", 4) == 0 || strncmp(line, "MOLT", 4) == 0) {
        int is_plan = line[0] == 'P';
        if (!match_started) { sendf(p, "ERROR The match has not started.\n"); return 0; }
        if (game.outcome != ONGOING) { sendf(p, "ERROR The match has ended.\n"); return 0; }
        if (locked[p]) { sendf(p, "ERROR Your plan is already locked for this round.\n"); return 0; }
        if (!parse_values(line + 4, values, is_plan ? SLOTS : 1)) {
            sendf(p, is_plan ? "ERROR Use PLAN followed by three hand positions.\n"
                             : "ERROR Use MOLT followed by one hand position.\n");
            return 0;
        }
        if (!is_plan) {
            if (!game_molt(&game, p, values[0], error, sizeof(error))) sendf(p, "ERROR %s\n", error);
            else send_state(p);
            return 0;
        }
        for (i = 0; i < SLOTS; i++) plans[p].picks[i] = values[i];
        if (!validate_plan(&game.players[p], &plans[p], error, sizeof(error))) {
            sendf(p, "ERROR %s\n", error);
            return 0;
        }
        locked[p] = 1;
        sendf(p, "LOCKED\n");
        sendf(1 - p, "OPPONENT_LOCKED\n");
        printf("Player %d locked a plan.\n", p + 1);
        fflush(stdout);
        if (locked[0] && locked[1]) resolve_round();
        return 0;
    }
    if (strcmp(line, "REMATCH") == 0) {
        if (!match_started || game.outcome == ONGOING) {
            sendf(p, "ERROR The match is still running.\n");
            return 0;
        }
        rematch[p] = 1;
        if (cpu_seat != NO_SEAT) rematch[cpu_seat] = 1;
        sendf(1 - p, "OPPONENT_REMATCH\n");
        if (rematch[0] && rematch[1]) start_match();
        return 0;
    }
    sendf(p, "ERROR Unknown command.\n");
    return 0;
}

// Collect bytes into lines; a player may send several lines in one packet.
static void receive_from(int p) {
    char chunk[256];
    int count = (int)recv(seats[p].sock, chunk, sizeof(chunk), 0), i;
    if (count < 0 && interrupted()) return;
    if (count <= 0) { drop(p); return; }
    for (i = 0; i < count && connected(p); i++) {
        Seat *seat = &seats[p];
        char ch = chunk[i];
        if (ch != '\n') {
            if (ch == '\0' || seat->used >= LINE_SIZE - 1) seat->too_long = 1;
            else seat->line[seat->used++] = ch;
            continue;
        }
        seat->line[seat->used] = '\0';
        if (seat->used > 0 && seat->line[seat->used - 1] == '\r') seat->line[seat->used - 1] = '\0';
        if (seat->too_long) sendf(p, "ERROR Line too long.\n");
        else if (handle_line(p, seat->line) < 0) drop(p);
        seat->used = 0;
        seat->too_long = 0;
    }
}

static void accept_player(socket_handle listener) {
    socket_handle sock = accept(listener, NULL, NULL);
    int p;
    if (sock == BAD_SOCKET) return;
#ifndef _WIN32
    // select cannot use Linux descriptors outside this range.
    if (sock >= FD_SETSIZE) { close_socket(sock); return; }
#endif
    for (p = 0; p < 2; p++)
        if (is_human(p) && !connected(p)) break;
    if (p == 2 || match_started) {
        send_text(sock, "FULL\n");
        close_socket(sock);
        return;
    }
    memset(&seats[p], 0, sizeof(Seat));
    seats[p].sock = sock;
    printf("Player %d connected.\n", p + 1);
    fflush(stdout);
    sendf(p, "WELCOME %d %s\n", p, cpu_seat == NO_SEAT ? "HUMAN" : "CPU");
    for (p = 0; p < 2; p++)
        if (is_human(p) && !connected(p)) break;
    if (p == 2) start_match();
    else sendf(1 - p, "WAITING\n");
}

static void print_addresses(int port) {
#ifndef _WIN32
    struct ifaddrs *list, *item;
    char text[INET_ADDRSTRLEN];
    if (getifaddrs(&list) != 0) return;
    for (item = list; item; item = item->ifa_next) {
        if (!item->ifa_addr || item->ifa_addr->sa_family != AF_INET) continue;
        inet_ntop(AF_INET, &((struct sockaddr_in *)item->ifa_addr)->sin_addr, text, sizeof(text));
        if (strncmp(text, "127.", 4) == 0) continue;
        printf("Join address: %s port %d\n", text, port);
    }
    freeifaddrs(list);
#else
    (void)port;
#endif
}

int main(int argc, char *argv[]) {
    socket_handle listener = BAD_SOCKET;
    struct sockaddr_in address;
#ifdef _WIN32
    int address_size = sizeof(address);
#else
    socklen_t address_size = sizeof(address);
#endif
    int port, i, local = 0, reuse = 1, status = 1;

    port = argc >= 2 && strcmp(argv[1], "0") == 0 ? 0 : argc >= 2 ? parse_port(argv[1]) : -1;
    for (i = 2; i < argc && port >= 0; i++) {
        if (strcmp(argv[i], "--cpu") == 0) cpu_seat = 1;
        else if (strcmp(argv[i], "--local") == 0) local = 1;
        else port = -1;
    }
    if (port < 0) {
        fprintf(stderr, "Usage: %s port_number [--cpu] [--local]\n", argv[0]);
        return 1;
    }
    srand((unsigned)time(NULL));
    seats[0].sock = seats[1].sock = BAD_SOCKET;
    if (network_start() != 0) return 1;
    listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener == BAD_SOCKET) goto cleanup;
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, (const char *)&reuse, sizeof(reuse));
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(local ? INADDR_LOOPBACK : INADDR_ANY);
    address.sin_port = htons((unsigned short)port);
    if (bind(listener, (struct sockaddr *)&address, sizeof(address)) != 0) {
        fprintf(stderr, "Could not use port %d. Is another server using it?\n", port);
        goto cleanup;
    }
    if (listen(listener, 4) != 0) goto cleanup;
    // With port 0 the system picked one; report the real number.
    if (getsockname(listener, (struct sockaddr *)&address, &address_size) == 0)
        port = ntohs(address.sin_port);
    printf("IPIS Arena server listening on port %d\n", port);
    printf("Mode: %s\n", cpu_seat == NO_SEAT ? "two players" : "one player vs CPU");
    if (!local) print_addresses(port);
    fflush(stdout);

    while (!match_over) {
        fd_set ready;
        int highest = (int)listener;
        FD_ZERO(&ready);
        FD_SET(listener, &ready);
        for (i = 0; i < 2; i++) {
            if (!connected(i)) continue;
            FD_SET(seats[i].sock, &ready);
            if ((int)seats[i].sock > highest) highest = (int)seats[i].sock;
        }
        if (select(highest + 1, &ready, NULL, NULL, NULL) < 0) {
            if (interrupted()) continue;
            goto cleanup;
        }
        for (i = 0; i < 2 && !match_over; i++)
            if (connected(i) && FD_ISSET(seats[i].sock, &ready)) receive_from(i);
        if (!match_over && FD_ISSET(listener, &ready)) accept_player(listener);
    }
    printf("Session ended.\n");
    status = 0;

cleanup:
    for (i = 0; i < 2; i++)
        if (connected(i)) close_socket(seats[i].sock);
    if (listener != BAD_SOCKET) close_socket(listener);
    network_stop();
    return status;
}
