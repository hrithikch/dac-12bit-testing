#warning "INCLUDING Ina219Rails.h (authoritative)"

#ifndef INA219_RAILS_H
#define INA219_RAILS_H

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>

// Global debug flag:
// - true  => helper functions print debug info over Serial via gCalDebug
// - false => helper functions are silent (setup/loop in your sketch can still print)
extern bool gCalDebug;
extern bool gNbDebug;

/// Maximum number of LUT points per rail (if you choose to use LUTs later).
#define MAX_LUT_POINTS 8

#define INA219RAILS_MAX_BATCH 32

/// Status codes for rail operations (initialization, setRailVoltage, etc.).
enum RailStatus : uint8_t {
  RAIL_STATUS_OK = 0,          ///< Operation successful and within tolerance.
  RAIL_STATUS_WARN,            ///< Operation completed, but outside tolerance.
  RAIL_STATUS_OUT_OF_RANGE,    ///< Target voltage not reachable within limits.
  RAIL_STATUS_STUCK,           ///< Legacy "stuck" condition (not heavily used).
  RAIL_STATUS_TIMEOUT,         ///< Operation timed out before convergence.
  RAIL_STATUS_DEVICE_FAIL,     ///< INA219 or driver failure for this rail.
  RAIL_STATUS_UNSTABLE,        ///< Voltage could not be stabilized near target.
  RAIL_STATUS_OVERCURRENT      ///< Current exceeded compliance limit; rail shut down.
};

typedef struct {
  const char *name;
  float       V;       // target voltage [V]
} RailSetReq;

/// How a rail is driven.
enum RailDriveType : uint8_t {
  DRIVE_POT   = 0,             ///< Driven by SPI digital pot (e.g., TPL0501).
  DRIVE_DAC   = 1,             ///< Driven by MCU DAC via analogWrite().
  DRIVE_NONE  = 2              ///< Measure-only; no drive element.
};

/// Description of one monitored/controlled rail.
/// You own the instances of this struct in your sketch.
typedef struct
{
  // Identity / I2C connection
  const char*  name;           ///< Human-readable rail name, e.g. "AVDD".
  uint8_t      inaAddr;        ///< INA219 7-bit I2C address.
  TwoWire*     wire;           ///< Pointer to I2C bus (&Wire or &Wire1).

  // Voltage constraints & control parameters
  float  V_min;                ///< Minimum allowed target voltage [V].
  float  V_max;                ///< Maximum allowed target voltage [V].
  float  tolerance;            ///< Voltage target tolerance [V].
  float  minChange;            ///< Minimum dV that matters [V] (currently unused hook).
  float  V_cal;                ///< Calibration offset added to measured bus voltage [V].

  // Pot control (optional)
  uint8_t  potCS;              ///< SPI chip select pin for pot (0/255 if none).
  uint8_t  w_max;              ///< Max pot wiper code (e.g., 255).
  uint8_t  maxStuck;           ///< Legacy "stuck" count threshold (not critical now).

  // DAC / drive control (optional)
  uint8_t  driveType;          ///< DRIVE_POT / DRIVE_DAC / DRIVE_NONE.
  uint8_t  dacPin;             ///< MCU pin used with analogWrite() when DRIVE_DAC.
  uint16_t dacMaxCode;         ///< Full-scale DAC code (e.g., 4095 for 12-bit).

  // Timing / safety
  unsigned long timeout_ms;    ///< Timeout for setRailVoltage() [ms].

  // Runtime state
  bool         present;        ///< true if INA219 responded and was configured.
  RailStatus   status;         ///< Last RailStatus for this rail.
  float        lastVoltage;    ///< Last measured bus voltage [V].
  unsigned long lastSample_ms; ///< Timestamp of last bus voltage measurement.

  // INA219 calibration parameters
  float     R_shunt;           ///< Shunt resistor value [Ω].
  float     I_maxExp;          ///< Expected max current [A] for this rail.
  float     I_limit_A;         ///< Absolute current compliance limit [A] (0 => disabled).
  float     currentLSB_A;      ///< Current LSB [A/bit] after calibration.
  float     powerLSB_W;        ///< Power LSB [W/bit] after calibration.
  uint16_t  calReg;            ///< Last CAL register value written to INA219.

  // Optional LUT for pot code vs voltage (not required, but supported)
  uint8_t   lutCount;          ///< Number of valid LUT points.
  float     lutV[MAX_LUT_POINTS]; ///< LUT voltages [V].
  uint8_t   lutCode[MAX_LUT_POINTS]; ///< Corresponding pot codes.

  // Stability control
  uint8_t   stableRequired;    ///< Number of successive in-tolerance reads to declare stable.

} INA219_Rail;

