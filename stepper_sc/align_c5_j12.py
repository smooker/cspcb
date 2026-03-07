#!/usr/bin/env python3
"""Align C5 +5V pad (pad1) with J12 pin 20 (x-coordinate, since connectors run horizontally)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'venv',
                                'lib', 'python3.13', 'site-packages'))
import kipy
from kipy.geometry import Vector2, Angle

SOCKET = 'ipc:///home/claude-agent/tmp/kicad/api.sock'

def main():
    k = kipy.KiCad(socket_path=SOCKET)
    board = k.get_board()

    # Get all pads
    pads = board.get_pads()

    # Find J12 pin 20 and C5 pad1
    j12_pin20 = None
    c5_pad1 = None
    c5_pad2 = None

    for p in pads:
        ref = p.parent_footprint_reference
        num = p.proto.number
        if ref == 'J12' and num == '20':
            j12_pin20 = p
        if ref == 'C5' and num == '1':
            c5_pad1 = p
        if ref == 'C5' and num == '2':
            c5_pad2 = p

    if not j12_pin20:
        print('ERROR: J12 pin 20 not found')
        return
    if not c5_pad1:
        print('ERROR: C5 pad1 not found')
        return

    j12p20_x = j12_pin20.position.x / 1e6
    j12p20_y = j12_pin20.position.y / 1e6
    c5p1_x = c5_pad1.position.x / 1e6
    c5p1_y = c5_pad1.position.y / 1e6
    print(f'J12 pin20: ({j12p20_x:.3f}, {j12p20_y:.3f})')
    print(f'C5 pad1(+5V): ({c5p1_x:.3f}, {c5p1_y:.3f})')

    if c5_pad2:
        c5p2_x = c5_pad2.position.x / 1e6
        c5p2_y = c5_pad2.position.y / 1e6
        print(f'C5 pad2(GND): ({c5p2_x:.3f}, {c5p2_y:.3f})')

    # Find C5 footprint
    fps = board.get_footprints()
    c5_fp = next((f for f in fps if f.reference_field.text.value == 'C5'), None)
    if not c5_fp:
        print('ERROR: C5 footprint not found')
        return

    c5_cx = c5_fp.position.x / 1e6
    c5_cy = c5_fp.position.y / 1e6
    print(f'C5 center: ({c5_cx:.3f}, {c5_cy:.3f})')

    # We want C5 pad1 x to align with J12 pin20 x
    # C5 pads are spread along x-axis (horizontal), J12 pins are also along x
    # Alignment: C5 pad1 x == J12 pin20 x
    dx = j12p20_x - c5p1_x
    # Also align y: C5 should be between J11 (y=63) and J12 (y=50), keep current y
    # But user says align with J12 pin20 — let's match x and keep y midpoint between J11 and J12
    new_cx = c5_cx + dx
    new_cy = c5_cy  # keep current y

    print(f'Moving C5 by dx={dx:.3f}mm: ({c5_cx:.3f},{c5_cy:.3f}) -> ({new_cx:.3f},{new_cy:.3f})')

    c5_fp.position = Vector2.from_xy_mm(new_cx, new_cy)
    board.update_items(c5_fp)
    k.run_action('view.redraw')

    # Verify
    pads2 = board.get_pads()
    for p in pads2:
        if p.parent_footprint_reference == 'C5' and p.proto.number == '1':
            print(f'C5 pad1 after: ({p.position.x/1e6:.3f}, {p.position.y/1e6:.3f})')
        if p.parent_footprint_reference == 'C5' and p.proto.number == '2':
            print(f'C5 pad2 after: ({p.position.x/1e6:.3f}, {p.position.y/1e6:.3f})')

    board.save()
    print('Done.')

if __name__ == '__main__':
    main()
