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
from kipy.geometry import Vector2

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
    #        R4─R5─Q2──J3            │          │  DIR buffer
    #   82  ├────────────────────────┤          │
    #        J4 J5 J6 J7             │          │  signal terminals
    #        J8 J9 J10               │          │
    #  145  └────────────────────────┴──────────┘

    # ── Power supply row (top, y=35) ────────────────────────────────────────
    # Horizontal row: J1 → C1/C2 → U1 → C3/C4 → C5 near BP
    "J1":  (  33.0,   35.0,    0 ),   # 24V screw terminal (top-left)
    "C1":  (  47.0,   35.0,    0 ),   # 47µF in
    "C2":  (  56.0,   35.0,    0 ),   # 100nF in
    "U1":  (  66.0,   35.0,    0 ),   # 78M05 regulator
    "C3":  (  77.0,   35.0,    0 ),   # 100µF out
    "C4":  (  86.0,   35.0,    0 ),   # 100nF out
    "C5":  (  80.0,   48.0,    0 ),   # 100nF BP VIN — offset row to avoid J11 column

    # ── PUL NPN buffer (y=65) ───────────────────────────────────────────────
    "R1":  (  33.0,   65.0,    0 ),   # 1k base
    "R2":  (  47.0,   65.0,    0 ),   # 10k gnd
    "Q1":  (  62.0,   65.0,    0 ),   # BC547
    "J2":  (  77.0,   65.0,    0 ),   # PUL output terminal

    # ── DIR NPN buffer (y=85) ───────────────────────────────────────────────
    "R4":  (  33.0,   85.0,    0 ),   # 1k base
    "R5":  (  47.0,   85.0,    0 ),   # 10k gnd
    "Q2":  (  62.0,   85.0,    0 ),   # BC547
    "J3":  (  77.0,   85.0,    0 ),   # DIR output terminal

    # ── Signal terminals (two rows, bottom section) ──────────────────────────
    "J4":  (  33.0,  108.0,    0 ),   # ES_L
    "J5":  (  47.0,  108.0,    0 ),   # ES_R
    "J6":  (  61.0,  108.0,    0 ),   # JOGL
    "J7":  (  75.0,  108.0,    0 ),   # JOGR
    "J8":  (  33.0,  125.0,    0 ),   # STEPL
    "J9":  (  47.0,  125.0,    0 ),   # STEPR
    "J10": (  61.0,  125.0,    0 ),   # BUZZ

    # ── Black Pill headers (right side, vertical) ────────────────────────────
    # Shifted left: J12 right edge = 106 + 5.3 = 111.3mm  (board right = 115mm) ✓
    # 15.24mm (6×2.54) center-to-center between rows
    "J11": (  91.0,   90.0,    0 ),   # front row (BP pins 1-20)
    "J12": ( 106.0,   90.0,    0 ),   # back row  (BP pins 21-40)
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

            fp.proto.position.x_nm = mm_to_nm(x_mm)
            fp.proto.position.y_nm = mm_to_nm(y_mm)
            fp.proto.orientation.value_degrees = float(rot)

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
