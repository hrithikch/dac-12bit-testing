#warning "COMPILING Ina219Rails.cpp (NB+batch version)"

// Ina219Rails.cpp
#include <Ina219Rails.h>
#include <math.h>
#include <string.h>

#warning "COMPILING Ina219Rails.cpp from Documents/Arduino/libraries/Ina219Rails"

// Global debug flag (blocking path)
bool gCalDebug = true;

// Non-blocking debug flag
bool gNbDebug = false;

// Internal macros for conditional debug printing
#define CALDBG(...) do { if (gCalDebug) { __VA_ARGS__; } } while (0)
#define NBDBG(...)  do { if (gNbDebug)  { __VA_ARGS__; } } while (0)

// Some cores already define dtostrf; avoid double-definition.
#ifndef dtostrf
char* dtostrf(double val, signed char width, unsigned char prec, char *s) {
  char fmt[20];
  sprintf(fmt, "%%%d.%df", width, prec);
  sprintf(s, fmt, (float)val);
  return s;
}
#endif

// INA219 register map
#define INA219_REG_CONFIG        0x00
#define INA219_REG_SHUNTVOLTAGE  0x01
#define INA219_REG_BUSVOLTAGE    0x02
#define INA219_REG_POWER         0x03
#define INA219_REG_CURRENT       0x04
#define INA219_REG_CALIBRATION   0x05

// rails[] and RAIL_COUNT are defined by the sketch
extern INA219_Rail  rails[];
extern const size_t RAIL_COUNT;

// Helper: full-scale shunt voltage based on INA219 PGA setting
static float pgaFullScale_V(uint8_t pg) {
  switch (pg) {
    case 0: return 0.04f;
    case 1: return 0.08f;
    case 2: return 0.16f;
    case 3: return 0.32f;
    default: return 0.32f;
  }
}

// ---------------------------------------------------------------------------
// Wire naming (GIGA + DUE safe)
// ---------------------------------------------------------------------------
static inline const char* wireNameOf(TwoWire* w) {
  if (w == &Wire) return "W0";

#if defined(ARDUINO_ARCH_SAM) || defined(ARDUINO_ARCH_MBED)
  // Due + GIGA both have Wire1; treat any non-Wire as Wire1 for this project
  return "W1";
#else
  return "W0";
#endif
}
// ============================================================================
//  Low-level INA219 access
// ============================================================================
uint16_t ina219ReadRegisterRaw(const INA219_Rail &r, uint8_t reg) {
  r.wire->beginTransmission(r.inaAddr);
  r.wire->write(reg);
  if (r.wire->endTransmission() != 0) {
    return 0;
  }
  r.wire->requestFrom((int)r.inaAddr, 2);
  if (r.wire->available() < 2) return 0;
  uint16_t value = ((uint16_t)r.wire->read() << 8) | r.wire->read();
  return value;
}

void ina219WriteRegisterRaw(const INA219_Rail &r, uint8_t reg, uint16_t data) {
  r.wire->beginTransmission(r.inaAddr);
  r.wire->write(reg);
  r.wire->write((uint8_t)(data >> 8));
  r.wire->write((uint8_t)(data & 0xFF));
  r.wire->endTransmission();
}

// ============================================================================
//  INA219 calibration + config
// ============================================================================
void ina219ApplyConfigFromRail(INA219_Rail &r) {
  if (r.R_shunt <= 0.0f || r.I_maxExp <= 0.0f) return;

  float currentLSB_min = r.I_maxExp / 32767.0f;
  float currentLSB_A   = ceil(currentLSB_min * 1e6f) / 1e6f;

  r.currentLSB_A = currentLSB_A;
  r.powerLSB_W   = 20.0f * currentLSB_A;

  float cal_f  = 0.04096f / (currentLSB_A * r.R_shunt);
  uint16_t cal = (uint16_t)(cal_f + 0.5f);
  r.calReg     = cal;
  ina219WriteRegisterRaw(r, INA219_REG_CALIBRATION, cal);

  float Vshunt_max = r.I_maxExp * r.R_shunt;
  uint8_t pg = 0;
  if      (Vshunt_max > 0.16f) pg = 3;
  else if (Vshunt_max > 0.08f) pg = 2;
  else if (Vshunt_max > 0.04f) pg = 1;
  else                         pg = 0;

  uint16_t config = 0;
  config |= (0 << 13);         // BRNG = 16V
  config |= (pg << 11);        // PGA
  config |= (0xF << 7);        // BADC = 12-bit
  config |= (0xF << 3);        // SADC = 12-bit
  config |= 0x7;               // MODE = shunt+bus continuous

  ina219WriteRegisterRaw(r, INA219_REG_CONFIG, config);
}
// ============================================================================
//  Measurements
// ============================================================================
float readRailBusVoltage_V(INA219_Rail &r) {
  if (!r.present) return NAN;
  uint16_t raw = ina219ReadRegisterRaw(r, INA219_REG_BUSVOLTAGE);
  raw >>= 3;
  float v = raw * 0.004f; // 4 mV/bit
  v += r.V_cal;
  r.lastVoltage = v;
  r.lastSample_ms = millis();
  return v;
}

float readRailShuntVoltage_mV(INA219_Rail &r) {
  if (!r.present) return NAN;
  int16_t raw = (int16_t)ina219ReadRegisterRaw(r, INA219_REG_SHUNTVOLTAGE);
  return raw * 0.01f; // 10 µV/bit -> mV
}

float readRailCurrent_A(INA219_Rail &r) {
  if (!r.present || r.currentLSB_A <= 0.0f) return NAN;
  int16_t raw = (int16_t)ina219ReadRegisterRaw(r, INA219_REG_CURRENT);
  return (float)raw * r.currentLSB_A;
}

float readRailPower_W(INA219_Rail &r) {
  if (!r.present || r.powerLSB_W <= 0.0f) return NAN;
  uint16_t raw = ina219ReadRegisterRaw(r, INA219_REG_POWER);
  return (float)raw * r.powerLSB_W;
}

