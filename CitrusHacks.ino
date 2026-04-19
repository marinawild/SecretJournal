#include <LiquidCrystal.h>
#include <Stepper.h>

// ---------------- LCD ----------------
LiquidCrystal lcd(7, 6, 9, 10, 11, 12);

// ---------------- Stepper ----------------
#define STEPS_PER_REV 2048
Stepper stepper(STEPS_PER_REV, 2, 4, 3, 5);

// ---------------- Button ----------------
#define BUTTON_PIN A0
#define GREEN_LED A1
#define RED_LED A2

unsigned long lastBlink = 0;
bool ledState = false;

unsigned long blinkStartTime = 0;
bool blinkActive = false;

enum BlinkType { NONE, BLINK_GREEN, BLINK_RED };
BlinkType blinkType = NONE;
const int THRESHOLD = 500;

// ---------------- State ----------------
enum State { LOCKED, UNLOCKED };
State state = LOCKED;

// ---------------- Button tracking ----------------
bool lastPressed = false;

// ---------------- VERIFY timeout ----------------
unsigned long verifyStart = 0;
bool waitingVerify = false;
const unsigned long VERIFY_TIMEOUT = 500000;  

// ---------------- Serial buffer ----------------
String input = "";

// ---------------- Setup ----------------
void setup() {
  Serial.begin(115200);

  pinMode(BUTTON_PIN, INPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);

  lcd.begin(16, 2);
  lcd.print("Booting...");

  stepper.setSpeed(10);

  delay(2000);

  lcd.clear();
  lcd.print("LOCKED");

  Serial.println("READY");
}

// ---------------- Main loop ----------------
void loop() {
  handleSerial();
  handleButton();
  handleTimeout();
  updateLEDs();
}

// ---------------- Button ----------------
void handleButton() {
  int val = analogRead(BUTTON_PIN);
  bool pressed = val > THRESHOLD;

  if (pressed && !lastPressed) {

    Serial.print("BTN ADC: ");
    Serial.println(val);

    if (state == LOCKED && !waitingVerify) {
      Serial.println("VERIFY");

      lcd.clear();
      lcd.print("Verifying...");

      waitingVerify = true;
      verifyStart = millis();
    }

    else if (state == UNLOCKED) {
      lockSystem();
    }
  }

  lastPressed = pressed;
}

// ---------------- Serial handling ----------------
void handleSerial() {
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n') {
      handleCommand(input);
      input = "";
    } else {
      input += c;
    }
  }
}

// ---------------- Command handler ----------------
void handleCommand(String cmd) {
  cmd.trim();

  Serial.print("RX: ");
  Serial.println(cmd);

  // ---------------- SUCCESS ----------------
  if (cmd == "UNLOCK") {
    waitingVerify = false;
    unlockSystem();
  }

  // ---------------- FAILURE (NEW) ----------------
  else if (cmd == "REJECT") {
    Serial.println("ACCESS DENIED");

    waitingVerify = false;

    lcd.clear();
    lcd.print("Denied");

    delay(1000);

    resetToLocked();
  }
}

// ---------------- Timeout ----------------
void handleTimeout() {
  if (waitingVerify && millis() - verifyStart > VERIFY_TIMEOUT) {
    waitingVerify = false;

    Serial.println("VERIFY_TIMEOUT");

    lcd.clear();
    lcd.print("Timeout");

    delay(1000);

    resetToLocked();
  }
}

// ---------------- Unlock ----------------
void unlockSystem() {
  state = UNLOCKED;

  lcd.clear();
  lcd.print("Welcome");

  stepper.step(2000);

  Serial.println("OK UNLOCKED");

  startBlink(BLINK_GREEN);
}

// ---------------- Lock ----------------
void lockSystem() {
  resetToLocked();

  stepper.step(-2000);

  Serial.println("OK LOCKED");

  startBlink(BLINK_RED);
}

// ---------------- Reset state ----------------
void resetToLocked() {
  state = LOCKED;
  waitingVerify = false;

  lcd.clear();
  lcd.print("LOCKED");

  digitalWrite(GREEN_LED, LOW);
  digitalWrite(RED_LED, HIGH);

  startBlink(BLINK_RED);
}

// ---------------- Blink LED ----------------
void updateLEDs() {
  if (!blinkActive) {
    digitalWrite(GREEN_LED, LOW);
    digitalWrite(RED_LED, LOW);
    return;
  }

  // stop blinking after 5 seconds
  if (millis() - blinkStartTime > 5000) {
    blinkActive = false;
    digitalWrite(GREEN_LED, LOW);
    digitalWrite(RED_LED, LOW);
    return;
  }

  // blinking logic
  bool state = (millis() / 400) % 2;

  if (blinkType == BLINK_GREEN) {
    digitalWrite(GREEN_LED, state);
    digitalWrite(RED_LED, LOW);
  }

  else if (blinkType == BLINK_RED) {
    digitalWrite(RED_LED, state);
    digitalWrite(GREEN_LED, LOW);
  }
}
void startBlink(BlinkType type) {
  blinkType = type;
  blinkActive = true;
  blinkStartTime = millis();
}