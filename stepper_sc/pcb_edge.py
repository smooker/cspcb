#!/usr/bin/env python3
"""
pcb_edge.py — Draw Edge.Cuts board outline on stepper_sc.kicad_pcb via KiCad IPC API

Board: 90 × 120 mm
Origin corner: (25, 25) mm from KiCad sheet origin

Run from host:
  sudo chroot /chroot/claude /bin/bash -c \
    "cd /home/claude-agent/work/stepper_sc && \
     venv/bin/python3 stepper_sc/pcb_edge.py"
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'venv',
                                'lib', 'python3.13', 'site-packages'))

import kipy
from kipy.board_types import BoardSegment
from kipy.proto.board.board_types_pb2 import BoardLayer

SOCKET = 'ipc:///home/claude-agent/tmp/kicad/api.sock'

MM  = 1_000_000   # nm per mm

# Board outline corners (mm)
X0, Y0 = 25.0, 25.0   # top-left
X1, Y1 = 115.0, 145.0  # bottom-right  (90 × 120 mm)

EDGES = [
    ((X0, Y0), (X1, Y0)),  # top
    ((X1, Y0), (X1, Y1)),  # right
    ((X1, Y1), (X0, Y1)),  # bottom
    ((X0, Y1), (X0, Y0)),  # left
]


def nm(v):
    return int(round(v * MM))


def main():
    k = kipy.KiCad(socket_path=SOCKET)
    print(f'KiCad {k.get_version()}')

    board = k.get_board()
    print(f'Board: {board.name}')

    segments = []
    for (x0, y0), (x1, y1) in EDGES:
        seg = BoardSegment()
        seg.proto.shape.segment.start.x_nm = nm(x0)
        seg.proto.shape.segment.start.y_nm = nm(y0)
        seg.proto.shape.segment.end.x_nm   = nm(x1)
        seg.proto.shape.segment.end.y_nm   = nm(y1)
        seg.proto.shape.attributes.stroke.width.value_nm = nm(0.05)
        seg.proto.layer = BoardLayer.BL_Edge_Cuts
        segments.append(seg)

    commit = board.begin_commit()
    try:
        board.create_items(segments)
        board.push_commit(commit, 'pcb_edge.py: add Edge.Cuts outline 90×120mm')
        print(f'Added {len(segments)} Edge.Cuts segments.')
    except Exception as e:
        board.drop_commit(commit)
        raise

    k.run_action('view.refresh')
    k.run_action('pcbnew.ZoomFitScreen')
    print('Done.')


if __name__ == '__main__':
    main()
