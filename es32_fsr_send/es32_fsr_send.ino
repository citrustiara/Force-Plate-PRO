#include <WiFi.h>
#include <esp_now.h>

// --- KONFIGURACJA PINÓW ---
#define CS_SCK_PIN 18
#define CS_DT_PIN 19

// --- KALIBRACJA (Zmienna zamiast define) ---
float rawPerKg = 12600.0;
#define GRAVITY 9.81

// --- PROGI (THRESHOLDS) ---
#define AIR_THRESHOLD 100000     // Poniżej tego = powietrze LUB pusta waga
#define MOVEMENT_THRESHOLD 24000 // Wykrycie ruchu do całkowania
#define STABILITY_TOLERANCE_KG                                                 \
  2.0 // Zakres stabilności (max - min) <= 2kg (czyli +/- 1kg)

// Limity bezpieczeństwa
#define MAX_PROPULSION_TIME_MS 1000
#define MAX_REALISTIC_VELOCITY 10.0
#define MIN_AIR_TIME 150
#define MAX_AIR_TIME 1500

// --- ESP-NOW ---
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
enum MessageType {
  MSG_WAITING,
  MSG_READY,
  MSG_IN_AIR,
  MSG_RESULT,
  MSG_DEBUG,
  MSG_CMD_RESET,
  MSG_CAL_START,
  MSG_CAL_WAIT_WEIGHT,
  MSG_CAL_MEASURING,
  MSG_CAL_DONE,
  MSG_CAL_ERROR
};

typedef struct struct_message {
  int msgType;
  unsigned long flightTime;
  long currentLoad;
  float calculatedWatts;
  float physicsAvgPower;
  float takeoffVelocity; // NEW FIELD
} struct_message;

struct_message myData;
struct_message incomingCmd;
esp_now_peer_info_t peerInfo;

// --- ZMIENNE STANU ---
bool isReady = false;
bool inAir = false;
bool isIntegrating = false;
bool isCalibrating = false; // New state

// --- Logika ważenia ---
bool weightConfirmed = false;
unsigned long calibrationStartTime = 0;
long long calibrationSum =
    0; // Zmiana na long long, aby uniknąć overflow przy 1280 próbkach
int calibrationCount = 0;
long calibrationMin = 0; // Do wykrywania stabilności
long calibrationMax = 0; // Do wykrywania stabilności

// --- Calibration Process Variables ---
int calStep = 0;
unsigned long calStepTimer = 0;
long long calAccumulator = 0;
int calSampleCount = 0;
long calMinVal = 0;
long calMaxVal = 0;

// Zmienne pomocnicze
unsigned long lastActivityTime = 0;
long zeroOffset = 0;
long noiseAmplitude = 0; // Amplitude of noise (Max - Min)
unsigned long lastDebugSend = 0;

// Fizyka skoku
long staticWeightRaw = 0;
float jumperMassKg = 0;
float currentVelocity = 0;
float peakPower = 0;
float lastTakeoffVelocity = 0; // NEW GLOBAL

// Average Power Variables
double sumPower = 0;
long powerSampleCount = 0;
float avgPower = 0;

unsigned long lastIntegrationMicros = 0;
unsigned long integrationStartTime = 0;
unsigned long takeoffTime = 0;

// Logging
unsigned long landingTimeForLog = 0;

// Diagnostyka Hz
long samplesPerSecCounter = 0;
unsigned long lastHzCheck = 0;
int currentRealHz = 0;
long startupMeasuredHz = 0; // NEW: Global to store startup rate

// =============================================================
// === KLASA STEROWNIKA CS1238 ===
// =============================================================
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

    digitalWrite(_sck, HIGH);
    delayMicroseconds(200);
    digitalWrite(_sck, LOW);
    delay(10);

    configure();
  }

  void configure() {
    unsigned long timeout = millis();
    while (digitalRead(_dt) == HIGH) {
      if (millis() - timeout > 500) {
        return;
      }
    }

    for (int i = 0; i < 24; i++)
      clockPulse();
    clockPulse();
    clockPulse();
    clockPulse();
    clockPulse();
    clockPulse();

    pinMode(_dt, OUTPUT);

    uint8_t cmd = 0x65;
    for (int i = 6; i >= 0; i--) {
      writeBit((cmd >> i) & 1);
    }
    clockPulse();

    uint8_t configVal = 0x3C; // 1280Hz, PGA 128
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
    clockPulse();
    clockPulse();
    clockPulse();
    if (value & 0x800000)
      value |= 0xFF000000;
    return value;
  }

  // Basic read average for quick internal use
  long readAverage(int samples = 20) {
    long sum = 0;
    int validSamples = 0;
    for (int i = 0; i < samples * 2; i++) {
      unsigned long timeout = millis();
      while (!isReady()) {
        if (millis() - timeout > 100)
          break;
        yield();
      }
      if (isReady()) {
        sum += readRaw();
        validSamples++;
        if (validSamples >= samples)
          break;
      }
    }
    return (validSamples > 0) ? (sum / validSamples) : 0;
  }
};

