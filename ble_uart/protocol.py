"""ファームウェアと共通のBLE識別子と、端末コマンドの解析処理。"""
from dataclasses import dataclass
from enum import Enum, auto

SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
DTR_UUID = "6e400004-b5a3-f393-e0a9-e50e24dcca9e"
CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"
PAYLOAD_SIZE = 20  # ATT MTUが最小の23バイトでも送れるデータ長。
NEWLINES = {"none": "", "lf": "\n", "crlf": "\r\n"}


class CommandKind(Enum):
    DATA = auto()
    DTR = auto()
    QUIT = auto()


@dataclass(frozen=True)
class Command:
    kind: CommandKind
    data: bytes = b""


def parse_command(line: str, newline: str = "crlf") -> Command:
    """入力した一行を、データ送信・DTR操作・終了のコマンドに変換する。"""
    if line == "/quit":
        return Command(CommandKind.QUIT)
    if line in ("/dtr on", "/dtr off"):
        return Command(CommandKind.DTR, bytes([line == "/dtr on"]))
    if line.startswith("/hex "):
        try:
            return Command(CommandKind.DATA, bytes.fromhex(line[5:]))
        except ValueError as exc:
            raise ValueError("HEX形式が不正です。例: /hex 01 ff 00") from exc
    return Command(CommandKind.DATA, (line + NEWLINES[newline]).encode("utf-8"))
