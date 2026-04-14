//
// This sketch is used in an Arduino Due to be the interface between a PC running Matlab and the A8T12B16T4G ADC chip
// It communicates to the host machine through the USB port and sends SPI commands to the test board LDOs and ADC chip
// The ADC chip configuration inputs are driven and the on chip FIFO can be read out through the Arduino
//
//  Author: Tracy Johancsik
//  Date Created: 10/23/2025
//
#include <Arduino.h>
#include <Ina219Rails.h>
#include <SPI.h>
#include <Wire.h>
#include <pure_analog_pins.h>

static RailStatus sts[INA219RAILS_MAX_BATCH];

// Digital I/O pin definitions

// Onboard LED pin
#define led_pin 13

// FIFO control pins
#define RCLK 2
#define W_RESET 5
#define R_RESET 8
#define SEL_FIFO 3
#define FIFO_RESET 7

// ADC control pins
#define ADC_EN 22
#define EN_REFTEST 13
#define VREF_PD 23
#define ENP0_OUTPUT 10
#define ENP0_CORE 11
#define ENP0_FIFO 9
#define DEC_RATE 6
#define GLOBAL_CAL_EN 4
#define EN9MODE 12

// Chip select pin definitions for all slaves on the SPI port
#define ADC_CS 24
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
  //  0.5f, 1.5f, 0.005f, 0.001f, 0.0f,
    0.5f, 1.5f, 0.005f, 0.001f, 0.0f,
    CS9, 255, 10,
    DRIVE_POT, 0, 0,
    0UL,
    false, RAIL_STATUS_DEVICE_FAIL, NAN, 0,
    12.7f,  0.00022f, 0.0000264f, 0.0f, 0.0f, 0,
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

// FIFO depth on A8T12B16T4G should be set to 18432
#define FIFO_SIZE 18432

// Setting for USB baud rate
// This should match the setting on the host computer
#define USB_BAUD_RATE 115200

// SPI frequency settings for LDO and ADC
#define LDO_SPI_FREQ 9600
#define ADC_SPI_FREQ 14000000

// Size of the slave ID and register addresses for the ADC SPI interface
#define Reg_addr_size 16
#define Slave_ID_size 8

// Defines the digital I/O pins that are used to read the 13 bit ADC output
// The first one in the list represents bit 0
const uint8_t inputPins[] = {D22, D23, D24, D25, D26, D27, D28, D29, D30, D31, D32, D33, D84};
const int pinCount = sizeof(inputPins) / sizeof(inputPins[0]);

// Structure for analog input lookup table
struct ADCconstants {
  const char* name;
  PureAnalogPin pin;  
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
  {"A5", A5},
  {"A6", A6},
  {"A7", A7},
  {"A8", A8},
  {"A9", A9},
  {"A10", A10},
  {"A11", A11}
};

