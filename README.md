# xiao-esp32s3-ble-uart

XIAO ESP32-S3をBLEとUARTの間のブリッジとして使うファームウェアと、Python製の受信・送信端末です。SchooMyのジャイロ出力で通信を確認しています。

```text
SchooMy ── UART / 115200bps ── XIAO ESP32-S3 ── BLE ── PC
```

このプロジェクトが書き込むのはXIAOだけです。SchooMy側の既存プログラムは変更しません。SchooMy側でシリアル出力するプログラムが動いている必要があります。

## クイックスタート

Python 3.14以上、uv、Bluetooth LE対応PCを使用します。

```powershell
uv sync --locked
uv run main.py --scan
uv run main.py --address 44:BD:8D:76:BB:7D
```

アドレスは確認に使用した個体のものです。別の個体では `--scan` で確認してください。アドレスを省略すると、UARTサービスを広告している機器を検索します。複数台ある場合はアドレスを指定します。

標準は受信専用です。Ctrl+Cで終了します。同じXIAOへ接続する端末・スマホアプリは一つにしてください。

```powershell
# 15秒受信して終了時に受信バイト数を表示
uv run main.py --address 44:BD:8D:76:BB:7D --duration 15

# バイナリデータを16進数で表示
uv run main.py --address 44:BD:8D:76:BB:7D --hex-rx

# キーボード送信とDTR操作
uv run main.py --address 44:BD:8D:76:BB:7D --interactive
```

|オプション|動作|
|---|---|
|`--scan`|周辺BLE機器の名前・アドレスを表示|
|`--address ADDRESS`|接続先を指定|
|`--duration SECONDS`|正の秒数を指定して受信を終了。受信専用モードで使用|
|`--hex-rx`|受信したバイト列を16進数で表示|
|`--interactive`|コマンド入力を有効化|
|`--newline none\|lf\|crlf`|テキスト送信時の改行。初期値はcrlf|

通常の受信表示はUTF-8です。文字が複数通知に分割されても継続して復号し、不正なバイトは置換文字で表示します。元のバイトを調べる場合は `--hex-rx` を使用してください。

### 対話モードの操作

|入力|動作|
|---|---|
|文字列 + Enter|UTF-8と指定した改行をUARTへ送信|
|`/hex 01 ff 00`|指定バイトだけを送信。改行は追加しない|
|`/dtr on`|DTRを有効化。標準設定ではLOW|
|`/dtr off`|DTRを解除。標準設定ではHIGH|
|`/quit`|終了|

Windowsではキー入力を非同期に読み取ります。受信出力と入力文字は同じ端末に表示されるため、入力中は表示が混ざる場合があります。

## 配線

**SchooMy本体の送受信方向を基準にする場合**は次の接続です。

|SchooMy側の信号|XIAO|GPIO|
|---|---|---|
|本体のTX（出力）|D7 / RX|44|
|本体のRX（入力）|D6 / TX|43|
|DTR|D0|1|
|GND|GND|—|
|+5V|5V（電源条件を確認）|—|
|3V3|未接続|—|

**元のUSB–UART変換器を置き換える場合**は、変換器に書かれた名前を基準に `RXD位置 → XIAO D7/RX`、`TXD位置 → XIAO D6/TX` と接続します。変換器のTXは本体へ送る信号なので、本体のTXとは逆方向です。この区別をせずに配線すると受信できません。

XIAOのGPIOへ入力できる信号は3.3Vです。相手の出力が5Vの場合はレベル変換が必要です。SchooMyの今回の個体について、UART信号電圧は未測定です。USBと外部5Vを併用する場合は電源の逆流・競合が起きない構成にしてください。3V3は電源出力であり、この接続では使用しません。付属BLEアンテナを接続してください。

## ファームウェアのビルドと書き込み

Arduino IDEで `firmware/ble_uart_bridge/ble_uart_bridge.ino` を開き、Espressifのesp32ボードパッケージから `XIAO_ESP32S3` を選択して書き込みます。BLEライブラリはボードパッケージ付属のものを使用します。検証したバージョンは3.3.12です。

Arduino CLIをPATHへ登録している場合は、次でも実行できます。書き込みポートは実際の検出結果に合わせてください。

```powershell
arduino-cli board list
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 --output-dir build firmware/ble_uart_bridge
arduino-cli upload --fqbn esp32:esp32:XIAO_ESP32S3 --port COM5 --input-dir build firmware/ble_uart_bridge
```

スケッチ冒頭の設定:

