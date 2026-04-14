// BasicUsage.ino
#include <Arduino.h>
#include <Ina219Rails.h>

// ====================== CS macros for THIS BOARD ============================
#define CS0   25
#define CS1   26
#define CS2   27
#define CS3   28
#define CS4   29
#define CS5   30
#define CS6   31
#define CS7   32
#define CS8   33
#define CS9   34
#define CS10  36
#define CS11  38
#define CS12  39
#define CS13  40
#define CS14  41
#define CS15  42
#define CS16  43
#define CS17  44

// ====================== rails[] table (owned by this sketch) ===============
INA219_Rail rails[] = {

  // -------- Wire, POT rails --------
  { "AVDD",   0x40, &Wire,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS0, 255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    0.05f,   0.335f, 0.402f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "FVDD",   0x41, &Wire,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS1, 255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    0.075f,  0.250f, 0.300f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "DVDD",   0x42, &Wire,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS2, 255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    0.05f,   0.487f, 0.5844f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "AVDD18", 0x43, &Wire,
    1.0f, 2.0f, 0.005f, 0.001f, 0.0f,
    CS3, 255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0022f, 0.00264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },
  { "VDDIO",  0x44, &Wire,
    1.0f, 2.0f, 0.005f, 0.001f, 0.0f,
    CS4, 255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0022f, 0.00264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "VDD_BUF",0x45, &Wire,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS5, 255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    0.150f, 0.128f, 0.1536f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "BVDD",   0x46, &Wire,
    0.5f, 1.5f, 0.005f, 0.001f, 0.0f,
    CS6, 255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    0.150f, 0.110f, 0.132f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "CLK_VCM",0x47, &Wire,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS7, 255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0004f, 0.00048f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "VIN_VCM",0x48, &Wire,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS8, 255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0004f, 0.00048f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  // -------- Wire1 rails --------
  { "VREFC_GATE",0x40, &Wire1,
    0.5f, 1.5f, 0.005f, 0.001f, 0.0f,
    CS9, 255, 10,
    DRIVE_POT, 0, 0,
    0UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.000040f, 0.0000264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "VREFF_GATE",0x41, &Wire1,
    0.25f, 1.25f, 0.005f, 0.001f, 0.0f,
    CS10, 255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0022f, 0.00264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "VREF",   0x44, &Wire1,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS13,255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0022f, 0.00264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "VBP",    0x45, &Wire1,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS14,255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0022f, 0.00264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "VBN",    0x46, &Wire1,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS15,255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0022f, 0.00264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "0.4V_CH",0x48, &Wire1,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS17,255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0022f, 0.00264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },
  // -------- Fine rails --------
  { "VTOP_FINE",0x42, &Wire1,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS11,255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0022f, 0.00264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "VBOT_FINE",0x43, &Wire,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS12,255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0022f, 0.00264f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  { "VTUNE12b",0x47, &Wire1,
    0.0f, 1.0f, 0.005f, 0.001f, 0.0f,
    CS17,255, 10,
    DRIVE_POT, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0011f, 0.00132f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    3
  },

  // -------- Measure-only rails --------
  { "VREFF",  0x49, &Wire1,
    0.0f, 1.5f, 0.005f, 0.001f, 0.0f,
    0, 0, 0,
    DRIVE_NONE, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0022f, 0.0f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    1
  },

  { "VREFC",  0x4A, &Wire1,
    0.0f, 1.5f, 0.005f, 0.001f, 0.0f,
    0, 0, 0,
    DRIVE_NONE, 0, 0,
    5000UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.0022f, 0.0f, 0.0f, 0.0f, 0,
    0, {0}, {0},
    1
  }
};

const size_t RAIL_COUNT = sizeof(rails) / sizeof(rails[0]);

static unsigned long lastPrint = 0;
void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) { }  // wait up to 3s for Serial Monitor
  delay(200);                              // small extra settle
  delay(2000);

  gCalDebug = true;    // show init + calibration summary
  gNbDebug  = true;    // show NB coarse/fine progress

  Serial.println(F("\n\n==== Rails + INA219 Parallel Batch Example ===="));

  RailStatus initStatus = beginAllRails();
  Serial.print(F("beginAllRails status = "));
  Serial.print((int)initStatus);
  Serial.print(F(" ("));
  Serial.print(railStatusToStr(initStatus));
  Serial.println(F(")"));

  resetAllComplianceToDefault();

  // -------- Parallel batch set: only the rails you include here are touched
  RailSetReq batch[] = {
    { "AVDD", 0.80f },
    { "VREFC_GATE", 1.2f },
    { "VREF", 0.6f },
  };

  RailStatus sts[INA219RAILS_MAX_BATCH];
  size_t N = sizeof(batch) / sizeof(batch[0]);
  if (N > INA219RAILS_MAX_BATCH) N = INA219RAILS_MAX_BATCH;

  size_t count = 7;
  N = (count - 1) / 2;

  Serial.print(F("Batch N=")); Serial.println(N);

  Serial.println(F("Starting parallel batch..."));
  bool ok = setRailsVoltageParallelByName(batch, N, sts);

  bool ok1 = checkAllRailsCompliance(sts);

  Serial.print(F("Compliance sweep ok="));
  Serial.println(ok1 ? "Y" : "N");

  for (size_t i = 0; i < RAIL_COUNT; ++i) {
    Serial.print(rails[i].name);
    Serial.print(F(": "));
    Serial.println(railStatusToStr(sts[i]));
  }

  Serial.print(F("Batch done. ok="));
  Serial.println(ok ? "Y" : "N");

  for (size_t i = 0; i < N; ++i) {
    Serial.print(batch[i].name);
    Serial.print(F(": target="));
    Serial.print(batch[i].V, 4);
    Serial.print(F(" status="));
    Serial.print((int)sts[i]);
    Serial.print(F(" ("));
    Serial.print(railStatusToStr(sts[i]));
    Serial.print(F(") Vmeas="));
    Serial.println(getRailBusVoltage_V(batch[i].name), 4);
  }
}

void loop() {
  // Periodic measurements
  if (millis() - lastPrint > 2000) {
    lastPrint = millis();
    Serial.println(F("---- Rail Measurements ----"));
    for (size_t i = 0; i < RAIL_COUNT; ++i) {
      INA219_Rail &r = rails[i];
      if (!r.present) {
        Serial.print(r.name);
        Serial.println(F(": INA219 not present"));
        continue;
      }

      float Vbus = getRailBusVoltage_V(r.name);
      float I_mA = getRailCurrent_mA(r.name);
      float P_mW = getRailPower_mW(r.name);

      Serial.print(r.name);
      Serial.print(F(": Vbus=")); Serial.print(Vbus, 4); Serial.print(F(" V"));
      Serial.print(F("  I="));    Serial.print(I_mA, 3); Serial.print(F(" mA"));
      Serial.print(F("  P="));    Serial.print(P_mW, 3); Serial.print(F(" mW"));
      Serial.print(F("  status="));
      Serial.print((int)r.status);
      Serial.print(F(" ("));
      Serial.print(railStatusToStr(r.status));
      Serial.println(F(")"));

//      if (INA219_Rail* r = getRailByName("VREFC_GATE")) {
//        bool ok = checkCurrentCompliance(*r);   // <-- forces the same compliance logic NOW
//        Serial.print(" complianceNow="); Serial.println(ok ? "OK" : "TRIPPED");
//      }

    }
    Serial.println();
  }
  while(true);
}