float readRailCurrent_mA(INA219_Rail &r) { return readRailCurrent_A(r) * 1000.0f; }
float readRailPower_mW  (INA219_Rail &r) { return readRailPower_W(r)   * 1000.0f; }

// ============================================================================
//  Name-based helpers
// ============================================================================
int findRailIndex(const char *name) {
  for (size_t i = 0; i < RAIL_COUNT; ++i) {
    if (strcmp(rails[i].name, name) == 0) return (int)i;
  }
  return -1;
}

INA219_Rail* getRailByName(const char *name) {
  int idx = findRailIndex(name);
  if (idx < 0) return nullptr;
  return &rails[idx];
}

float getRailBusVoltage_V(const char *name) {
  INA219_Rail *r = getRailByName(name);
  return r ? readRailBusVoltage_V(*r) : NAN;
}

float getRailShuntVoltage_mV(const char *name) {
  INA219_Rail *r = getRailByName(name);
  return r ? readRailShuntVoltage_mV(*r) : NAN;
}

float getRailCurrent_A(const char *name) {
  INA219_Rail *r = getRailByName(name);
  return r ? readRailCurrent_A(*r) : NAN;
}

float getRailPower_W(const char *name) {
  INA219_Rail *r = getRailByName(name);
  return r ? readRailPower_W(*r) : NAN;
}

float getRailCurrent_mA(const char *name) {
  INA219_Rail *r = getRailByName(name);
  return r ? readRailCurrent_mA(*r) : NAN;
}

float getRailPower_mW(const char *name) {
  INA219_Rail *r = getRailByName(name);
  return r ? readRailPower_mW(*r) : NAN;
}
// ============================================================================
//  Compliance
// ============================================================================
bool setRailCompliance_A(const char *name, float I_limit_A) {
  INA219_Rail *r = getRailByName(name);
  if (!r) return false;
  r->I_limit_A = I_limit_A;
  return true;
}

bool setRailCompliance_mA(const char *name, float I_limit_mA) {
  return setRailCompliance_A(name, I_limit_mA / 1000.0f);
}

void resetAllComplianceToDefault() {
  for (size_t i = 0; i < RAIL_COUNT; ++i) {
    INA219_Rail &r = rails[i];
    if (r.I_maxExp > 0.0f) {
      r.I_limit_A = 1.2f * r.I_maxExp;
    }
  }
}

// ============================================================================
//  DAC / Pot helpers (generic)
// ============================================================================
static void dacInit() {
#if defined(ARDUINO_ARCH_SAM) || defined(ARDUINO_ARCH_SAMD) || defined(ARDUINO_ARCH_MBED)
  analogWriteResolution(12);
#endif
}

static void potInitCS(uint8_t cs) {
  if (cs == 0 || cs == 255) return;
  pinMode(cs, OUTPUT);
  digitalWrite(cs, HIGH);
}

static void potWrite(uint8_t cs, uint8_t code) {
  if (cs == 0 || cs == 255) return;
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(cs, LOW);
  SPI.transfer(code);
  digitalWrite(cs, HIGH);
  SPI.endTransaction();
}

// ============================================================================
//  Debug: calibration summary
// ============================================================================
void printCalibrationSummary() {
  if (!gCalDebug) return;

  Serial.println();
  Serial.println(F("========== INA219 Calibration / Range Summary =========="));
  Serial.println(F("Idx Name        Addr Bus  Rsh[Ω]    Imax[A]   Vsh_max[mV]  PGA     Use[%FS]  I_LSB[µA]  P_LSB[µW]"));
  Serial.println(F("--- ----------  ---- --- --------  --------  -----------  -------  --------  ----------  ----------"));

  for (size_t i = 0; i < RAIL_COUNT; ++i) {
    INA219_Rail &r = rails[i];

    float Vsh_max = r.I_maxExp * r.R_shunt;
    uint8_t pg = 0;
    if      (Vsh_max > 0.16f) pg = 3;
    else if (Vsh_max > 0.08f) pg = 2;
    else if (Vsh_max > 0.04f) pg = 1;
    else                      pg = 0;

    float fs = pgaFullScale_V(pg);
    float util = (fs > 0.0f) ? (Vsh_max / fs * 100.0f) : 0.0f;

    const char* pgaStr = "";
    switch (pg) {
      case 0: pgaStr = "±40mV"; break;
      case 1: pgaStr = "±80mV"; break;
      case 2: pgaStr = "±160mV";break;
      case 3: pgaStr = "±320mV";break;
    }

    char buf[16];

    Serial.print(i < 10 ? " " : "");
    Serial.print(i); Serial.print(' ');

    snprintf(buf, sizeof(buf), "%-10s", r.name);
    Serial.print(buf); Serial.print(' ');

    Serial.print("0x");
    if (r.inaAddr < 0x10) Serial.print('0');
    Serial.print(r.inaAddr, HEX);
    Serial.print(' ');

    Serial.print(wireNameOf(r.wire));
    Serial.print(' ');

    dtostrf(r.R_shunt, 8, 4, buf);
    Serial.print(buf); Serial.print(' ');

    dtostrf(r.I_maxExp, 8, 4, buf);
    Serial.print(buf); Serial.print(' ');

    dtostrf(Vsh_max * 1000.0f, 11, 3, buf);
    Serial.print(buf); Serial.print(' ');

    snprintf(buf, sizeof(buf), "%-7s", pgaStr);
    Serial.print(buf); Serial.print(' ');

    dtostrf(util, 8, 2, buf);
    Serial.print(buf); Serial.print(' ');

    float I_LSB_uA = r.currentLSB_A * 1e6f;
    float P_LSB_uW = r.powerLSB_W   * 1e6f;

    dtostrf(I_LSB_uA, 10, 3, buf);
    Serial.print(buf); Serial.print(' ');

    dtostrf(P_LSB_uW, 10, 3, buf);
    Serial.print(buf);

    Serial.println();
  }
  Serial.println();
}
// ============================================================================
//  Initialization
// ============================================================================
RailStatus beginAllRails() {
  Wire.begin();

#if defined(ARDUINO_ARCH_SAM) || defined(ARDUINO_ARCH_MBED)
  Wire1.begin();
#endif

  SPI.begin();
  dacInit();

  for (size_t i = 0; i < RAIL_COUNT; ++i) {
    potInitCS(rails[i].potCS);
  }

  for (size_t i = 0; i < RAIL_COUNT; ++i) {
    INA219_Rail &r = rails[i];
    if (r.driveType == DRIVE_POT && r.potCS != 0 && r.potCS != 255) {
      potWrite(r.potCS, 0);
    }
  }
  delay(5);

  bool anyPresent = false;

  for (size_t i = 0; i < RAIL_COUNT; ++i) {
    INA219_Rail &r = rails[i];
    r.present = false;
    r.status  = RAIL_STATUS_DEVICE_FAIL;

    if (r.inaAddr == 0) continue;

    r.wire->beginTransmission(r.inaAddr);
    uint8_t err = r.wire->endTransmission();
    if (err != 0) {
      CALDBG(Serial.print(r.name));
      CALDBG(Serial.println(F(": I2C address not responding")));
      continue;
    }

    uint16_t cfg0 = ina219ReadRegisterRaw(r, INA219_REG_CONFIG);
    if (cfg0 == 0x0000 || cfg0 == 0xFFFF) {
      CALDBG(Serial.print(r.name));
      CALDBG(Serial.println(F(": bad initial CONFIG read")));
      continue;
    }

    ina219ApplyConfigFromRail(r);
    uint16_t cfg1 = ina219ReadRegisterRaw(r, INA219_REG_CONFIG);
    if (cfg1 == 0x0000 || cfg1 == 0xFFFF) {
      CALDBG(Serial.print(r.name));
      CALDBG(Serial.println(F(": bad CONFIG after apply")));
      continue;
    }

    r.present = true;
    r.status  = RAIL_STATUS_OK;
    anyPresent = true;

    CALDBG(Serial.print(r.name));
    CALDBG(Serial.println(F(": INA219 present and configured")));
  }

  if (gCalDebug) {
    printCalibrationSummary();
  }

  return anyPresent ? RAIL_STATUS_OK : RAIL_STATUS_DEVICE_FAIL;
}

