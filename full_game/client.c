/* IPIS Arena client: the network side of the graphical game.

   Connects to ipis_server, prints every line the server sends, and sends every
   line written to standard input. The Python GUI starts this program and talks
   to it through pipes, so all socket work stays in C. It also works on its own
   in a terminal for testing:

     ./ipis_client 127.0.0.1 5001 */

#define _POSIX_C_SOURCE 200809L
#include "socket_io.h"

#ifdef _WIN32
#error "ipis_client waits on standard input with select(), which needs Linux or macOS."
#endif

int main(int argc, char *argv[]) {
    socket_handle sock = BAD_SOCKET;
    struct sockaddr_in server_addr;
    char buffer[1024];
    int port, input_open = 1, status = 1;

    if (argc != 3 || (port = parse_port(argv[2])) < 0) {
        fprintf(stderr, "Usage: %s server_ipv4 port_number\n", argv[0]);
        return 1;
    }
    if (network_start() != 0) return 1;
    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock == BAD_SOCKET || sock >= FD_SETSIZE) goto cleanup;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons((unsigned short)port);
    if (inet_pton(AF_INET, argv[1], &server_addr.sin_addr) != 1) {
        fprintf(stderr, "Enter an IPv4 address, such as 127.0.0.1.\n");
        goto cleanup;
    }
    if (connect(sock, (struct sockaddr *)&server_addr, sizeof(server_addr)) != 0) {
        fprintf(stderr, "Could not connect to %s port %d. Check the address and that the host is running.\n",
                argv[1], port);
        goto cleanup;
    }

    // Watch the server and our input at the same time; either can speak first.
    while (1) {
        fd_set ready;
        int count;
        FD_ZERO(&ready);
        FD_SET(sock, &ready);
        if (input_open) FD_SET(STDIN_FILENO, &ready);
        if (select(sock + 1, &ready, NULL, NULL, NULL) < 0) {
            if (interrupted()) continue;
            break;
        }
        if (FD_ISSET(sock, &ready)) {
            count = (int)recv(sock, buffer, sizeof(buffer), 0);
            if (count < 0 && interrupted()) continue;
            if (count <= 0) {
                // After we asked to leave, the server closing is the normal ending.
                if (input_open) fprintf(stderr, "The server closed the connection.\n");
                else status = 0;
                break;
            }
            // Server text is already newline-terminated; pass it straight through.
            if (fwrite(buffer, 1, (size_t)count, stdout) != (size_t)count) break;
            fflush(stdout);
        }
        if (input_open && FD_ISSET(STDIN_FILENO, &ready)) {
            count = (int)read(STDIN_FILENO, buffer, sizeof(buffer) - 1);
            if (count < 0 && errno == EINTR) continue;
            if (count <= 0) {
                // The GUI closed our input: leave the match politely.
                send_text(sock, "QUIT\n");
                input_open = 0;
                continue;
            }
            buffer[count] = '\0';
            if (send_text(sock, buffer) < 0) {
                fprintf(stderr, "Could not send to the server.\n");
                break;
            }
        }
    }

cleanup:
    if (sock != BAD_SOCKET) close_socket(sock);
    network_stop();
    return status;
}
