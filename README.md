# Real-Time Multiplayer Tic-Tac-Toe

This project is a simple console-based multiplayer Tic-Tac-Toe game built with Python's standard-library sockets. A central TCP server handles matchmaking, validates moves, owns the board state, and keeps both players synchronized.

## Project Files

- `server.py`: matchmaking server and game-state authority
- `client.py`: console client for players
- `protocol.py`: shared message encoding and decoding helpers

## Requirements

- Python 3.10+ recommended
- No external dependencies

## How To Run

Open one terminal for the server:

```powershell
python server.py
```

Open two more terminals for players:

```powershell
python client.py
```

You can also customize the host or port:

```powershell
python server.py --host 127.0.0.1 --port 5001
python client.py --host 127.0.0.1 --port 5001
```

## Local Demo Flow

1. Start the server.
2. Start the first client and enter a player name.
3. Start the second client and enter a player name.
4. The server automatically matches the two players.
5. Player X goes first and chooses a board cell from `1` to `9`.
6. After every valid move, both clients receive the updated board.
7. When the match ends, both players can type `yes` or `no` to replay.

## Protocol Summary

Messages are newline-delimited. Each message starts with a command name. When extra data is needed, it is sent as a JSON payload after `|`.

Client commands:

- `HELLO|{"name":"Alice"}`
- `MOVE|{"cell":5}`
- `REPLAY|{"decision":"yes"}`
- `QUIT`

Server commands:

- `WELCOME`
- `WAIT`
- `MATCH_FOUND`
- `STATE`
- `YOUR_TURN`
- `INVALID`
- `RESULT`
- `OPPONENT_LEFT`
- `PLAY_AGAIN`
- `GOODBYE`

## Known Limitations

- The client is terminal-based, so server messages can appear while a prompt is visible.
- Matchmaking is in-memory only and resets when the server stops.
- Replay keeps the same two players and symbols only if both accept immediately.
- The project is designed for localhost or small LAN demos rather than public internet deployment.
