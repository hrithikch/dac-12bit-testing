// Unified DAC demo / experimentation firmware
//
// Source-of-truth decisions used for this merge:
// - DAC pattern-control pins come from sine_din_h.ino
// - CS1..CS5 rail-control pins come from Arduino_DAC_control_sketch.ino
// - Existing rail-control serial protocol is preserved
// - Sine generation / loading logic is exposed as serial commands instead of auto-running in loop()

#include <Arduino.h>
#include <Ina219Rails.h>
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_DotStar.h>
#include <math.h>

// Define pins for ItsyBitsy M0 DotStar
#define DOTSTAR_DATA 41
#define DOTSTAR_CLK  40
#define NUMPIXELS  1

Adafruit_DotStar strip(NUMPIXELS, DOTSTAR_DATA, DOTSTAR_CLK, DOTSTAR_BGR);

static RailStatus sts[INA219RAILS_MAX_BATCH];

// Onboard LED pin
#define led_pin 13

// DAC control pins from sine_din_h.ino (authoritative per user)
#define SPI_DOUT 10
#define DIN_PAT 9
#define SPI_SCK_PAT 1
#define SPI_SCAN 12
#define EN_PAT 7
#define WR_PAT 13
#define SPI_CP 11
#define SEL_EXT_DIN 5

// Chip select pin definitions from Arduino_DAC_control_sketch.ino
#define CS1   15
#define CS2   16
#define CS3   17
#define CS4   18
#define CS5   19

#define USB_BAUD_RATE 115200
#define CLK_DELAY_US 1
#define BITS_PER_WORD 12
#define DAC_NUM_SAMPLES 256

static const uint32_t DAC_CONTROL_WORD = 0x01586;

INA219_Rail rails[] = {
  { "AVDD",   0x40, &Wire,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS4, 255, 10,
    DRIVE_POT, 0, 0,
    15000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    0.100f,   0.335f, 0.402f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },
  { "AVDD0P85",   0x41, &Wire,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS2, 255, 10,
    DRIVE_POT, 0, 0,
    15000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    0.100f,  0.250f, 0.300f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },
  { "AVDD18", 0x42, &Wire,
    1.0f, 2.0f, 0.005f, 0.001f, 0.0f,
    CS3, 255, 10,
    DRIVE_POT, 0, 0,
    15000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    0.100f,  0.0022f, 0.00264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },
  { "VCM",  0x43, &Wire,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS5, 255, 10,
    DRIVE_POT, 0, 0,
    15000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    0.100f,  0.0022f, 0.00264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },
  { "DVDD",   0x44, &Wire,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS1, 255, 10,
    DRIVE_POT, 0, 0,
    15000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    0.05f,   0.335f, 0.402f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  }
};

const size_t RAIL_COUNT = sizeof(rails) / sizeof(rails[0]);

struct ADCconstants {
  const char* name;
  size_t pin;
};

const ADCconstants constants[] = {
  {"A0", A0},
  {"A1", A1},
  {"A2", A2},
  {"A3", A3},
  {"A4", A4},
  {"A5", A5}
};

void sendStatuses(const RailStatus* sts, uint8_t n);
void sendBits(uint32_t data, uint8_t numBits);
void sendDataBitsLSB(uint32_t data, uint8_t numBits);
void loadSinePattern(double fOut, double fSample);

void setup() {
  strip.begin();
  strip.setBrightness(30);
  strip.show();

  Serial.begin(USB_BAUD_RATE);

  pinMode(led_pin, OUTPUT);

  pinMode(SPI_DOUT, INPUT_PULLDOWN);
  pinMode(DIN_PAT, OUTPUT);
  pinMode(SPI_SCK_PAT, OUTPUT);
  pinMode(SPI_SCAN, OUTPUT);
  pinMode(EN_PAT, OUTPUT);
  pinMode(WR_PAT, OUTPUT);
  pinMode(SPI_CP, OUTPUT);
  pinMode(SEL_EXT_DIN, OUTPUT);

  pinMode(CS1, OUTPUT);
  pinMode(CS2, OUTPUT);
  pinMode(CS3, OUTPUT);
  pinMode(CS4, OUTPUT);
  pinMode(CS5, OUTPUT);

  digitalWrite(led_pin, LOW);
  digitalWrite(DIN_PAT, LOW);
  digitalWrite(SPI_SCK_PAT, LOW);
  digitalWrite(SPI_SCAN, LOW);
  digitalWrite(EN_PAT, LOW);
  digitalWrite(WR_PAT, LOW);
  digitalWrite(SPI_CP, LOW);
  digitalWrite(SEL_EXT_DIN, LOW);

  digitalWrite(CS1, HIGH);
  digitalWrite(CS2, HIGH);
  digitalWrite(CS3, HIGH);
  digitalWrite(CS4, HIGH);
  digitalWrite(CS5, HIGH);

  gCalDebug = false;
  gNbDebug  = false;

  beginAllRails();
  resetAllComplianceToDefault();
}