// ============================================================================
//  Current compliance helper
// ============================================================================
static bool checkCurrentComplianceInternal(INA219_Rail &r) {
  if (!r.present) return true;
  if (r.I_maxExp <= 0.0f || r.I_limit_A <= 0.0f) return true; // disabled

  float I = readRailCurrent_A(r);
  if (isnan(I)) return true;

  float limit = r.I_limit_A;

  NBDBG(Serial.print(F("NBDBG compliance ")));
  NBDBG(Serial.print(r.name));
  NBDBG(Serial.print(F(" I=")));
  NBDBG(Serial.print(I, 9));
  NBDBG(Serial.print(F(" A limit=")));
  NBDBG(Serial.println(r.I_limit_A, 9));

  if (fabs(I) > limit) {
    CALDBG(Serial.print(r.name));
    CALDBG(Serial.print(F(": OVERCURRENT! I=")));
    CALDBG(Serial.print(I, 6));
    CALDBG(Serial.print(F(" A  limit=")));
    CALDBG(Serial.println(limit, 6));

    if (r.driveType == DRIVE_POT && r.potCS != 0 && r.potCS != 255) {
      potWrite(r.potCS, 0);
    } else if (r.driveType == DRIVE_DAC) {
      analogWrite(r.dacPin, 0);
    }

    r.status = RAIL_STATUS_OVERCURRENT;
    return false;
  }
  return true;
}

bool checkCurrentCompliance(INA219_Rail &r) {
  return checkCurrentComplianceInternal(r);
}

bool checkAllRailsCompliance(RailStatus *outStatus)
{
  if (!outStatus) return false;

  bool ok = true;

  for (size_t i = 0; i < RAIL_COUNT; ++i) {
    INA219_Rail &r = rails[i];

    if (!r.present) {
      // If you prefer to preserve existing status for not-present rails,
      // replace this line with: outStatus[i] = r.status;
      outStatus[i] = RAIL_STATUS_DEVICE_FAIL;
      ok = false;
      continue;
    }

    // This will shut the rail down and set r.status = OVERCURRENT if tripped.
    bool pass = checkCurrentCompliance(r);

    outStatus[i] = r.status;

    if (!pass) ok = false;
  }

  return ok;
}

bool writeRailPotRawByName(const char *name, uint8_t code)
{
  INA219_Rail *r = getRailByName(name);
  if (!r) {
    CALDBG(Serial.print(name));
    CALDBG(Serial.println(F(": rail not found (pot raw write)")));
    return false;
  }

  if (!r->present) {
    CALDBG(Serial.print(r->name));
    CALDBG(Serial.println(F(": INA219 not present (pot raw write)")));
    return false;
  }

  if (r->driveType != DRIVE_POT) {
    CALDBG(Serial.print(r->name));
    CALDBG(Serial.println(F(": not a POT-driven rail")));
    return false;
  }

  if (r->potCS == 0 || r->potCS == 255) {
    CALDBG(Serial.print(r->name));
    CALDBG(Serial.println(F(": invalid pot CS pin")));
    return false;
  }

  // Clamp explicitly (defensive)
  if (code > r->w_max) code = r->w_max;

  potWrite(r->potCS, code);

  // Optional: take a measurement so state reflects reality
  delay(5);
  r->lastVoltage = readRailBusVoltage_V(*r);
  r->status = RAIL_STATUS_OK;

  CALDBG(Serial.print(F("RAW POT write: ")));
  CALDBG(Serial.print(r->name));
  CALDBG(Serial.print(F(" code=")));
  CALDBG(Serial.print(code));
  CALDBG(Serial.print(F(" Vbus=")));
  CALDBG(Serial.println(r->lastVoltage, 4));

  return true;
}

