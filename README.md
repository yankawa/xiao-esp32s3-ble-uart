# xiao-esp32s3-ble-uart

XIAO ESP32-S3でUARTのデータをBLE経由で送受信するためのファームウェアと、Python製の端末プログラムです。SchooMyのジャイロ出力を使って通信を確認しています。

```text
SchooMy ── UART / 115200bps ── XIAO ESP32-S3 ── BLE ── PC
```

ファームウェアはXIAOに書き込みます。SchooMyに書き込まれているプログラムは変更しません。SchooMyではデータをシリアル出力するプログラムを動かしておく必要があります。

## クイックスタート

Python 3.14以上、uv、Bluetooth LE対応PCを使用します。

```powershell
uv sync --locked
uv run main.py --scan
uv run main.py --address 44:BD:8D:76:BB:7D
```

上のアドレスは動作確認に使ったXIAOのものです。別のXIAOを使う場合は `--scan` でアドレスを確認してください。アドレスを省略すると、UARTサービスを広告している機器を検索します。複数台ある場合はアドレスを指定します。

標準では受信だけを行います。Ctrl+Cで終了します。同じXIAOへ同時に接続する端末やスマホアプリは一つにしてください。

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

受信したデータはUTF-8として表示します。一つの文字のバイト列が複数のBLE通知に分かれて届いても、続けて読み取って文字に戻します。不正なバイトは置換文字で表示します。受信したバイト列をそのまま確認する場合は `--hex-rx` を使用してください。

### 対話モードの操作

|入力|動作|
|---|---|
|文字列 + Enter|UTF-8と指定した改行をUARTへ送信|
|`/hex 01 ff 00`|指定バイトだけを送信。改行は追加しない|
|`/dtr on`|DTRを有効化。標準設定ではLOW|
|`/dtr off`|DTRを解除。標準設定ではHIGH|
|`/quit`|終了|

WindowsではBLEの受信処理と並行してキー入力を読み取ります。受信データと入力中の文字は同じ端末に表示されるため、表示が混ざる場合があります。

## 配線

SchooMy本体のTX・RXを基準にすると、配線は次のとおりです。

|SchooMy側の信号|XIAO|GPIO|
|---|---|---|
|本体のTX（出力）|D7 / RX|44|
|本体のRX（入力）|D6 / TX|43|
|DTR|D0|1|
|GND|GND|—|
|+5V|5V（電源条件を確認）|—|
|3V3|未接続|—|

元のUSB–UART変換器をXIAOに置き換える場合は、変換器の端子名を基準にします。変換器のRXDが接続されていた位置にはXIAOのD7/RXを、TXDが接続されていた位置にはD6/TXをつなぎます。変換器のTXはSchooMy本体へ送る信号なので、本体のTXとは向きが逆です。どちらの端子名を基準にするかを区別しないと、正しく配線できず受信できません。

XIAOのGPIOへ入力できる信号は3.3Vです。相手の出力が5Vの場合はレベル変換が必要です。動作確認に使ったSchooMyのUART信号電圧はまだ測定していません。USBと外部5Vを併用する場合は、電源の逆流や競合が起きないように接続してください。3V3は電源出力で、この接続では使用しません。付属のBLEアンテナを接続してください。

## ファームウェアのビルドと書き込み

Arduino IDEで `firmware/ble_uart_bridge/ble_uart_bridge.ino` を開きます。Espressifのesp32ボードパッケージから `XIAO_ESP32S3` を選択して書き込みます。BLEライブラリはボードパッケージに付属するものを使います。動作確認に使ったボードパッケージは3.3.12です。

Arduino CLIをPATHへ登録している場合は、次のコマンドでもビルドと書き込みができます。書き込み先のポートは `board list` の結果に合わせてください。

```powershell
arduino-cli board list
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 --output-dir build firmware/ble_uart_bridge
arduino-cli upload --fqbn esp32:esp32:XIAO_ESP32S3 --port COM5 --input-dir build firmware/ble_uart_bridge
```

スケッチの冒頭で変更できる設定は次のとおりです。

|設定|初期値|用途|
|---|---|---|
|`UART_BAUD`|115200|相手のプログラムと合わせる。フレーム形式は8N1|
|`DTR_ACTIVE_LOW`|true|有効時LOW、解除時HIGH|
|`RX_PIN` / `TX_PIN`|44 / 43|UART入出力|
|`DTR_PIN`|1|DTR出力|

