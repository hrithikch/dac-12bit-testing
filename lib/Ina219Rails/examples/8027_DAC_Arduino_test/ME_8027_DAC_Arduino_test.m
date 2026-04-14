% writeread_matlab.m
% MATLAB port of your Python serial script (binary-safe)
%
% Requirements:
%   - MATLAB R2019b+ recommended (serialport)
%   - Set COM port and baud rate below

clear; clc;

% -------------------------------------------------------------------------
% Enumerate available serial ports (similar to list_ports.comports())
% -------------------------------------------------------------------------
ports = serialportlist("available");
disp(ports);

% -------------------------------------------------------------------------
% Configure and open serial port
% -------------------------------------------------------------------------
PORT = "COM4";
BAUD = 115200;

s = serialport(PORT, BAUD);
% configureTerminator(s, "");     % no terminator; we do raw framed/binary reads
s.Timeout = 30;%2;                  % seconds (adjust as needed)
flush(s);

%%
% -------------------------------------------------------------------------
% Status name map (RailStatus)
% -------------------------------------------------------------------------
NAMES = containers.Map( ...
    num2cell(uint8([0 1 2 3 4 5 6 7])), ...
    {'OK','WARN','OUT_OF_RANGE','STUCK','TIMEOUT','DEVICE_FAIL','UNSTABLE','OVERCURRENT'} ...
);