/// Your sketch must define these:
extern INA219_Rail  rails[];      ///< Global rail table (owned by the sketch).
extern const size_t RAIL_COUNT;   ///< Number of rails in rails[].

// ---------------------------------------------------------------------------
// Low-level / calibration helpers
// ---------------------------------------------------------------------------

/**
 * @brief Read a raw 16-bit INA219 register.
 *
 * @param r   Rail whose INA219 to talk to (uses r.inaAddr and r.wire).
 * @param reg Register address (e.g., 0x00 for CONFIG).
 * @return 16-bit raw register value (0 if I2C read fails).
 */
uint16_t ina219ReadRegisterRaw(const INA219_Rail &r, uint8_t reg);

/**
 * @brief Write a raw 16-bit INA219 register.
 *
 * @param r    Rail whose INA219 to talk to.
 * @param reg  Register address.
 * @param data 16-bit value to write.
 */
void     ina219WriteRegisterRaw(const INA219_Rail &r, uint8_t reg, uint16_t data);

/**
 * @brief Compute INA219 calibration and CONFIG register from rail’s R_shunt / I_maxExp.
 *
 * This writes CALIBRATION and CONFIG to the chip and updates r.currentLSB_A,
 * r.powerLSB_W and r.calReg.
 *
 * @param r Rail to configure.
 */
void     ina219ApplyConfigFromRail(INA219_Rail &r);

// ---------------------------------------------------------------------------
// Measurements (per-rail)
// ---------------------------------------------------------------------------

/**
 * @brief Read bus voltage in volts from the INA219 and apply V_cal.
 *
 * @param r Rail to measure.
 * @return Bus voltage [V], or NaN if not present.
 */
float    readRailBusVoltage_V(INA219_Rail &r);

/**
 * @brief Read shunt voltage in millivolts from the INA219.
 *
 * @param r Rail to measure.
 * @return Shunt voltage [mV], or NaN if not present.
 */
float    readRailShuntVoltage_mV(INA219_Rail &r);

/**
 * @brief Read current in amperes using the calibrated INA219.
 *
 * @param r Rail to measure.
 * @return Current [A], or NaN if not available.
 */
float    readRailCurrent_A(INA219_Rail &r);

/**
 * @brief Read power in watts using the calibrated INA219.
 *
 * @param r Rail to measure.
 * @return Power [W], or NaN if not available.
 */
float    readRailPower_W(INA219_Rail &r);

/**
 * @brief Read current in milliamps.
 *
 * @param r Rail to measure.
 * @return Current [mA], or NaN if not available.
 */
float    readRailCurrent_mA(INA219_Rail &r);

/**
 * @brief Read power in milliwatts.
 *
 * @param r Rail to measure.
 * @return Power [mW], or NaN if not available.
 */
float    readRailPower_mW(INA219_Rail &r);

// ---------------------------------------------------------------------------
// Name-based lookup & measurement
// ---------------------------------------------------------------------------

/**
 * @brief Find a rail index by its name string.
 *
 * @param name Null-terminated rail name, must match rails[i].name exactly.
 * @return Index into rails[] if found, or -1 if not found.
 */
int         findRailIndex(const char *name);

/**
 * @brief Get a pointer to a rail by name.
 *
 * @param name Rail name string.
 * @return Pointer to INA219_Rail, or nullptr if not found.
 */
INA219_Rail* getRailByName(const char *name);

/**
 * @brief Read bus voltage [V] by rail name.
 */
float       getRailBusVoltage_V(const char *name);

/**
 * @brief Read shunt voltage [mV] by rail name.
 */
float       getRailShuntVoltage_mV(const char *name);

/**
 * @brief Read current [A] by rail name.
 */
float       getRailCurrent_A(const char *name);

/**
 * @brief Read power [W] by rail name.
 */
float       getRailPower_W(const char *name);

/**
 * @brief Read current [mA] by rail name.
 */
float       getRailCurrent_mA(const char *name);