CS1238_Driver scale;

// =============================================================

void OnDataRecv(const uint8_t *mac, const uint8_t *incomingBytes, int len) {
  memcpy(&incomingCmd, incomingBytes, sizeof(incomingCmd));
  if (incomingCmd.msgType == MSG_CMD_RESET) {
    ESP.restart();
  } else if (incomingCmd.msgType == MSG_CAL_START) {
    isCalibrating = true;
    calStep = 0;
    calStepTimer = millis();
    weightConfirmed = false; // Reset normal operation
    isReady = false;
  }
}

// SMART ZERO CALIBRATION
void calibrateZero() {
  Serial.println("{\"event\":\"log\",\"msg\":\"Starting Smart Zero...\"}");
  long long sum = 0;
  long minVal = 20000000;
  long maxVal = -20000000;
  int count = 0;
  unsigned long start = millis();

  // Measure for 2 seconds
  while (millis() - start < 2000) {
    if (scale.isReady()) {
      long val = scale.readRaw();
      sum += val;
      if (val < minVal)
        minVal = val;
      if (val > maxVal)
        maxVal = val;
      count++;
    }
    yield();
  }

  if (count > 0) {
    zeroOffset = sum / count;
    noiseAmplitude = maxVal - minVal;

    // Send calibration JSON
    Serial.printf(
        "{\"event\":\"zero\",\"offset\":%ld,\"noise\":%ld,\"count\":%d}\n",
        zeroOffset, noiseAmplitude, count);
  } else {
    Serial.println(
        "{\"event\":\"error\",\"msg\":\"Calibration failed (no data)\"}");
  }
}

// STARTUP FREQUENCY MEASUREMENT
void measureStartupFrequency() {
  Serial.println("{\"event\":\"log\",\"msg\":\"Measuring HZ...\"}");
  long count = 0;
  unsigned long start = millis();

  // Measure for 1 second
  while (millis() - start < 1000) {
    if (scale.isReady()) {
      scale.readRaw(); // Just read to clear and count
      count++;
    }
    yield();
  }

  startupMeasuredHz = count;
  // Send Rate JSON
  Serial.printf("{\"event\":\"rate\",\"hz\":%ld}\n", startupMeasuredHz);
}

void setup() {
  Serial.begin(921600); // INCREASED SPEED to prevent blocking
  delay(1000);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  if (esp_now_init() != ESP_OK) {
    ESP.restart();
  }
  esp_now_register_recv_cb((esp_now_recv_cb_t)OnDataRecv);

  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  esp_now_add_peer(&peerInfo);

  scale.begin(CS_SCK_PIN, CS_DT_PIN);

  delay(200);

  // Perform Smart Zero Calibration
  calibrateZero();

  // Measure Startup Frequency
  measureStartupFrequency();

  lastActivityTime = millis();
}

void sendStatus(int type, unsigned long timeVal, long loadVal, float powerVal) {
  myData.msgType = type;
  myData.flightTime = timeVal;
  myData.currentLoad = loadVal;
  myData.calculatedWatts = powerVal;
  myData.physicsAvgPower = avgPower;            // Send Average
  myData.takeoffVelocity = lastTakeoffVelocity; // Send Takeoff Velocity

  esp_now_send(broadcastAddress, (uint8_t *)&myData, sizeof(myData));

  // Also send event via Serial for Desktop App
  if (type == MSG_RESULT) {
    Serial.printf(
        "{\"event\":\"jump\",\"height\":%lu,\"pwr\":%.2f,\"time\":%lu}\n",
        (unsigned long)calculateHeight(timeVal), powerVal, timeVal);
  }

  if (type != MSG_DEBUG)
    lastActivityTime = millis();
}

// Helper for Serial JSON - duplicating logic for display
float calculateHeight(unsigned long timeMs) {
  return (9.81 * (timeMs / 1000.0) * (timeMs / 1000.0)) / 8.0 * 100.0;
}