try
    % ---------------------------------------------------------------------
    % Initialize current compliance to default values in rail table
    % ---------------------------------------------------------------------
    disp("Initializing current compliance");
    write_ascii(s, "INITIALIZE_COMPLIANCE");
    value = read_exact(s, 1, "uint8");
    disp(value(1));
    disp("Finished initializing current compliance");
    disp(" ");

    % ---------------------------------------------------------------------
    % Basic LED test: toggle ON/OFF several times
    % ---------------------------------------------------------------------
    disp("Flashing LED");

    write_ascii(s, "ON");
    disp(read_exact(s, 1, "uint8"));
    pause(1);

    write_ascii(s, "OFF");
    disp(read_exact(s, 1, "uint8"));
    pause(1);

    write_ascii(s, "ON");
    disp(read_exact(s, 1, "uint8"));
    pause(1);

    write_ascii(s, "OFF");
    disp(read_exact(s, 1, "uint8"));
    pause(1);

    disp("Finished flashing LED");
    disp(" ");

    % ---------------------------------------------------------------------
    % Pulse digital I/O pin 13 (toggles green LED on hardware)
    % ---------------------------------------------------------------------
    disp("Pulse DIO 13 high, low, high, low, high. Flashes green LED");

    write_ascii(s, "DIO_ON,13");
    disp(read_exact(s, 1, "uint8"));
    pause(1);

    write_ascii(s, "DIO_OFF,13");
    disp(read_exact(s, 1, "uint8"));
    pause(1);

    write_ascii(s, "DIO_ON,13");
    disp(read_exact(s, 1, "uint8"));
    pause(1);

    write_ascii(s, "DIO_OFF,13");
    disp(read_exact(s, 1, "uint8"));
    pause(1);

    write_ascii(s, "DIO_ON,13");
    disp(read_exact(s, 1, "uint8"));
    pause(1);

    disp("Finished pulsing DIO 13");
    disp(" ");

    % ---------------------------------------------------------------------
    % Read Arduino internal ADC pin A0 (uint16 little-endian)
    % ---------------------------------------------------------------------
    disp("Reading Arduino ADC value");
    write_ascii(s, "READ_ADC,A0");
    raw = read_exact(s, 2, "uint8");
    adc_val = typecast(uint8(raw), 'uint16');   % little-endian on Windows/Intel
    disp(adc_val);
    disp("Finished reading Arduino ADC value");
    disp(" ");

    pause(3);

    % ---------------------------------------------------------------------
    % Read AVDD rail measurements via INA219 (float32 little-endian)
    % ---------------------------------------------------------------------
    disp("Reading AVDD voltage");
    write_ascii(s, "READ_VOLTAGE,AVDD");
    v = read_f32_le(s);
    fprintf("%.3f\n", v);
    disp("Finished reading AVDD voltage");
    disp(" ");

    disp("Reading AVDD shunt voltage");
    write_ascii(s, "READ_SHUNTV,AVDD");
    v = read_f32_le(s);
    fprintf("%.3f\n", v);
    disp("Finished reading AVDD shunt voltage");
    disp(" ");

    disp("Reading AVDD current");
    write_ascii(s, "READ_CURRENT,AVDD");
    v = read_f32_le(s);
    fprintf("%.3f\n", v);
    disp("Finished reading AVDD current");
    disp(" ");

    disp("Reading AVDD power");
    write_ascii(s, "READ_POWER,AVDD");
    v = read_f32_le(s);
    fprintf("%.3f\n", v);
    disp("Finished reading AVDD power");
    disp(" ");

    pause(3);

    % ---------------------------------------------------------------------
    % Set multiple rail voltages (returns framed status response)
    % Frame: 0xAA 0x55, LEN, PAYLOAD, CHK (XOR of payload)
    % ---------------------------------------------------------------------
    disp("Setting voltages");
    write_ascii(s, "SET_VOLTAGE,AVDD,0.7,AVDD0P85,0.85,AVDD18,1.8");

    statuses = read_status_frame(s);   % returns uint8 vector
    disp(statuses_to_names(statuses, NAMES));
    disp("Finished setting voltages");
    disp(" ");

    % ---------------------------------------------------------------------
    % Read back rail voltages and power metrics
    % ---------------------------------------------------------------------
    disp("Reading AVDD voltage");
    write_ascii(s, "READ_VOLTAGE,AVDD");
    fprintf("%.3f\n", read_f32_le(s));
    disp("Finished reading AVDD voltage");
    disp(" ");

    disp("Reading AVDD0P85 voltage");
    write_ascii(s, "READ_VOLTAGE,AVDD0P85");
    fprintf("%.3f\n", read_f32_le(s));
    disp("Finished reading AVDD0P85 voltage");
    disp(" ");

    disp("Reading AVDD18 voltage");
    write_ascii(s, "READ_VOLTAGE,AVDD18");
    fprintf("%.3f\n", read_f32_le(s));
    disp("Finished reading AVDD18 voltage");
    disp(" ");

    disp("Reading AVDD18 shunt voltage");
    write_ascii(s, "READ_SHUNTV,AVDD18");
    fprintf("%.3f\n", round(read_f32_le(s), 3));
    disp("Finished reading AVDD18 shunt voltage");
    disp(" ");

    disp("Reading AVDD18 current in mA");
    write_ascii(s, "READ_CURRENT,AVDD18");
    fprintf("%.3f\n", round(read_f32_le(s), 3));
    disp("Finished reading AVDD18 current");
    disp(" ");

    disp("Reading AVDD18 power");
    write_ascii(s, "READ_POWER,AVDD18");
    fprintf("%.3f\n", round(read_f32_le(s), 3));
    disp("Finished reading AVDD18 power");
    disp(" ");

    % ---------------------------------------------------------------------
    % Set LDO digital potentiometer
    % ---------------------------------------------------------------------
    disp("Setting LDO pot");
    write_ascii(s, "LDO_WRITE,AVDD,128");
    disp(read_exact(s, 1, "uint8"));
    disp("Done setting LDO pot");

    % ---------------------------------------------------------------------
    % Read AVDD voltage after setting LDO pot
    % ---------------------------------------------------------------------
    disp("Reading AVDD voltage");
    write_ascii(s, "READ_VOLTAGE,AVDD");
    fprintf("%.3f\n", round(read_f32_le(s), 3));
    disp("Finished reading AVDD voltage");
    disp(" ");

    % ---------------------------------------------------------------------
    % Set compliance current on VREFC_GATE rail
    % ---------------------------------------------------------------------
    disp("Setting VDD18 compliance to 0.04 mA");
    write_ascii(s, "SET_COMPLIANCE,VREFC_GATE,0.04");
    disp(read_exact(s, 1, "uint8"));
    disp("Finished setting AVDD compliance");
    disp(" ");

    % ---------------------------------------------------------------------
    % Set multiple rail voltages (blocking version) -> framed response
    % ---------------------------------------------------------------------
    disp("Setting voltages");
    write_ascii(s, "SET_VOLTAGE,AVDD,0.8,AVDD0P85,0.6,AVDD18,1.2");
    statuses = read_status_frame(s);
    disp(statuses_to_names(statuses, NAMES));
    disp("Finished setting voltages");
    disp(" ");

    % ---------------------------------------------------------------------
    % Read back AVDD voltage
    % ---------------------------------------------------------------------
    disp("Reading AVDD voltage");
    write_ascii(s, "READ_VOLTAGE,AVDD");
    fprintf("%.3f\n", round(read_f32_le(s), 3));
    disp("Finished reading AVDD voltage");
    disp(" ");

    % ---------------------------------------------------------------------
    % Read back AVDD0P85 voltage
    % ---------------------------------------------------------------------
    disp("Reading AVDD0P85 voltage");
    write_ascii(s, "READ_VOLTAGE,AVDD0P85");
    fprintf("%.3f\n", round(read_f32_le(s), 3));
    disp("Finished reading AVDD0P85 voltage");
    disp(" ");

    % ---------------------------------------------------------------------
    % Read back AVDD18 voltage
    % ---------------------------------------------------------------------
    disp("Reading AVDD18 voltage");
    write_ascii(s, "READ_VOLTAGE,AVDD18");
    fprintf("%.3f\n", round(read_f32_le(s), 3));
    disp("Finished reading AVDD18 voltage");
    disp(" ");

