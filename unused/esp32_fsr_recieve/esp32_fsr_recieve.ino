#include <TFT_eSPI.h>
#include <WiFi.h>
#include <esp_now.h>

#define TFT_BL 4
#define BTN_OK 35
#define BTN_NAV 0

// --- CHANGED: Variable instead of Macro ---
float calibrationFactor = 13000.0;

TFT_eSPI tft = TFT_eSPI(135, 240);

// Enum updated: Added MODE_CALIBRATION
enum AppMode {
  MODE_MENU,
  MODE_CONTINUOUS,
  MODE_CONTINUOUS_SUMMARY,
  MODE_DATA,
  MODE_DEBUG,
  MODE_CALIBRATION
};
AppMode currentMode = MODE_MENU;
int menuCursor = 0;

// Update MessageType with Calibration codes
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

struct_message incomingData;
struct_message outboundCmd;

volatile bool newData = false;
bool resultLocked = false;
int dataModePage = 0;

uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
esp_now_peer_info_t peerInfo;

struct PhysicsData {
  unsigned long timeMs;
  float height;
  float velocity;
  float physicsPower;
  float physicsAvgPower;
  float formulaPower;
  float formulaAvgPower;
  float bodyMassKg;
  float relPower;
  float impulseHeight;   // NEW
  float impulseVelocity; // NEW
} lastJump;

// Continuous Stats
int contJumpCount = 0;
float contTotalHeight = 0;
unsigned long lastLandTimestamp = 0;
float contTotalContactTime = 0;
float contMinContactTime = 9999.0;
int contContactCount = 0;
float tempContactTime = 0;

// Function Declarations
void drawMenu();
void showWaitingScreen(String modeName);
void showDataResultPage1();
void showDataResultPage2();
void showDataResultPage3(); // NEW
void showReadyScreen();
void showJumpingScreen();
void showContinuousActiveJump(int n, bool fly, float h);
void showContinuousSummary();
void showDebugScreen(long load, float hz);
void showCalibrationScreen(String status, String val);
void showResetSendingScreen();
float calculateHeight(unsigned long timeMs);
void resetContinuousStats();
void processContinuousMode();
void processDataMode();
void processDebugMode();
void processCalibrationMode();
void sendResetCommand();
void sendCalibrationStart();
void handleButtons();
void goToSleep();

void OnDataRecv(const uint8_t *mac, const uint8_t *incomingBytes, int len) {
  if (len == sizeof(incomingData)) {
    memcpy(&incomingData, incomingBytes, sizeof(incomingData));
    newData = true;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BTN_OK, INPUT_PULLUP);
  pinMode(BTN_NAV, INPUT_PULLUP);
  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, HIGH);

  tft.init();
  tft.setRotation(3);
  tft.fillScreen(TFT_BLACK);
  esp_sleep_enable_ext0_wakeup(GPIO_NUM_0, 0);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  if (esp_now_init() != ESP_OK) {
    tft.fillScreen(TFT_RED);
    tft.drawString("ESP-NOW ERROR", 120, 67);
    while (1)
      ;
  }

  esp_now_register_recv_cb((esp_now_recv_cb_t)OnDataRecv);

  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  esp_now_add_peer(&peerInfo);

  drawMenu();
}

void sendResetCommand() {
  outboundCmd.msgType = MSG_CMD_RESET;
  outboundCmd.flightTime = 0;
  outboundCmd.currentLoad = 0;
  outboundCmd.calculatedWatts = 0;
  esp_now_send(broadcastAddress, (uint8_t *)&outboundCmd, sizeof(outboundCmd));
  showResetSendingScreen();
  drawMenu();
}

void sendCalibrationStart() {
  outboundCmd.msgType = MSG_CAL_START;
  outboundCmd.flightTime = 0;
  outboundCmd.currentLoad = 0;
  outboundCmd.calculatedWatts = 0;
  esp_now_send(broadcastAddress, (uint8_t *)&outboundCmd, sizeof(outboundCmd));
}

void showResetSendingScreen() {
  tft.fillScreen(TFT_RED);
  tft.setTextColor(TFT_WHITE, TFT_RED);
  tft.setTextDatum(MC_DATUM);
  tft.drawString("RESET!", 120, 67);
  delay(1000);
}