// ============================================================================
//  Non-blocking (NB) internal context + phase enum
//  (This must appear BEFORE any NB functions that use RailNBContext.)
// ============================================================================

enum RailNBPhase : uint8_t {
  RAIL_NB_IDLE = 0,        // not active
  RAIL_NB_START,           // initialize / first drive apply
  RAIL_NB_WAIT_SETTLE,     // wait for settle_ms before sampling
  RAIL_NB_SAMPLE_ACCUM,    // take samples with spacing
  RAIL_NB_EVAL_POINT,      // evaluate average / decide next action
  RAIL_NB_APPLY_DRIVE,     // apply next code (coarse or fine)
  RAIL_NB_STABILITY_INIT,
  RAIL_NB_STABILITY_WAIT,
  RAIL_NB_STABILITY_READ,
  RAIL_NB_DONE,            // finished successfully (OK/WARN)
  RAIL_NB_FAIL             // finished unsuccessfully (TIMEOUT/etc)
};

typedef struct RailNBContext {
  // lifecycle
  bool      active = false;
  bool      done   = false;
  RailStatus result = RAIL_STATUS_DEVICE_FAIL;

  // state machine
  RailNBPhase phase = RAIL_NB_START;

  // timing
  uint32_t t_start_ms = 0;
  uint32_t t_next_ms  = 0;
  uint32_t timeout_ms = 0;     // computed per rail if r.timeout_ms == 0
  uint32_t settle_ms  = 200;   // default settle
  uint32_t sampleSpacing_ms = 5;

  // target
  float V_target = NAN;

  // drive/search params
  int maxCode = 255;
  int stepCoarse = 4;
  int maxCoarse  = 80;
  int fineSamples   = 3;
  int coarseSamples = 1;  // DAC uses more
  int windowHalf = 4;
  int maxIter = 10;

  // working state
  int   code = 0;
  int   prevCode = 0;
  float prevV = NAN;

  int   lastBelowCode  = -1;
  float lastBelowV     = NAN;

  int   firstAboveCode = -1;
  float firstAboveV    = NAN;

  int coarseSteps = 0;

  // fine search bounds/candidates
  int low = 0;
  int high = 0;
  int iter = 0;

  int   bestBelowCode = -1;
  float bestBelowV    = NAN;
  float bestBelowErr  = 1e9f;

  int   bestAboveCode = -1;
  float bestAboveV    = NAN;
  float bestAboveErr  = 1e9f;

  // sampling accumulator
  float sampleSum = 0.0f;
  int   samplesTaken  = 0;
  int   samplesGood   = 0;
  int   samplesPlanned = 0;

  // stability check
  uint8_t stableReadsRequired = 3;
  uint8_t stableReadsDone     = 0;
} RailNBContext;

// ============================================================================
//  Non-blocking engine helpers
// ============================================================================
static inline uint32_t clamp_u32(uint32_t x, uint32_t lo, uint32_t hi) {
  if (x < lo) return lo;
  if (x > hi) return hi;
  return x;
}

uint32_t estimateRailTimeoutMs(const INA219_Rail &r, float V_target,
                               uint32_t settle_ms,
                               float safety,
                               uint32_t min_ms,
                               uint32_t max_ms)
{
  // Clamp target to the rail’s allowed range
  float Vt = V_target;
  if (Vt < r.V_min) Vt = r.V_min;
  if (Vt > r.V_max) Vt = r.V_max;

  // Effective control span: this is the key for "pot only" vs "regulator window"
  float span = r.V_max - r.V_min;
  if (!(span > 0.0f)) span = 1.0f;     // fallback

  // Pot resolution
  int wmax = (r.w_max > 0) ? (int)r.w_max : 255;

  // Convert target voltage into an estimated pot code distance from low end.
  // Assumes monotonic mapping from code 0 -> V_min, code wmax -> V_max.
  float code_per_V = (float)wmax / span;
  float codes_to_target_f = (Vt - r.V_min) * code_per_V;
  if (codes_to_target_f < 0.0f) codes_to_target_f = 0.0f;
  if (codes_to_target_f > (float)wmax) codes_to_target_f = (float)wmax;

  // NB defaults (match your NB Begin settings for DRIVE_POT)
  int stepCoarse = 4;
  int maxIter    = 10;
  uint8_t stableReads = r.stableRequired ? r.stableRequired : 3;

  // Estimated number of coarse steps from code 0
  uint32_t coarseSteps = (uint32_t)ceilf(codes_to_target_f / (float)stepCoarse);

  // Worst-case: you do coarseSteps "apply+settle+measure", then fine binary steps,
  // then stability reads. Add a small constant overhead.
  uint32_t totalSteps = coarseSteps + (uint32_t)maxIter + (uint32_t)stableReads + 4;

  // Measurement sampling adds a little time, but settle dominates.
  // Keep it simple: steps * settle_ms, then apply safety.
  float t_ms = (float)totalSteps * (float)settle_ms;
  t_ms *= (safety > 1.0f ? safety : 1.0f);

  return clamp_u32((uint32_t)(t_ms + 0.5f), min_ms, max_ms);
}

