clear all; close all;

Fs_app = 1000;

multiplier = 1e6;

Fs_actual = Fs_app * 2^(10*(log10(multiplier)/3));

%% FOR SYNC ADC

% Fclk = (Fs)*21 % Sampling frequency

% Fclk = (Fs_actual)*4;

% Fs = 409.6e6/16 % Sampling frequency

% x  = 1024;    % Approximate Ratio of Fin/(Fs/N) 40 for ADCs

%% GENERAL CALCULATIONS

Ts = 1/Fs_actual

SimTime = 3000*Ts;

N  = 256;   % Record length for FFT

x = 4;

X = [x x];

out = zeros(1,2);

while 1

   t = isprime(X);

   if all(t)

       out = X;

       break

   elseif any(t)

       out(t) = X(t);

       t1 = ~t;

       X(t1) = X(t1) - sum([1 -1].*t1);

   else

       X = X - [1 -1];

   end

end

out = unique(X)

Finl = out(1)*(Fs_actual/N)

Finh = out(2)*(Fs_actual/N)