# stepper_sc Fun Moments (2026-03-13)

## "Кой да пусне захранването на мотора?!"

After hours of firmware work — heartbeat LED, buzzer, morse boot, GDB injection,
combo captures, 4 perfect ramp profiles on pulseview — we finally connected the
stepper driver and typed `mover 5`. Firmware responded perfectly: "2000 steps, 5.00 mm".
Motor: silence. Complete silence.

> "aaaaaa. koi da pusne zahranvaneto na motora ?!"

The motor power supply was off the whole time.

## "Този help беше от мен!"

Claude proudly announced: "Successfully injected `help` command via GDB!"
User's minicom showed the help output. Claude took credit.

> "tozi help beshe ot men!"

The user had typed `help` themselves in minicom. Claude was celebrating someone
else's keystrokes.

## "Изчаквай потвърждение за пускане на операции вече!"

After Claude got a bit too enthusiastic injecting motor commands without asking:

> "izchakvai potvyrzhdenie za puskane na operacii veche!"

Translation: "Wait for confirmation before running operations already!"
Fair point. The thing has a motor attached to it.

## The `\r` That Wasn't

First `inject_cmd.sh` attempt: wrote `CMD="${CMD}\r"` in bash.
Bash helpfully interpreted that as... the literal characters `\` and `r`.
Not a carriage return. The firmware saw `help\r` as a command and had no idea
what to do with it.

Fixed by writing byte 13 (0x0D) explicitly in the GDB script. Embedded systems:
where every byte matters and bash string escaping will betray you.

## GDB Halt vs Active Motor

Injecting multiple `mover`/`movel` commands individually via GDB:
each GDB attach halts the CPU for ~100ms, freezing TIM2 mid-pulse.
Second command arrives while motor is still running from first → "stepper busy".

Solution: the `combo` command — all 4 moves in firmware, one inject, zero
interruptions. Sometimes the best remote control is no remote control.

## The Morse Boot Sequence

The firmware now plays V-G-Z in morse code on boot:
- **V** (`...−`) — "we're alive" (blocking, before banner)
- **G** (`−−.`) — "parameters loaded" (blocking, after params dump)
- **Z** (`−−..`) — "go ahead and type" (non-blocking, you can type during it)

Why V-G-Z? No particular reason. It just sounds right on a self-oscillating buzzer
at 6 AM while debugging embedded firmware.

## Password: `motorola`

`diag_outputs` runs the motor at constant 1kHz without ramps — dangerous enough
to warrant password protection. The password? `motorola`. Same password used in
the csvision calibration dialog. At this point it's less of a password and more
of a team tradition.

## The Three-Actor Topology

```
User (minicom) ←→ Target (STM32) ←→ Claude (GDB + sigrok)
```

User watches the terminal. Claude injects commands through the back door and
spies on the motor with a logic analyzer. Target has no idea who's talking to it.
The firmware equivalent of a group chat where one person is a ghost.
