"""Shared protocol helpers for the multiplayer Tic-Tac-Toe project."""

from __future__ import annotations

import json
from typing import Any

CLIENT_COMMANDS = {"HELLO", "MOVE", "REPLAY", "QUIT"}
SERVER_COMMANDS = {
    "WELCOME",
    "WAIT",
    "MATCH_FOUND",
    "STATE",
    "YOUR_TURN",
    "INVALID",
    "RESULT",
    "OPPONENT_LEFT",
    "PLAY_AGAIN",
    "GOODBYE",
}


class ProtocolError(ValueError):
    """Raised when a message cannot be parsed."""


def encode_message(command: str, **payload: Any) -> bytes:
    """Encode a protocol message as a newline-delimited UTF-8 frame."""
    message = command
    if payload:
        message = f"{command}|{json.dumps(payload, separators=(',', ':'))}"
    return (message + "\n").encode("utf-8")


def decode_message(raw_line: str) -> tuple[str, dict[str, Any]]:
    """Decode a protocol line into a command and payload dictionary."""
    line = raw_line.strip()
    if not line:
        raise ProtocolError("Empty protocol message.")

    if "|" not in line:
        return line, {}

    command, payload_text = line.split("|", 1)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise ProtocolError("Invalid JSON payload.") from exc

    if not isinstance(payload, dict):
        raise ProtocolError("Protocol payload must be a JSON object.")

    return command, payload


def board_to_text(board: list[str]) -> str:
    """Render a 3x3 board to a compact string for logging or debugging."""
    return "".join(cell if cell != " " else "-" for cell in board)
