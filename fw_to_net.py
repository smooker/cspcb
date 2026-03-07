#!/usr/bin/env python3
"""
fw_to_net.py — Generate KiCad netlist (Format-E) from firmware main.h

Pipeline:
  firmware/Core/Inc/main.h  →  fw_to_net.py  →  stepper_sc.net

How it works:
  1. Parse #define SIGNAL_Pin / SIGNAL_GPIO_Port from main.h
  2. Map GPIO port+pin → Black Pill header connector pin (J11A / J11B)
  3. For each signal, apply template:
       output_npn  → R_base(1k) + R_bgnd(10k) + Q(BC547) + J_out(2-pin screw)
       input_direct→ J_in(2-pin screw, pin1=signal, pin2=GND)
       skip        → LED_USER and other on-board-only signals
  4. Add static BOM: power supply (U1, C1-C5, J1) + BP headers (J11A, J11B)
  5. Write .net file
"""

import re, os, datetime

HERE     = os.path.dirname(os.path.abspath(__file__))
MAIN_H   = os.path.join(HERE, 'firmware', 'Core', 'Inc', 'main.h')
OUT_NET  = os.path.join(HERE, 'howto_sch_and_then_api', 'stepper_sc.net')

# ── Black Pill v3.1 — GPIO → (connector, connector_pin) ─────────────────────
# Front row  J11A: BP pins  1-20  (USB end, left→right)
# Back  row  J11B: BP pins 21-40  (non-USB end, right→left), J11B pin N = BP pin 20+N
BP_PIN_MAP = {
    # J11A (front row, BP pins 1-20)
    ('GPIOB', 12): ('J11A',  1),  ('GPIOB', 13): ('J11A',  2),
    ('GPIOB', 14): ('J11A',  3),  ('GPIOB', 15): ('J11A',  4),
    ('GPIOA',  8): ('J11A',  5),  ('GPIOA',  9): ('J11A',  6),
    ('GPIOA', 10): ('J11A',  7),  ('GPIOA', 11): ('J11A',  8),
    ('GPIOA', 12): ('J11A',  9),  ('GPIOA', 15): ('J11A', 10),
    ('GPIOB',  3): ('J11A', 11),  ('GPIOB',  4): ('J11A', 12),
    ('GPIOB',  5): ('J11A', 13),  ('GPIOB',  6): ('J11A', 14),
    ('GPIOB',  7): ('J11A', 15),  ('GPIOB',  8): ('J11A', 16),
    ('GPIOB',  9): ('J11A', 17),
    # pin 18=5V, 19=GND, 20=3V3 — handled in static nets

    # J11B (back row, BP pins 21-40)
    ('GPIOC', 13): ('J11B',  2),  # PC13 = LED_USER
    ('GPIOC', 14): ('J11B',  3),  ('GPIOC', 15): ('J11B',  4),
    ('GPIOA',  0): ('J11B',  6),  ('GPIOA',  1): ('J11B',  7),
    ('GPIOA',  2): ('J11B',  8),  ('GPIOA',  3): ('J11B',  9),
    ('GPIOA',  4): ('J11B', 10),  ('GPIOA',  5): ('J11B', 11),
    ('GPIOA',  6): ('J11B', 12),  ('GPIOA',  7): ('J11B', 13),
    ('GPIOB',  0): ('J11B', 14),  ('GPIOB',  1): ('J11B', 15),
    ('GPIOB',  2): ('J11B', 16),  ('GPIOB', 10): ('J11B', 17),
    # pin 18=3V3, 19=GND, 20=5V — handled in static nets
}

# ── Signal configuration ─────────────────────────────────────────────────────
# type:
#   'output_npn'   → NPN buffer (R_base + R_bgnd + Q + J_out)
#   'input_direct' → direct connector (J_in, pin1=signal, pin2=GND)
#   'skip'         → on-board only, no external connection
#
# connector_label: value field for the output/input screw terminal
# description:     goes into comp description field