void loop() {
  handleButtons();
  if (newData) {
    newData = false;
    if (currentMode == MODE_CONTINUOUS)
      processContinuousMode();
    else if (currentMode == MODE_DATA)
      processDataMode();
    else if (currentMode == MODE_DEBUG)
      processDebugMode();
    else if (currentMode == MODE_CALIBRATION)
      processCalibrationMode();
  }
}

void goToSleep() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("WYLACZANIE...", 120, 67);
  delay(1000);
  digitalWrite(TFT_BL, LOW);
  tft.writecommand(TFT_DISPOFF);
  esp_deep_sleep_start();
}

void handleButtons() {
  if (digitalRead(BTN_OK) == LOW && digitalRead(BTN_NAV) == LOW) {
    goToSleep();
    return;
  }

  static unsigned long lastPress = 0;
  if (millis() - lastPress < 200)
    return;

  bool btnNavPressed = (digitalRead(BTN_NAV) == LOW);
  bool btnOkPressed = (digitalRead(BTN_OK) == LOW);
  if (btnNavPressed || btnOkPressed)
    lastPress = millis();
  else
    return;

  if (currentMode == MODE_MENU) {
    if (btnNavPressed) {
      menuCursor++;
      if (menuCursor > 3)
        menuCursor = 0;
      drawMenu(); // Increased to 3 options (0-3)
    } else if (btnOkPressed) {
      if (menuCursor == 0) {
        currentMode = MODE_DATA;
        resultLocked = false;
        dataModePage = 0;
        showWaitingScreen("SINGLE JUMP");
      } else if (menuCursor == 1) {
        currentMode = MODE_CONTINUOUS;
        resetContinuousStats();
        showWaitingScreen("CONTINUOUS");
      } else if (menuCursor == 2) {
        currentMode = MODE_DEBUG;
        showDebugScreen(0, 0);
      } else if (menuCursor == 3) {
        currentMode = MODE_CALIBRATION;
        sendCalibrationStart();
        showCalibrationScreen("Inicjacja...", "");
      }
    }
  } else if (currentMode == MODE_DEBUG) {
    if (btnOkPressed) {
      sendResetCommand();
      currentMode = MODE_MENU;
      drawMenu();
    } else if (btnNavPressed) {
      currentMode = MODE_MENU;
      drawMenu();
    }
  } else if (currentMode == MODE_CALIBRATION) {
    if (btnNavPressed) {
      currentMode = MODE_MENU;
      drawMenu();
    }
  } else {
    // RESULT MODE NAVIGATION
    if (btnNavPressed) {
      currentMode = MODE_MENU;
      resultLocked = false;
      drawMenu();
    } else if (btnOkPressed) {
      if (currentMode == MODE_DATA && resultLocked) {
        // CYCLE PAGE 0 -> 1 -> 2 -> 0
        if (dataModePage == 0) {
          dataModePage = 1;
          showDataResultPage2();
        } else if (dataModePage == 1) {
          dataModePage = 2;
          showDataResultPage3();
        } else {
          resultLocked = false;
          dataModePage = 0;
          showWaitingScreen("SINGLE JUMP");
        }
      } else if (resultLocked) {
        resultLocked = false;
        showWaitingScreen("...");
      }

      if (currentMode == MODE_CONTINUOUS_SUMMARY) {
        resetContinuousStats();
        currentMode = MODE_CONTINUOUS;
        showWaitingScreen("CONTINUOUS");
      }
    }
  }
}

void processCalibrationMode() {
  if (incomingData.msgType == MSG_CAL_WAIT_WEIGHT) {
    showCalibrationScreen("POLOZ 15KG", "Czekam na wage...");
  } else if (incomingData.msgType == MSG_CAL_MEASURING) {
    showCalibrationScreen("MIERZENIE...", "Nie ruszac!");
  } else if (incomingData.msgType == MSG_CAL_DONE) {
    calibrationFactor =
        incomingData.calculatedWatts; // Using this field for factor transfer
    showCalibrationScreen("GOTOWE!", "F: " + String((int)calibrationFactor));
    delay(2000);
    currentMode = MODE_MENU;
    drawMenu(); // Back to menu automatically
  } else if (incomingData.msgType == MSG_CAL_ERROR) {
    showCalibrationScreen("BLAD!", "Sponuj ponownie");
  } else if (incomingData.msgType == MSG_CMD_RESET) {
    currentMode = MODE_MENU;
    drawMenu();
  }
}

