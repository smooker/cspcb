# stepper_sc Firmware

STM32F411CEU6 (Black Pill) stepper motor controller with USB CDC command interface,
trapezoidal velocity profiling, and EEPROM emulation in internal flash.

## Motor Control (stepper.c)

State machine: IDLE → ACCEL → CONST → DECEL → IDLE

- PWM: TIM2 Channel 3 @ 96 MHz, pulse width ~50 µs (5000 ticks)
- Ramp tables: precomputed via sqrt(v² + 2·a·s) using hardware VSQRT
- ISR: updates TIM2 ARR (period) each step for smooth velocity profile
- Direction: PB14 (DIR pin), set before first pulse

### Parameters (saved to EEPROM)

| Param    | Default | Unit    | Description              |
|----------|---------|---------|--------------------------|
| mmpsmax  | 50.0    | mm/s    | Maximum speed            |
| mmpsmin  | 1.0     | mm/s    | Minimum speed            |
| dvdtacc  | 100.0   | mm/s²   | Acceleration rate        |
| dvdtdecc | 80.0    | mm/s²   | Deceleration rate        |
| jogmm    | 1.0     | mm      | Jog distance             |
| stepmm   | 1.0     | mm      | Step button distance     |
| spmm     | 80      | steps/mm| Steps per millimeter     |

## USB CDC Commands

| Command              | Description                        |
|----------------------|------------------------------------|
| move \<mm\>          | Move by distance                   |
| movel \<mm\>         | Move left (negative)               |
| mover \<mm\>         | Move right (positive)              |
| steps \<n\>          | Move by step count                 |
| set \<param\> \<val\>| Set parameter                      |
| stop                 | Force deceleration stop            |
| params               | Print current parameters           |
| save                 | Persist params to EEPROM           |
| dump                 | Debug variable dump                |
| cls                  | Clear terminal screen              |
| uptime               | Print HAL_GetTick() ms             |
| reset                | Software reset (NVIC_SystemReset)  |
| help                 | Print command list                 |

Terminal escape sequences supported (arrow keys, F1-F4).

## Pin Assignments

| Pin  | Port | Function         | Type    |
|------|------|------------------|---------|
| PB10 | B    | PULSE (TIM2_CH3) | AF PWM  |
| PB14 | B    | DIR              | GPIO PP |
| PB15 | B    | BUZZ             | GPIO PP |
| PC13 | C    | LED_USER         | GPIO PP |
| PA3  | A    | ES_L (Limit L)   | EXTI    |
| PA4  | A    | ES_R (Limit R)   | EXTI    |
| PA6  | A    | BUTT_JOGL        | EXTI    |
| PA7  | A    | BUTT_JOGR        | EXTI    |
| PB0  | B    | BUTT_STEPL       | EXTI    |
| PB1  | B    | BUTT_STEPR       | EXTI    |
| PA11 | A    | USB_OTG_FS_DM    | USB     |
| PA12 | A    | USB_OTG_FS_DP    | USB     |
| PA13 | A    | SWDIO            | Debug   |
| PA14 | A    | SWCLK            | Debug   |

## EEPROM Emulation (eeprom_emul_uint32_t.c)

Dual-page wear-leveling using flash sectors 6 & 7 (128 KB each).

- 8-byte atomic records: 4-byte header (virtual address) + 4-byte data
- Page states: ERASED (0xFFFFFFFF) → RECEIVE (0xEEEEEEEE) → VALID (0xAAAAAAAA)
- Page-swap compaction when active page fills
- Power-loss safe: unfinished records ignored on recovery
- Virtual addresses 1-7 map to the 7 motor parameters

## Clock Configuration

- HSE: 24 MHz
- PLL: M=12, N=96 → 96 MHz SYSCLK
- APB1: 48 MHz (÷2)
- APB2: 96 MHz (÷1)
- TIM2: 96 MHz, initial period 9599, pulse 4800

## Build

```bash
cd firmware
make          # produces build/stepper_sc.elf/.hex/.bin
```

Post-CubeMX regeneration: run `./post_cubemx.sh` to restore -Wno-error=unused-parameter.

## Debug

```bash
./go_gdb.sh   # launches gdb-dashboard + script2.gdb
```

GDB commands:
- `ag` — attach to Black Magic Probe
- `ld` — load stepper_sc.elf/hex + verify

SVD register inspection via PyCortexMDebug + STM32F411.svd.

## Source Files

| File | Description |
|------|-------------|
| Core/Src/main.c | Main loop, USB CDC parsing, morse TX |
| Core/Src/stepper.c | Motor control engine, ramp tables |
| Core/Inc/stepper.h | Stepper API |
| Core/Inc/defines.h | GPIO/semaphore macros |
| Core/Inc/main.h | Parameter struct, CubeMX pin defs |
| Core/Src/eeprom_emul_uint32_t.c | Flash EEPROM emulation |
| Core/Inc/eeprom_emul_uint32_t.h | EEPROM API |
| USB_DEVICE/App/usbd_cdc_if.c | USB CDC callbacks |