void loop() {
  char cmd_char[192];
  String split_cmd[40];

  if (Serial.available() <= 0) {
    return;
  }

  String cmd = Serial.readString();
  cmd.trim();
  cmd.toCharArray(cmd_char, sizeof(cmd_char));

  uint8_t count = 0;
  char *p = strtok(cmd_char, ",");
  while (p && count < (sizeof(split_cmd) / sizeof(split_cmd[0]))) {
    split_cmd[count++] = p;
    p = strtok(NULL, ",");
  }
  if (count == 0) {
    return;
  }

  if (split_cmd[0] == "LDO_WRITE") {
    bool ok = writeRailPotRawByName(split_cmd[1].c_str(), split_cmd[2].toInt());
    Serial.write((byte*)&ok, 1);
    return;
  }

  if (split_cmd[0] == "SET_VOLTAGE") {
    RailSetReq batch[32];
    for (size_t i = 1; i < count; i = i + 2) {
      batch[(i - 1) / 2].name = split_cmd[i].c_str();
      batch[(i - 1) / 2].V = atof(split_cmd[i + 1].c_str());
    }
    const size_t N = (count - 1) / 2;
    setRailsVoltageParallelByName(batch, N, sts);
    sendStatuses(sts, (uint8_t)N);
    return;
  }

  if (split_cmd[0] == "INITIALIZE_COMPLIANCE") {
    resetAllComplianceToDefault();
    bool ok = true;
    Serial.write((byte*)&ok, 1);
    return;
  }

  if (split_cmd[0] == "SET_COMPLIANCE") {
    bool ok = setRailCompliance_mA(split_cmd[1].c_str(), atof(split_cmd[2].c_str()));
    Serial.write((byte*)&ok, 1);
    return;
  }

  if (split_cmd[0] == "READ_ADC") {
    bool found = false;
    size_t adcpin = A0;
    for (size_t k = 0; k < sizeof(constants) / sizeof(constants[0]); ++k) {
      if (split_cmd[1] == constants[k].name) {
        adcpin = constants[k].pin;
        found = true;
        break;
      }
    }
    if (!found) {
      uint16_t zero = 0;
      Serial.write((uint8_t*)&zero, sizeof(zero));
      return;
    }
    uint16_t analogValue = (uint16_t)analogRead(adcpin);
    Serial.write((uint8_t*)&analogValue, sizeof(analogValue));
    return;
  }

  if (split_cmd[0] == "READ_VOLTAGE") {
    float busvoltage = -1.0f;
    int railnum = findRailIndex(split_cmd[1].c_str());
    if (railnum != -1) {
      INA219_Rail &r = rails[railnum];
      busvoltage = getRailBusVoltage_V(r.name);
    }
    Serial.write((byte*)&busvoltage, 4);
    return;
  }

  if (split_cmd[0] == "READ_SHUNTV") {
    float shuntvoltage = -1.0f;
    int railnum = findRailIndex(split_cmd[1].c_str());
    if (railnum != -1) {
      INA219_Rail &r = rails[railnum];
      shuntvoltage = getRailShuntVoltage_mV(r.name);
    }
    Serial.write((byte*)&shuntvoltage, 4);
    return;
  }

  if (split_cmd[0] == "READ_CURRENT") {
    float current_mA = -1.0f;
    int railnum = findRailIndex(split_cmd[1].c_str());
    if (railnum != -1) {
      INA219_Rail &r = rails[railnum];
      current_mA = getRailCurrent_mA(r.name);
    }
    Serial.write((byte*)&current_mA, 4);
    return;
  }

  if (split_cmd[0] == "READ_POWER") {
    float power_mW = -1.0f;
    int railnum = findRailIndex(split_cmd[1].c_str());
    if (railnum != -1) {
      INA219_Rail &r = rails[railnum];
      power_mW = getRailPower_mW(r.name);
    }
    Serial.write((byte*)&power_mW, 4);
    return;
  }

  if (split_cmd[0] == "DIO_ON") {
    digitalWrite(split_cmd[1].toInt(), HIGH);
    bool ok = true;
    Serial.write((byte*)&ok, 1);
    return;
  }

  if (split_cmd[0] == "DIO_OFF") {
    digitalWrite(split_cmd[1].toInt(), LOW);
    bool ok = true;
    Serial.write((byte*)&ok, 1);
    return;
  }

  if (split_cmd[0] == "ON") {
    strip.setPixelColor(0, 0, 0, 255);
    strip.show();
    bool ok = true;
    Serial.write((byte*)&ok, 1);
    return;
  }

  if (split_cmd[0] == "OFF") {
    strip.setPixelColor(0, 0, 0, 0);
    strip.show();
    bool ok = true;
    Serial.write((byte*)&ok, 1);
    return;
  }

  if (split_cmd[0] == "DAC_DISABLE_PATTERN") {
    digitalWrite(EN_PAT, LOW);
    bool ok = true;
    Serial.write((byte*)&ok, 1);
    return;
  }

  if (split_cmd[0] == "DAC_ENABLE_PATTERN") {
    digitalWrite(EN_PAT, HIGH);
    bool ok = true;
    Serial.write((byte*)&ok, 1);
    return;
  }

  if (split_cmd[0] == "DAC_LOAD_SINE") {
    loadSinePattern(atof(split_cmd[1].c_str()), atof(split_cmd[2].c_str()));
    bool ok = true;
    Serial.write((byte*)&ok, 1);
    return;
  }

  if (split_cmd[0] == "DAC_PLAY_SINE") {
    loadSinePattern(atof(split_cmd[1].c_str()), atof(split_cmd[2].c_str()));
    digitalWrite(EN_PAT, HIGH);
    bool ok = true;
    Serial.write((byte*)&ok, 1);
    return;
  }

  bool ok = false;
  Serial.write((byte*)&ok, 1);
}