void showCalibrationScreen(String status, String val) {
  tft.fillScreen(TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(3);
  tft.drawString(status, 120, 50);
  tft.setTextSize(2);
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.drawString(val, 120, 90);

  tft.setTextSize(1);
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.drawString("NAV: ANULUJ", 120, 125);
}

void processDebugMode() {
  showDebugScreen(incomingData.currentLoad, incomingData.calculatedWatts);
}

void processDataMode() {
  if (resultLocked)
    return;
  if (incomingData.msgType == MSG_RESULT) {
    resultLocked = true;
    dataModePage = 0;
    lastJump.timeMs = incomingData.flightTime;
    lastJump.height = calculateHeight(lastJump.timeMs);
    lastJump.velocity = sqrt(2 * 9.81 * (lastJump.height / 100.0));

    // NEW: Impulse Based Calculations
    lastJump.impulseVelocity = incomingData.takeoffVelocity;
    // H = v^2 / 2g
    lastJump.impulseHeight =
        (lastJump.impulseVelocity * lastJump.impulseVelocity) / (2 * 9.81) *
        100.0; // cm

    lastJump.bodyMassKg =
        incomingData.currentLoad / calibrationFactor; // USE VARIABLE
    if (lastJump.bodyMassKg < 1)
      lastJump.bodyMassKg = 1;
    lastJump.physicsPower = incomingData.calculatedWatts;

    // Harman Formula Avg Power: 21.2 * Jump Height (cm) + 23.0 * Body Mass (kg)
    // - 1393
    lastJump.formulaAvgPower =
        (21.2 * lastJump.height) + (23.0 * lastJump.bodyMassKg) - 1393;
    if (lastJump.formulaAvgPower < 0)
      lastJump.formulaAvgPower = 0;

    // Sayers Formula Peak Power: 60.7 * Height + 45.3 * Mass - 2055
    lastJump.formulaPower =
        (60.7 * lastJump.height) + (45.3 * lastJump.bodyMassKg) - 2055;
    if (lastJump.formulaPower < 0)
      lastJump.formulaPower = 0;

    // Measured Avg Power (Physics)
    lastJump.physicsAvgPower = incomingData.physicsAvgPower;

    lastJump.relPower = lastJump.physicsPower / lastJump.bodyMassKg;
    showDataResultPage1();
  } else if (incomingData.msgType == MSG_READY)
    showReadyScreen();
  else if (incomingData.msgType == MSG_IN_AIR)
    showJumpingScreen();
}

void showDebugScreen(long load, float hz) {
  tft.fillScreen(TFT_BLACK);
  float kg = load / calibrationFactor;
  tft.setTextDatum(TC_DATUM);
  tft.setTextColor(TFT_ORANGE, TFT_BLACK);
  tft.setTextSize(2);
  tft.drawString("DEBUG MODE", 120, 5);
  tft.setTextSize(1);
  tft.setTextColor(TFT_RED, TFT_BLACK);
  tft.drawString("BTN OK = RESET SENDER", 120, 25);
  tft.drawLine(0, 35, 240, 35, TFT_BLUE);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(4);
  tft.drawFloat(kg, 2, 120, 65);
  tft.setTextSize(2);
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.drawString("kg", 200, 80);
  tft.setTextSize(2);
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.drawString("Raw: " + String(load), 120, 100);
  tft.setTextColor(TFT_GREEN, TFT_BLACK);
  tft.drawString("Rate: " + String((int)hz) + " Hz", 120, 125);
}

void showDataResultPage1() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextDatum(TR_DATUM);
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.setTextSize(1);
  tft.drawString("1/3", 235, 5); // 1/3
  tft.setTextDatum(TC_DATUM);
  tft.setTextColor(TFT_GREEN, TFT_BLACK);
  tft.setTextSize(4);
  tft.drawFloat(lastJump.height, 1, 120, 5);
  tft.setTextSize(2);
  tft.drawString("cm", 200, 20);
  tft.drawLine(0, 40, 240, 40, TFT_BLUE);
  tft.setTextSize(2);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.drawString("Flight Time", 60, 60);
  tft.setTextColor(TFT_MAGENTA, TFT_BLACK);
  tft.drawNumber(lastJump.timeMs, 60, 80);
  tft.setTextSize(1);
  tft.drawString("ms", 95, 85);
  tft.setTextSize(2);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("Peak Power", 180, 60);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.drawNumber((int)lastJump.physicsPower, 180, 80);
  tft.setTextSize(1);
  tft.drawString("W", 215, 85);
  tft.setTextSize(2);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("Rel Pwr", 60, 105);
  tft.setTextColor(TFT_ORANGE, TFT_BLACK);
  tft.drawFloat(lastJump.relPower, 1, 60, 125);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("Mass", 180, 105);
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.drawFloat(lastJump.bodyMassKg, 1, 180, 125);
  tft.setTextDatum(BR_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(1);
  tft.drawString("OK >", 235, 130);
}

void showDataResultPage2() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextDatum(TR_DATUM);
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.setTextSize(1);
  tft.drawString("2/3", 235, 5); // 2/3
  tft.setTextDatum(TC_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  tft.drawString("MOC (W)", 120, 10);
  tft.drawLine(0, 30, 240, 30, TFT_BLUE);

  // Header
  tft.setTextSize(1);
  tft.setTextColor(TFT_LIGHTGREY, TFT_BLACK);
  tft.drawString("TYPE", 20, 45);
  tft.drawString("FORMULA", 100, 45);
  tft.drawString("PHYSICS", 180, 45);

  // Peak Row
  int y = 65;
  tft.setTextSize(2);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("PEAK", 40, y);
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.drawString(String((int)lastJump.formulaPower), 120, y);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.drawString(String((int)lastJump.physicsPower), 200, y);

  // Avg Row
  y += 35;
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("AVG", 40, y);
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.drawString(String((int)lastJump.formulaAvgPower), 120, y);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.drawString(String((int)lastJump.physicsAvgPower), 200, y);

  tft.setTextDatum(BR_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("OK >", 235, 130);
}

void showDataResultPage3() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextDatum(TR_DATUM);
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.setTextSize(1);
  tft.drawString("3/3", 235, 5);
  tft.setTextDatum(TC_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  tft.drawString("IMPULS vs CZAS", 120, 10);
  tft.drawLine(0, 30, 240, 30, TFT_BLUE);

  // Header
  tft.setTextSize(1);
  tft.setTextColor(TFT_LIGHTGREY, TFT_BLACK);
  tft.drawString("METRIC", 30, 45);
  tft.drawString("TIME", 110, 45);
  tft.drawString("FORCE", 190, 45);

  // Height Row
  int y = 65;
  tft.setTextSize(2);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("H (cm)", 30, y);
  tft.setTextColor(TFT_MAGENTA, TFT_BLACK);
  tft.drawFloat(lastJump.height, 1, 110, y);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.drawFloat(lastJump.impulseHeight, 1, 190, y);

  // Velocity Row
  y += 35;
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("V (m/s)", 30, y);
  tft.setTextColor(TFT_MAGENTA, TFT_BLACK);
  tft.drawFloat(lastJump.velocity, 2, 110, y);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.drawFloat(lastJump.impulseVelocity, 2, 190, y);

  tft.setTextDatum(BC_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("[OK] RESET", 120, 130);
}

float calculateHeight(unsigned long timeMs) {
  return (9.81 * (timeMs / 1000.0) * (timeMs / 1000.0)) / 8.0 * 100.0;
}

void drawMenu() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextSize(2);
  tft.setTextDatum(TC_DATUM);
  tft.setTextColor(TFT_ORANGE, TFT_BLACK);
  tft.drawString("MENU GLOWNE", 120, 5);
  tft.setTextDatum(ML_DATUM);
  int y = 35;
  int dy = 25;
  tft.setTextColor(menuCursor == 0 ? TFT_BLACK : TFT_WHITE,
                   menuCursor == 0 ? TFT_WHITE : TFT_BLACK);
  tft.drawString("1. Single Jump", 20, y);
  tft.setTextColor(menuCursor == 1 ? TFT_BLACK : TFT_WHITE,
                   menuCursor == 1 ? TFT_WHITE : TFT_BLACK);
  tft.drawString("2. Continuous", 20, y + dy);
  tft.setTextColor(menuCursor == 2 ? TFT_BLACK : TFT_WHITE,
                   menuCursor == 2 ? TFT_WHITE : TFT_BLACK);
  tft.drawString("3. Debug View", 20, y + dy * 2);
  tft.setTextColor(menuCursor == 3 ? TFT_BLACK : TFT_WHITE,
                   menuCursor == 3 ? TFT_WHITE : TFT_BLACK);
  tft.drawString("4. Kalibracja", 20, y + dy * 3);
}

void showWaitingScreen(String modeName) {
  tft.fillScreen(TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.setTextSize(2);
  tft.drawString(modeName, 120, 20);
  tft.setTextSize(3);
  tft.drawString("WEJDZ", 120, 60);
  tft.drawString("NA MATE", 120, 95);
}
void showReadyScreen() {
  tft.fillScreen(TFT_GREEN);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_BLACK, TFT_GREEN);
  tft.setTextSize(4);
  tft.drawString("GOTOWY!", 120, 67);
}
void showJumpingScreen() {
  tft.fillScreen(TFT_BLUE);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLUE);
  tft.setTextSize(4);
  tft.drawString("LOT...", 120, 67);
}

void showContinuousActiveJump(int n, bool fly, float h) {
  tft.fillScreen(TFT_BLACK);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.setTextSize(3);
  tft.drawString("Skok #" + String(n), 120, 30);
  if (fly) {
    tft.setTextColor(TFT_CYAN, TFT_BLACK);
    tft.setTextSize(3);
    tft.drawString("W gorze...", 120, 80);
  } else {
    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    tft.setTextSize(5);
    tft.drawFloat(h, 1, 120, 80);
    tft.setTextSize(2);
    tft.drawString("cm", 210, 95);
  }
}
void showContinuousSummary() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  tft.drawString("WYNIKI SERII:", 5, 5);
  tft.drawLine(0, 25, 240, 25, TFT_BLUE);
  float avgH = (contJumpCount > 0) ? (contTotalHeight / contJumpCount) : 0;
  float avgC =
      (contContactCount > 0) ? (contTotalContactTime / contContactCount) : 0;
  if (contMinContactTime > 100)
    contMinContactTime = 0;
  int y = 35, dy = 25;
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.drawString("Ilosc skokow: " + String(contJumpCount), 5, y);
  y += dy;
  tft.setTextColor(TFT_GREEN, TFT_BLACK);
  tft.drawString("Srednia Wys: " + String(avgH, 1) + " cm", 5, y);
  y += dy;
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.drawString("Min Kontakt: " + String(contMinContactTime, 3) + " s", 5, y);
  y += dy;
  tft.drawString("Sred Kontakt: " + String(avgC, 3) + " s", 5, y);
  tft.setTextDatum(MC_DATUM);
  tft.setTextColor(TFT_DARKGREY, TFT_BLACK);
  tft.setTextSize(1);
  tft.drawString("NAV: MENU  |  OK: RESET", 120, 128);
}