// Initialize Arduino and startup setting for the ADC
void setup() {

// Initialize USB port and baud rate
// This must match the baud rate of the host
  Serial.begin(USB_BAUD_RATE);

// Initialize pins as inputs or outputs

  // Onboard LED
  pinMode(LED_BLUE, OUTPUT);

  // FIFO controls
  pinMode(RCLK, OUTPUT);
  pinMode(W_RESET, OUTPUT);
  pinMode(R_RESET, OUTPUT);
  pinMode(SEL_FIFO, OUTPUT);
  pinMode(FIFO_RESET, OUTPUT);

  // Data pins from ADC
  //for (int i=0; i < pinCount; i++) {
  //  pinMode(inputPins[i], INPUT);
  //}

  // ADC controls
  pinMode(ADC_EN, OUTPUT);
  pinMode(EN_REFTEST, OUTPUT);
  pinMode(VREF_PD, OUTPUT);
  pinMode(ENP0_OUTPUT, OUTPUT);
  pinMode(ENP0_CORE, OUTPUT);
  pinMode(ENP0_FIFO, OUTPUT);
  pinMode(DEC_RATE, OUTPUT);
  pinMode(GLOBAL_CAL_EN, OUTPUT);
  pinMode(EN9MODE, OUTPUT);

  // SPI port initialization
  pinMode(ADC_CS, OUTPUT);
  pinMode(CS0, OUTPUT);
  pinMode(CS1, OUTPUT);
  pinMode(CS2, OUTPUT);
  pinMode(CS3, OUTPUT);
  pinMode(CS4, OUTPUT);
  pinMode(CS5, OUTPUT);
  pinMode(CS6, OUTPUT);
  pinMode(CS7, OUTPUT);
  pinMode(CS8, OUTPUT);
  pinMode(CS9, OUTPUT);
  pinMode(CS10, OUTPUT);
  pinMode(CS11, OUTPUT);
  pinMode(CS12, OUTPUT);
  pinMode(CS13, OUTPUT);
  pinMode(CS14, OUTPUT);
  pinMode(CS15, OUTPUT);
  pinMode(CS16, OUTPUT);
  pinMode(CS17, OUTPUT);

// Set pins to the startup values

  // Onboard LED off
  digitalWrite(LED_BLUE, LOW);

  // FIFO controls
  digitalWrite(RCLK, LOW);
  digitalWrite(W_RESET, LOW);
  digitalWrite(R_RESET, LOW);
  digitalWrite(SEL_FIFO, LOW);

  // ADC controls
  digitalWrite(EN_REFTEST, LOW);
  digitalWrite(VREF_PD, LOW);
  digitalWrite(ENP0_OUTPUT, LOW);
  digitalWrite(ENP0_CORE, HIGH);
  digitalWrite(ENP0_FIFO, LOW);
  digitalWrite(DEC_RATE, LOW);
  digitalWrite(GLOBAL_CAL_EN, LOW);
  digitalWrite(EN9MODE, LOW);

  // SPI chip select pin initialization
  digitalWrite(ADC_CS, LOW);
  digitalWrite(CS0, HIGH);
  digitalWrite(CS1, HIGH);
  digitalWrite(CS2, HIGH);
  digitalWrite(CS3, HIGH);
  digitalWrite(CS4, HIGH);
  digitalWrite(CS5, HIGH);
  digitalWrite(CS6, HIGH);
  digitalWrite(CS7, HIGH);
  digitalWrite(CS8, HIGH);
  digitalWrite(CS9, HIGH);
  digitalWrite(CS10, HIGH);
  digitalWrite(CS11, HIGH);
  digitalWrite(CS12, HIGH);
  digitalWrite(CS13, HIGH);
  digitalWrite(CS14, HIGH);
  digitalWrite(CS15, HIGH);
  digitalWrite(CS16, HIGH);
  digitalWrite(CS17, HIGH);

  // Perform initial reset
  digitalWrite(FIFO_RESET, LOW);
  digitalWrite(ADC_EN, LOW);
  delay(3);
  digitalWrite(FIFO_RESET, HIGH);
  digitalWrite(ADC_EN, HIGH);

  // Initialize SPI port
  //SPI.begin();

  gCalDebug = false;    // turn off init + calibration summary
  gNbDebug  = false;    // turn off NB coarse/fine progress

  beginAllRails();

  resetAllComplianceToDefault();

// -------- Parallel batch set: only the rails you include here are touched
//  RailSetReq batch[] = {
//    { "AVDD", 0.80f },
//    { "VREFC_GATE", 1.2f },
//    { "VREF", 0.6f },
//  };

//  const size_t N = sizeof(batch) / sizeof(batch[0]);
//  RailStatus sts[N];

//  bool ok = setRailsVoltageParallelByName(batch, N, sts);

}