void railNB_Init(RailNBContext &ctx) {
  ctx.active = false;
  ctx.done = false;
  ctx.result = RAIL_STATUS_OK;
  ctx.phase = RAIL_NB_IDLE;

  ctx.V_target = NAN;
  ctx.t_start_ms = 0;
  ctx.t_next_ms = 0;
  ctx.settle_ms = 200;
  ctx.timeout_ms = 0;

  ctx.code = 0;
  ctx.prevCode = 0;
  ctx.prevV = NAN;

  ctx.lastBelowCode = -1;
  ctx.lastBelowV = NAN;
  ctx.firstAboveCode = -1;
  ctx.firstAboveV = NAN;

  ctx.coarseSteps = 0;

  ctx.low = 0;
  ctx.high = 0;
  ctx.iter = 0;
  ctx.maxIter = 0;

  ctx.bestBelowCode = -1;
  ctx.bestBelowV = NAN;
  ctx.bestBelowErr = 1e9f;

  ctx.bestAboveCode = -1;
  ctx.bestAboveV = NAN;
  ctx.bestAboveErr = 1e9f;

  ctx.samplesPlanned = 0;
  ctx.samplesTaken = 0;
  ctx.samplesGood = 0;
  ctx.sampleSum = 0.0f;
  ctx.sampleSpacing_ms = 5;

  ctx.stableReadsRequired = 3;
  ctx.stableReadsDone = 0;

  ctx.maxCode = 255;
  ctx.stepCoarse = 4;
  ctx.maxCoarse = 80;
  ctx.fineSamples = 3;
  ctx.coarseSamples = 5;
  ctx.windowHalf = 4;
}

bool setRailVoltageNB_IsDone(const RailNBContext &ctx) {
  return ctx.done;
}

static inline void nbSetResultDone(RailNBContext &ctx, RailStatus s) {
  ctx.done = true;
  ctx.active = false;
  ctx.result = s;
  ctx.phase = (s == RAIL_STATUS_OK || s == RAIL_STATUS_WARN) ? RAIL_NB_DONE : RAIL_NB_FAIL;
}

static inline bool nbTimedOut(const INA219_Rail &r, const RailNBContext &ctx) {
  (void)r;
  return (millis() - ctx.t_start_ms) > ctx.timeout_ms;
}

static inline void nbStartSampling(RailNBContext &ctx, int nSamples) {
  ctx.samplesPlanned = nSamples;
  ctx.samplesTaken = 0;
  ctx.samplesGood = 0;
  ctx.sampleSum = 0.0f;
}

static inline bool nbSamplingDone(const RailNBContext &ctx) {
  return (ctx.samplesTaken >= ctx.samplesPlanned);
}

static inline float nbSamplingAvg(const RailNBContext &ctx) {
  if (ctx.samplesGood <= 0) return NAN;
  return ctx.sampleSum / (float)ctx.samplesGood;
}

static inline void nbApplyDrive(INA219_Rail &r, int code) {
  if (r.driveType == DRIVE_POT) {
    potWrite(r.potCS, (uint8_t)code);
  } else if (r.driveType == DRIVE_DAC) {
    analogWrite(r.dacPin, code);
  }
}

static inline void nbUpdateFineCandidatesAndBounds(
  RailNBContext &ctx,
  float Vavg
) {
  float e = Vavg - ctx.V_target;
  float ae = fabs(e);

  if (Vavg < ctx.V_target) {
    if (ae < ctx.bestBelowErr || (fabs(ae - ctx.bestBelowErr) < 1e-7 && ctx.code > ctx.bestBelowCode)) {
      ctx.bestBelowErr = ae;
      ctx.bestBelowCode = ctx.code;
      ctx.bestBelowV = Vavg;
    }
    ctx.low = ctx.code + 1;
  } else {
    if (ae < ctx.bestAboveErr || (fabs(ae - ctx.bestAboveErr) < 1e-7 && ctx.code > ctx.bestAboveCode)) {
      ctx.bestAboveErr = ae;
      ctx.bestAboveCode = ctx.code;
      ctx.bestAboveV = Vavg;
    }
    ctx.high = ctx.code - 1;
  }

  ctx.iter++;
}

// ============================================================================
//  Non-blocking Begin
// ============================================================================
RailStatus setRailVoltageNB_Begin(INA219_Rail &r, float V_target, RailNBContext &ctx) {
  uint32_t keepSpacing = ctx.sampleSpacing_ms;
  railNB_Init(ctx);
  ctx.sampleSpacing_ms = keepSpacing ? keepSpacing : 5;

  if (!r.present) {
    r.status = RAIL_STATUS_DEVICE_FAIL;
    nbSetResultDone(ctx, r.status);
    return r.status;
  }

  if (r.driveType == DRIVE_NONE) {
    r.status = RAIL_STATUS_DEVICE_FAIL;
    nbSetResultDone(ctx, r.status);
    return r.status;
  }

  if (V_target < r.V_min) V_target = r.V_min;
  if (V_target > r.V_max) V_target = r.V_max;

  ctx.active   = true;
  ctx.done     = false;
  ctx.result   = RAIL_STATUS_OK;
  ctx.phase    = RAIL_NB_START;

  ctx.V_target   = V_target;
  ctx.t_start_ms = millis();
  ctx.t_next_ms  = ctx.t_start_ms;
  if (r.timeout_ms == 0) {
    ctx.timeout_ms = estimateRailTimeoutMs(r, V_target, ctx.settle_ms, 1.25f, 3000, 30000);
  } else {
    ctx.timeout_ms = r.timeout_ms;
  }

  ctx.settle_ms  = 200;

  if (r.driveType == DRIVE_POT) {
    ctx.maxCode     = (int)r.w_max;
    ctx.stepCoarse  = 4;
    ctx.maxCoarse   = 80;
    ctx.fineSamples = 3;
    ctx.coarseSamples = 1;
    ctx.windowHalf  = 4;
    ctx.maxIter     = 10;
  } else {
    int fullScale = r.dacMaxCode > 0 ? r.dacMaxCode : 4095;
    int step = fullScale / 32;
    if (step < 16) step = 16;

    ctx.maxCode       = fullScale;
    ctx.stepCoarse    = step;
    ctx.maxCoarse     = 64;
    ctx.fineSamples   = 5;
    ctx.coarseSamples = 5;
    ctx.windowHalf    = 0;
    ctx.maxIter       = 16;
  }

  ctx.prevCode = 0;
  ctx.prevV    = NAN;

  ctx.lastBelowCode  = -1;
  ctx.lastBelowV     = NAN;
  ctx.firstAboveCode = -1;
  ctx.firstAboveV    = NAN;

  ctx.coarseSteps = 0;

  ctx.bestBelowCode = -1;
  ctx.bestBelowV    = NAN;
  ctx.bestBelowErr  = 1e9f;

  ctx.bestAboveCode = -1;
  ctx.bestAboveV    = NAN;
  ctx.bestAboveErr  = 1e9f;

  ctx.stableReadsRequired = r.stableRequired ? r.stableRequired : 3;
  ctx.stableReadsDone     = 0;

  ctx.code = 0;

  NBDBG(Serial.print(F("NB begin ")));
  NBDBG(Serial.print(r.name));
  NBDBG(Serial.print(F(" target=")));
  NBDBG(Serial.print(ctx.V_target, 4));
  NBDBG(Serial.println(F(" V")));

  return r.status;
}

