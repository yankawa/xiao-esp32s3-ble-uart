"""BLE機器への接続、受信データの表示、UARTへの送信。"""
import asyncio
import codecs
from contextlib import suppress
from typing import TextIO
import sys

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from .protocol import CCCD_UUID, DTR_UUID, PAYLOAD_SIZE, RX_UUID, SERVICE_UUID, TX_UUID
from .protocol import CommandKind, parse_command
from .terminal import read_command


class Receiver:
    """BLE通知に分かれて届くUTF-8を文字に戻し、受信バイト数を数える。"""

    def __init__(self, hex_output: bool = False, output: TextIO | None = None):
        self.total_bytes = 0
        self.hex_output = hex_output
        self.output = output if output is not None else sys.stdout
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def __call__(self, _characteristic, data: bytearray) -> None:
        self.total_bytes += len(data)
        text = data.hex(" ") + "\n" if self.hex_output else self.decoder.decode(data)
        print(text, end="", file=self.output, flush=True)

    def finish(self) -> None:
        if not self.hex_output:
            print(self.decoder.decode(b"", final=True), end="", file=self.output, flush=True)


async def scan_devices() -> None:
    for device, advertisement in (await BleakScanner.discover(return_adv=True)).values():
        print(device.address, advertisement.local_name or device.name or "(unnamed)")


async def find_device(address: str | None) -> BLEDevice:
    if address:
        device = await BleakScanner.find_device_by_address(address, timeout=10)
    else:
        device = await BleakScanner.find_device_by_filter(
            lambda _device, adv: SERVICE_UUID in [u.lower() for u in adv.service_uuids],
            timeout=10,
        )
    if device is None:
        raise RuntimeError("XIAO-BLE-UARTが見つかりません。電源と他のBLE接続を確認してください。")
    return device


async def subscribe(client: BleakClient, receiver: Receiver) -> None:
    """BLE通知を登録し直し、読み取れた場合は通知設定の値を表示する。"""
    await client.start_notify(TX_UUID, receiver)
    await client.stop_notify(TX_UUID)
    await asyncio.sleep(0.2)
    await client.start_notify(TX_UUID, receiver)
    characteristic = client.services.get_characteristic(TX_UUID)
    if characteristic is None:
        raise RuntimeError("UART受信用のBLE特性がありません。ファームウェアを確認してください。")
    descriptor = next((d for d in characteristic.descriptors if d.uuid.lower() == CCCD_UUID), None)
    if descriptor is not None:
        try:
            state = await client.read_gatt_descriptor(descriptor.handle)
            print(f"BLE通知設定: {state.hex(' ')}（正常: 01 00）", flush=True)
        except BleakError as exc:
            print(f"通知設定の読み取り不可（受信は継続）: {exc}", file=sys.stderr)


async def send_command(client: BleakClient, line: str, newline: str) -> bool:
    """入力した一行に応じてデータやDTR設定を送る。/quitではFalseを返す。"""
    command = parse_command(line, newline)
    if command.kind is CommandKind.QUIT:
        return False
    if command.kind is CommandKind.DTR:
        await client.write_gatt_char(DTR_UUID, command.data, response=True)
    else:
        for offset in range(0, len(command.data), PAYLOAD_SIZE):
            await client.write_gatt_char(RX_UUID, command.data[offset:offset + PAYLOAD_SIZE], response=True)
    return True


async def receive_session(client: BleakClient, receiver: Receiver, duration: float | None) -> None:
    started = asyncio.get_running_loop().time()
    warned = False
    while client.is_connected:
        await asyncio.sleep(0.1)
        elapsed = asyncio.get_running_loop().time() - started
        if not warned and elapsed >= 5 and receiver.total_bytes == 0:
            print("5秒間受信なし。通知・UART出力・配線の確認が必要です。", flush=True)
            warned = True
        if duration is not None and elapsed >= duration:
            return


async def interactive_session(client: BleakClient, newline: str) -> None:
    """コマンド入力を受け付け、BLEが切断されたら入力待ちを終了する。"""
    print("送信: /dtr on | /dtr off | /hex 01 ff | /quit", flush=True)
    while client.is_connected:
        task = asyncio.create_task(read_command())
        try:
            while not task.done():
                await asyncio.sleep(0.1)
                if not client.is_connected:
                    return
            try:
                if not await send_command(client, task.result(), newline):
                    return
            except ValueError as exc:
                print(exc, flush=True)
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task


async def run_session(address: str | None, hex_output: bool, interactive: bool,
                      duration: float | None, newline: str) -> None:
    device = await find_device(address)
    receiver = Receiver(hex_output)
    async with BleakClient(device) as client:
        try:
            await subscribe(client, receiver)
            print(f"接続: {device.address}。受信待ち。Ctrl+Cで終了。", flush=True)
            if interactive:
                await interactive_session(client, newline)
            else:
                await receive_session(client, receiver, duration)
        finally:
            receiver.finish()
            print(f"\n受信合計: {receiver.total_bytes} bytes", flush=True)
            if client.is_connected:
                try:
                    await client.write_gatt_char(DTR_UUID, b"\x00", response=True)
                except BleakError as exc:
                    print(f"終了時のDTR解除に失敗: {exc}", file=sys.stderr)