void sendStatuses(const RailStatus* sts, uint8_t n) {
  const uint8_t SOF0 = 0xAA;
  const uint8_t SOF1 = 0x55;
  Serial.write(SOF0);
  Serial.write(SOF1);
  Serial.write(n);
  Serial.write(reinterpret_cast<const uint8_t*>(sts), n);
  uint8_t x = 0;
  for (uint8_t i = 0; i < n; i++) {
    x ^= static_cast<uint8_t>(sts[i]);
  }
  Serial.write(x);
}

void sendBits(uint32_t data, uint8_t numBits) {
  digitalWrite(SPI_SCAN, HIGH);
  delay(10);
  for (int j = numBits - 1; j >= 0; j--) {
    digitalWrite(SPI_SCK_PAT, LOW);
    digitalWrite(DIN_PAT, (data >> j) & 0x01);
    digitalWrite(SPI_SCK_PAT, HIGH);
    delayMicroseconds(CLK_DELAY_US);
  }
  delay(10);
  digitalWrite(SPI_SCAN, LOW);
}

void sendDataBitsLSB(uint32_t data, uint8_t numBits) {
  for (int j = 0; j < numBits; j++) {
    digitalWrite(SPI_SCK_PAT, LOW);
    digitalWrite(DIN_PAT, (data >> j) & 0x01);
    delayMicroseconds(CLK_DELAY_US);
    digitalWrite(SPI_SCK_PAT, HIGH);
    delayMicroseconds(CLK_DELAY_US);
  }
}

void loadSinePattern(double fOut, double fSample) {
  uint32_t data_sine[DAC_NUM_SAMPLES];
  const double M = (fOut * DAC_NUM_SAMPLES) / fSample;

  for (int k = 0; k < DAC_NUM_SAMPLES; k++) {
    data_sine[k] = (uint32_t)(round(2047.5 * sin(2.0 * PI * M * k / (double)DAC_NUM_SAMPLES) + 2047.5));
  }

  digitalWrite(SPI_CP, LOW);
  digitalWrite(SEL_EXT_DIN, LOW);
  digitalWrite(WR_PAT, LOW);
  digitalWrite(EN_PAT, LOW);

  sendBits(DAC_CONTROL_WORD, 20);

  digitalWrite(WR_PAT, HIGH);
  delay(10);

  for (int k = 0; k < DAC_NUM_SAMPLES; k++) {
    sendDataBitsLSB(data_sine[k], BITS_PER_WORD);
  }

  digitalWrite(WR_PAT, LOW);
  delay(100);
}