// ============================================================================
//  Non-blocking Update
// ============================================================================
RailStatus setRailVoltageNB_Update(INA219_Rail &r, RailNBContext &ctx) {
  if (!ctx.active) {
    return ctx.done ? ctx.result : r.status;
  }

  if (!r.present) {
    r.status = RAIL_STATUS_DEVICE_FAIL;
    nbSetResultDone(ctx, r.status);
    return r.status;
  }

  if (nbTimedOut(r, ctx)) {
    r.status = RAIL_STATUS_TIMEOUT;
    nbSetResultDone(ctx, r.status);
    return r.status;
  }

  if (millis() < ctx.t_next_ms) {
    return r.status;
  }

  switch (ctx.phase) {
    case RAIL_NB_START: {
    nbApplyDrive(r, ctx.code);
  
    if (!checkCurrentComplianceInternal(r)) {
      nbSetResultDone(ctx, r.status);
      return r.status;
    }

    ctx.t_next_ms = millis() + ctx.settle_ms;
      ctx.phase = RAIL_NB_WAIT_SETTLE;

      NBDBG(Serial.print(F("NB ")));
      NBDBG(Serial.print(r.name));
      NBDBG(Serial.print(F(" COARSE set code=")));
      NBDBG(Serial.println(ctx.code));

      return r.status;
    }

    case RAIL_NB_WAIT_SETTLE: {
      int n = (r.driveType == DRIVE_DAC) ? ctx.coarseSamples : 1;
      nbStartSampling(ctx, n);
      ctx.t_next_ms = millis();
      ctx.phase = RAIL_NB_SAMPLE_ACCUM;
      return r.status;
    }

    case RAIL_NB_SAMPLE_ACCUM: {
      float v = readRailBusVoltage_V(r);
      if (!isnan(v)) {
        ctx.sampleSum += v;
        ctx.samplesGood++;
      }
      ctx.samplesTaken++;

      if (!checkCurrentComplianceInternal(r)) {
        nbSetResultDone(ctx, r.status);
        return r.status;
      }

      if (!nbSamplingDone(ctx)) {
        ctx.t_next_ms = millis() + ctx.sampleSpacing_ms;
        return r.status;
      }

      ctx.phase = RAIL_NB_EVAL_POINT;
      ctx.t_next_ms = millis();
      return r.status;
    }

    case RAIL_NB_EVAL_POINT: {
      float Vavg = nbSamplingAvg(ctx);
      if (isnan(Vavg)) {
        r.status = RAIL_STATUS_DEVICE_FAIL;
        nbSetResultDone(ctx, r.status);
        return r.status;
      }

      float err = Vavg - ctx.V_target;
      float ae  = fabs(err);

      NBDBG(Serial.print(F("NB ")));
      NBDBG(Serial.print(r.name));
      NBDBG(Serial.print((ctx.firstAboveCode < 0) ? F(" COARSE") : F(" FINE")));
      NBDBG(Serial.print(F(" Vavg=")));
      NBDBG(Serial.print(Vavg, 4));
      NBDBG(Serial.print(F(" err=")));
      NBDBG(Serial.println(err, 4));

      if (ae <= r.tolerance) {
        r.status = (ae <= r.tolerance) ? RAIL_STATUS_OK : RAIL_STATUS_WARN;
        ctx.phase = RAIL_NB_STABILITY_INIT;
        ctx.t_next_ms = millis();
        return r.status;
      }

      // Coarse mode: find first bracket crossing
      if (ctx.firstAboveCode < 0) {
        if (Vavg < ctx.V_target) {
          ctx.lastBelowCode = ctx.code;
          ctx.lastBelowV    = Vavg;
        } else {
          ctx.firstAboveCode = ctx.code;
          ctx.firstAboveV    = Vavg;
        }

        if (ctx.code == 0 && Vavg >= ctx.V_target) {
          ctx.phase = RAIL_NB_STABILITY_INIT;
          ctx.t_next_ms = millis();
          return r.status;
        }

        if (ctx.firstAboveCode < 0) {
          if (ctx.coarseSteps >= ctx.maxCoarse || ctx.code >= ctx.maxCode) {
            nbApplyDrive(r, ctx.maxCode);
            r.status = RAIL_STATUS_OUT_OF_RANGE;
            nbSetResultDone(ctx, r.status);
            return r.status;
          }

          ctx.prevCode = ctx.code;
          ctx.prevV    = Vavg;

          int nextCode = ctx.code + ctx.stepCoarse;
          if (nextCode > ctx.maxCode) nextCode = ctx.maxCode;
          ctx.code = nextCode;
          ctx.coarseSteps++;

          nbApplyDrive(r, ctx.code);
          ctx.t_next_ms = millis() + ctx.settle_ms;
          ctx.phase = RAIL_NB_WAIT_SETTLE;

          NBDBG(Serial.print(F("NB ")));
          NBDBG(Serial.print(r.name));
          NBDBG(Serial.print(F(" COARSE step code=")));
          NBDBG(Serial.println(ctx.code));

          return r.status;
        }

        // We now have a bracket; set fine bounds
        if (ctx.lastBelowCode < 0) {
          r.status = RAIL_STATUS_DEVICE_FAIL;
          nbSetResultDone(ctx, r.status);
          return r.status;
        }

        if (r.driveType == DRIVE_POT) {
          float slope = (ctx.firstAboveV - ctx.lastBelowV) / (float)(ctx.firstAboveCode - ctx.lastBelowCode);
          if (slope <= 0.0f || isnan(slope)) {
            slope = (r.V_max - r.V_min) / (float)ctx.maxCode;
          }

          int estCode = ctx.lastBelowCode + (int)round((ctx.V_target - ctx.lastBelowV) / slope);
          if (estCode < 0) estCode = 0;
          if (estCode > ctx.maxCode) estCode = ctx.maxCode;

          int searchStart = estCode - ctx.windowHalf;
          int searchEnd   = estCode + ctx.windowHalf;
          if (searchStart < 0) searchStart = 0;
          if (searchEnd > ctx.maxCode) searchEnd = ctx.maxCode;

          ctx.low  = searchStart;
          ctx.high = searchEnd;
          ctx.iter = 0;
        } else {
          ctx.low  = (ctx.lastBelowCode < 0) ? 0 : ctx.lastBelowCode;
          ctx.high = ctx.firstAboveCode;
          ctx.iter = 0;
        }

        ctx.bestBelowCode = -1; ctx.bestBelowV = NAN; ctx.bestBelowErr = 1e9f;
        ctx.bestAboveCode = -1; ctx.bestAboveV = NAN; ctx.bestAboveErr = 1e9f;

        ctx.phase = RAIL_NB_APPLY_DRIVE;
        ctx.t_next_ms = millis();
        return r.status;
      }

      // Fine mode: update candidates and bounds
      if (ctx.low <= ctx.high && ctx.iter < ctx.maxIter) {
        nbUpdateFineCandidatesAndBounds(ctx, Vavg);
        ctx.phase = RAIL_NB_APPLY_DRIVE;
        ctx.t_next_ms = millis();
        return r.status;
      }

      // Fine done: pick best code and move to stability
      {
        int chosenCode = -1;
        float chosenErr = 1e9f;

        if (ctx.bestBelowCode >= 0 && ctx.bestAboveCode >= 0) {
          if (ctx.bestBelowErr < ctx.bestAboveErr) {
            chosenCode = ctx.bestBelowCode; chosenErr = ctx.bestBelowErr;
          } else if (ctx.bestAboveErr < ctx.bestBelowErr) {
            chosenCode = ctx.bestAboveCode; chosenErr = ctx.bestAboveErr;
          } else {
            chosenCode = (ctx.bestAboveCode >= ctx.bestBelowCode) ? ctx.bestAboveCode : ctx.bestBelowCode;
            chosenErr  = (chosenCode == ctx.bestAboveCode) ? ctx.bestAboveErr : ctx.bestBelowErr;
          }
        } else if (ctx.bestBelowCode >= 0) {
          chosenCode = ctx.bestBelowCode; chosenErr = ctx.bestBelowErr;
        } else if (ctx.bestAboveCode >= 0) {
          chosenCode = ctx.bestAboveCode; chosenErr = ctx.bestAboveErr;
        } else {
          r.status = RAIL_STATUS_DEVICE_FAIL;
          nbSetResultDone(ctx, r.status);
          return r.status;
        }

        ctx.code = chosenCode;
        nbApplyDrive(r, ctx.code);
        ctx.t_next_ms = millis() + ctx.settle_ms;

        r.status = (chosenErr <= r.tolerance) ? RAIL_STATUS_OK : RAIL_STATUS_WARN;

        ctx.phase = RAIL_NB_STABILITY_INIT;
        return r.status;
      }
    }

    case RAIL_NB_APPLY_DRIVE: {
      if (ctx.low > ctx.high || ctx.iter >= ctx.maxIter) {
        ctx.phase = RAIL_NB_EVAL_POINT;
        ctx.t_next_ms = millis();
        return r.status;
      }

      int mid = (ctx.low + ctx.high) / 2;
      ctx.code = mid;

      nbApplyDrive(r, ctx.code);

      if (!checkCurrentComplianceInternal(r)) {
        nbSetResultDone(ctx, r.status);
        return r.status;
      }

      ctx.t_next_ms = millis() + ctx.settle_ms;

      NBDBG(Serial.print(F("NB ")));
      NBDBG(Serial.print(r.name));
      NBDBG(Serial.print(F(" FINE set code=")));
      NBDBG(Serial.println(ctx.code));

      nbStartSampling(ctx, ctx.fineSamples);
      ctx.phase = RAIL_NB_SAMPLE_ACCUM;
      return r.status;
    }

    case RAIL_NB_STABILITY_INIT: {
      ctx.stableReadsDone = 0;
      ctx.phase = RAIL_NB_STABILITY_WAIT;
      ctx.t_next_ms = millis() + ctx.settle_ms;
      return r.status;
    }

    case RAIL_NB_STABILITY_WAIT: {
      ctx.phase = RAIL_NB_STABILITY_READ;
      ctx.t_next_ms = millis();
      return r.status;
    }

    case RAIL_NB_STABILITY_READ: {
      float Vcheck = readRailBusVoltage_V(r);
      if (!checkCurrentComplianceInternal(r)) {
        nbSetResultDone(ctx, r.status);
        return r.status;
      }

      float ae = isnan(Vcheck) ? 1e9f : fabs(Vcheck - ctx.V_target);
      float stableTol = r.tolerance * 2.0f;

      if (!isnan(Vcheck) && ae <= stableTol) {
        ctx.stableReadsDone++;
      } else {
        r.status = RAIL_STATUS_UNSTABLE;
        nbSetResultDone(ctx, r.status);
        return r.status;
      }

      if (ctx.stableReadsDone >= ctx.stableReadsRequired) {
        nbSetResultDone(ctx, r.status);
        return r.status;
      }

      ctx.phase = RAIL_NB_STABILITY_WAIT;
      ctx.t_next_ms = millis() + ctx.settle_ms;
      return r.status;
    }

    default:
      r.status = RAIL_STATUS_DEVICE_FAIL;
      nbSetResultDone(ctx, r.status);
      return r.status;
  }
}

