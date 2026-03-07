#!/usr/bin/env python3
"""
router.py — Main smooker-router entry point.

1. Query KiCad board via IPC
2. Build obstacle grid from existing tracks, pads, courtyards
3. Find unconnected nets (ratsnest)
4. Route each net with A* (shortest first)
5. Push tracks + vias back to KiCad
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'venv',
                                'lib', 'python3.13', 'site-packages'))
sys.path.insert(0, os.path.dirname(__file__))

import kipy
from kipy.board_types import Track, Via, BoardLayer, Net
from kipy.geometry import Vector2

from grid import Grid, FCU, BCU
from astar import astar
from segments import path_to_segments

SOCKET = 'ipc:///home/claude-agent/tmp/kicad/api.sock'

# Board extents (mm) — Edge.Cuts
BX0, BY0 = 25.0, 25.0
BX1, BY1 = 115.0, 161.0

# Router settings
GRID_RES   = 0.1    # mm per cell
CLEARANCE  = 0.2    # mm — extra obstacle inflation
MIL        = 25400  # nm/mil

NET_WIDTHS = {
    '+24V': 60 * MIL,
    '+5V':  30 * MIL,
}
DEFAULT_WIDTH = 10 * MIL

VIA_DIAMETER = int(0.8 * 1e6)   # 0.8mm
VIA_DRILL    = int(0.4 * 1e6)   # 0.4mm


def nm(mm): return int(round(mm * 1e6))


def layer_to_kicad(layer_idx):
    return BoardLayer.BL_F_Cu if layer_idx == FCU else BoardLayer.BL_B_Cu


def make_track(net, x0, y0, x1, y1, layer_idx, width):
    t = Track()
    t.net   = net
    t.layer = layer_to_kicad(layer_idx)
    t.width = width
    t.start = Vector2.from_xy(nm(x0), nm(y0))
    t.end   = Vector2.from_xy(nm(x1), nm(y1))
    return t


def make_via(net, x, y):
    v = Via()
    v.net = net
    v.position = Vector2.from_xy(nm(x), nm(y))
    v.pad_size   = Vector2.from_xy(VIA_DIAMETER, VIA_DIAMETER)
    v.drill_size = Vector2.from_xy(VIA_DRILL, VIA_DRILL)
    return v


def build_base_grid(board):
    """Build obstacle grid from existing tracks only (no pads)."""
    grid = Grid(BX0, BY0, BX1, BY1, GRID_RES)

    tracks = board.get_tracks()
    for t in tracks:
        x0 = t.start.x / 1e6
        y0 = t.start.y / 1e6
        x1 = t.end.x / 1e6
        y1 = t.end.y / 1e6
        w  = t.width / 1e6
        layer = FCU if t.layer == BoardLayer.BL_F_Cu else BCU
        grid.block_segment(x0, y0, x1, y1, w, layer, inflate=CLEARANCE)

    return grid


def add_pad_obstacles(grid, board, exclude_net=None):
    """Block all pads EXCEPT those belonging to exclude_net."""
    pads = board.get_pads()
    for p in pads:
        if exclude_net and p.net.proto.name == exclude_net:
            continue
        cx  = p.position.x / 1e6
        cy  = p.position.y / 1e6
        # Use pad bounding box from proto size field
        # Conservative: 1.05mm half-size for 2.1mm pads, 0.85mm for 1.7mm pads
        bbox = board.get_item_bounding_box(p)
        hw = (bbox.size.x / 1e6) / 2
        hh = (bbox.size.y / 1e6) / 2
        grid.block_rect(cx-hw, cy-hh, cx+hw, cy+hh, 'both', inflate=CLEARANCE)


def get_ratsnest(board):
    """Return dict of {net_name: [pad_list]} for unrouted nets."""
    pads = board.get_pads()
    nets = {}
    for p in pads:
        n = p.net.proto.name
        if n and not n.startswith('unconnected'):
            nets.setdefault(n, []).append(p)

    tracks = board.get_tracks()
    routed = set(t.net.proto.name for t in tracks)

    # Only return nets not yet started AND with exactly 2 pads
    todo = {name: ps for name, ps in nets.items()
            if name not in routed and len(ps) == 2}
    return todo


def manhattan(p0, p1):
    return (abs(p0.position.x - p1.position.x) +
            abs(p0.position.y - p1.position.y))


def main():
    k     = kipy.KiCad(socket_path=SOCKET)
    board = k.get_board()
    print(f'KiCad {k.get_version()}')

    todo = get_ratsnest(board)
    if not todo:
        print('Nothing to route!')
        return

    # Sort nets: shortest Manhattan distance first
    def net_dist(item):
        name, ps = item
        return manhattan(ps[0], ps[1])

    todo_sorted = sorted(todo.items(), key=net_dist)
    print(f'\nNets to route ({len(todo_sorted)}):')
    for name, ps in todo_sorted:
        d = manhattan(ps[0], ps[1]) / 1e6
        print(f'  {name}: {d:.1f}mm')

    # Build base grid with tracks only
    print('\nBuilding obstacle grid...')
    base_grid = build_base_grid(board)

    all_tracks = []
    all_vias   = []
    failed     = []

    for net_name, ps in todo_sorted:
        p0, p1 = ps
        x0, y0 = p0.position.x / 1e6, p0.position.y / 1e6
        x1, y1 = p1.position.x / 1e6, p1.position.y / 1e6
        net_obj = p0.net
        width   = NET_WIDTHS.get(net_name, DEFAULT_WIDTH)
        w_mm    = width / 1e6

        print(f'\n  Routing {net_name}: ({x0:.2f},{y0:.2f}) → ({x1:.2f},{y1:.2f})')

        # Fresh grid for this net: base tracks + all pads except this net's
        import copy
        grid = copy.deepcopy(base_grid)
        add_pad_obstacles(grid, board, exclude_net=net_name)

        start_rc = grid.mm_to_cell(x0, y0)
        end_rc   = grid.mm_to_cell(x1, y1)

        # Ensure start/end cells are unblocked
        for l in range(2):
            grid.unblock_cell(start_rc[0], start_rc[1], l)
            grid.unblock_cell(end_rc[0],   end_rc[1],   l)

        path = astar(grid, start_rc, end_rc)

        if path is None:
            print(f'    FAILED — no path found')
            failed.append(net_name)
            continue

        segs, vias = path_to_segments(path, grid)
        print(f'    OK — {len(segs)} segments, {len(vias)} vias, {len(path)} cells')

        # Create track objects
        for (tx0, ty0, tx1, ty1, layer) in segs:
            all_tracks.append(make_track(net_obj, tx0, ty0, tx1, ty1, layer, width))

        for (vx, vy) in vias:
            all_vias.append(make_via(net_obj, vx, vy))

        # Update base grid with new tracks (so next net avoids them)
        for (tx0, ty0, tx1, ty1, layer) in segs:
            base_grid.block_segment(tx0, ty0, tx1, ty1, w_mm, layer, inflate=CLEARANCE)

    print(f'\nPushing {len(all_tracks)} tracks + {len(all_vias)} vias to KiCad...')
    items = all_tracks + all_vias
    if items:
        board.create_items(items)
        k.run_action('view.redraw')
        board.save()

    print(f'\n=== Done ===')
    print(f'  Routed: {len(todo_sorted) - len(failed)} nets')
    if failed:
        print(f'  Failed: {failed}')


if __name__ == '__main__':
    main()