DTRはXIAOの起動時とBLE切断時に解除します。PC側の端末プログラムも終了時にDTRの解除を試みます。BLEに接続しただけではDTRを有効にしません。電源を入れてから初期化が終わるまでのピン状態は、ソフトウェアでは保証できません。動作確認に使ったSchooMyで、DTRが何を制御するかは未確認です。

## BLE仕様

BLEデバイス名は `XIAO-BLE-UART` です。Nordic UART Serviceと同じUUID構成を使い、DTR操作用の独自の特性を追加しています。

|用途|UUIDの先頭8桁|操作|
|---|---|---|
|サービス|`6e400001`|—|
|PC → UART|`6e400002`|Write with response|
|UART → PC|`6e400003`|Notify|
|DTR|`6e400004`|Read / Write|

完全なUUIDは表の先頭8桁に `-b5a3-f393-e0a9-e50e24dcca9e` を付けたものです。DTRにはバイナリの1バイトを送り、`00` で解除、`01` で有効にします。ASCII文字の0/1は使いません。データは20バイト以下に分けて送信します。

PC側のプログラムは接続時にBLE通知を登録し直します。通知設定を記録するCCCDの値を読み取れた場合は、その値も表示します。`01 00` は通知が有効な状態です。ただし、この値だけではUARTデータが届いているとは判断できません。通知の再登録は原因を調べるために追加しました。受信がときどき止まる原因は、まだ分かっていません。

## 確認結果とトラブルシューティング

SchooMyをUSBでPCへ直接つないだところ、115200bpsでテキストを正常に受信できました。公開例の9600bpsは動作確認に使ったSchooMyの設定とは一致しませんでした。

XIAO経由では15秒間に450行・10,800バイトを受信し、次のように値が変わることを確認しました。SchooMyに書き込まれたプログラムを取得していないため、各列に対応する軸や単位、最後の値の意味は未確認です。

```text
6.000,-4.460,-27.860,0
5.999,-4.459,-27.865,0
5.994,-4.444,-27.933,0
```

BLEに接続できても、受信が0バイトになる回があります。安定して受信を続けられるかは未確認で、リファクタリング後もこの問題の解消は確認できていません。

|症状|確認する点|
|---|---|
|機器が見つからない|電源、BLEアドレス、アンテナ、他の端末の接続|
|接続するが0バイト|通知設定、本体TX → D7、GND、SchooMyのシリアル出力と電源|
|文字化け|UART速度、8N1、信号電圧。`--hex-rx` でバイト列を確認|
|別の個体へ接続する|`--scan` の結果から `--address` を指定|

配線に問題があるかを調べるには、電源を切ってSchooMyを外し、XIAOのD6とD7を直接つなぎます。これは送信データを受信側へ戻すループバックです。`--interactive --hex-rx` で起動し、`/hex 00 01 ff` を送って同じバイト列が戻れば、BLEとXIAOのUARTで往復できることを確認できます。確認後は電源を切り、D6とD7をつないだ線を外して元の配線に戻します。

### 制約

- UARTのフロー制御と、アプリ側でのBLE通知の受信確認・再送はありません。通信量が多い場合に、データを欠落なく転送できる保証はありません。
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
tests/test_client.py          ハードウェア不要のテスト
```

```powershell
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run main.py --help
```

テストでは、分割して送ったバイナリを元どおりに復元できること、DTR操作でUARTデータを送らないこと、分割されたUTF-8を表示できること、CLI引数の扱いを確認します。実機との接続が安定するかどうかや、信号電圧などの電気的な条件は検証しません。

このディレクトリは独立したGitリポジトリとして管理します。仮想環境、ビルドしたバイナリ、キャッシュ、調査用の商品画像はGitの管理対象から除外します。依存パッケージのバージョンを固定する `uv.lock` は管理対象に含めます。

```powershell
git status
git diff
git add main.py ble_uart firmware tests README.md pyproject.toml uv.lock
git commit -m "Describe the change"
```

参考: [Seeed公式ピン仕様](https://wiki.seeedstudio.com/xiao_esp32s3_pin_multiplexing/)、[Espressif公式BLE UART例](https://github.com/espressif/arduino-esp32/blob/master/libraries/BLE/examples/UART/UART.ino)。
