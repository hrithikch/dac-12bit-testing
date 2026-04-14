//
// This sketch is used in an Adafruit ItsyBitsy M0 Express to be the interface between a PC running Matlab and the A8T12B16T4G ADC chip
// It communicates to the host machine through the USB port and sends SPI commands to the test board LDOs and ADC chip
// The ADC chip configuration inputs are driven and the on chip FIFO can be read out through the Arduino
//
//  Author: Tracy Johancsik
//  Date Created: 2/11/2026
//
#include <Arduino.h>
#include <Ina219Rails.h>
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_DotStar.h>

// Define pins for ItsyBitsy M0 DotStar
#define DOTSTAR_DATA 41
#define DOTSTAR_CLK  40
#define NUMPIXELS  1 // Only 1 LED on board

Adafruit_DotStar strip(NUMPIXELS, DOTSTAR_DATA, DOTSTAR_CLK, DOTSTAR_BGR);

static RailStatus sts[INA219RAILS_MAX_BATCH];

// Digital I/O pin definitions

// Onboard LED pin
#define led_pin 13

// DAC control pins
#define SPI_DOUT 13     // 13
#define WR_PAT 12       // 12
#define SEL_EXT_DIN 11  // 11
#define SPI_CP 10       // 10
#define CLK_PAT 9       // 9 
#define EN_PAT 7        // 7
#define SPI_SCAN 5      // 5  VCM
#define DIN_PAT 1       // 1

// Chip select pin definitions for all slaves on the SPI port
#define CS1   15
#define CS2   16
#define CS3   17
#define CS4   18
#define CS5   19

