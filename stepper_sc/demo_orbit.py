#!/usr/bin/env python3
"""
demo_orbit.py — Orbit the first footprint in a circle to demo live KiCad IPC control.
Press Ctrl+C to stop — footprint is returned to its original position.
"""

import sys, os, time, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'venv',
                                'lib', 'python3.13', 'site-packages'))

import kipy
from kipy.geometry import Vector2, Angle

SOCKET = 'ipc:///home/claude-agent/tmp/kicad/api.sock'

RADIUS   = 15.0   # mm — orbit radius
STEPS    = 60     # steps per full revolution
DELAY    = 0.05   # seconds between steps  → ~3s per orbit
MM       = 1_000_000


def main():
    k = kipy.KiCad(socket_path=SOCKET)
    print(f'KiCad {k.get_version()}')

    board = k.get_board()
    fps = board.get_footprints()
    if not fps:
        print('No footprints on board.')
        return

    fp = fps[0]
    ref = fp.reference_field.text.value
    orig_pos = fp.position                      # Vector2 — read via property
    orig_rot = fp.orientation                   # Angle   — read via property
    cx = orig_pos.x / MM
    cy = orig_pos.y / MM

    print(f'Orbiting {ref} around ({cx:.1f}, {cy:.1f}) mm, radius={RADIUS}mm')
    print('Press Ctrl+C to stop.\n')

    step = 0
    try:
        while True:
            angle = 2 * math.pi * step / STEPS
            x = cx + RADIUS * math.cos(angle)
            y = cy + RADIUS * math.sin(angle)
            rot = (step / STEPS) * 360.0

            commit = board.begin_commit()
            fp.position = Vector2.from_xy_mm(x, y)
            fp.orientation = Angle.from_degrees(rot)
            board.update_items(fp)
            board.push_commit(commit, 'orbit')
            k.run_action('view.redraw')

            sys.stdout.write(f'\r  {ref} @ ({x:.1f}, {y:.1f}) rot={rot:.0f}°  step {step:3d}')
            sys.stdout.flush()

            step = (step + 1) % STEPS
            time.sleep(DELAY)

    except KeyboardInterrupt:
        print('\n\nRestoring original position...')
        commit = board.begin_commit()
        fp.position = orig_pos
        fp.orientation = orig_rot
        board.update_items(fp)
        board.push_commit(commit, 'demo_orbit: restore')
        k.run_action('view.redraw')
        k.run_action('pcbnew.ZoomFitScreen')
        print(f'{ref} restored to ({cx:.1f}, {cy:.1f}).')


if __name__ == '__main__':
    main()
