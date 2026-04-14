% 8027_ADC_Arduino_test.m
% MATLAB conversion of the provided Python serial script.
% Requires MATLAB R2019b+ (serialport).

clear; clc;

% -----------------------------------------------------------------------------
% Enumerate available serial ports (similar to Python list_ports)
% -----------------------------------------------------------------------------
try
    disp("Available ports:");
    disp(serialportlist("available"));
catch
    disp("serialportlist() not available in this MATLAB version.");
end

% -----------------------------------------------------------------------------
% Configure and open serial port
% -----------------------------------------------------------------------------
portName = "COM6";
baudRate = 115200;

s = serialport(portName, baudRate);
s.Timeout = 5;      % seconds (increase if needed)
flush(s);

% -----------------------------------------------------------------------------
% Status code name map (like Python dict)
% -----------------------------------------------------------------------------
NAMES = containers.Map( ...
    {0,1,2,3,4,5,6,7}, ...
    {"OK","WARN","OUT_OF_RANGE","STUCK","TIMEOUT","DEVICE_FAIL","UNSTABLE","OVERCURRENT"} );

% -----------------------------------------------------------------------------
% Initialize current compliance to default values in rail table
% -----------------------------------------------------------------------------
disp("Initializing current compliance");
sendCmd(s, "INITIALIZE_COMPLIANCE");
disp(readUInt8(s));
disp("Finished initializing current compliance");
disp(" ");

% -----------------------------------------------------------------------------
% Basic LED test: toggle ON/OFF several times
% -----------------------------------------------------------------------------
disp("Flashing LED");

sendCmd(s, "ON");
disp(readUInt8(s));
pause(1);

sendCmd(s, "OFF");
disp(readUInt8(s));
pause(1);

sendCmd(s, "ON");
disp(readUInt8(s));
pause(1);

sendCmd(s, "OFF");
disp(readUInt8(s));
pause(1);

disp("Finished flashing LED");
disp(" ");

% -----------------------------------------------------------------------------
% Pulse digital I/O pin 87 (toggles green LED on hardware)
% -----------------------------------------------------------------------------
disp("Pulse DIO 87 high, low, high, low, high. Flashes green LED");

sendCmd(s, "DIO_ON,87");
disp(readUInt8(s));
pause(1);

sendCmd(s, "DIO_OFF,87");
disp(readUInt8(s));
pause(1);

sendCmd(s, "DIO_ON,87");
disp(readUInt8(s));
pause(1);

sendCmd(s, "DIO_OFF,87");
disp(readUInt8(s));
pause(1);

sendCmd(s, "DIO_ON,87");
disp(readUInt8(s));
pause(1);

disp("Finished pulsing DIO 87");
disp(" ");

% -----------------------------------------------------------------------------
% Read FIFO data stream until sentinel value 0xFFFF is received
% -----------------------------------------------------------------------------
disp("Downloading FIFO Data");
sendCmd(s, "READ_FIFO");

count = 0;
while true
    v = readUInt16LE(s);
    if v == 65535
        disp("Exiting");
        disp(" ");
        break;
    end
    count = count + 1;
end

fprintf("Received %d samples\n", count);
disp("Finished downloading FIFO data");
disp(" ");

% -----------------------------------------------------------------------------
% SPI write to ADC (chip select 23, 4 bytes, hex payload)
% -----------------------------------------------------------------------------
disp("Writing to ADC SPI port");
sendCmd(s, "SPI_WRITE,23,4,32A67CF5");
disp(readUInt8(s));
disp("Finished write to ADC SPI port");
disp(" ");

pause(3);

% -----------------------------------------------------------------------------
% SPI read from ADC (chip select 23, 4 bytes)
% -----------------------------------------------------------------------------
disp("Reading from ADC SPI port");
sendCmd(s, "SPI_READ,23,4");
u32 = readUInt32LE(s);
disp(u32);
disp("Finished read ADC SPI port");
disp(" ");

% -----------------------------------------------------------------------------
% Read Arduino internal ADC pin A0
% -----------------------------------------------------------------------------
disp("Reading Arduino ADC value");
sendCmd(s, "READ_ADC,A0");
u16 = readUInt16LE(s);
disp(u16);
disp("Finished reading Arduino ADC value");
disp(" ");

pause(3);

% -----------------------------------------------------------------------------
% Read AVDD rail measurements via INA219
% -----------------------------------------------------------------------------
disp("Reading AVDD voltage");
sendCmd(s, "READ_VOLTAGE,AVDD");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading AVDD voltage");
disp(" ");

disp("Reading AVDD shunt voltage");
sendCmd(s, "READ_SHUNTV,AVDD");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading AVDD shunt voltage");
disp(" ");

disp("Reading AVDD current");
sendCmd(s, "READ_CURRENT,AVDD");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading AVDD current");
disp(" ");

disp("Reading AVDD power");
sendCmd(s, "READ_POWER,AVDD");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading AVDD power");
disp(" ");

pause(3);

% -----------------------------------------------------------------------------
% Set multiple rail voltages (returns framed status response)
% -----------------------------------------------------------------------------
disp("Setting voltages");
sendCmd(s, "SET_VOLTAGE,AVDD,0.7,VREFC_GATE,1.2,VREF,0.6");

statuses = readStatusFrame(s);
disp(statusCodesToStrings(statuses, NAMES));
disp("Finished setting voltages");
disp(" ");

% -----------------------------------------------------------------------------
% Read back rail voltages and power metrics
% -----------------------------------------------------------------------------
disp("Reading AVDD voltage");
sendCmd(s, "READ_VOLTAGE,AVDD");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading AVDD voltage");
disp(" ");

