# Project Tempo

This project is an artifact of [Tempo PAKE](https://eprint.iacr.org/2025/1399).
It benchmarks alternative specifications/implementations of the ML-KEM SampleNTT algorithm specified in [FIPS 203, Algorithm 7](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.203.pdf).
This project has two Git submodules: `OpenSSL` and `pqm4`.
Algorithms A0, A1 and C1 are self-contained. Algorithms B0 and C0 require OpenSSL.
Running the main python script produces the benchmarks presented in Table 1 of the paper.
To run the benchmarks on ARM Cortex-M4, see instructions below. Results are provided in `results/pqm4_Nucleo_L4R5ZI.md` and summarized in Table 2 of the paper.

## Bibliography

When referring to Tempo PAKE or this GitHub repository in academic literature, please consider citing this work:
```
@misc{cryptoeprint:2025/1399,
      author = {Afonso Arriaga and Manuel Barbosa and Stanislaw Jarecki},
      title = {Tempo: An {ML}-{KEM} to {PAKE} Compiler Resilient to Timing Attacks},
      howpublished = {Cryptology {ePrint} Archive, Paper 2025/1399, {to appear in TCHES 2026/3}},
      year = {2025},
      url = {https://eprint.iacr.org/2025/1399}
}
```
> [!NOTE]
> The paper will appear in TCHES 2026/3 and reference will be updated soon.

## Benchmarks on 64-bit x86 (x86_64) and ARM (aarch64)

To compile and run the benchmarks:
```console
% git clone https://github.com/afonsoarriaga/ProjectTempo.git
% cd ProjectTempo
% git submodule update --init --recursive
% make
% python3 main.py
```

If you have a Mac M1, you can measure CPU cycles (instead of elapsed milliseconds) by running the following command instead (this is based on the work of [@ibireme](https://gist.github.com/ibireme/) and requires root privileges):
```console
% sudo python3 main_count_cycles_mac_m1.py
```

If you have a Linux OS running on x86, use the following command:
```console
% python3 -m venv venv
% source venv/bin/activate
% pip install -r requirements.txt
% python3 main_count_cycles_x86.py
```

Results (on a MacBook Air M1, 2020):

|                  |  Algorithm A0  |   Algorithm A1   |    Algorithm B0   |   Algorithm C0   |   Algorithm C1   |
|------------------|---------------:|-----------------:|------------------:|-----------------:|-----------------:|
| MLKEM-512.gen_a  |      0.0095 ms |        0.1026 ms |         0.2218 ms |        0.2036 ms |        0.0486 ms |
| MLKEM-768.gen_a  |      0.0145 ms |        0.2165 ms |         0.4899 ms |        0.4116 ms |        0.1127 ms |
| MLKEM-1024.gen_a |      0.0248 ms |        0.3826 ms |         0.8764 ms |        0.6736 ms |        0.1898 ms |
|                  |                |                  |                   |                  |                  |
| MLKEM-512        |      0.0769 ms |        0.3423 ms |         0.7258 ms |        0.6055 ms |        0.1968 ms |
| MLKEM-768        |      0.1289 ms |        0.7261 ms |         1.5547 ms |        1.2223 ms |        0.3968 ms |
| MLKEM-1024       |      0.1987 ms |        1.2583 ms |         2.7466 ms |        2.1382 ms |        0.6808 ms |
|                  |                |                  |                   |                  |                  |
| NoIC[MLKEM-512]  |      0.1076 ms |        0.4596 ms |         0.9711 ms |        0.7556 ms |        0.2668 ms |
| NoIC[MLKEM-768]  |      0.1716 ms |        0.8982 ms |         1.9324 ms |        1.5150 ms |        0.5006 ms |
| NoIC[MLKEM-1024] |      0.2582 ms |        1.4960 ms |         3.2376 ms |        2.5611 ms |        0.8161 ms |

Average cycle count: ML-KEM runs keygen+enc+dec; NoIC runs init+resp+end.

- Algorithm A0 : FIPS 203
- Algorithm A1 : Fixed Loop Sampler (FLS)
- Algorithm B0 : Repeated Modular Division (RMD)
- Algorithm C0 : Single Modular Division OpenSSL
- Algorithm C1 : Single Modular Division (SMD)

## Benchmarks on ARM Cortex-M4

These instructions are for a Nucleo-L4R5ZI board connected to a laptop running MacOS 15.6.1.

1. Download and install manually arm-gnu-toolchain-13.3.rel1-darwin-arm64-arm-none-eabi.pkg. Brew installs version 14.3.rel1 which doesn't work as of 26/09/2025.
```console
% vim ~/.zshrc
export PATH="/Applications/ArmGNUToolchain/13.3.rel1/arm-none-eabi/bin:$PATH"

% source ~/.zshrc

% which arm-none-eabi-gcc && arm-none-eabi-gcc --version
/Applications/ArmGNUToolchain/13.3.rel1/arm-none-eabi/bin/arm-none-eabi-gcc
arm-none-eabi-gcc (Arm GNU Toolchain 13.3.Rel1 (Build arm-13.24)) 13.3.1 20240614
Copyright (C) 2023 Free Software Foundation, Inc.
This is free software; see the source for copying conditions.  There is NO
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
```
2. Install OpenOCD to allow benchmarks.py to flash the compiled binaries
```console
% brew install openocd
```
3. Copy PAKEs to pqm4
```console
% make copy-pakes
```
4. Compile 
```console
% cd external/pqm4
% make -j4 PLATFORM=nucleo-l4r5zi
```
5. Install Python dependences
```console
% python3 -m venv venv
% source venv/bin/activate
% pip3 install -r requirements.txt
```
6. Connect board
```console
% ls /dev/tty.*
/dev/tty.usbmodem1103
```
7. Run benchmarks with 100 iterations
```console
% python3 benchmarks.py -p nucleo-l4r5zi -u /dev/tty.usbmodem1103 -i 100 --no-stack \
    ml-kem-512 ml-kem-768 ml-kem-1024 \
    noic-a0-mlkem512 noic-a0-mlkem768 noic-a0-mlkem1024 \
    noic-a1-mlkem512 noic-a1-mlkem768 noic-a1-mlkem1024 \
    noic-c1-mlkem512 noic-c1-mlkem768 noic-c1-mlkem1024 \
    tempo-a1-mlkem512 tempo-a1-mlkem768 tempo-a1-mlkem1024 \
    tempo-c1-mlkem512 tempo-c1-mlkem768 tempo-c1-mlkem1024
% python3 convert_benchmarks.py md
```

For convenience, the results are available in *results/pqm4_Nucleo_L4R5ZI.md*.

8. Compute averages and standard deviations
```
% cd ../..
% for dir in external/pqm4/benchmarks/speed/crypto_kem/*/*/; do echo "Processing: $dir"; python3 pqm4_compute_avg_and_std_dev.py "$dir"; done
```

## License

Submodules located in the `external` directory have their own license agreements. We are using public domain code for ML-KEM and SHA-3. All original work in this repository is licensed under [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0.html).