// ============================================================================
//  Parallel batch (single-call wrapper)
// ============================================================================
bool setRailsVoltageParallelByName(const RailSetReq req[], size_t n, RailStatus outStatus[]) {
  if (!outStatus) return false;

  const size_t MAX_BATCH = INA219RAILS_MAX_BATCH;

  if (!req || n == 0) return true;

  if (n > MAX_BATCH) {
    for (size_t i = 0; i < n; ++i) outStatus[i] = RAIL_STATUS_DEVICE_FAIL;
    NBDBG(Serial.println(F("NB batch: n exceeds INA219RAILS_MAX_BATCH")));
    return false;
  }

  // Static storage avoids stack pressure on smaller MCUs.
  static RailNBContext ctx[INA219RAILS_MAX_BATCH];
  static INA219_Rail*  rptr[INA219RAILS_MAX_BATCH];

  for (size_t i = 0; i < n; ++i) {
    railNB_Init(ctx[i]);
    rptr[i] = nullptr;
    outStatus[i] = RAIL_STATUS_DEVICE_FAIL;

    if (!req[i].name) {
      ctx[i].done = true;
      ctx[i].result = RAIL_STATUS_DEVICE_FAIL;
      continue;
    }

    INA219_Rail* r = getRailByName(req[i].name);
    rptr[i] = r;

    if (!r) {
      NBDBG(Serial.print(F("NB batch: not found ")));
      NBDBG(Serial.println(req[i].name));
      ctx[i].done = true;
      ctx[i].result = RAIL_STATUS_DEVICE_FAIL;
      outStatus[i] = RAIL_STATUS_DEVICE_FAIL;
      continue;
    }

    if (!r->present || r->driveType == DRIVE_NONE || isnan(req[i].V)) {
      NBDBG(Serial.print(F("NB batch: cannot begin ")));
      NBDBG(Serial.print(r->name));
      NBDBG(Serial.print(F(" present=")));
      NBDBG(Serial.print(r->present ? 1 : 0));
      NBDBG(Serial.print(F(" driveType=")));
      NBDBG(Serial.print((int)r->driveType));
      NBDBG(Serial.print(F(" V=")));
      NBDBG(Serial.println(req[i].V, 4));

      r->status = RAIL_STATUS_DEVICE_FAIL;
      ctx[i].done = true;
      ctx[i].result = r->status;
      outStatus[i] = r->status;
      continue;
    }

    RailStatus s = setRailVoltageNB_Begin(*r, req[i].V, ctx[i]);
    outStatus[i] = s;

    if (!ctx[i].active) {
      ctx[i].done = true;
      ctx[i].result = s;
    }
  }

  bool anyActive;
  do {
    anyActive = false;

    for (size_t i = 0; i < n; ++i) {
      INA219_Rail* r = rptr[i];
      if (!r) continue;

      static uint8_t lastPhase[INA219RAILS_MAX_BATCH];
      static uint32_t lastPrintMs[INA219RAILS_MAX_BATCH];

      for (size_t i = 0; i < n; ++i) {
        if (ctx[i].active && !ctx[i].done) {
          (void)setRailVoltageNB_Update(*rptr[i], ctx[i]);
        }

        // Throttle: print only on phase change or every 250ms
        uint32_t now = millis();
        if (gNbDebug) {
          if (ctx[i].phase != lastPhase[i] || (now - lastPrintMs[i]) > 250) {
            lastPhase[i] = ctx[i].phase;
            lastPrintMs[i] = now;

            Serial.print(F("NBDBG slot ")); Serial.print(i);
            Serial.print(' '); Serial.print(rptr[i] ? rptr[i]->name : "(null)");
            Serial.print(F(" act=")); Serial.print(ctx[i].active);
            Serial.print(F(" done=")); Serial.print(ctx[i].done);
            Serial.print(F(" phase=")); Serial.println(ctx[i].phase);
          }
        }

  outStatus[i] = ctx[i].done ? ctx[i].result : (rptr[i] ? rptr[i]->status : RAIL_STATUS_DEVICE_FAIL);
}

      if (ctx[i].active && !ctx[i].done) {
        anyActive = true;
        (void)setRailVoltageNB_Update(*r, ctx[i]);
      }

      outStatus[i] = ctx[i].done ? ctx[i].result : r->status;
    }

    yield();
  } while (anyActive);

  bool ok = true;
  for (size_t i = 0; i < n; ++i) {
    RailStatus s = outStatus[i];
    if (!(s == RAIL_STATUS_OK || s == RAIL_STATUS_WARN)) ok = false;
  }
  return ok;
}

// ============================================================================
//  Status -> string
// ============================================================================
const char* railStatusToStr(RailStatus s) {
  switch (s) {
    case RAIL_STATUS_OK:           return "OK";
    case RAIL_STATUS_WARN:         return "WARN";
    case RAIL_STATUS_OUT_OF_RANGE: return "OUT_OF_RANGE";
    case RAIL_STATUS_STUCK:        return "STUCK";
    case RAIL_STATUS_TIMEOUT:      return "TIMEOUT";
    case RAIL_STATUS_DEVICE_FAIL:  return "DEVICE_FAIL";
    case RAIL_STATUS_UNSTABLE:     return "UNSTABLE";
    case RAIL_STATUS_OVERCURRENT:  return "OVERCURRENT";
    default:                       return "UNKNOWN";
  }
}

