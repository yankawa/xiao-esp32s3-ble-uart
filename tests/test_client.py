"""ハードウェアなしで実行できるプロトコルと受信処理のテスト。"""
import io
import unittest
from unittest.mock import AsyncMock

from ble_uart.cli import parse_args
from ble_uart.client import Receiver, send_command
from ble_uart.protocol import CommandKind, DTR_UUID, RX_UUID, parse_command


class ProtocolTests(unittest.TestCase):
    def test_text_and_newlines(self):
        self.assertEqual(parse_command("日本語").data, "日本語\r\n".encode())
        self.assertEqual(parse_command("test", "none").data, b"test")
        self.assertEqual(parse_command("test", "lf").data, b"test\n")

    def test_binary_and_control(self):
        self.assertEqual(parse_command("/hex 00 ff 01").data, b"\x00\xff\x01")
        self.assertEqual(parse_command("/dtr on").data, b"\x01")
        self.assertEqual(parse_command("/dtr off").data, b"\x00")
        self.assertIs(parse_command("/quit").kind, CommandKind.QUIT)
        with self.assertRaises(ValueError):
            parse_command("/hex zz")

    def test_duration_validation(self):
        for value in ("0", "-1", "nan", "inf"):
            with self.subTest(value=value), unittest.mock.patch("sys.stderr", io.StringIO()):
                with self.assertRaises(SystemExit):
                    parse_args(["--duration", value])

    def test_fragmented_utf8(self):
        output = io.StringIO()
        receiver = Receiver(output=output)
        data = "温度\r\n".encode()
        for byte in data:
            receiver(None, bytearray([byte]))
        receiver.finish()
        self.assertEqual(output.getvalue(), "温度\r\n")
        self.assertEqual(receiver.total_bytes, len(data))

    def test_hex_preserves_binary(self):
        output = io.StringIO()
        receiver = Receiver(hex_output=True, output=output)
        receiver(None, bytearray(b"\x00\xff"))
        self.assertEqual(output.getvalue(), "00 ff\n")


class SendTests(unittest.IsolatedAsyncioTestCase):
    async def test_chunked_binary_is_lossless(self):
        client = AsyncMock()
        data = bytes(range(51))
        await send_command(client, "/hex " + data.hex(" "), "crlf")
        calls = client.write_gatt_char.await_args_list
        self.assertEqual(b"".join(call.args[1] for call in calls), data)
        self.assertTrue(all(len(call.args[1]) <= 20 for call in calls))
        self.assertTrue(all(call.args[0] == RX_UUID and call.kwargs["response"] for call in calls))

    async def test_dtr_and_quit_do_not_write_uart(self):
        client = AsyncMock()
        self.assertTrue(await send_command(client, "/dtr on", "crlf"))
        client.write_gatt_char.assert_awaited_once_with(DTR_UUID, b"\x01", response=True)
        client.write_gatt_char.reset_mock()
        self.assertFalse(await send_command(client, "/quit", "crlf"))
        client.write_gatt_char.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
