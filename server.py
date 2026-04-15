"""Server-authoritative multiplayer Tic-Tac-Toe over TCP."""

from __future__ import annotations

import argparse
import socket
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from protocol import ProtocolError, board_to_text, decode_message, encode_message

WIN_COMBINATIONS = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)


@dataclass(eq=False)
class ClientSession:
    sock: socket.socket
    address: tuple[str, int]
    server: "GameServer"
    name: Optional[str] = None
    symbol: Optional[str] = None
    match: Optional["GameMatch"] = None
    connected: bool = True
    send_lock: threading.Lock = field(default_factory=threading.Lock)

    def send(self, command: str, **payload: object) -> None:
        with self.send_lock:
            self.sock.sendall(encode_message(command, **payload))

    def label(self) -> str:
        if self.name:
            return f"{self.name}@{self.address[0]}:{self.address[1]}"
        return f"{self.address[0]}:{self.address[1]}"


@dataclass(eq=False)
class GameMatch:
    player_x: ClientSession
    player_o: ClientSession
    board: list[str] = field(default_factory=lambda: [" "] * 9)
    current_symbol: str = "X"
    status: str = "active"
    replay_votes: dict[ClientSession, bool] = field(default_factory=dict)

    def other_player(self, session: ClientSession) -> ClientSession:
        if session is self.player_x:
            return self.player_o
        return self.player_x

    def symbol_for(self, session: ClientSession) -> str:
        return "X" if session is self.player_x else "O"

    def player_for_symbol(self, symbol: str) -> ClientSession:
        return self.player_x if symbol == "X" else self.player_o

    def reset(self) -> None:
        self.board = [" "] * 9
        self.current_symbol = "X"
        self.status = "active"
        self.replay_votes.clear()


