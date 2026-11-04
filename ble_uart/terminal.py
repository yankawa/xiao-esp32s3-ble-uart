"""BLEイベント処理を止めない端末入力。"""
import asyncio
import sys


async def read_command() -> str:
    """Windowsではinput()による標準出力ロックを避けて一行読む。"""
    if sys.platform != "win32":
        return await asyncio.to_thread(input)
    import msvcrt

    chars: list[str] = []
    extended_key = False
    while True:
        if not msvcrt.kbhit():
            await asyncio.sleep(0.02)
            continue
        char = msvcrt.getwch()
        if extended_key:
            extended_key = False
        elif char in ("\x00", "\xe0"):
            extended_key = True
        elif char == "\x03":
            raise KeyboardInterrupt
        elif char == "\r":
            print(flush=True)
            return "".join(chars)
        elif char == "\b":
            if chars:
                chars.pop()
                print("\b \b", end="", flush=True)
        else:
            chars.append(char)
            print(char, end="", flush=True)
