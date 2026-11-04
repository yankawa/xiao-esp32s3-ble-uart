"""BLE UART端末のコマンドライン入口。"""
import argparse
import asyncio
import math
import sys

from .client import run_session, scan_devices


def positive_seconds(value: str) -> float:
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("秒数には正の有限値を指定してください。")
    return seconds


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true", help="周辺のBLE機器を一覧表示")
    parser.add_argument("--address", help="接続先のBLEアドレス")
    parser.add_argument("--hex-rx", action="store_true", help="受信を16進数で表示")
    parser.add_argument("--interactive", action="store_true", help="送信・DTR操作を有効化")
    parser.add_argument("--duration", type=positive_seconds, help="指定秒数で受信を終了")
    parser.add_argument("--newline", choices=["none", "lf", "crlf"], default="crlf")
    args = parser.parse_args(argv)
    if args.interactive and args.duration is not None:
        parser.error("--durationは受信専用モードで使用してください。")
    return args


async def run(args: argparse.Namespace) -> None:
    if args.scan:
        await scan_devices()
    else:
        await run_session(args.address, args.hex_rx, args.interactive, args.duration, args.newline)


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run(args))
    except (KeyboardInterrupt, EOFError):
        pass
    except Exception as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
