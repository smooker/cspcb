# stepper_sc — STM32F411 Stepper Controller PCB

Single-axis stepper motor controller board built around the **WeAct STM32F411CEU6 Black Pill v3.1**.

Drives a **CWD556** opto-isolated stepper driver (PUL/DIR interface) from MCU outputs via NPN buffer stage.

## Block Diagram

```
24V ──── 78M05 ──── +5V ──── Black Pill (3.3V regulator on-board)
                              │
                    PB10 ─── R1/R2/Q1 ─── J2 (PUL → CWD556)
                    PB14 ─── R3/R4/Q2 ─── J3 (DIR → CWD556)
                    PA3  ─── J4 (Endstop L)
                    PA4  ─── J5 (Endstop R)
                    PA6  ─── J6 (Jog L)
                    PA7  ─── J7 (Jog R)
                    PB0  ─── J8 (Step L)
                    PB1  ─── J9 (Step R)
                    PB15 ─── J10 (Buzzer)
```

## Hardware

| Ref | Value | Function |
|-----|-------|----------|
| U1 | 78M05 | 24V → 5V regulator |
| Q1, Q2 | BC547 | NPN buffer (PUL, DIR) |
| R1, R3 | 1kΩ | Base resistor |
| R2, R4 | 10kΩ | Base pull-down |
| C1 | 47µF | Regulator input bulk |
| C2, C4 | 100nF | Regulator decoupling |
| C3 | 100µF | Regulator output bulk |
| C5 | 100nF | Black Pill VIN decoupling |
| J1 | 2-pin screw | 24V power input |
| J2 | 2-pin screw | PUL output to CWD556 |
| J3 | 2-pin screw | DIR output to CWD556 |
| J4–J10 | 2-pin screw | Signal terminals |
| J11A, J11B | 1×20 header | Black Pill socket |

## Pipeline

Schematic and netlist are **generated from firmware source** — `main.h` is the single source of truth for MCU pin assignments.

```
firmware/Core/Inc/main.h
        │
        ▼ fw_to_net.py
howto_sch_and_then_api/stepper_sc.net
        │
        ▼ howto_sch_and_then_api/stepper_sc_gen.py
stepper_sc/stepper_sc.kicad_sch
```

### Re-generating after pin changes

```bash
# Activate venv (needs kicad-sch-api)
source venv/bin/activate

# Step 1: netlist from firmware
python3 fw_to_net.py

# Step 2: schematic from netlist
python3 howto_sch_and_then_api/stepper_sc_gen.py
```

### Setup

```bash
python3 -m venv venv
venv/bin/pip install kicad-sch-api

# KiCad symbol libraries — set path to your KiCad install
# e.g. /usr/share/kicad/symbols
ln -s /path/to/kicad/symbols kicad_sym
```

## Firmware

See `firmware/` for STM32 application source (`Core/`).

Requires ST HAL (`Drivers/`) — generate via STM32CubeMX or download from [st.com](https://www.st.com).

Build:
```bash
cd firmware && make
```

Flash via Black Magic Probe:
```bash
arm-none-eabi-gdb -x script2.gdb build/stepper.elf
```

See `doc/build-and-debug.md` for full build, flash and debug instructions.