void loop() {
  char cmd_char[128];
  int i;
  String split_cmd[40];

  // Listen for data from the USB port
  if (Serial.available() > 0){

    // Get command string from the USB port
    String cmd = Serial.readString();

    // Split the command string using the ',' as a delimeter and put it in an array of strings called split_cmd
    cmd.toCharArray(cmd_char, sizeof(cmd_char));
    uint8_t count = 0;

    i = 0;
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
  // SPI_WRITE,SLAVE_ID,REG_ADDR,DATA  
  // SPI_READ,SLAVE_ID,REG_ADDR
  // READ_ADC,Channel
  // READ_VOLTAGE,RAIL
  // READ_SHUNTV,RAIL
  // READ_CURRENT,RAIL
  // READ_POWER,RAIL
  // DIO_ON,Pin
  // DIO_OFF,Pin
  // ON
  // OFF
  // FIFO_READ
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
  // SPI_WRITE,SLAVE_ID,REG_ADDR,DATA  
  //    Description:
  //      This command is used to set the value of the POT for the target LDO for adjusting the voltage
  //    Arguments:
  //      SLAVE_ID    (8-bit Hex)         This is the address of the target SPI module to write to
  //      REG_ADDR    (16-bits Hex)       This is the target register within the SPI module to write to
  //    Returns:
  //      Nothing
  //
  // SPI_READ,SLAVE_ID,REG_ADDR
  //    Description:
  //      Sets the value of the POT for the target LDO for adjusting the voltage
  //    Arguments:
  //      SLAVE_ID    (8-bit Hex)         This is the address of the target SPI module to read from
  //      REG_ADDR    (16-bits Hex)       This is the target register within the SPI module to read from
  //    Returns:
  //      A 32-bit integer value that the target register is set to
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
  // FIFO_READ
  //    Description:
  //      Reads the contents of the high-speed capture FIFO on the chip
  //    Arguments:
  //      None
  //    Returns:
  //      The contents of the FIFO starting with first value captured
  //      The number of values returned is set by FIFO_SIZE
  //      Every value is a 16-bit integer
  //      The number of 65535 is the last word sent to mark the end of the contents
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

    // Write to SPI port
    // SPI_WRITE,SLAVE_ID,REG_ADDR,DATA
    if (split_cmd[0] == "SPI_WRITE"){
      int control_word = 0;
      int bytes[4];
      char temp_char[100];

      // Begin SPI transfer to ADC chip
      SPI.beginTransaction(SPISettings(ADC_SPI_FREQ, MSBFIRST, SPI_MODE0));
      digitalWrite(ADC_CS, HIGH);

      // Set write mode in the SPI control word
      bitWrite(control_word, 31, 1);

      // Convert HEX register address to an integer and add it to the proper range in the control word
      split_cmd[2].toCharArray(temp_char, split_cmd[2].length() + 1);
      int Reg_addr = strtol(temp_char, NULL, 16);
      for (int i = 0; i < Reg_addr_size; i++)
        bitWrite(control_word, i, bitRead(Reg_addr, i));

      // Convert HEX slave ID to an integer and add it to the proper range in the control word
      split_cmd[1].toCharArray(temp_char, split_cmd[1].length() + 1);
      int Slave_ID = strtol(temp_char, NULL, 16);
      for (int i=0; i < Slave_ID_size; i++)
        bitWrite(control_word, i+Reg_addr_size, bitRead(Slave_ID, i));

      // Split the control word up into four bytes to be sent to the SPI
      for (int i = 0; i<4; i++)
        bytes[i] = control_word >> i*8 & 0xFF;

      // Write 32-bit command word to SPI port
      for (int i = 3; i > -1; i--)
        SPI.transfer(bytes[i]);
      for (int i = 0; i<4; i++)
        bytes[i] = split_cmd[3].toInt() >> i*8 & 0xFF;
      for (int i = 3; i > -1; i--)
        SPI.transfer(bytes[i]);

      // End SPI transfer to chip
      digitalWrite(ADC_CS, LOW);

      bool ok = true;
      Serial.write((byte*)&ok, 1);
    }


    // Read from SPI port
    // SPI_READ,SLAVE_ID,REG_ADDR
    if (split_cmd[0] == "SPI_READ"){
      int control_word = 0;
      int data_word = 0;
      int bytes[4];
      char temp_char[100];

      // Begin SPI transfer to ADC chip
      SPI.beginTransaction(SPISettings(ADC_SPI_FREQ, MSBFIRST, SPI_MODE0));
      digitalWrite(ADC_CS, HIGH);

      // Convert HEX register address to an integer and add it to the proper bit range in the control word
      split_cmd[2].toCharArray(temp_char, split_cmd[2].length() + 1);
      int Reg_addr = strtol(temp_char, NULL, 16);
      for (int i = 0; i < Reg_addr_size; i++)
        bitWrite(control_word, i, bitRead(Reg_addr, i));

      // Convert HEX slave ID to an integer and add it to the proper range in the control word
      split_cmd[1].toCharArray(temp_char, split_cmd[1].length() + 1);
      int Slave_ID = strtol(temp_char, NULL, 16);
      for (int i=0; i < Slave_ID_size; i++)
        bitWrite(control_word, i+Reg_addr_size, bitRead(Slave_ID, i));
      for (i = 0; i<4; i++)
        bytes[i] = control_word >> i*8 & 0xFF;
      for (int i = 3; i > -1; i--)
        SPI.transfer(bytes[i]);
      for (int i = 3; i > -1; i--)
        bytes[i]=SPI.transfer(0x00);
      for (int i = 0; i<4; i++)
        data_word = data_word | bytes[i] << i*8;

      // End SPI transfer to chip
      digitalWrite(ADC_CS, LOW);

      // Return contents of SPI register
      Serial.write((byte*)&data_word, 4);
    }

    // Read ADC Channel A0 through A11
    // READ_ADC,Channel
    if (split_cmd[0] == "READ_ADC"){

      bool found = false;
      PureAnalogPin adcpin = A0;

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
      digitalWrite(LED_BLUE, LOW);

      bool ok = true;
      Serial.write((byte*)&ok, 1);
    }

    // Turn onboard LED off
    // OFF
    if (split_cmd[0] == "OFF"){
      digitalWrite(LED_BLUE, HIGH);

      bool ok = true;
      Serial.write((byte*)&ok, 1);
    }

    // Read out the FIFO contents and output them through the USB port
    // FIFO_READ
    if (split_cmd[0] == "READ_FIFO"){

      // Starts FIFO capture at full clock rate
      digitalWrite(W_RESET, HIGH);
      delay(1);
      digitalWrite(W_RESET, LOW);

      // Switch the digital outputs to the FIFO
      digitalWrite(SEL_FIFO, HIGH);
      delay(3);

      // Start FIFO read
      digitalWrite(R_RESET, HIGH);
      delay(1);
      digitalWrite(R_RESET, LOW);
      delay(1);

      // Read out FIFO contents one value at a time and send through USB port
      
      for (int j = 0; j<FIFO_SIZE; j++){
        int busValue = 0;

        // This read the value from the ADC digital outputs and puts it in the variable busValue
        for (int i = 0; i < pinCount; i++){
          bitWrite(busValue, i, digitalRead(inputPins[i]));
        }

      // This clocks the FIFO and returns a value through the USB port
      digitalWrite(RCLK, HIGH);
        Serial.write((byte*)&busValue, 2);
      digitalWrite(RCLK, LOW);
      }

      // Send a 16 bit word that is all ones to mark the end of the FIFO transmission
      int busValue = 65535;
      Serial.write((byte*)&busValue, 2);

      // Switch back to normal ADC output instead of FIFO
      digitalWrite(SEL_FIFO, LOW);
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



