#!/usr/bin/env python3
"""
pcb_place.py — Place footprints on stepper_sc.kicad_pcb via KiCad IPC API (kipy)

Knowledge is filled in step by step.
Coordinates in mm (script converts to nm for kipy).
Origin: board Edge.Cuts starts at (25, 25) mm → usable area (25..115) x (25..145).

Run with venv python:
  KICAD_API_SOCKET=ipc:///home/claude-agent/tmp/kicad/api.sock \
      ../venv/bin/python3 pcb_place.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'venv',
                                'lib', 'python3.13', 'site-packages'))

import kipy
from kipy.geometry import Vector2, Angle

# ── IPC socket ──────────────────────────────────────────────────────────────
SOCKET = 'ipc:///home/claude-agent/tmp/kicad/api.sock'

# ── Target positions (mm) ────────────────────────────────────────────────────
# Board usable area: x=25..115, y=25..145  (90×120mm, origin at top-left of cuts)
#
# Layout plan:
#   Power row  (top):     J1  C1 C2  U1  C3 C4 C5
#   PUL buffer (mid-top): R1 R2  Q1  J2
#   DIR buffer (mid-bot): R4 R5  Q2  J3
#   Terminals  (left col):J4 J5 J6 J7 J8 J9 J10
#   BP headers (right):   J11  J12
#
# ⚠  All positions are (x, y) in mm from KiCad board origin (top-left of sheet,
#    NOT the Edge.Cuts corner).  Use KiCad's coordinate readout to calibrate.

POSITIONS = {
    # ref:   (  x_mm,   y_mm,  rot_deg )   rot=0 → default orientation
    #
    # Board Edge.Cuts: (25,25)..(115,145)  →  usable 90×120mm
    #
    # Concept:
    #   Left half  (x=28..72):  power row, NPN buffers, signal terminals
    #   Right half (x=80..110): Black Pill headers J11/J12 (1×20, 50.8mm tall)
    #
    #         28        50        72     87  102
    #   30  ┌────────────────────────┬──────────┐
    #        J1─C1─C2─U1─C3─C4─C5   │          │  power row
    #   55  ├────────────────────────┤  J11 J12 │
    #        R1─R2─Q1──J2            │  (Black  │  PUL buffer
    #   68  ├────────────────────────┤   Pill)  │
    #        R3─R4─Q2──J3            │          │  DIR buffer
    #   82  ├────────────────────────┤          │
    #        J4 J5 J6 J7             │          │  signal terminals
    #        J8 J9 J10               │          │
    #  145  └────────────────────────┴──────────┘

    # ── Power supply row (top, y=35) ────────────────────────────────────────
    # Horizontal row: J1 → C1/C2 → U1 → C3/C4 → C5 near BP
    # Layout: J4-J10 column at left edge (x=30), then power+buffers, then BP headers at right
    #
    #  25  30  42  55  65  75  85   95  110
    #   │   │   │   │   │   │   │    │    │
    #   │  J4  J1─C1─C2─U1─C3─C4   │    │   y=35  power row
    #   │  J5                  C5   │    │   y=48
    #   │  J6  R1─R2──Q1───J2      │    │   y=65  PUL buffer
    #   │  J7  R3─R4──Q2───J3     J11  J12  y=85  DIR buffer
    #   │  J8                      │    │   y=102
    #   │  J9                      │    │   y=115
    #   │  J10                     │    │   y=128

    # Layout (all x relative to left Edge.Cuts at x=25):
    #   col A x=30: J4-J10 signal terminals (left edge, rot=90)
    #   col B x=42: J1, R1/R3 (base resistors)
    #   col C x=52: C1/C2, R2/R4 (bypass caps + gnd resistors)
    #   col D x=62: U1, Q1/Q2 (regulator + transistors)
    #   col E x=72: C3, J2/J3 (bulk out cap + PUL/DIR terminals)
    #   col F x=82: C4/C5
    #   col G x=95/108: J11/J12 Black Pill headers

    "J1":  (  42.0,   35.0,    0 ),   # 24V screw terminal
    "C1":  (  52.0,   35.0,    0 ),   # 47µF in
    "C2":  (  62.0,   35.0,    0 ),   # 100nF in
    "U1":  (  72.0,   35.0,    0 ),   # 78M05 regulator
    "C3":  (  82.0,   35.0,    0 ),   # 100µF out
    "C4":  (  82.0,   48.0,    0 ),   # 100nF out
    "C5":  (  82.0,   58.0,    0 ),   # 100nF BP VIN

    # ── PUL NPN buffer (y=70) ───────────────────────────────────────────────
    "R1":  (  42.0,   70.0,    0 ),   # 1k base
    "R2":  (  52.0,   70.0,    0 ),   # 10k gnd
    "Q1":  (  62.0,   70.0,    0 ),   # BC547
    "J2":  (  72.0,   70.0,    0 ),   # PUL output terminal

    # ── DIR NPN buffer (y=90) ───────────────────────────────────────────────
    "R3":  (  42.0,   90.0,    0 ),   # 1k base
    "R4":  (  52.0,   90.0,    0 ),   # 10k gnd
    "Q2":  (  62.0,   90.0,    0 ),   # BC547
    "J3":  (  72.0,   90.0,    0 ),   # DIR output terminal

    # ── Signal terminals (left edge column) ──────────────────────────────────
    "J4":  (  30.0,   50.0,   90 ),   # ES_L
    "J5":  (  30.0,   63.0,   90 ),   # ES_R
    "J6":  (  30.0,   76.0,   90 ),   # JOGL
    "J7":  (  30.0,   89.0,   90 ),   # JOGR
    "J8":  (  30.0,  102.0,   90 ),   # STEPL
    "J9":  (  30.0,  115.0,   90 ),   # STEPR
    "J10": (  30.0,  128.0,   90 ),   # BUZZ

    # ── Black Pill headers (right side) ──────────────────────────────────────
    "J11": (  95.0,   90.0,    0 ),   # front row (BP pins 1-20)
    "J12": ( 108.0,   90.0,    0 ),   # back row  (BP pins 21-40)
}

# ── helpers ──────────────────────────────────────────────────────────────────

MM2NM = 1_000_000   # 1 mm = 1e6 nm

def mm_to_nm(v):
    return int(round(v * MM2NM))


def refresh(kicad):
    """Refresh + zoom-fit the PCBnew display."""
    kicad.run_action('view.refresh')
    kicad.run_action('pcbnew.ZoomFitScreen')


def place(board, fps_by_ref):
    moved = []
    skipped = []

    commit = board.begin_commit()
    try:
        for ref, (x_mm, y_mm, rot) in POSITIONS.items():
            fp = fps_by_ref.get(ref)
            if fp is None:
                skipped.append(f'{ref}: not found on board')
                continue

            fp.position = Vector2.from_xy_mm(x_mm, y_mm)
            fp.orientation = Angle.from_degrees(float(rot))

            board.update_items(fp)
            moved.append(f'{ref:6s} → ({x_mm:.1f}, {y_mm:.1f}) rot={rot}°')

        board.push_commit(commit, 'pcb_place.py: initial placement')
    except Exception as e:
        board.drop_commit(commit)
        raise

    return moved, skipped


def main():
    k = kipy.KiCad(socket_path=SOCKET)
    print(f'KiCad {k.get_version()}')

    board = k.get_board()
    print(f'Board: {board.name}')

    fps = board.get_footprints()
    fps_by_ref = {fp.reference_field.text.value: fp for fp in fps}
    print(f'Footprints on board: {sorted(fps_by_ref.keys())}')
    print()

    if not POSITIONS:
        print('POSITIONS dict is empty — nothing to place yet.')
        print('Uncomment entries in POSITIONS to start placing.')
        return

    moved, skipped = place(board, fps_by_ref)

    if moved:
        print('Placed:')
        for m in moved:
            print(f'  {m}')
    if skipped:
        print('Skipped:')
        for s in skipped:
            print(f'  {s}')

    print(f'\nDone. {len(moved)} placed, {len(skipped)} skipped.')
    refresh(k)
    print('PCBnew refreshed.')


if __name__ == '__main__':
    main()
