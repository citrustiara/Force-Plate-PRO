/**
 * Platform Send - Minimal ESP32 firmware for Force Plate PRO
 *
 * Streams raw ADC data over USB Serial for Python app processing.
 * All physics calculations are done on the PC side.
 *
 * Serial Commands:
 *   {"cmd":"tare"}  - Re-zero the scale
 *   {"cmd":"reset"} - Restart ESP32
 */

// --- PIN CONFIGURATION ---
#define CS_SCK_PIN 18
#define CS_DT_PIN 19

// --- TARE CONFIGURATION ---
#define TARE_DURATION_MS 300
#define TARE_STABILITY_THRESHOLD 20000 // Max noise amplitude for valid tare

// --- CS1238 ADC DRIVER ---
class CS1238_Driver {
private:
  int _sck, _dt;

  void clockPulse() {
    digitalWrite(_sck, HIGH);
    delayMicroseconds(1);
    digitalWrite(_sck, LOW);
    delayMicroseconds(1);
  }

  void writeBit(bool bit) {
    digitalWrite(_dt, bit ? HIGH : LOW);
    delayMicroseconds(1);
    clockPulse();
  }

public:
  void begin(int sck, int dt) {
    _sck = sck;
    _dt = dt;

    pinMode(_sck, OUTPUT);
    pinMode(_dt, INPUT);
    digitalWrite(_sck, LOW);

    // Reset sequence
    digitalWrite(_sck, HIGH);
    delayMicroseconds(200);
    digitalWrite(_sck, LOW);
    delay(10);

    configure();
  }

  void configure() {
    // Wait for ADC ready
    unsigned long timeout = millis();
    while (digitalRead(_dt) == HIGH) {
      if (millis() - timeout > 500)
        return;
    }

    // 24 data bits + 5 extra clocks
    for (int i = 0; i < 24; i++)
      clockPulse();
    for (int i = 0; i < 5; i++)
      clockPulse();

    // Write config command
    pinMode(_dt, OUTPUT);
    uint8_t cmd = 0x65;
    for (int i = 6; i >= 0; i--) {
      writeBit((cmd >> i) & 1);
    }
    clockPulse();

    // Config: 1280Hz, PGA 128
    uint8_t configVal = 0x3C;
    for (int i = 7; i >= 0; i--) {
      writeBit((configVal >> i) & 1);
    }

    pinMode(_dt, INPUT);
    clockPulse();
    delay(100);
  }

  bool isReady() { return digitalRead(_dt) == LOW; }

  long readRaw() {
    if (!isReady())
      return 0;

    long value = 0;
    for (int i = 0; i < 24; i++) {
      digitalWrite(_sck, HIGH);
      delayMicroseconds(1);
      value = (value << 1) | digitalRead(_dt);
      digitalWrite(_sck, LOW);
      delayMicroseconds(1);
    }

    // 3 extra clocks
    clockPulse();
    clockPulse();
    clockPulse();

    // Sign extend 24-bit to 32-bit
    if (value & 0x800000)
      value |= 0xFF000000;

    return value;
  }
};

CS1238_Driver scale;

// --- GLOBAL VARIABLES ---
long zeroOffset = 0;
bool isTaring = false;
long long tareSum = 0;
int tareCount = 0;
long tareMin = 0;
long tareMax = 0;
unsigned long tareStartTime = 0;

// Serial command buffer
String cmdBuffer = "";

// --- TARE (ZERO CALIBRATION) ---
void startTare() {
  isTaring = true;
  tareSum = 0;
  tareCount = 0;
  tareMin = 2000000000;
  tareMax = -2000000000;
  tareStartTime = millis();
  Serial.println("{\"event\":\"tare_start\"}");
}

void processTare(long raw) {
  tareSum += raw;
  tareCount++;
  if (raw < tareMin)
    tareMin = raw;
  if (raw > tareMax)
    tareMax = raw;

  if (millis() - tareStartTime >= TARE_DURATION_MS) {
    // Check stability
    long noise = tareMax - tareMin;

    if (noise < TARE_STABILITY_THRESHOLD && tareCount > 0) {
      zeroOffset = tareSum / tareCount;
      Serial.printf(
          "{\"event\":\"zero\",\"offset\":%ld,\"noise\":%ld,\"samples\":%d}\n",
          zeroOffset, noise, tareCount);
    } else {
      // Unstable - retry
      Serial.printf("{\"event\":\"tare_retry\",\"noise\":%ld}\n", noise);
      startTare();
      return;
    }

    isTaring = false;
  }
}

// --- FREQUENCY MEASUREMENT ---
void measureFrequency() {
  long count = 0;
  unsigned long start = millis();

  while (millis() - start < 1000) {
    if (scale.isReady()) {
      scale.readRaw();
      count++;
    }
    yield();
  }

  Serial.printf("{\"event\":\"rate\",\"hz\":%ld}\n", count);
}

// --- SERIAL COMMAND PROCESSING ---
void processCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0)
    return;

  // Parse JSON command
  if (cmd.startsWith("{") && cmd.indexOf("\"cmd\"") > 0) {
    if (cmd.indexOf("\"tare\"") > 0) {
      startTare();
    } else if (cmd.indexOf("\"reset\"") > 0) {
      Serial.println("{\"event\":\"resetting\"}");
      delay(100);
      ESP.restart();
    }
  }
}

void checkSerialCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      processCommand(cmdBuffer);
      cmdBuffer = "";
    } else {
      cmdBuffer += c;
    }
  }
}

// --- SETUP ---
void setup() {
  Serial.begin(921600);
  delay(500);

  scale.begin(CS_SCK_PIN, CS_DT_PIN);
  delay(200);

  // Initial tare
  startTare();
  while (isTaring) {
    if (scale.isReady()) {
      processTare(scale.readRaw());
    }
    yield();
  }

  measureFrequency();
}

// --- MAIN LOOP ---
void loop() {
  // Check for serial commands
  checkSerialCommands();

  if (scale.isReady()) {
    long raw = scale.readRaw();

    // Process tare if active
    if (isTaring) {
      processTare(raw);
      return;
    }

    long weight = raw - zeroOffset;

    // Handle negative weight (inverted sensor)
    if (weight < -10000)
      weight = -weight;

    // Send only the weight value
    Serial.printf("{\"w\":%ld}\n", weight);
  }
}