/**
 * @brief Read power [mW] by rail name.
 */
float       getRailPower_mW(const char *name);

/**
 * @brief Directly write a raw pot code to a rail (debug / manual override).
 *
 * This bypasses all voltage control logic (coarse/fine/NB).
 * Intended for bring-up and debugging only.
 *
 * @param name Rail name
 * @param code Pot wiper code [0..255]
 * @return true if rail found and pot written, false otherwise
 */
bool 	writeRailPotRawByName(const char *name, uint8_t code);

/**
 * @brief Directly write a raw pot code to a rail (debug / manual override).
 *
 * This bypasses all voltage control logic (coarse/fine/NB).
 * Intended for bring-up and debugging only.
 *
 * @param name Rail name
 * @param code Pot wiper code [0..255]
 * @return true if rail found and pot written, false otherwise
 */
bool writeRailPotRawByName(const char *name, uint8_t code);

bool setRailsVoltageParallelByName(
  const RailSetReq *reqs,
  size_t            count,
  RailStatus       *outStatus
);

// ---------------------------------------------------------------------------
// Compliance
// ---------------------------------------------------------------------------

/**
 * @brief Set absolute current compliance (limit) in amperes for a rail.
 *
 * If |I| exceeds this limit during setRailVoltage, the rail is shut down and
 * status is set to RAIL_STATUS_OVERCURRENT.
 *
 * @param name      Rail name.
 * @param I_limit_A Compliance limit [A]; 0 disables compliance.
 * @return true if rail found, false otherwise.
 */
bool        setRailCompliance_A(const char *name, float I_limit_A);

/**
 * @brief Set absolute current compliance (limit) in milliamps for a rail.
 *
 * @param name       Rail name.
 * @param I_limit_mA Compliance limit [mA]; 0 disables compliance.
 * @return true if rail found, false otherwise.
 */
bool        setRailCompliance_mA(const char *name, float I_limit_mA);

/**
 * @brief Set I_limit_A for all rails to 120% of I_maxExp (if I_maxExp > 0).
 *
 * Call this after your rails[] table is defined to get default compliance.
 */
void        resetAllComplianceToDefault();

bool checkCurrentCompliance(INA219_Rail &r);

/**
 * @brief Check current compliance on all rails once.
 *
 * For each rail:
 * - If rail not present -> RAIL_STATUS_DEVICE_FAIL (or keeps existing status)
 * - If compliance disabled -> leaves status unchanged (usually OK)
 * - If overcurrent -> shuts rail down (same behavior as checkCurrentCompliance)
 *
 * @param outStatus  Array of length RAIL_COUNT (required).
 * @return true if no rail tripped overcurrent; false if any did.
 */
bool checkAllRailsCompliance(RailStatus *outStatus);

// ---------------------------------------------------------------------------
// Init / voltage control
// ---------------------------------------------------------------------------

/**
 * @brief Initialize I2C, SPI, DAC, and all rails in rails[].
 *
 * - Probes each INA219, applies calibration/config if present.
 * - Sets r.present and r.status for each rail.
 *
 * @return RAIL_STATUS_OK if at least one INA219 is present and configured,
 *         RAIL_STATUS_DEVICE_FAIL otherwise.
 */
RailStatus  beginAllRails();

// ---------------------------------------------------------------------------
// Limits
// ---------------------------------------------------------------------------

#define MAX_LUT_POINTS 8
#define MAX_NB_RAILS   32   // Due / GIGA safe (itsybitsy can use fewer)

// Batch helper: how many rails you can drive in one parallel batch call
#ifndef INA219RAILS_MAX_BATCH
  #define INA219RAILS_MAX_BATCH MAX_NB_RAILS
#endif

// ---------------------------------------------------------------------------
// Debug / calibration
// ---------------------------------------------------------------------------

/**
 * @brief Print a calibration summary table for all rails over Serial.
 *
 * This function itself is fully gated by gCalDebug:
 * - If gCalDebug == true, prints a nice summary.
 * - If gCalDebug == false, it does nothing.
 */
void        printCalibrationSummary();

/**
 * @brief Convert RailStatus enum to a human-readable string.
 *
 * @param s RailStatus value.
 * @return Constant C-string describing the status.
 */
const char* railStatusToStr(RailStatus s);

#endif // INA219_RAILS_H
