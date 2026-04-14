#include <math.h>

const int SPI_DOUT    = 10;
const int DIN_PAT     = 9;
const int SPI_SCK_PAT = 1;
const int SPI_SCAN    = 12;
const int EN_PAT      = 7;
const int WR_PAT      = 13;
const int SPI_CP      = 11;
const int SEL_EXT_DIN = 5;

#define CLK_DELAY_US 1   // smaller = faster
#define BITS_PER_WORD 12 // DAC word width

// GENERALIZED FREQUENCY SETTINGS (in Hz)
// Defined as double to prevent 32-bit integer overflow at GHz frequencies
const double F_OUT       = 266240000; // Desired Sine Wave Frequency: 1.015808 GHz
const double F_SAMPLE    = 5.24288e9; // DAC Sampling Rate: 8.388608 GHz
const int    NUM_SAMPLES = 256;        // Number of samples in the buffer

uint8_t i = 0;

void setup() {
  pinMode(DIN_PAT,     OUTPUT);
  pinMode(SPI_SCK_PAT, OUTPUT);
  pinMode(SPI_SCAN,    OUTPUT);
  pinMode(EN_PAT,      OUTPUT);
  pinMode(WR_PAT,      OUTPUT);
  pinMode(SPI_CP,      OUTPUT);
  pinMode(SEL_EXT_DIN, OUTPUT);
  pinMode(SPI_DOUT,    INPUT_PULLDOWN);
}

void loop() {
  if (i == 0) {
    start();
    i = i + 1;
  }
}

void start() {
  uint32_t CNTRL = 0x01586;  // 20-control bits
  uint32_t data_sine[NUM_SAMPLES]; 
  
  // Generalized calculation of M (number of coherent cycles)
  const double M = (F_OUT * NUM_SAMPLES) / F_SAMPLE; 
  
  // Dynamically generate a 12-bit sine wave (0 to 4095) across NUM_SAMPLES
  for(int k = 0; k < NUM_SAMPLES; k++) {
    // Math: sin() outputs -1.0 to 1.0. 
    // Multiply by 2047.5 to scale amplitude, then add 2047.5 for DC offset.
    data_sine[k] = (uint32_t)(round(2047.5 * sin(2.0 * PI * M * k / (double)NUM_SAMPLES) + 2047.5)); 
  }

  digitalWrite(SPI_CP, LOW);
  digitalWrite(SEL_EXT_DIN, LOW);
  digitalWrite(WR_PAT, LOW);
  digitalWrite(EN_PAT, LOW);

  sendBits(CNTRL, 20); // Loading 20 control bits

  // Write Data into Pattern Generator
  digitalWrite(WR_PAT, HIGH);
  delay(10);
  
  // Load the full sine wave buffer
  for (int k = 0; k < NUM_SAMPLES; k++) {
    send_data_Bits_LSB(data_sine[k], BITS_PER_WORD); 
  }
  
  digitalWrite(WR_PAT, LOW);
  delay(100);
  
  digitalWrite(EN_PAT, HIGH); // Enable Pattern Generator
  delay(1000);
}

// Keep sendBits as MSB-first if the 20-bit CNTRL register requires it
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

// Send Data LSB first for the DAC Pattern Generator
void send_data_Bits_LSB(uint32_t data, uint8_t numBits) {
  // Counting UP from 0 sends the Least Significant Bit first
  for (int j = 0; j < numBits; j++) {
    digitalWrite(SPI_SCK_PAT, LOW);
    digitalWrite(DIN_PAT, (data >> j) & 0x01);
    delayMicroseconds(CLK_DELAY_US);
    digitalWrite(SPI_SCK_PAT, HIGH);  
    delayMicroseconds(CLK_DELAY_US);
  }
}