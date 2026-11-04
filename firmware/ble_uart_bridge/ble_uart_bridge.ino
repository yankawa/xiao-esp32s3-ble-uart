#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <atomic>

constexpr int RX_PIN = 44, TX_PIN = 43, DTR_PIN = 1;
constexpr uint32_t UART_BAUD = 115200;
constexpr bool DTR_ACTIVE_LOW = true;
constexpr size_t BLE_PAYLOAD_SIZE = 20;  // ATT MTUが最小の23バイトでも送れる長さ。
constexpr size_t UART_RX_BUFFER_SIZE = 4096;
#define SERVICE_UUID "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define RX_UUID "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
#define TX_UUID "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
#define DTR_UUID "6e400004-b5a3-f393-e0a9-e50e24dcca9e"
HardwareSerial target(1);
std::atomic<bool> connected{false}, restartAdvertising{false};
BLECharacteristic *txCharacteristic, *dtrCharacteristic;
BLE2902 *subscription;
void setDtr(bool asserted) {
  digitalWrite(DTR_PIN, (asserted != DTR_ACTIVE_LOW) ? HIGH : LOW);
}

void updateDtrState(bool asserted) {
  setDtr(asserted);
  uint8_t state = asserted;
  dtrCharacteristic->setValue(&state, 1);
}
class ConnectionCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *) override { connected = true; }
  void onDisconnect(BLEServer *) override {
    connected = false;
    updateDtrState(false);
    subscription->setNotifications(false);
    restartAdvertising = true;
  }
};
class ReceiveCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *characteristic) override {
    const String value = characteristic->getValue();
    target.write(reinterpret_cast<const uint8_t *>(value.c_str()), value.length());
  }
};
class DtrCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *characteristic) override {
    const String value = characteristic->getValue();
    if (value.length() == 1 && (value[0] == 0 || value[0] == 1)) {
      updateDtrState(value[0] == 1);
    } else {
      uint8_t state = digitalRead(DTR_PIN) == (DTR_ACTIVE_LOW ? LOW : HIGH);
      characteristic->setValue(&state, 1);
    }
  }
};
void initializeUart() {
  digitalWrite(DTR_PIN, DTR_ACTIVE_LOW ? HIGH : LOW);
  pinMode(DTR_PIN, OUTPUT);
  target.setRxBufferSize(UART_RX_BUFFER_SIZE);
  target.begin(UART_BAUD, SERIAL_8N1, RX_PIN, TX_PIN);
}

void initializeBle() {
  BLEDevice::init("XIAO-BLE-UART");
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ConnectionCallbacks());
  BLEService *service = server->createService(SERVICE_UUID);
  txCharacteristic = service->createCharacteristic(TX_UUID, BLECharacteristic::PROPERTY_NOTIFY);
  subscription = new BLE2902();
  txCharacteristic->addDescriptor(subscription);
  BLECharacteristic *rx = service->createCharacteristic(RX_UUID, BLECharacteristic::PROPERTY_WRITE);
  rx->setCallbacks(new ReceiveCallbacks());
  dtrCharacteristic = service->createCharacteristic(DTR_UUID,
    BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_WRITE);
  uint8_t state = 0;
  dtrCharacteristic->setValue(&state, 1);
  dtrCharacteristic->setCallbacks(new DtrCallbacks());
  service->start();
  BLEAdvertising *advertising = server->getAdvertising();
  advertising->addServiceUUID(SERVICE_UUID);
  advertising->setScanResponse(true);
  advertising->start();
}
void forwardUartData() {
  if (connected && subscription->getNotifications()) {
    uint8_t data[BLE_PAYLOAD_SIZE];
    size_t count = 0;
    while (count < sizeof(data) && target.available()) data[count++] = target.read();
    if (count) {
      txCharacteristic->setValue(data, count);
      txCharacteristic->notify();
      delay(5);
    }
  } else {
    // 古い測定値を次の接続で送らないよう、未接続・通知無効時のデータは捨てる。
    for (size_t i = 0; i < 256 && target.available(); ++i) target.read();
  }
}

void setup() {
  initializeUart();
  initializeBle();
}

void loop() {
  if (restartAdvertising.exchange(false)) BLEDevice::startAdvertising();
  forwardUartData();
  delay(1);
}
