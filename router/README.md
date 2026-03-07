# smooker-router

A homegrown PCB autorouter for KiCad 9 via IPC (kipy).

## Architecture

```
grid.py        — Board grid, obstacle map (tracks, pads, courtyards)
astar.py       — A* pathfinder on the grid (supports F.Cu + B.Cu + vias)
segments.py    — Convert A* path → 45° track segments
router.py      — Main: query board, build ratsnest, route net by net, push to KiCad
```

## Grid
- Resolution: 0.1mm per cell (configurable)
- Layers: F.Cu, B.Cu (two-layer board)
- Obstacles: existing tracks (inflated by clearance), pad copper, courtyard edges
- Vias: allowed anywhere not blocked, cost penalty applied

## Pathfinder (A*)
- 8-directional moves (N, NE, E, SE, S, SW, W, NW) on each layer
- Via transition: move between layers at same cell (cost = via penalty)
- Heuristic: Chebyshev distance (optimal for 45° routing)
- Cost: straight=1.0, diagonal=1.0 (equal on grid), via=10.0

## Segment generation
- Collapse collinear A* cells into minimal segments
- Output: list of (x0,y0,x1,y1,layer) tuples → Track objects

## Routing order
- Nets sorted by: shortest Manhattan distance first (easiest first)
- After each net: update obstacle map with new tracks
