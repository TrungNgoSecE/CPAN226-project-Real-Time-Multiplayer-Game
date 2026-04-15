"""Console client for the multiplayer Tic-Tac-Toe server."""

from __future__ import annotations

import argparse
import socket
import threading

from protocol import ProtocolError, decode_message, encode_message


class ClientState:
    def __init__(self) -> None:
        self.connected = True
        self.name = ""
        self.symbol = ""
        self.opponent = ""
        self.board = [" "] * 9
        self.my_turn = False
        self.awaiting_replay = False
        self.lock = threading.Lock()


def render_board(board: list[str]) -> str:
    cells = [cell if cell != " " else str(index + 1) for index, cell in enumerate(board)]
    rows = [
        f" {cells[0]} | {cells[1]} | {cells[2]} ",
        f" {cells[3]} | {cells[4]} | {cells[5]} ",
        f" {cells[6]} | {cells[7]} | {cells[8]} ",
    ]
    return "\n---+---+---\n".join(rows)


def receiver_loop(sock: socket.socket, state: ClientState) -> None:
    buffer = ""

    try:
        while state.connected:
            data = sock.recv(4096)
            if not data:
                break

            buffer += data.decode("utf-8")
            while "\n" in buffer:
                raw_line, buffer = buffer.split("\n", 1)
                if not raw_line.strip():
                    continue

                try:
                    command, payload = decode_message(raw_line)
                except ProtocolError as exc:
                    print(f"\nProtocol error from server: {exc}")
                    continue

                handle_server_message(command, payload, state)
    except (ConnectionResetError, OSError):
        pass
    finally:
        with state.lock:
            state.connected = False
            state.my_turn = False
            state.awaiting_replay = False
        print("\nDisconnected from server.")


def handle_server_message(command: str, payload: dict[str, object], state: ClientState) -> None:
    message = str(payload.get("message", "")).strip()

    if command == "WELCOME":
        print(f"\n{message}")
    elif command == "WAIT":
        print(f"\n{message}")
    elif command == "MATCH_FOUND":
        with state.lock:
            state.symbol = str(payload.get("symbol", ""))
            state.opponent = str(payload.get("opponent", ""))
            state.my_turn = False
            state.awaiting_replay = False
        print(f"\nMatch found against {state.opponent}. You are {state.symbol}.")
        if message:
            print(message)
    elif command == "STATE":
        board = payload.get("board", state.board)
        if isinstance(board, list) and len(board) == 9:
            with state.lock:
                state.board = [str(cell) for cell in board]
        print("\nCurrent board:")
        print(render_board(state.board))
        if message:
            print(message)
    elif command == "YOUR_TURN":
        with state.lock:
            state.my_turn = True
            state.awaiting_replay = False
        print(f"\n{message}")
    elif command == "INVALID":
        print(f"\nInvalid action: {message}")
    elif command == "RESULT":
        with state.lock:
            state.my_turn = False
        print(f"\nResult: {message}")
    elif command == "PLAY_AGAIN":
        with state.lock:
            state.my_turn = False
            state.awaiting_replay = True
        print(f"\n{message}")
    elif command == "OPPONENT_LEFT":
        with state.lock:
            state.my_turn = False
            state.awaiting_replay = False
            state.symbol = ""
            state.opponent = ""
            state.board = [" "] * 9
        print(f"\n{message}")
    elif command == "GOODBYE":
        print(f"\n{message}")
        with state.lock:
            state.connected = False
            state.my_turn = False
            state.awaiting_replay = False
    else:
        print(f"\nUnknown server message: {command} {payload}")


def input_loop(sock: socket.socket, state: ClientState) -> None:
    while True:
        with state.lock:
            connected = state.connected
            my_turn = state.my_turn
            awaiting_replay = state.awaiting_replay

        if not connected:
            break

        try:
            if awaiting_replay:
                decision = input("Replay? Enter yes or no: ").strip().lower()
                if decision not in {"yes", "no"}:
                    print("Please type yes or no.")
                    continue
                with state.lock:
                    state.awaiting_replay = False
                sock.sendall(encode_message("REPLAY", decision=decision))
                continue

            if my_turn:
                move_text = input("Choose a cell (1-9) or type quit: ").strip().lower()
                if move_text == "quit":
                    sock.sendall(encode_message("QUIT"))
                    break
                if not move_text.isdigit():
                    print("Enter a number from 1 to 9.")
                    continue
                cell = int(move_text)
                with state.lock:
                    state.my_turn = False
                sock.sendall(encode_message("MOVE", cell=cell))
                continue

            idle_command = input("Type quit to exit, or press Enter to keep waiting: ").strip().lower()
            if idle_command == "quit":
                sock.sendall(encode_message("QUIT"))
                break
        except (EOFError, KeyboardInterrupt):
            try:
                sock.sendall(encode_message("QUIT"))
            except OSError:
                pass
            break
        except OSError:
            break


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Tic-Tac-Toe client.")
    parser.add_argument("--host", default="127.0.0.1", help="Server host/IP.")
    parser.add_argument("--port", type=int, default=5001, help="Server TCP port.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = ClientState()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((args.host, args.port))

    receiver = threading.Thread(target=receiver_loop, args=(sock, state), daemon=True)
    receiver.start()

    name = ""
    while not name:
        name = input("Enter your player name: ").strip()
        if not name:
            print("Name cannot be empty.")

    state.name = name
    sock.sendall(encode_message("HELLO", name=name))

    input_loop(sock, state)

    with state.lock:
        state.connected = False

    try:
        sock.close()
    except OSError:
        pass

    receiver.join(timeout=1.0)


if __name__ == "__main__":
    main()
