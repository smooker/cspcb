#!/usr/bin/env python3
"""
gnd_pour.py — Add GND copper pour zones on F.Cu and B.Cu, then refill.

Board Edge.Cuts: x=25..115, y=25..161 (approx — we read it from edge graphics).
Zone outline = 0.5mm inside Edge.Cuts on all sides.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'venv',
                                'lib', 'python3.13', 'site-packages'))

import kipy
import kipy.board_types as bt
from kipy.board_types import (Zone, ZoneType, ZoneFillMode, ZoneBorderStyle,
                               IslandRemovalMode, BoardLayer,
                               PolygonWithHoles, Net)
from kipy.geometry import Vector2, PolyLine, PolyLineNode

SOCKET = 'ipc:///home/claude-agent/tmp/kicad/api.sock'

# Inset from Edge.Cuts (mm) — zone outline slightly inside board edge
INSET = 0.5

def mm(v):
    return int(round(v * 1_000_000))

def make_gnd_zone(gnd_net, layer, x0, y0, x1, y1):
    """Create a GND filled zone on the given layer covering (x0,y0)..(x1,y1) mm."""
    z = Zone()
    z.type   = ZoneType.ZT_COPPER
    z.layers = [layer]
    z.net    = gnd_net

    # Zone settings
    z.min_thickness   = mm(0.25)
    z.clearance       = mm(0.3)
    z.island_mode     = IslandRemovalMode.IRM_ALWAYS
    z.border_style    = ZoneBorderStyle.ZBS_DIAGONAL_EDGE
    z.border_hatch_pitch = mm(0.5)

    # Build rectangular outline
    corners = [
        Vector2.from_xy(mm(x0), mm(y0)),
        Vector2.from_xy(mm(x1), mm(y0)),
        Vector2.from_xy(mm(x1), mm(y1)),
        Vector2.from_xy(mm(x0), mm(y1)),
    ]

    poly = PolygonWithHoles()
    pl = PolyLine()
    pl.closed = True
    for pt in corners:
        pl.append(PolyLineNode.from_point(pt))
    poly.outline = pl

    z.outline = poly
    return z

def main():
    k     = kipy.KiCad(socket_path=SOCKET)
    board = k.get_board()
    print(f'KiCad {k.get_version()}')

    # Find GND net from any GND pad
    pads    = board.get_pads()
    gnd_pad = next((p for p in pads if p.net.proto.name == 'GND'), None)
    if not gnd_pad:
        print('ERROR: no GND net found on board')
        return
    gnd_net = gnd_pad.net
    print(f'GND net found: "{gnd_net.proto.name}"')

    # Board area (from Edge.Cuts — confirmed 25..115 x 25..161)
    bx0, by0 = 25.0 + INSET, 25.0 + INSET
    bx1, by1 = 115.0 - INSET, 161.0 - INSET
    print(f'Zone outline: ({bx0},{by0}) .. ({bx1},{by1}) mm')

    # Create zones for F.Cu and B.Cu
    zone_fcu = make_gnd_zone(gnd_net, BoardLayer.BL_F_Cu, bx0, by0, bx1, by1)
    zone_bcu = make_gnd_zone(gnd_net, BoardLayer.BL_B_Cu, bx0, by0, bx1, by1)

    print('Creating F.Cu GND zone...')
    board.create_items(zone_fcu)
    print('Creating B.Cu GND zone...')
    board.create_items(zone_bcu)

    print('Refilling zones...')
    board.refill_zones()

    k.run_action('view.redraw')
    board.save()
    print('Done. GND pour on F.Cu + B.Cu complete.')

if __name__ == '__main__':
    main()
