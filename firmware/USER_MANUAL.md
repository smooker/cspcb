# stepper_sc User Manual

## Boot Sequence

1. Power on / reset (`reset` command clears screen first)
2. Buzzer plays **V** (morse: `...-`) — blocking
3. Boot banner with git hash and build date
4. Parameter dump (from EEPROM)
5. Buzzer plays **G** (morse: `--.`) — blocking
6. Prompt `>` appears — CDC commands work from here
7. Buzzer plays **Z** (morse: `--..`) — non-blocking, you can type during it
8. **3 second delay** — buttons disabled, endstops active
9. **Input self-test** — reads all 6 inputs (4 buttons + 2 endstops)
   - All clear → buzzer plays **OK** (morse: `--- -.-`) → buttons enabled → system ready
   - Any input stuck LOW → prints which input is stuck (e.g. `STUCK: ES_L`) → buzzer plays **CQ CQ CQ DE LZ1CCM** → 2s pause → re-checks → repeats until fault cleared

### Input Self-Test Fault Loop

If a button is physically stuck, a cable is shorted, or an endstop is blocked at power-on,
the system refuses to enable buttons and loops the CQ call until the problem is fixed.
This prevents unintended motor movement from a stuck jog button at startup.

Buttons can also be manually controlled via CDC commands (`buttons on` / `buttons off`)
at any time, regardless of boot state.

## CDC Terminal Commands

Connect via serial terminal (minicom, screen, etc.) at any baud rate (USB CDC).

### Movement

| Command | Description | Parameter |
|---------|-------------|-----------|
| `mover <mm>` | Move right (positive) | distance in mm |
| `movel <mm>` | Move left (negative) | distance in mm |
| `move <mm>` | Move by signed distance | + = right, - = left |
| `steps <n>` | Move by raw step count | signed integer |
| `stop` | Decelerate and stop | — |

### Parameters

| Command | Description |
|---------|-------------|
| `set mmpsmax <f>` | Max velocity (mm/s) — top speed of ramp |
| `set mmpsmin <f>` | Min velocity (mm/s) — start/end speed of ramp |
| `set dvdtacc <f>` | Acceleration (mm/s²) |
| `set dvdtdecc <f>` | Deceleration (mm/s²) — can differ from accel for asymmetric ramps |
| `set jogmm <f>` | Jog distance (mm) — used by jog buttons |
| `set stepmm <f>` | Step distance (mm) — used by step buttons |
| `set spmm <n>` | Steps per mm — depends on driver microstepping and lead screw pitch |
| `params` | Show all current parameters |
| `save` | Save parameters to EEPROM (persists across resets) |

### Input Control

| Command | Description |
|---------|-------------|
| `buttons on` | Enable button inputs (default after boot self-test passes) |
| `buttons off` | Disable button inputs — EXTI events ignored |
| `endstops on` | Enable endstop inputs (default always on) |
| `endstops off` | Disable endstop inputs — **use with caution** |

### Diagnostics

| Command | Description |
|---------|-------------|
| `diag_inputs` or `di` | Toggle input diagnostics — buttons/endstops print name only, no motor movement |
| `diag_outputs` or `do` | PULSE+DIR test loop — 16000 steps each direction @ 1kHz. **Password protected** (`motorola`). Reset to stop |
| `combo` | Run 4 test moves: triangle L, triangle R, trapezoid L, trapezoid R |
| `dump` | Debug variable dump |
| `uptime` | Print milliseconds since boot |
| `cls` | Clear terminal screen |
| `reset` | Software reset (NVIC_SystemReset) |
| `help` | Print command list |

## Physical Buttons

Active low (pulled up internally, press connects to GND).

| Button | Pin | Short Press | Long Hold (>300ms) |
|--------|-----|-------------|---------------------|
| JOG L | PA6 | Jog left by `jogmm` with ramps | Continuous left at `mmpsmax` until release |
| JOG R | PA7 | Jog right by `jogmm` with ramps | Continuous right at `mmpsmax` until release |
| STEP L | PB0 | Move left by `stepmm` with ramps | — |
| STEP R | PB1 | Move right by `stepmm` with ramps | — |

## Endstops

| Endstop | Pin | Behavior |
|---------|-----|----------|
| ES_L | PA3 | Immediate deceleration stop. Falling edge (active low) |
| ES_R | PA4 | Immediate deceleration stop. Falling edge (active low) |

Endstops have **no software debounce** in normal mode (safety first).
In `diag_inputs` mode, endstops have 30ms debounce and only print — no stop.

## Buzzer

Self-oscillating buzzer on PB15 (active low).

- **Boot**: morse V-G-Z sequence
- **Button/endstop press**: 50ms beep on any EXTI event
- **Morse functions**: `dot()` / `dash()` available for custom sequences

## LED (PC13)

- **Normal**: toggles every 500ms (1Hz heartbeat) — confirms main loop is running
- **Error handler**: fast blink 50ms — indicates crash
- **GDB attached**: LED frozen — CPU halted
- **Morse**: blinks in sync with buzzer during boot sequence

## Velocity Profile

Trapezoidal/triangular velocity profile with configurable acceleration and deceleration.

- Short moves (distance < ramp distance): **triangle** profile — accel then decel, never reaches max speed
- Long moves: **trapezoid** profile — accel → constant speed → decel
- Asymmetric ramps supported: set `dvdtdecc` different from `dvdtacc`

## EEPROM

Parameters persist across power cycles. Stored in internal flash (sectors 6 & 7)
with wear-leveling. Use `save` command after changing parameters.

## Safety Notes

- `diag_outputs` is password protected — moves motor without ramps at constant speed
- Endstops always active in normal mode (no debounce, immediate stop)
- `stop` command triggers smooth deceleration from any state
- EMI from stepper driver can cause false button/endstop triggers without hardware filtering (external pull-ups + caps recommended)
