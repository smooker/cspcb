# Тест на входове — 2026-03-13

## Хардуер

- MCU: STM32F411CEU6 (Black Pill)
- GPIO: PULLUP + FALLING edge
- Бутони към GND, без външни резистори (вътрешни pull-up)

## GDB регистров тест (без флашване)

Pull-up активирани чрез PUPDR регистъра от GDB. Четене на IDR за всеки вход.

```
# Enable pull-ups
set *(uint32_t*)0x4002000C = *(uint32_t*)0x4002000C | (1<<6)|(1<<8)|(1<<12)|(1<<14)
set *(uint32_t*)0x4002040C = *(uint32_t*)0x4002040C | (1<<0)|(1<<2)

# Read inputs
printf "PA: ES_L=%d ES_R=%d JOGL=%d JOGR=%d\n", ...
printf "PB: STEPL=%d STEPR=%d\n", ...
```

| Тест | Резултат |
|------|----------|
| Idle (нищо натиснато) | ES_L=1 ES_R=1 JOGL=1 JOGR=1 STEPL=1 STEPR=1 |
| BUTT_JOGL (PA6) | JOGL=0, останалите 1 |
| BUTT_JOGR (PA7) | JOGR=0, останалите 1 |
| BUTT_STEPL (PB0) | STEPL=0, останалите 1 |
| BUTT_STEPR (PB1) | STEPR=0, останалите 1 |
| ES_L (PA3) | ES_L=0, останалите 1 |
| ES_R (PA4) | ES_R=0, останалите 1 |

**6/6 входа работят с вътрешни pull-up на Black Pill.**

## Firmware диагностичен режим

Команда `diag` — toggle. В diag режим бутоните само печатат, без движение на мотора.

### Първи опит — printf от ISR

```
> diag
B_JGL
TT_OR
TTEPL
BUT_STERES ht
ES_R it
```

**Проблем**: printf от EXTI ISR конфликтира с USB CDC.
Символите се разбъркват — CDC буферът се пълни от ISR контекст
докато USB прекъсването не може да флъшне.

**УРОК: НИКОГА printf от ISR!**

### Втори опит — event flags + main loop printf

ISR само вдига флагове (`evtFlags |= EVT_xxx`), printf от main loop
чрез `ProcessEvents()`.

```
> diag
diag mode ON
> BUTT_JOGL
> BUTT_JOGR
> BUTT_STEPL
> BUTT_STEPR
> ES_L hit
> ES_R hit
```

**6/6 — всички входове работят коректно.**

Ендстопите леко се сливат (`LiR`) без дебаунс — добавен 30ms
дебаунс за ендстопите само в диаг режим. В нормален режим
ендстопите спират мотора веднага без дебаунс (безопасност).

## NVIC приоритети

| IRQ | Приоритет | Описание |
|-----|-----------|----------|
| TIM2 | 1 | Stepper PWM |
| EXTI3 (ES_L) | 1 | Ендстоп ляв |
| EXTI4 (ES_R) | 1 | Ендстоп десен |
| EXTI0 (STEPL) | 2 | Бутон step ляво |
| EXTI1 (STEPR) | 2 | Бутон step дясно |
| EXTI9_5 (JOGL/R) | 2 | Бутони jog |
| OTG_FS (USB) | 0 (default) | USB CDC |

## Boot banner

```
========================================
  stepper_sc  afc340e-dirty  2026-03-13_11:05
  STM32F411CEU6 @ 96 MHz
  type 'help' for commands
========================================
>
```

Git hash и дата на компилация се вграждат от Makefile:
```makefile
GIT_HASH := $(shell git rev-parse --short HEAD)
BUILD_DATE := $(shell date '+%Y-%m-%d_%H:%M')
C_DEFS += -DGIT_HASH=\"$(GIT_HASH)\" -DBUILD_DATE=\"$(BUILD_DATE)\"
```