class GameServer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.lock = threading.RLock()
        self.waiting_players: deque[ClientSession] = deque()
        self.active_matches: list[GameMatch] = []

    def start(self) -> None:
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Server listening on {self.host}:{self.port}")

        try:
            while True:
                client_socket, address = self.server_socket.accept()
                session = ClientSession(client_socket, address, self)
                threading.Thread(
                    target=self.handle_client,
                    args=(session,),
                    daemon=True,
                ).start()
        except KeyboardInterrupt:
            print("\nServer shutting down.")
        finally:
            self.server_socket.close()

    def handle_client(self, session: ClientSession) -> None:
        print(f"Client connected: {session.label()}")
        session.sock.settimeout(1.0)

        try:
            session.send("WELCOME", message="Connected to multiplayer Tic-Tac-Toe.")
            buffer = ""

            while session.connected:
                try:
                    data = session.sock.recv(4096)
                except socket.timeout:
                    continue

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
                        session.send("INVALID", message=str(exc))
                        continue
                    self.process_command(session, command, payload)
        except (ConnectionResetError, OSError):
            pass
        finally:
            self.disconnect(session)

    def process_command(
        self,
        session: ClientSession,
        command: str,
        payload: dict[str, object],
    ) -> None:
        if command == "HELLO":
            self.handle_hello(session, payload)
            return

        if session.name is None:
            session.send("INVALID", message="Send HELLO before any other command.")
            return

        if command == "MOVE":
            self.handle_move(session, payload)
        elif command == "REPLAY":
            self.handle_replay(session, payload)
        elif command == "QUIT":
            self.send_goodbye_and_disconnect(session, "You left the game.")
        else:
            session.send("INVALID", message=f"Unknown command: {command}")

    def handle_hello(self, session: ClientSession, payload: dict[str, object]) -> None:
        if session.name is not None:
            session.send("INVALID", message="HELLO has already been sent.")
            return

        name = str(payload.get("name", "")).strip()
        if not name:
            session.send("INVALID", message="Player name cannot be empty.")
            return

        session.name = name
        session.send("WAIT", message="Waiting for an opponent...")
        print(f"Player registered: {session.label()}")

        with self.lock:
            self.waiting_players.append(session)
            self.try_start_match()

    def try_start_match(self) -> None:
        while len(self.waiting_players) >= 2:
            player_x = self.waiting_players.popleft()
            player_o = self.waiting_players.popleft()

            if not player_x.connected or not player_o.connected:
                if player_x.connected:
                    self.waiting_players.appendleft(player_x)
                if player_o.connected:
                    self.waiting_players.appendleft(player_o)
                return

            match = GameMatch(player_x=player_x, player_o=player_o)
            self.active_matches.append(match)
            player_x.match = match
            player_o.match = match
            player_x.symbol = "X"
            player_o.symbol = "O"

            print(
                "Match started: "
                f"{player_x.name} (X) vs {player_o.name} (O)"
            )
            self.send_match_start(match)

    def send_match_start(self, match: GameMatch) -> None:
        x_name = match.player_x.name or "Player X"
        o_name = match.player_o.name or "Player O"

        match.player_x.send(
            "MATCH_FOUND",
            symbol="X",
            opponent=o_name,
            message=f"You are X. {o_name} is O.",
        )
        match.player_o.send(
            "MATCH_FOUND",
            symbol="O",
            opponent=x_name,
            message=f"You are O. {x_name} is X.",
        )
        self.broadcast_state(match, message=f"{x_name} goes first.")
        self.prompt_current_turn(match)

    def broadcast_state(self, match: GameMatch, message: str = "") -> None:
        payload = {
            "board": match.board,
            "next_turn": match.current_symbol,
            "status": match.status,
            "message": message,
            "board_text": board_to_text(match.board),
        }
        match.player_x.send("STATE", **payload)
        match.player_o.send("STATE", **payload)

    def prompt_current_turn(self, match: GameMatch) -> None:
        current_player = match.player_for_symbol(match.current_symbol)
        current_player.send(
            "YOUR_TURN",
            symbol=match.current_symbol,
            message="It is your turn. Choose a cell from 1 to 9.",
        )

    def handle_move(self, session: ClientSession, payload: dict[str, object]) -> None:
        with self.lock:
            match = session.match
            if match is None or match.status != "active":
                session.send("INVALID", message="You are not currently in an active match.")
                return

            if match.player_for_symbol(match.current_symbol) is not session:
                session.send("INVALID", message="It is not your turn yet.")
                return

            cell = payload.get("cell")
            if not isinstance(cell, int):
                session.send("INVALID", message="MOVE requires an integer cell from 1 to 9.")
                self.prompt_current_turn(match)
                return

            index = cell - 1
            if index < 0 or index >= 9:
                session.send("INVALID", message="Cell must be between 1 and 9.")
                self.prompt_current_turn(match)
                return

            if match.board[index] != " ":
                session.send("INVALID", message="That cell is already occupied.")
                self.prompt_current_turn(match)
                return

            symbol = match.symbol_for(session)
            match.board[index] = symbol
            print(f"{session.name} placed {symbol} at cell {cell}")

            winner = self.check_winner(match.board)
            if winner:
                match.status = "finished"
                self.broadcast_state(match, message=f"{session.name} played cell {cell}.")
                self.send_result(
                    match,
                    winner_symbol=winner,
                    reason=f"{session.name} wins!",
                )
                return

            if " " not in match.board:
                match.status = "finished"
                self.broadcast_state(match, message=f"{session.name} played cell {cell}.")
                self.send_result(match, winner_symbol=None, reason="The game is a draw.")
                return

            match.current_symbol = "O" if match.current_symbol == "X" else "X"
            self.broadcast_state(match, message=f"{session.name} played cell {cell}.")
            self.prompt_current_turn(match)

    def send_result(
        self,
        match: GameMatch,
        winner_symbol: Optional[str],
        reason: str,
    ) -> None:
        for player in (match.player_x, match.player_o):
            outcome = "draw"
            if winner_symbol is not None:
                outcome = "win" if match.symbol_for(player) == winner_symbol else "loss"
            player.send("RESULT", outcome=outcome, message=reason)
            player.send("PLAY_AGAIN", message="Play again? Reply with REPLAY yes or REPLAY no.")

    def handle_replay(self, session: ClientSession, payload: dict[str, object]) -> None:
        with self.lock:
            match = session.match
            if match is None or match.status != "finished":
                session.send("INVALID", message="Replay is only available after a finished match.")
                return

            raw_decision = payload.get("decision")
            if not isinstance(raw_decision, str):
                session.send("INVALID", message="REPLAY requires decision='yes' or 'no'.")
                return

            decision = raw_decision.strip().lower()
            if decision not in {"yes", "no"}:
                session.send("INVALID", message="Replay decision must be 'yes' or 'no'.")
                session.send("PLAY_AGAIN", message="Play again? Reply with REPLAY yes or REPLAY no.")
                return

            match.replay_votes[session] = decision == "yes"

            if len(match.replay_votes) < 2:
                session.send("WAIT", message="Waiting for your opponent's replay choice...")
                return

            x_vote = match.replay_votes.get(match.player_x, False)
            o_vote = match.replay_votes.get(match.player_o, False)

            if x_vote and o_vote:
                match.reset()
                self.broadcast_state(match, message="Both players accepted a replay.")
                self.prompt_current_turn(match)
                return

            self.finish_match_after_replay(match)

    def finish_match_after_replay(self, match: GameMatch) -> None:
        if match in self.active_matches:
            self.active_matches.remove(match)

        for player in (match.player_x, match.player_o):
            wants_replay = match.replay_votes.get(player, False)
            player.match = None
            player.symbol = None

            if not player.connected:
                continue

            if wants_replay:
                self.waiting_players.append(player)
                player.send("WAIT", message="Looking for a new opponent...")
            else:
                self.send_goodbye_and_disconnect(player, "Thanks for playing!")

        self.try_start_match()

    def disconnect(self, session: ClientSession) -> None:
        with self.lock:
            if not session.connected:
                return

            session.connected = False
            print(f"Client disconnected: {session.label()}")

            try:
                session.sock.close()
            except OSError:
                pass

            if session in self.waiting_players:
                self.waiting_players = deque(
                    player for player in self.waiting_players if player is not session
                )

            match = session.match
            if match is None:
                return

            opponent = match.other_player(session)
            session.match = None
            session.symbol = None

            if match in self.active_matches:
                self.active_matches.remove(match)

            if opponent.connected:
                opponent.match = None
                opponent.symbol = None
                opponent.send(
                    "OPPONENT_LEFT",
                    message="Your opponent disconnected. Returning you to matchmaking.",
                )
                self.waiting_players.append(opponent)
                opponent.send("WAIT", message="Waiting for a new opponent...")

            self.try_start_match()

    def send_goodbye_and_disconnect(self, session: ClientSession, message: str) -> None:
        try:
            session.send("GOODBYE", message=message)
        except OSError:
            pass
        self.disconnect(session)

    @staticmethod
    def check_winner(board: list[str]) -> Optional[str]:
        for a, b, c in WIN_COMBINATIONS:
            if board[a] != " " and board[a] == board[b] == board[c]:
                return board[a]
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Tic-Tac-Toe matchmaking server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host/IP to bind the server to.")
    parser.add_argument("--port", type=int, default=5001, help="TCP port to listen on.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    GameServer(args.host, args.port).start()