|設定|初期値|用途|
|---|---|---|
|`UART_BAUD`|115200|相手のプログラムと合わせる。フレーム形式は8N1|
|`DTR_ACTIVE_LOW`|true|有効時LOW、解除時HIGH|
|`RX_PIN` / `TX_PIN`|44 / 43|UART入出力|
|`DTR_PIN`|1|DTR出力|

DTRは起動時・BLE切断時に解除します。PC端末の終了時にも解除を試みます。接続しただけでは有効化しません。電源投入から初期化までのピン状態はソフトウェアでは保証できません。今回のSchooMyでDTRが何を制御するかは未確認です。

## BLE仕様

デバイス名は `XIAO-BLE-UART`。Nordic UART ServiceのUUID構成に独自のDTR特性を追加しています。

|用途|UUID末尾の識別子|操作|
|---|---|---|
|サービス|`6e400001`|—|
|PC → UART|`6e400002`|Write with response|
|UART → PC|`6e400003`|Notify|
|DTR|`6e400004`|Read / Write|

完全なUUIDは各識別子に `-b5a3-f393-e0a9-e50e24dcca9e` を付けたものです。DTRはバイナリ1バイトで `00` が解除、`01` が有効です。ASCII文字の0/1は使用しません。データは20バイト以下に分割して送信します。

PC側は接続時に通知を登録し直し、読み取れる場合はCCCD値を表示します。`01 00` は通知有効を表しますが、UARTデータの到着を保証するものではありません。通知の再登録は診断のために追加したもので、断続的な受信停止の原因が解明されたわけではありません。

## 確認結果とトラブルシューティング

SchooMyのUSB直結では115200bpsで正常なテキストを受信しました。公開例の9600bpsは今回の個体には一致しませんでした。

XIAO経由では15秒間に450行・10,800バイトを受信し、次のような値の変化を確認しています。SchooMyのプログラムを取得していないため、各列の軸・単位・最後の値の意味は未確認です。

```text
6.000,-4.460,-27.860,0
5.999,-4.459,-27.865,0
5.994,-4.444,-27.933,0
```

一方で、接続成功後も0バイトになる回があります。継続的な安定動作は未確認です。リファクタリングだけでこの問題を解消したとは扱いません。

|症状|確認する点|
|---|---|
|機器が見つからない|電源、BLEアドレス、アンテナ、他の端末の接続|
|接続するが0バイト|通知設定、本体TX → D7、GND、SchooMyのシリアル出力と電源|
|文字化け|UART速度、8N1、信号電圧。`--hex-rx` でバイト列を確認|
|別の個体へ接続する|`--scan` の結果から `--address` を指定|

配線を切り分けるには、電源を切ってSchooMyを外し、XIAOのD6とD7を短絡したループバックを使います。`--interactive --hex-rx` で `/hex 00 01 ff` がそのまま戻れば、BLEとXIAO UARTの往復を確認できます。確認後は電源を切り、短絡を外して元に戻します。

### 制約

- UARTのフロー制御、BLE通知のアプリ側ACK・再送はありません。高負荷時の無欠落転送は保証しません。
- UART受信バッファは4096バイト。未接続・通知未購読のデータは破棄します。
- 単一クライアント用です。BLEの認証・暗号化は設定していません。
- 仮想COMポートやBluetooth Classic SPP、自動ファームウェア書き込みには対応しません。

## コード構成と開発

```text
main.py                       CLIの起動
ble_uart/cli.py               引数解析と終了処理
ble_uart/client.py            検出・接続・通知・受信・送信
ble_uart/protocol.py          UUIDとコマンド形式
ble_uart/terminal.py          非同期のキー入力
firmware/ble_uart_bridge/     XIAO用Arduinoスケッチ
 tests/test_client.py         ハードウェア不要のテスト
```

```powershell
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run main.py --help
```

テストはバイナリ送信の分割・復元、DTRとデータ送信の分離、分割UTF-8の受信表示、CLI引数を確認します。実機の接続安定性や電気的な条件は検証しません。

このディレクトリを独立したGitリポジトリとして管理します。仮想環境、生成バイナリ、キャッシュ、調査用の商品画像は追跡しません。依存関係を固定する `uv.lock` は追跡します。

```powershell
git status
git diff
git add main.py ble_uart firmware tests README.md pyproject.toml uv.lock
git commit -m "Describe the change"
```

参考: [Seeed公式ピン仕様](https://wiki.seeedstudio.com/xiao_esp32s3_pin_multiplexing/)、[Espressif公式BLE UART例](https://github.com/espressif/arduino-esp32/blob/master/libraries/BLE/examples/UART/UART.ino)。
