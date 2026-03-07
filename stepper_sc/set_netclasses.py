#!/usr/bin/env python3
"""
set_netclasses.py — Define net classes with track widths in mils.

  Default  : 10 mil = 0.254mm  (all signals)
  Power_5V : 30 mil = 0.762mm  (+5V)
  Power_24V: 60 mil = 1.524mm  (+24V)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'venv',
                                'lib', 'python3.13', 'site-packages'))

import kipy
from kipy.board import NetClass
from kipy.proto.common.commands import project_commands_pb2
from kipy.proto.common.types.base_types_pb2 import MapMergeMode
from kipy.proto.common.types.project_settings_pb2 import NetClassType
from google.protobuf.empty_pb2 import Empty

SOCKET = 'ipc:///home/claude-agent/tmp/kicad/api.sock'

MIL = 25400  # 1 mil = 25400 nm

def mil(v):
    return int(v * MIL)

def make_nc(name, track_mil, clearance_mil, nets=None):
    nc = NetClass()
    nc._proto.name       = name
    nc._proto.type       = NetClassType.NCT_EXPLICIT
    nc.track_width       = mil(track_mil)
    nc.clearance         = mil(clearance_mil)
    if nets:
        nc._proto.constituents.extend(nets)
    return nc

def main():
    k    = kipy.KiCad(socket_path=SOCKET)
    board = k.get_board()
    proj  = board.get_project()

    # Show existing
    existing = proj.get_net_classes()
    print('Existing net classes:')
    for nc in existing:
        tw = nc.track_width
        print(f'  {nc.name}: {tw/MIL:.0f} mil' if tw else f'  {nc.name}: (default)')

    # Define net classes
    nc_default = make_nc('Default',   track_mil=10, clearance_mil=8)
    nc_5v      = make_nc('Power_5V',  track_mil=30, clearance_mil=8,  nets=['+5V'])
    nc_24v     = make_nc('Power_24V', track_mil=60, clearance_mil=10, nets=['+24V'])

    # Send SetNetClasses command directly (not yet exposed in Project API)
    cmd = project_commands_pb2.SetNetClasses()
    cmd.net_classes.extend([nc_default._proto, nc_5v._proto, nc_24v._proto])
    cmd.merge_mode = MapMergeMode.MMM_REPLACE

    k._client.send(cmd, Empty)

    print('\nNet classes applied:')
    print(f'  Default   : 10 mil (0.254mm) — all signals')
    print(f'  Power_5V  : 30 mil (0.762mm) — +5V')
    print(f'  Power_24V : 60 mil (1.524mm) — +24V')

    print('Done. Save the project in KiCad (Ctrl+S) to persist.')

if __name__ == '__main__':
    main()
