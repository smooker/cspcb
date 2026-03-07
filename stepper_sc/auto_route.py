#!/usr/bin/env python3
"""
auto_route.py — Route all unconnected 2-pad nets on F.Cu using 45° routing.

Strategy per net:
  If dx == 0 or dy == 0 → single straight segment
  Otherwise → two segments: diagonal (45°) then straight
  Diagonal goes first to eat up the smaller dimension.
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'venv',
                                'lib', 'python3.13', 'site-packages'))

import kipy
from kipy.board_types import Track, BoardLayer, Net
from kipy.geometry import Vector2

SOCKET = 'ipc:///home/claude-agent/tmp/kicad/api.sock'

MIL = 25400  # nm per mil

# Net class track widths (mil → nm)
NET_WIDTHS = {
    '+24V':   60 * MIL,
    '+5V':    30 * MIL,
    '+3.3V':  10 * MIL,
}
DEFAULT_WIDTH = 10 * MIL

LAYER = BoardLayer.BL_F_Cu


def nm(mm_val):
    return int(round(mm_val * 1_000_000))


def make_track(net, x0, y0, x1, y1, width):
    t = Track()
    t.net   = net
    t.layer = LAYER
    t.width = width
    t.start = Vector2.from_xy(nm(x0), nm(y0))
    t.end   = Vector2.from_xy(nm(x1), nm(y1))
    return t


def route_45(net, x0, y0, x1, y1, width):
    """Route from (x0,y0) to (x1,y1) with 45° bend. Returns list of Track."""
    dx = x1 - x0
    dy = y1 - y0
    if abs(dx) < 0.001 or abs(dy) < 0.001:
        # Straight line
        return [make_track(net, x0, y0, x1, y1, width)]

    # Diagonal segment eats up min(|dx|, |dy|) in both axes
    adx, ady = abs(dx), abs(dy)
    sx, sy = (1 if dx > 0 else -1), (1 if dy > 0 else -1)

    if adx <= ady:
        # Diagonal goes full dx, then straight vertical
        mx = x1
        my = y0 + sy * adx
    else:
        # Diagonal goes full dy, then straight horizontal
        mx = x0 + sx * ady
        my = y1

    return [
        make_track(net, x0, y0, mx, my, width),
        make_track(net, mx, my, x1, y1, width),
    ]


def main():
    k     = kipy.KiCad(socket_path=SOCKET)
    board = k.get_board()
    print(f'KiCad {k.get_version()}')

    # Group pads by net
    pads = board.get_pads()
    nets = {}
    for p in pads:
        n = p.net.proto.name
        if n and not n.startswith('unconnected'):
            nets.setdefault(n, []).append(p)

    # Get already-routed nets
    tracks = board.get_tracks()
    routed = set(t.net.proto.name for t in tracks)

    # Only route TODO nets (not yet started)
    todo = {name: ps for name, ps in nets.items()
            if name not in routed and len(ps) == 2}

    print(f'\nNets to route: {sorted(todo.keys())}')

    new_tracks = []
    for net_name, ps in sorted(todo.items()):
        p0, p1 = ps
        x0, y0 = p0.position.x / 1e6, p0.position.y / 1e6
        x1, y1 = p1.position.x / 1e6, p1.position.y / 1e6
        width = NET_WIDTHS.get(net_name, DEFAULT_WIDTH)
        net_obj = p0.net

        segs = route_45(net_obj, x0, y0, x1, y1, width)
        new_tracks.extend(segs)
        print(f'  {net_name}: ({x0:.2f},{y0:.2f}) → ({x1:.2f},{y1:.2f}) '
              f'[{width//MIL}mil, {len(segs)} seg(s)]')

    print(f'\nCreating {len(new_tracks)} track segments...')
    board.create_items(new_tracks)
    k.run_action('view.redraw')
    board.save()
    print('Done.')


if __name__ == '__main__':
    main()
