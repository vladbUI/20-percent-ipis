CC = gcc
CFLAGS = -std=c11 -Wall -Wextra -Wpedantic -I../game_logic_demo -I..
ENGINE = ../game_logic_demo/game.c ../game_logic_demo/game.h

all: ipis_server ipis_client

ipis_server: server.c cpu.c cpu.h ../socket_io.h $(ENGINE)
	$(CC) $(CFLAGS) server.c cpu.c ../game_logic_demo/game.c -o ipis_server -lm

ipis_client: client.c ../socket_io.h
	$(CC) $(CFLAGS) client.c -o ipis_client

test: all
	python3 -m unittest test_network.py

clean:
	rm -f ipis_server ipis_client

.PHONY: all test clean
