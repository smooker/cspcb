#!/usr/bin/env python3
"""
demo_orbit_all.py — Orbit ALL footprints simultaneously via KiCad IPC.

Each footprint orbits around its home position in a circle.
A phase offset spreads them into a ripple/wave pattern.
Press Ctrl+C to restore all footprints to their original positions.
"""

import sys, os, time, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'venv',
                                'lib', 'python3.13', 'site-packages'))

import kipy
from kipy.geometry import Vector2, Angle

SOCKET = 'ipc:///home/claude-agent/tmp/kicad/api.sock'

RADIUS  = 3.0    # mm — orbit radius per footprint
STEPS   = 360    # steps per full revolution
DELAY   = 0.01   # seconds per step → ~3.6s per orbit


def main():
    k = kipy.KiCad(socket_path=SOCKET)
    print(f'KiCad {k.get_version()}')

    board = k.get_board()
    fps = board.get_footprints()
    if not fps:
        print('No footprints on board.')
        return

    # Sort for a nice wave order: left→right, top→bottom
    fps.sort(key=lambda f: (
        round(f.position.x / 1_000_000),
        round(f.position.y / 1_000_000)
    ))

    # Snapshot home positions
    homes = []
    for fp in fps:
        ref  = fp.reference_field.text.value
        pos  = fp.position
        rot  = fp.orientation
        cx   = pos.x / 1_000_000
        cy   = pos.y / 1_000_000
        homes.append((fp, ref, cx, cy, rot))

    n = len(fps)
    print(f'Orbiting {n} footprints (radius={RADIUS}mm, {STEPS} steps/rev)')
    print('Press Ctrl+C to stop and restore.\n')

    step = 0
    try:
        while True:
            commit = board.begin_commit()

            for i, (fp, ref, cx, cy, orig_rot) in enumerate(homes):
                # Phase spreads footprints evenly around the clock
                phase = 2 * math.pi * i / n
                angle = 2 * math.pi * step / STEPS + phase

                x = cx + RADIUS * math.cos(angle)
                y = cy + RADIUS * math.sin(angle)
                spin = (step / STEPS * 360.0 + i * (360.0 / n)) % 360.0

                fp.position    = Vector2.from_xy_mm(x, y)
                fp.orientation = Angle.from_degrees(spin)

            board.push_commit(commit, 'orbit_all')
            k.run_action('view.redraw')

            sys.stdout.write(f'\r  step {step:4d}/{STEPS}  ')
            sys.stdout.flush()

            step = (step + 1) % STEPS
            time.sleep(DELAY)

    except KeyboardInterrupt:
        print('\n\nRestoring all footprints...')
        commit = board.begin_commit()
        for fp, ref, cx, cy, orig_rot in homes:
            fp.position    = Vector2.from_xy_mm(cx, cy)
            fp.orientation = orig_rot
        board.push_commit(commit, 'orbit_all: restore')
        k.run_action('view.redraw')
        k.run_action('pcbnew.ZoomFitScreen')
        print(f'All {n} footprints restored.')


if __name__ == '__main__':
    main()