SIGNAL_CONFIG = {
    'LED_USER': {
        'type': 'skip',
    },
    'PULSE': {
        'type': 'output_npn',
        'connector_label': 'PUL',
        'description': 'CWD556 PUL: pin1=PUL+(+5V), pin2=PUL-(Q collector). Opto LED inside driver.',
    },
    'DIR': {
        'type': 'output_npn',
        'connector_label': 'DIR',
        'description': 'CWD556 DIR: pin1=DIR+(+5V), pin2=DIR-(Q collector). Opto LED inside driver.',
    },
    'ES_L': {
        'type': 'input_direct',
        'connector_label': 'ES_L',
        'description': 'Endstop left — active LOW both edges',
    },
    'ES_R': {
        'type': 'input_direct',
        'connector_label': 'ES_R',
        'description': 'Endstop right — active LOW both edges',
    },
    'BUTT_JOGL': {
        'type': 'input_direct',
        'connector_label': 'JOGL',
        'description': 'Jog left button — active LOW both edges',
    },
    'BUTT_JOGR': {
        'type': 'input_direct',
        'connector_label': 'JOGR',
        'description': 'Jog right button — active LOW both edges',
    },
    'BUTT_STEPL': {
        'type': 'input_direct',
        'connector_label': 'STEPL',
        'description': 'Step left button — active LOW both edges',
    },
    'BUTT_STEPR': {
        'type': 'input_direct',
        'connector_label': 'STEPR',
        'description': 'Step right button — active LOW both edges',
    },
    'BUZZ': {
        'type': 'input_direct',   # direct connector, driven by BP pin
        'connector_label': 'BUZZ',
        'description': 'Buzzer output',
    },
}

# ── Static BOM ───────────────────────────────────────────────────────────────
FP_SCREW   = 'TerminalBlock_RND:TerminalBlock_RND_205-00232_1x02_P5.08mm_Horizontal'
FP_HEADER  = 'Connector_PinHeader_2.54mm:PinHeader_1x20_P2.54mm_Vertical'
FP_CAP_TH  = 'Capacitor_THT:CP_Radial_D8.0mm_P3.50mm'
FP_CAP_SMD = 'Capacitor_SMD:C_0805_2012Metric'
FP_RES_SMD = 'Resistor_SMD:R_0805_2012Metric'
FP_TO92    = 'Package_TO_SOT_THT:TO-92_Inline'
FP_TO252   = 'Package_TO_SOT_SMD:TO-252-2'

STATIC_COMPS = [
    # ref, value, footprint, description, lib, part, tstamp
    ('U1',   '78M05',         FP_TO252,   '5V linear regulator',
     'Regulator_Linear', 'L78M05_TO252',   'u1-78m05'),
    ('C1',   '47uF',          FP_CAP_TH,  '78M05 input bulk cap',
     'Device',           'C_Polarized',    'c1-47u-in'),
    ('C2',   '100nF',         FP_CAP_SMD, '78M05 input decoupling',
     'Device',           'C',              'c2-100n-in'),
    ('C3',   '100uF',         FP_CAP_TH,  '78M05 output bulk cap',
     'Device',           'C_Polarized',    'c3-100u-out'),
    ('C4',   '100nF',         FP_CAP_SMD, '78M05 output decoupling',
     'Device',           'C',              'c4-100n-out'),
    ('C5',   '100nF',         FP_CAP_SMD, 'Black Pill VIN decoupling',
     'Device',           'C',              'c5-100n-bp'),
    ('J1',   'PWR_24V',       FP_SCREW,   'Power input 24V + GND',
     'Connector',        'Conn_01x02_Screw', 'j1-pwr'),
    ('J11A', 'Black_Pill_front', FP_HEADER,
     'Black Pill front row — pins 1-20, USB end left: B12..B9,5V,GND,3V3',
     'Connector',        'Conn_01x20',     'j11a-bp-front'),
    ('J11B', 'Black_Pill_back', FP_HEADER,
     'Black Pill back row — BP pins 21-40, J11B pin 1=BP21(VBAT)..pin 20=BP40(5V)',
     'Connector',        'Conn_01x20',     'j11b-bp-back'),
]

# ── helpers ──────────────────────────────────────────────────────────────────

def parse_main_h(path):
    """Return {SIGNAL_NAME: (port_str, pin_int)} from main.h #defines."""
    with open(path) as f:
        txt = f.read()

    pins  = {}
    ports = {}

    for m in re.finditer(r'#define\s+(\w+)_Pin\s+GPIO_PIN_(\d+)', txt):
        pins[m.group(1)] = int(m.group(2))

    for m in re.finditer(r'#define\s+(\w+)_GPIO_Port\s+(GPIO[A-Z])', txt):
        ports[m.group(1)] = m.group(2)

    signals = {}
    for sig in pins:
        if sig in ports:
            signals[sig] = (ports[sig], pins[sig])
    return signals