// ====================== rails[] table (owned by this sketch) ===============
INA219_Rail rails[] = {

  // -------- Wire, POT rails --------
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

// Setting for USB baud rate
// This should match the setting on the host computer
#define USB_BAUD_RATE 115200

// SPI frequency settings for LDO
#define LDO_SPI_FREQ 9600

// Structure for analog input lookup table
struct ADCconstants {
  const char* name;
  size_t pin;  
};

// Arduino analog input lookup table
// This table is used to look up the the pin address based on the text string provided
// for the ADC read operation.  A0-A1 are predefined constants in the arduino library
const ADCconstants constants[] = {
  {"A0", A0},
  {"A1", A1},
  {"A2", A2},
  {"A3", A3},
  {"A4", A4},
  {"A5", A5}
};

// Initialize Arduino and startup setting for the DAC
void setup() {

// DotStar LED initialization
  strip.begin(); // Initialize pins
  strip.setBrightness(30); // Set brightness (0-255)
  strip.show(); // Initialize all pixels to 'off'

// Initialize USB port and baud rate
// This must match the baud rate of the host
  Serial.begin(USB_BAUD_RATE);

// Initialize pins as inputs or outputs

  // Onboard LED
  pinMode(led_pin, OUTPUT);

  // DAC controls
  pinMode(SPI_DOUT, OUTPUT);
  pinMode(WR_PAT, OUTPUT);
  pinMode(SEL_EXT_DIN, OUTPUT);
  pinMode(SPI_CP, OUTPUT);
  pinMode(CLK_PAT, OUTPUT);
  pinMode(EN_PAT, OUTPUT);
  pinMode(SPI_SCAN, OUTPUT);
  pinMode(DIN_PAT, OUTPUT);

  // SPI port initialization
  pinMode(CS1, OUTPUT);
  pinMode(CS2, OUTPUT);
  pinMode(CS3, OUTPUT);
  pinMode(CS4, OUTPUT);
  pinMode(CS5, OUTPUT);

// Set pins to the startup values

  // Onboard LED off
  digitalWrite(led_pin, LOW);

  // DAC controls
  digitalWrite(SPI_DOUT, LOW);
  digitalWrite(WR_PAT, LOW);
  digitalWrite(SEL_EXT_DIN, LOW);
  digitalWrite(SPI_CP, LOW);
  digitalWrite(CLK_PAT, LOW);
  digitalWrite(EN_PAT, LOW);
  digitalWrite(SPI_SCAN, LOW);
  digitalWrite(DIN_PAT, LOW);

  // SPI chip select pin initialization
  digitalWrite(CS1, HIGH);
  digitalWrite(CS2, HIGH);
  digitalWrite(CS3, HIGH);
  digitalWrite(CS4, HIGH);
  digitalWrite(CS5, HIGH);

  // Initialize SPI port
  //SPI.begin();

  gCalDebug = false;    // turn off init + calibration summary
  gNbDebug  = false;    // turn off NB coarse/fine progress

  beginAllRails();

  resetAllComplianceToDefault();

}

void loop() {
  char cmd_char[128];
  String split_cmd[40];

  // Listen for data from the USB port
  if (Serial.available() > 0){

    // Get command string from the USB port
    String cmd = Serial.readString();

    // Split the command string using the ',' as a delimeter and put it in an array of strings called split_cmd
    cmd.toCharArray(cmd_char, sizeof(cmd_char));
    uint8_t count = 0;

    char *p = strtok(cmd_char, ",");
    while(p && count < (sizeof(split_cmd) / sizeof(split_cmd[0]))){
      split_cmd[count++] = p;
      p = strtok(NULL, ",");
    }

  // This section decodes all of the possible commands.
  //
  // List of commands and arguments:

  // LDO_WRITE,RAIL,value
  // SET_VOLTAGE,RAIL_name1,RAIL_value1,RAIL_name2,RAIL_value2,RAIL_name3,RAIL_value3,RAIL_name4,RAIL_value4,RAIL_name5,RAIL_value5,....
  // INITIALIZE_COMPLIANCE
  // SET_COMPLIANCE,RAIL,value
  // READ_ADC,Channel
  // READ_VOLTAGE,RAIL
  // READ_SHUNTV,RAIL
  // READ_CURRENT,RAIL
  // READ_POWER,RAIL
  // DIO_ON,Pin
  // DIO_OFF,Pin
  // ON
  // OFF
  //
  // Detailed command description:
  //
  // LDO_WRITE,CS,VALUE
  //    Description:
  //      This command is used to set the value of the POT for the target LDO for adjusting the voltage
  //    Arguments:
  //      CS          (8-bit Integer)     Digital I/O pin number to address the LDO on the SPI port
  //      VALUE       (8-bit Integer)     Value to set it to
  //    Returns:
  //      true
  //
  // SET_VOLTAGE,RAIL_name1,RAIL_value1,RAIL_name2,RAIL_value2,RAIL_name3,RAIL_value3,RAIL_name4,RAIL_value4,RAIL_name5,RAIL_value5,....
  //    Description:
  //      This command is used to set the voltage on multiple rails with one command.
  //    Arguments:
  //      RAIL_name*, RAIL_value*         Multiple pairs of rail and values separated by commas.  The rail is set to the voltage in value.
  //    Returns:
  //      Array of uint8_t enumerated with status values for each rail that was set.  The values in the array are in the same order as
  //      the rail name and value given in the command.  The status values are preceded by a 0xAA, 0x55 and then the number of status values
  //      that were in the rail/value pair arguments.  Finally an xor checksum of the returned status is performed to finalize the frame.
  //      The format is 0xAA, 0x55, number of rail/voltage pair statuses, all rail/voltage pair statuses, xor of all statuses of rail/value pairs.
  //      This is the enumerated table:
  //          RAIL_STATUS_OK = 0,          Operation successful and within tolerance.
  //          RAIL_STATUS_WARN,            Operation completed, but outside tolerance.
  //          RAIL_STATUS_OUT_OF_RANGE,    Target voltage not reachable within limits.
  //          RAIL_STATUS_STUCK,           Legacy "stuck" condition (not heavily used).
  //          RAIL_STATUS_TIMEOUT,         Operation timed out before convergence.
  //          RAIL_STATUS_DEVICE_FAIL,     INA219 or driver failure for this rail.
  //          RAIL_STATUS_UNSTABLE,        Voltage could not be stabilized near target.
  //          RAIL_STATUS_OVERCURRENT      Current exceeded compliance limit; rail shut down.
  //
  //
  // INITIALIZE_COMPLIANCE
  //    Description:
  //      Initializes current compliance to default values in rail table
  //    Arguments:
  //      none
  //    Returns:
  //      true
  //
  // SET_COMPLIANCE,RAIL,value
  //    Description:
  //      Sets the current compliance for a specific rail.
  //    Arguments:
  //      RAIL        Name of rail to set compliance for
  //      value       Max current before shutting down the rail in mA
  //    Returns:
  //      true
  //
  // READ_ADC,Channel
  //    Description:
  //      Reads the value from the targe Arduino ADC
  //    Arguments:
  //      Channel     (String)            The name of the channel that is defined in ADCconstants structure above without quotes
  //    Returns:
  //      A 16-bit integer with a range of 0-1023 that is read from the target ADC that represents the voltage range 0.0V to 3.3V
  //
  // READ_VOLTAGE,RAIL
  //    Description:
  //      Reads the value of the named voltage rail.
  //    Arguments:
  //      RAIL        (String)            The name of the rail
  //    Returns:
  //      Returns the voltage, -1 if rail name is wrong, or NaN if it can't find the Ina219 all as type floats
  //
  // READ_SHUNTV,RAIL
  //    Description:
  //      Reads the voltage of the named voltage rail.
  //    Arguments:
  //      RAIL        (String)            The name of the rail
  //    Returns:
  //      Returns the shunt voltage, -1 if rail name is wrong, or NaN if it can't find the Ina219 all as type floats
  //
  // READ_CURRENT,RAIL
  //    Description:
  //      Reads the current consuption of the named voltage rail.
  //    Arguments:
  //      RAIL        (String)            The name of the rail
  //    Returns:
  //      Returns the current in mA, -1 if rail name is wrong, or NaN if it can't find the Ina219 all as type floats
  //
  // READ_POWER,RAIL
  //    Description:
  //      Reads the power consumption of the named voltage rail.
  //    Arguments:
  //      RAIL        (String)            The name of the rail
  //    Returns:
  //      Returns the power in mW, -1 if rail name is wrong, or NaN if it can't find the Ina219 all as type floats
  //
  // DIO_ON,Pin
  //    Description:
  //      Sets the DIO Pin to high
  //    Arguments:
  //      Pin         (decimal number)    The pin number for the I/O port
  //    Returns:
  //      true
  //
  // DIO_OFF,Pin
  //    Description:
  //      Sets the DIO Pin to low
  //    Arguments:
  //      Pin         (decimal number)    The pin number for the I/O port
  //    Returns:
  //      true
  //
  // ON
  //    Description:
  //      Turns the onboard LED on
  //    Arguments:
  //      None
  //    Returns:
  //      true
  //
  // OFF
  //    Description:
  //      Turns the onboard LED on
  //    Arguments:
  //      None
  //    Returns:
  //      true
  //

    // Set LDO pot
    // LDO_WRITE,LDO_name,LDO_value
    if (split_cmd[0] == "LDO_WRITE"){

      bool ok = writeRailPotRawByName(split_cmd[1].c_str(), split_cmd[2].toInt());

      Serial.write((byte*)&ok, 1);

    }

    // Set Rail voltage
    // SET_VOLTAGE,RAIL_name1,RAIL_value1,RAIL_name2,RAIL_value2,RAIL_name3,RAIL_value3,RAIL_name4,RAIL_value4,RAIL_name5,RAIL_value5,....
    if (split_cmd[0] == "SET_VOLTAGE"){

      RailSetReq batch[32];
      for (size_t i=1; i < count; i=i+2) {
        batch[(i-1)/2].name = split_cmd[i].c_str();
        batch[(i-1)/2].V = atof(split_cmd[i+1].c_str());
      }

      const size_t N = (count-1)/2;

      setRailsVoltageParallelByName(batch, N, sts);

      sendStatuses(sts, (uint8_t)N);

    }

    // Set rail current compliance to default values from the rail table
    // INITIALIZE_COMPLIANCE
    if (split_cmd[0] == "INITIALIZE_COMPLIANCE"){

      resetAllComplianceToDefault();

      bool ok = true;
      Serial.write((byte*)&ok, 1);
    }

    // Set rail current compliance in mA
    // SET_COMPLIANCE,RAIL,value
    if (split_cmd[0] == "SET_COMPLIANCE"){

      bool ok = setRailCompliance_mA(split_cmd[1].c_str(), atof(split_cmd[2].c_str()));

      Serial.write((byte*)&ok, 1);
    }

    // Read ADC Channel A0 through A11
    // READ_ADC,Channel
    if (split_cmd[0] == "READ_ADC"){

      bool found = false;
      size_t adcpin = A0;

      for (size_t k = 0; k < sizeof(constants) / sizeof(constants[0]); ++k) {
        if (split_cmd[1] == constants[k].name) {
          adcpin  = constants[k].pin;
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
    }
    
    // Read INA219 Voltage
    // READ_VOLTAGE,RAIL
    if (split_cmd[0] == "READ_VOLTAGE"){

      float busvoltage = -1.0f;

      int railnum=findRailIndex(split_cmd[1].c_str());
      if (railnum == -1) {
        Serial.write((byte*)&busvoltage, 4);
        return;
      }
      INA219_Rail &r = rails[railnum];
      busvoltage = getRailBusVoltage_V(r.name);
      Serial.write((byte*)&busvoltage, 4);
    }

    // Read INA219 Shunt Voltage
    // READ_SHUNTV,RAIL
    if (split_cmd[0] == "READ_SHUNTV"){

      float shuntvoltage = -1.0f;

      int railnum=findRailIndex(split_cmd[1].c_str());
      if (railnum == -1) {
        Serial.write((byte*)&shuntvoltage, 4);
        return;
      }
      INA219_Rail &r = rails[railnum];
      shuntvoltage = getRailShuntVoltage_mV(r.name);
      Serial.write((byte*)&shuntvoltage, 4);
    }

    // Read INA219 Current
    // READ_CURRENT,RAIL
    if (split_cmd[0] == "READ_CURRENT"){

     float current_mA = -1.0f;

     int railnum=findRailIndex(split_cmd[1].c_str());
      if (railnum == -1) {
        Serial.write((byte*)&current_mA, 4);
        return;
      }
      INA219_Rail &r = rails[railnum];
      current_mA = getRailCurrent_mA(r.name);
      Serial.write((byte*)&current_mA, 4);
    }

    // Read INA219 Power
    // READ_POWER,RAIL
    if (split_cmd[0] == "READ_POWER"){

      float power_mW = -1.0f;

      int railnum=findRailIndex(split_cmd[1].c_str());
      if (railnum == -1) {
        Serial.write((byte*)&power_mW, 4);
        return;
      }
      INA219_Rail &r = rails[railnum];
      power_mW = getRailPower_mW(r.name);
      Serial.write((byte*)&power_mW, 4);
    }

    // Turn specified DIO pin on
    // DIO_ON,Pin
    if (split_cmd[0] == "DIO_ON"){
      digitalWrite(split_cmd[1].toInt(), HIGH);      

      bool ok = true;
      Serial.write((byte*)&ok, 1);
    }

    // Turn specified DIO pin off
    // DIO_OFF,Pin
    if (split_cmd[0] == "DIO_OFF"){
      digitalWrite(split_cmd[1].toInt(), LOW);      

      bool ok = true;
      Serial.write((byte*)&ok, 1);
    }

    // Turn onboard LED on
    // ON
    if (split_cmd[0] == "ON"){
//      digitalWrite(led_pin, LOW);
      // Set pixel 0 to Blue
      strip.setPixelColor(0, 0, 0, 255);
      strip.show();

      bool ok = true;
      Serial.write((byte*)&ok, 1);
    }

    // Turn onboard LED off
    // OFF
    if (split_cmd[0] == "OFF"){
//      digitalWrite(led_pin, HIGH);
      // Set pixel 0 to Off
      strip.setPixelColor(0, 0, 0, 0);
      strip.show();

      bool ok = true;
      Serial.write((byte*)&ok, 1);
    }

  }
}

void sendStatuses(const RailStatus* sts, uint8_t n) {
  const uint8_t SOF0 = 0xAA;
  const uint8_t SOF1 = 0x55;

  Serial.write(SOF0);
  Serial.write(SOF1);
  Serial.write(n);  // length

  // payload
  Serial.write(reinterpret_cast<const uint8_t*>(sts), n);

  // checksum: XOR of payload bytes
  uint8_t x = 0;
  for (uint8_t i = 0; i < n; i++) x ^= static_cast<uint8_t>(sts[i]);
  Serial.write(x);
}