catch ME
    % Bubble up with context; you'll still get cleanup below
    disp("ERROR:");
    disp(getReport(ME, 'extended'));
end

% -------------------------------------------------------------------------
% Close serial connection cleanly
% -------------------------------------------------------------------------
try
    clear s;  % releases the serialport object
catch
end

% =========================================================================
% Local helper functions
% =========================================================================

function write_ascii(s, cmd)
% Write ASCII command bytes (no newline terminator)
    write(s, uint8(char(cmd)), "uint8");
end

function b = read_exact(s, n, dtype)
% Read exactly N bytes; error if short (prevents silent framing bugs)
    b = read(s, n, dtype);
    if numel(b) ~= n
        error("Incomplete read: wanted %d, got %d", n, numel(b));
    end
end

function f = read_f32_le(s)
% Read float32 little-endian (4 bytes)
    raw = read_exact(s, 4, "uint8");
    f = typecast(uint8(raw), 'single');
    f = double(f); % MATLAB prints nicer as double
end

function payload = read_status_frame(s)
% Read framed status response:
%   SOF 0xAA 0x55, LEN, PAYLOAD, CHK (XOR of payload)
    % Search for SOF
    % keyboard
    % pause('60')
    % count = 0;
    while true
        % count = count + 1 %debugging code
        b1 = read_exact(s, 1, "uint8");
        if b1 == hex2dec('AA')
            b2 = read_exact(s, 1, "uint8");
            if b2 == hex2dec('55')
                break;
            end
        end
    end

    n = read_exact(s, 1, "uint8");     % length byte
    payload = read_exact(s, double(n), "uint8");
    chk = read_exact(s, 1, "uint8");

    % XOR checksum verify
    x = uint8(0);
    for k = 1:numel(payload)
        x = bitxor(x, payload(k));
    end
    if x ~= chk
        error("Bad checksum (frame corrupted or misaligned)");
    end
end

function out = statuses_to_names(statuses, NAMES)
% Convert uint8 status codes to readable strings (cell array of char)
    out = cell(1, numel(statuses));
    for i = 1:numel(statuses)
        k = uint8(statuses(i));
        if isKey(NAMES, k)
            out{i} = NAMES(k);
        else
            out{i} = sprintf("UNKNOWN(%d)", k);
        end
    end
end