def node(ref, pin, pinfunc='~', pintype='passive'):
    return f'      (node (ref "{ref}")  (pin "{pin}") (pinfunction "{pinfunc}") (pintype "{pintype}"))'


def comp_block(ref, value, fp, desc, lib, part, tstamp):
    lines = [f'    (comp (ref "{ref}")']
    lines.append(f'      (value "{value}")')
    lines.append(f'      (footprint "{fp}")')
    if desc:
        lines.append(f'      (description "{desc}")')
    lines.append(f'      (libsource (lib "{lib}") (part "{part}"))')
    lines.append(f'      (sheetpath (names "/") (tstamps "/"))')
    lines.append(f'      (tstamp "{tstamp}")')
    lines.append(f'    )')
    return '\n'.join(lines)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    # 1. Parse firmware
    signals = parse_main_h(MAIN_H)
    print(f'Parsed {len(signals)} signals from main.h:')
    for sig, (port, pin) in sorted(signals.items()):
        cfg = SIGNAL_CONFIG.get(sig, {})
        print(f'  {sig:16s}  {port} pin {pin:2d}  → {cfg.get("type","unknown")}')

    # 2. Build component list and nets
    comps  = []   # list of comp_block strings
    nets   = {}   # net_name → [node strings]

    net_code = [0]
    def next_code():
        net_code[0] += 1
        return str(net_code[0])

    def ensure_net(name):
        if name not in nets:
            nets[name] = []
        return name

    # Static power nets
    for n in ('+24V', '+5V', 'GND', '+3.3V'):
        ensure_net(n)

    # Static components
    for s in STATIC_COMPS:
        ref, value, fp, desc, lib, part, tstamp = s
        comps.append(comp_block(ref, value, fp, desc, lib, part, tstamp))

    # Static net nodes — power supply
    nets['+24V'] += [
        node('J1',  '1', 'Pin_1',  'passive'),
        node('U1',  '1', 'VI',     'power_in'),
        node('C1',  '1', '+',      'passive'),
        node('C2',  '1', '~',      'passive'),
    ]
    nets['+5V'] += [
        node('U1',  '3', 'VO',     'power_out'),
        node('C3',  '1', '+',      'passive'),
        node('C4',  '1', '~',      'passive'),
        node('C5',  '1', '~',      'passive'),
        node('J11A','18','Pin_18', 'passive'),
        node('J11B','20','Pin_20', 'passive'),
    ]
    nets['GND'] += [
        node('J1',   '2', 'Pin_2',  'passive'),
        node('U1',   '2', 'GND',    'power_in'),
        node('C1',   '2', '-',      'passive'),
        node('C2',   '2', '~',      'passive'),
        node('C3',   '2', '-',      'passive'),
        node('C4',   '2', '~',      'passive'),
        node('C5',   '2', '~',      'passive'),
        node('J11A','19', 'Pin_19', 'passive'),
        node('J11B','19', 'Pin_19', 'passive'),
    ]
    nets['+3.3V'] += [
        node('J11A','20','Pin_20', 'passive'),
        node('J11B','18','Pin_18', 'passive'),
    ]

    # 3. Process signals — counters for dynamic ref assignment
    q_idx  = 0
    r_idx  = 0
    j_idx  = 1   # J1=power, so start at J2

    # Sort signals: outputs first, then inputs, for clean numbering
    def sort_key(item):
        sig, (port, pin) = item
        cfg = SIGNAL_CONFIG.get(sig, {})
        t = cfg.get('type', 'z')
        order = {'output_npn': 0, 'input_direct': 1, 'skip': 2}.get(t, 3)
        return (order, port, pin)

    for sig, (port, pin) in sorted(signals.items(), key=sort_key):
        cfg = SIGNAL_CONFIG.get(sig, {'type': 'input_direct',
                                      'connector_label': sig,
                                      'description': f'{port}{pin} signal'})
        sig_type = cfg['type']

        if sig_type == 'skip':
            print(f'  SKIP {sig}')
            continue

        # Net name for this MCU signal
        port_letter = port.replace('GPIO', '')   # 'A', 'B', 'C'
        net_sig = f'P{port_letter}{pin}_{sig}'
        ensure_net(net_sig)

        # BP header connection
        bp_key = (port, pin)
        if bp_key in BP_PIN_MAP:
            bp_conn, bp_pin = BP_PIN_MAP[bp_key]
            nets[net_sig].append(
                node(bp_conn, str(bp_pin), f'Pin_{bp_pin}', 'passive')
            )
        else:
            print(f'  WARN: {sig} ({port} pin {pin}) not in BP_PIN_MAP')

        j_idx += 1
        j_ref = f'J{j_idx}'
        label = cfg.get('connector_label', sig)
        desc  = cfg.get('description', '')

        if sig_type == 'output_npn':
            # ── NPN buffer template ──────────────────────────────────────
            q_idx += 1
            r_idx += 1
            q_ref     = f'Q{q_idx}'
            r_base    = f'R{r_idx * 2 - 1}'   # R1, R3, R5...
            r_bgnd    = f'R{r_idx * 2}'        # R2, R4, R6...
            net_base  = f'NET_{sig}_BASE'
            net_col   = f'NET_{sig}_COL'
            ensure_net(net_base)
            ensure_net(net_col)

            comps.append(comp_block(
                r_base, '1k', FP_RES_SMD,
                f'{q_ref} base resistor — {port_letter}{pin} to base',
                'Device', 'R', f'{r_base.lower()}-1k-base-{sig.lower()}'))
            comps.append(comp_block(
                r_bgnd, '10k', FP_RES_SMD,
                f'{q_ref} base pull-down to GND',
                'Device', 'R', f'{r_bgnd.lower()}-10k-bgnd-{sig.lower()}'))
            comps.append(comp_block(
                q_ref, 'BC547', FP_TO92,
                f'NPN buffer {sig}: MCU({port_letter}{pin})->{r_base}->B, E->GND, C->{j_ref}({label}-)',
                'Device', 'Q_NPN', f'{q_ref.lower()}-npn-{sig.lower()}'))
            comps.append(comp_block(
                j_ref, label, FP_SCREW, desc,
                'Connector', 'Conn_01x02_Screw', f'{j_ref.lower()}-{sig.lower()}'))

            # nets
            nets[net_sig]  += [node(r_base, '1', '~', 'passive')]
            nets[net_base] += [
                node(r_base, '2', '~', 'passive'),
                node(r_bgnd, '1', '~', 'passive'),
                node(q_ref,  'B', 'B', 'input'),
            ]
            nets['GND']    += [
                node(r_bgnd, '2', '~', 'passive'),
                node(q_ref,  'E', 'E', 'passive'),
            ]
            nets['+5V']    += [node(j_ref, '1', 'Pin_1', 'passive')]
            nets[net_col]  += [
                node(q_ref,  'C', 'C', 'passive'),
                node(j_ref,  '2', 'Pin_2', 'passive'),
            ]

        elif sig_type == 'input_direct':
            # ── direct connector ─────────────────────────────────────────
            comps.append(comp_block(
                j_ref, label, FP_SCREW, desc,
                'Connector', 'Conn_01x02_Screw', f'{j_ref.lower()}-{sig.lower()}'))

            nets[net_sig] += [node(j_ref, '1', 'Pin_1', 'passive')]
            nets['GND']   += [node(j_ref, '2', 'Pin_2', 'passive')]

        print(f'  {sig:16s}  {q_ref if sig_type=="output_npn" else "     "} {j_ref}  net={net_sig}')

    # 4. Serialise
    lines = []
    lines.append('(export (version "E")')
    lines.append('  (design')
    lines.append(f'    (source "firmware/Core/Inc/main.h")')
    lines.append(f'    (date "{datetime.date.today().isoformat()}")')
    lines.append(f'    (tool "fw_to_net.py — generated from firmware")')
    lines.append('    (sheet (number "1") (name "/") (tstamps "/"))')
    lines.append('  )')
    lines.append('')
    lines.append('  (components')
    for c in comps:
        lines.append(c)
    lines.append('  )')
    lines.append('')
    lines.append('  (libparts)')
    lines.append('  (libraries)')
    lines.append('')
    lines.append('  (nets')
    for code, (name, nodes) in enumerate(nets.items(), start=1):
        lines.append(f'    (net (code "{code}") (name "{name}")')
        for n in nodes:
            lines.append(n)
        lines.append('    )')
    lines.append('  )')
    lines.append(')')

    with open(OUT_NET, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f'\nWritten: {OUT_NET}')
    print(f'  {len(comps)} components, {len(nets)} nets')


if __name__ == '__main__':
    main()