disp("Reading VREFC_GATE voltage");
sendCmd(s, "READ_VOLTAGE,VREFC_GATE");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading VREFC_GATE voltage");
disp(" ");

disp("Reading VREF voltage");
sendCmd(s, "READ_VOLTAGE,VREF");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading VREF voltage");
disp(" ");

disp("Reading VREFC_GATE shunt voltage");
sendCmd(s, "READ_SHUNTV,VREFC_GATE");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading VREFC_GATE shunt voltage");
disp(" ");

disp("Reading VREFC_GATE current in mA");
sendCmd(s, "READ_CURRENT,VREFC_GATE");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading VREFC_GATE current");
disp(" ");

disp("Reading VREFC_GATE power");
sendCmd(s, "READ_POWER,VREFC_GATE");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading VREFC_GATE power");
disp(" ");

% -----------------------------------------------------------------------------
% Set LDO digital potentiometer
% -----------------------------------------------------------------------------
disp("Setting LDO pot");
sendCmd(s, "LDO_WRITE,AVDD,128");
disp(readUInt8(s));
disp("Done setting LDO pot");
disp(" ");

% -----------------------------------------------------------------------------
% Read AVDD voltage to see that it changed after setting the LDO pot
% -----------------------------------------------------------------------------
disp("Reading AVDD voltage");
sendCmd(s, "READ_VOLTAGE,AVDD");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading AVDD voltage");
disp(" ");

% -----------------------------------------------------------------------------
% Set compliance current on VREFC_GATE rail
% -----------------------------------------------------------------------------
disp("Setting VREFC_GATE compliance to 0.04 mA");
sendCmd(s, "SET_COMPLIANCE,VREFC_GATE,0.04");
disp(readUInt8(s));
disp("Finished setting VREFC_GATE compliance");
disp(" ");

% -----------------------------------------------------------------------------
% Set multiple rail voltages (blocking version) - second setpoint set
% -----------------------------------------------------------------------------
disp("Setting voltages");
sendCmd(s, "SET_VOLTAGE,AVDD,0.8,VREFC_GATE,1.3,VREF,0.5");

statuses = readStatusFrame(s);
disp(statusCodesToStrings(statuses, NAMES));

disp("Finished reading Error value");
disp("Finished setting voltages");
disp(" ");

% -----------------------------------------------------------------------------
% Read back AVDD, VREFC_GATE, VREF voltages to verify convergence
% -----------------------------------------------------------------------------
disp("Reading AVDD voltage");
sendCmd(s, "READ_VOLTAGE,AVDD");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading AVDD voltage");
disp(" ");

disp("Reading VREFC_GATE voltage");
sendCmd(s, "READ_VOLTAGE,VREFC_GATE");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading VREFC_GATE voltage");
disp(" ");

disp("Reading VREF voltage");
sendCmd(s, "READ_VOLTAGE,VREF");
fprintf("%.3f\n", readFloat32LE(s));
disp("Finished reading VREF voltage");
disp(" ");

% -----------------------------------------------------------------------------
% Close serial connection cleanly
% -----------------------------------------------------------------------------
clear s;   % releases COM port
disp("Serial port closed.");

% =========================================================================
% Local helper functions
% =========================================================================

function sendCmd(s, cmd)
% Send ASCII command WITHOUT newline/terminator (matches Python ser.write()).
    write(s, uint8(cmd), "uint8");
end

function b = readExact(s, n)
% Read exactly n bytes or error.
    b = read(s, n, "uint8");
    if numel(b) ~= n
        error("Incomplete read: wanted %d, got %d", n, numel(b));
    end
end

function u8 = readUInt8(s)
% Read a single uint8.
    u8 = readExact(s, 1);
    u8 = u8(1);
end

function u16 = readUInt16LE(s)
% Read 2 bytes little-endian -> uint16.
    b = readExact(s, 2);
    u16 = uint16(b(1)) + bitshift(uint16(b(2)), 8);
end

function u32 = readUInt32LE(s)
% Read 4 bytes little-endian -> uint32.
    b = readExact(s, 4);
    u32 = uint32(b(1)) + bitshift(uint32(b(2)), 8) + bitshift(uint32(b(3)), 16) + bitshift(uint32(b(4)), 24);
end

function f = readFloat32LE(s)
% Read 4 bytes little-endian -> IEEE754 single.
    b = readExact(s, 4);
    u = uint32(b(1)) + bitshift(uint32(b(2)), 8) + bitshift(uint32(b(3)), 16) + bitshift(uint32(b(4)), 24);
    f = typecast(u, "single");
end

function payload = readStatusFrame(s)
% Read framed status response:
%   SOF=0xAA 0x55, LEN (1 byte), PAYLOAD (LEN bytes), CHK (XOR over payload)
    % Find SOF
    while true
        b1 = readExact(s, 1);
        if b1 == hex2dec('AA')
            b2 = readExact(s, 1);
            if b2 == hex2dec('55')
                break;
            end
        end
    end

    n = double(readExact(s, 1));      % payload length
    payload = readExact(s, n);        % payload bytes
    chk = double(readExact(s, 1));    % checksum byte

    % XOR checksum over payload
    x = uint8(0);
    for k = 1:numel(payload)
        x = bitxor(x, payload(k));
    end

    if double(x) ~= chk
        error("Bad checksum (frame corrupted or misaligned)");
    end
end

function out = statusCodesToStrings(statuses, namesMap)
% Convert uint8 status codes into string array using containers.Map.
    out = strings(1, numel(statuses));
    for k = 1:numel(statuses)
        code = double(statuses(k));
        if isKey(namesMap, code)
            out(k) = namesMap(code);
        else
            out(k) = "UNKNOWN(" + string(code) + ")";
        end
    end
end
