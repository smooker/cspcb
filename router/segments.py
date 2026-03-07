"""
segments.py — Convert A* path to track segments and via locations.

Groups consecutive cells on the same layer with the same direction
into single track segments. Layer changes become vias.
"""
from grid import FCU, BCU


def path_to_segments(path, grid):
    """
    path: list of (row, col, layer)
    grid: Grid instance (for cell_to_mm)

    Returns:
      tracks: list of (x0,y0, x1,y1, layer)
      vias:   list of (x, y)  — via centers
    """
    if not path or len(path) < 2:
        return [], []

    tracks = []
    vias   = []

    # Walk the path, grouping same-layer same-direction runs
    seg_start = path[0]
    prev      = path[0]

    def flush(seg_start, seg_end):
        r0, c0, l0 = seg_start
        r1, c1, _  = seg_end
        x0, y0 = grid.cell_to_mm(r0, c0)
        x1, y1 = grid.cell_to_mm(r1, c1)
        if abs(x1-x0) > 1e-9 or abs(y1-y0) > 1e-9:
            tracks.append((x0, y0, x1, y1, l0))

    for i in range(1, len(path)):
        cur = path[i]
        pr, pc, pl = prev
        cr, cc, cl = cur

        if cl != pl:
            # Layer change → flush current segment, add via
            flush(seg_start, prev)
            x, y = grid.cell_to_mm(pr, pc)
            vias.append((x, y))
            seg_start = cur
        else:
            # Same layer — check if direction changed
            sr0, sc0, _ = seg_start
            dr_prev = pr - sr0
            dc_prev = pc - sc0
            dr_cur  = cr - pr
            dc_cur  = cc - pc

            # Normalize direction
            def sign(v): return (1 if v > 0 else -1) if v != 0 else 0
            dir_prev = (sign(dr_prev), sign(dc_prev))
            dir_cur  = (sign(dr_cur),  sign(dc_cur))

            if dir_prev != dir_cur and i > 1:
                flush(seg_start, prev)
                seg_start = prev

        prev = cur

    flush(seg_start, prev)
    return tracks, vias