void resetContinuousStats() {
  contJumpCount = 0;
  contTotalHeight = 0;
  contTotalContactTime = 0;
  contMinContactTime = 9999.0;
  contContactCount = 0;
  lastLandTimestamp = 0;
}
void processContinuousMode() {
  unsigned long now = millis();
  if (incomingData.msgType == MSG_IN_AIR) {
    if (contJumpCount > 0 && lastLandTimestamp > 0)
      tempContactTime = (now - lastLandTimestamp) / 1000.0;
    showContinuousActiveJump(contJumpCount + 1, true, 0);
  } else if (incomingData.msgType == MSG_RESULT) {
    contJumpCount++;
    float h = calculateHeight(incomingData.flightTime);
    contTotalHeight += h;
    if (contJumpCount > 1) {
      contTotalContactTime += tempContactTime;
      if (tempContactTime < contMinContactTime)
        contMinContactTime = tempContactTime;
      contContactCount++;
    }
    lastLandTimestamp = millis();
    showContinuousActiveJump(contJumpCount, false, h);
  } else if (incomingData.msgType == MSG_WAITING) {
    if (contJumpCount > 0) {
      currentMode = MODE_CONTINUOUS_SUMMARY;
      showContinuousSummary();
    } else
      showWaitingScreen("CONTINUOUS");
  } else if (incomingData.msgType == MSG_READY && contJumpCount == 0)
    showReadyScreen();
}