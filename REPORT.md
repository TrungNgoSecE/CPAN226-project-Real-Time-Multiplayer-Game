# Real-Time Multiplayer Tic-Tac-Toe Report

## Introduction

This project implements a real-time multiplayer Tic-Tac-Toe game using Python and TCP socket programming. The main objective of the project is to demonstrate how two remote players can join the same game session, exchange moves through a server, and remain synchronized throughout the match. The project focuses on the networking concepts of client-server communication, state synchronization, matchmaking, turn validation, and basic fault handling.

Unlike a local Tic-Tac-Toe game where both players share the same device, this implementation uses a server-authoritative model. In this model, the server is responsible for maintaining the official game state and making all decisions about whether a move is valid. This design is useful in multiplayer networking because it prevents clients from directly controlling the game state and helps keep both players consistent even if messages arrive at different times.

The system is implemented with Python's standard library only, which keeps the project simple and suitable for academic purposes. No external frameworks are required. The final result is a console-based multiplayer application where two players can connect to the server, enter their names, get paired automatically, and play multiple rounds of Tic-Tac-Toe over the network.

## System Design

The project is divided into three main files: `server.py`, `client.py`, and `protocol.py`. Each file has a specific responsibility that supports the overall architecture of the system.

The `server.py` file acts as the core of the application. It starts a TCP server, listens for incoming connections, accepts players, and manages active matches. The server stores the waiting players in a queue and automatically pairs the first two available clients into a game. Once a match begins, the server assigns symbols `X` and `O`, creates a fresh 3x3 board, and controls whose turn it is. Every move sent by a client is checked on the server side before the board is updated. This ensures that illegal moves, such as choosing an occupied square or moving out of turn, are rejected.

The `client.py` file provides the user-facing side of the application. It connects to the server, asks the user for a player name, and then waits for server instructions. The client uses a simple console interface to display the board and allow the player to enter moves from `1` to `9`. A receiver thread continuously listens for server messages while the main input loop handles user actions. This approach allows the client to react to real-time updates without blocking all communication.

The `protocol.py` file defines the communication format shared by both the server and client. Messages are newline-delimited, and payload data is encoded as JSON after a `|` separator. For example, a move can be sent as `MOVE|{"cell":5}`. This design makes the protocol readable, easy to debug, and easy to extend in the future. The protocol layer also validates whether received payloads are properly formatted JSON objects.

## Functional Workflow

The workflow begins when the server is started and begins listening on a configurable host and port. Players then launch the client application in separate terminals and connect to the server. Each player enters a name, and the client sends a `HELLO` command containing that name. After registration, the server places the client in the waiting queue.

When two players are available, the server creates a match and informs both clients that a game has started. One player is assigned symbol `X` and the other symbol `O`. The server sends the initial board state and notifies player `X` to make the first move. From this point forward, the entire game is controlled by the server.

Whenever a player chooses a cell, the client sends a `MOVE` message to the server. The server verifies that the player is in an active match, confirms that it is the correct player's turn, checks that the cell number is valid, and ensures that the target square is empty. If the move is valid, the server updates the board and broadcasts the new state to both players. It then either prompts the next turn or ends the game if a win or draw has occurred.

At the end of a game, the server sends a `RESULT` message followed by a `PLAY_AGAIN` prompt. Both players may choose whether to replay. If both players accept, the board is reset and a new round begins. If one or both decline, the match ends. This replay logic makes the project more interactive and demonstrates how a server can manage a simple game lifecycle beyond just one round.

## Networking and State Synchronization

The most important networking feature in this project is state synchronization. In multiplayer systems, synchronization means that all participants should have the same understanding of the current game state. In this implementation, synchronization is achieved by making the server the single source of truth.

After every accepted move, the server sends the full board state to both clients using the `STATE` command. Instead of relying on clients to update the board independently, the server broadcasts the complete state so that both clients remain aligned. This reduces the risk of desynchronization and makes the logic simpler and safer.

TCP was chosen as the communication protocol because Tic-Tac-Toe is a turn-based game and does not require extremely low-latency message delivery. TCP guarantees ordered and reliable data transmission, which is appropriate for this kind of application. Using TCP also avoids the additional complexity of packet loss handling, reordering, and reliability mechanisms that would be needed in a UDP-based design.

The project also includes basic synchronization support for replay and disconnect events. Replay requires both players to vote before a new round begins. If a player disconnects during matchmaking or gameplay, the server handles the session cleanup and informs the remaining client. The remaining player is then returned to the waiting queue to be matched again. This behavior keeps the system stable and demonstrates practical session management in a multiplayer environment.

## Validation and Error Handling

A good networked application must be able to reject invalid input and recover from common runtime issues. This project includes several examples of such validation.

First, the server ensures that a client sends `HELLO` before performing any other action. Second, the `MOVE` command is checked carefully so that only integer cell values from `1` to `9` are accepted. Third, the server verifies that the requested board position is not already occupied. If any rule is violated, the server responds with an `INVALID` message rather than corrupting the board state.

The protocol layer also protects the program from malformed messages. If a payload is not valid JSON or is not in the expected object format, a protocol error is raised and the server can notify the client that the message was invalid. This shows how structured communication rules improve robustness.

The client also includes input validation. During gameplay it only accepts numeric moves, and during replay it only accepts `yes` or `no`. These checks reduce the number of bad requests sent to the server and improve the user experience.

## Strengths and Limitations

One strength of the project is its clean separation of responsibilities. The server manages game logic, the client handles presentation and user input, and the protocol file manages message formatting. This modular structure makes the program easier to understand, maintain, and extend.

Another strength is that the project demonstrates several important networking ideas in a small and understandable example. These include socket communication, multiple client handling with threads, matchmaking through a queue, server-authoritative state management, and handling disconnects. For a course project, this creates a strong connection between theory and implementation.

However, the project also has limitations. The client is console-based, so user interaction is less polished than a graphical interface. The system stores matchmaking and game sessions only in memory, which means all information is lost when the server stops. In addition, the game is intended for localhost or small LAN demonstrations and is not designed for public internet deployment or large-scale concurrency.

There is also some room for improvement in user experience. Because the client is terminal-based and uses both a receiver thread and user input, messages from the server can sometimes appear while the user is typing. Although this does not break the game logic, it can make the interface look slightly messy.

## Conclusion

In conclusion, this project successfully demonstrates a real-time multiplayer game built on top of TCP networking. Even though Tic-Tac-Toe is a simple game, the implementation highlights several key topics in network programming, including client-server design, protocol definition, matchmaking, synchronization, validation, and connection handling.

The use of a server-authoritative architecture is one of the most important design choices in the system because it ensures fairness and consistency between players. The project also shows how structured message protocols and clear separation between components can make a networked application easier to build and maintain.

Overall, the project meets its objective as a course-level demonstration of multiplayer networking. It is simple enough to understand clearly, yet complex enough to illustrate real challenges in distributed game development. Future improvements could include a graphical user interface, persistent player statistics, room-based matchmaking, or support for more advanced multiplayer games.