void processPhysics(long rawForce, unsigned long currentMicros) {
  if (jumperMassKg == 0)
    return;
  if (millis() - integrationStartTime > MAX_PROPULSION_TIME_MS)
    return;

  float dt = (currentMicros - lastIntegrationMicros) / 1000000.0;
  if (dt > 0.05 || dt <= 0)
    dt = 0;
  lastIntegrationMicros = currentMicros;
  float forceN = (rawForce / rawPerKg) * GRAVITY;
  float weightN = jumperMassKg * GRAVITY;
  float netForce = forceN - weightN;
  float acceleration = netForce / jumperMassKg;

  currentVelocity += acceleration * dt;
  float instantPower = forceN * currentVelocity;

  // Accumulate Average Power
  if (!inAir &&
      currentVelocity >
          0) { // Only accumulate power during propulsion (velocity > 0)
    sumPower += instantPower;
    powerSampleCount++;
  }

  if (instantPower > peakPower)
    peakPower = instantPower;
  if (currentVelocity > MAX_REALISTIC_VELOCITY) {
    currentVelocity = 0;
    peakPower = 0;
    sumPower = 0;
    powerSampleCount = 0;
    integrationStartTime = millis();
  }
}

void loop() {
  // Licznik Hz
  if (millis() - lastHzCheck >= 1000) {
    currentRealHz = samplesPerSecCounter;
    samplesPerSecCounter = 0;
    lastHzCheck = millis();
  }

  if (scale.isReady()) {
    samplesPerSecCounter++;

    unsigned long nowMicros = micros();
    long raw = scale.readRaw();
    long weight = raw - zeroOffset;
    if (weight < -10000)
      weight = -weight;

    // --- LOGGING (JSON STREAM) ---
    // Log at ~50Hz or similar to avoid spamming too much?
    // Or just stream everything if baud rate allows (115200 is fast enough for
    // 80sps text) To be safe, let's decimate slightly or send all. Sending all
    // for best graph resolution.
    // Serial.printf("{\"w\":%ld}\n", weight);
    Serial.printf("{\"w\":%ld,\"t\":%lu}\n", weight,
                  nowMicros); // Added Timestamp

    // --- CALIBRATION LOGIC ---
    if (isCalibrating) {
      if (calStep == 0) {
        // STEP 0: Wait for load between 11kg and 19kg (approx)
        // Using current known factor for estimation
        float estimatedKg = weight / rawPerKg;
        if (estimatedKg > 11.0 && estimatedKg < 19.0) {
          if (millis() - calStepTimer > 500) { // Wait 0.5s stability
            calStep = 1;
            calStepTimer = millis();
            calAccumulator = 0;
            calSampleCount = 0;
            calMinVal = 20000000;
            calMaxVal = -20000000;
            sendStatus(MSG_CAL_MEASURING, 0, weight, 0);
          }
        } else {
          calStepTimer = millis(); // Reset timer if out of range
          if (millis() - lastDebugSend > 200) {
            sendStatus(MSG_CAL_WAIT_WEIGHT, 0, weight, 0);
            lastDebugSend = millis();
          }
        }
      } else if (calStep == 1) {
        // STEP 1: Measuring (3 seconds)
        calAccumulator += weight;
        calSampleCount++;
        if (weight < calMinVal)
          calMinVal = weight;
        if (weight > calMaxVal)
          calMaxVal = weight;

        if (millis() - calStepTimer > 3000) {
          // Done measuring
          long range = calMaxVal - calMinVal;
          // Check noise
          if (range / rawPerKg > STABILITY_TOLERANCE_KG) {
            // Too unstable, restart measurement
            calStep = 1;
            calStepTimer = millis();
            calAccumulator = 0;
            calSampleCount = 0;
            sendStatus(MSG_CAL_ERROR, 0, weight,
                       0); // Receiver can ignore or flash
          } else {
            // Calculate new factor
            if (calSampleCount > 0) {
              float avg = (float)(calAccumulator / calSampleCount);
              rawPerKg = avg / 15.0; // CALIBRATING TO 15 KG
              sendStatus(MSG_CAL_DONE, 0, 0,
                         rawPerKg);  // Send new factor in calculatedWatts field
              isCalibrating = false; // Exit calibration
            }
          }
        } else {
          // Keep User Updated
          if (millis() - lastDebugSend > 500) {
            sendStatus(MSG_CAL_MEASURING, 0, weight, 0);
            lastDebugSend = millis();
          }
        }
      }
      return; // Skip normal logic
    }

    // --- NORMAL LOGIC ---
    // (Existing code starts here...)

    // --- 1. WYSYŁANIE DEBUGU ---
    if (millis() - lastDebugSend > 100) {
      if (!weightConfirmed && weight > AIR_THRESHOLD && !inAir) {
        sendStatus(MSG_WAITING, 0, weight, 0);
      } else if (isReady) {
        sendStatus(MSG_READY, 0, weight, 0);
      } else if (!inAir) {
        sendStatus(MSG_DEBUG, 0, weight, (float)currentRealHz);
      }
      lastDebugSend = millis();
    }

    // --- 2. LOGIKA GŁÓWNA ---

    // SYTUACJA A: Jesteśmy w powietrzu
    if (inAir) {
      unsigned long currentAirTime = millis() - takeoffTime;
      if (weight >= AIR_THRESHOLD) { // LĄDOWANIE
        if (currentAirTime >= MIN_AIR_TIME) {
          // Calculate Average Power
          if (powerSampleCount > 0)
            avgPower = sumPower / powerSampleCount;
          else
            avgPower = 0;

          sendStatus(MSG_RESULT, currentAirTime, staticWeightRaw, peakPower);
          inAir = false;
          isReady = true;
          isIntegrating = false;
          landingTimeForLog = millis(); // Start 0.5s log
          delay(10);
        } else {
          inAir = false;
          isReady = true;
          isIntegrating = false;
        }
      } else if (currentAirTime > MAX_AIR_TIME) { // Timeout
        inAir = false;
        isReady = false;
        weightConfirmed = false;
        sendStatus(MSG_WAITING, 0, weight, 0);
      }
      return;
    }

    // SYTUACJA B: Spadek wagi poniżej progu
    if (weight < AIR_THRESHOLD) {
      if (isReady) {
        // Capture Takeoff Velocity BEFORE resetting or moving to air state
        lastTakeoffVelocity = currentVelocity;

        takeoffTime = millis();
        isReady = false;
        inAir = true;
        isIntegrating = false;

        // Finalize Avg Power (just in case we want the push phase avg)
        if (powerSampleCount > 0)
          avgPower = sumPower / powerSampleCount;
        else
          avgPower = 0;

        sendStatus(MSG_IN_AIR, 0, weight, peakPower);
      } else {
        if (weightConfirmed) {
          weightConfirmed = false;
          jumperMassKg = 0;
        }
        isReady = false;
        isIntegrating = false;
        calibrationStartTime = 0;
      }
    }
    // SYTUACJA C: Waga powyżej progu (Ktoś stoi)
    else {
      // 1. Czy mamy ustaloną masę?
      if (!weightConfirmed) {
        if (calibrationStartTime == 0) {
          calibrationStartTime = millis();
          calibrationSum = 0;
          calibrationCount = 0;
          calibrationMin = 20000000;
          calibrationMax = -20000000;
        }

        calibrationSum += weight;
        calibrationCount++;

        if (weight < calibrationMin)
          calibrationMin = weight;
        if (weight > calibrationMax)
          calibrationMax = weight;

        if (millis() - calibrationStartTime >= 1000) {
          long noiseRaw = calibrationMax - calibrationMin;
          float noiseKg = noiseRaw / rawPerKg; // USE VARIABLE

          if (noiseKg <= STABILITY_TOLERANCE_KG) {
            if (calibrationCount > 0) {
              staticWeightRaw = (long)(calibrationSum / calibrationCount);
              jumperMassKg = staticWeightRaw / rawPerKg; // USE VARIABLE
              weightConfirmed = true;
              isReady = true;
              sendStatus(MSG_READY, 0, staticWeightRaw, 0);
            }
            calibrationStartTime = 0;
          } else {
            calibrationStartTime = 0;
          }
        }
      }
      // 2. Mamy masę
      else {
        isReady = true;
        if (!isIntegrating) {
          if (abs(weight - staticWeightRaw) > MOVEMENT_THRESHOLD) {
            isIntegrating = true;
            integrationStartTime = millis();
            lastIntegrationMicros = nowMicros;
            currentVelocity = 0;
            peakPower = 0;
            sumPower = 0;         // Reset
            powerSampleCount = 0; // Reset
            avgPower = 0;         // Reset
          }
        } else {
          processPhysics(weight, nowMicros);
          if (millis() - integrationStartTime > MAX_PROPULSION_TIME_MS) {
            isIntegrating = false;
            currentVelocity = 0;
            peakPower = 0;
            sumPower = 0;
            powerSampleCount = 0;
          }
        }
      }
    }
  }
}