"""
astar.py — A* pathfinder on the two-layer grid.

State: (row, col, layer)
Moves:
  - 8 directions on same layer (cost 1.0 each)
  - Via: switch layer at same cell (cost = VIA_COST)

Returns list of (row, col, layer) from start to end, or None if no path.
"""
import heapq
from grid import FCU, BCU, NLAYERS

# Move costs
STRAIGHT_COST  = 1.0   # N, S, E, W
DIAGONAL_COST  = 1.0   # NE, NW, SE, SW (equal on grid for 45° routing)
VIA_COST       = 15.0  # penalty for layer change

DIRECTIONS = [
    (-1,  0, STRAIGHT_COST),   # N
    ( 1,  0, STRAIGHT_COST),   # S
    ( 0,  1, STRAIGHT_COST),   # E
    ( 0, -1, STRAIGHT_COST),   # W
    (-1,  1, DIAGONAL_COST),   # NE
    (-1, -1, DIAGONAL_COST),   # NW
    ( 1,  1, DIAGONAL_COST),   # SE
    ( 1, -1, DIAGONAL_COST),   # SW
]


def chebyshev(r0, c0, r1, c1):
    """Chebyshev distance — admissible heuristic for 8-directional movement."""
    return max(abs(r1 - r0), abs(c1 - c0))


def astar(grid, start_rc, end_rc, start_layer=FCU, end_layer=FCU):
    """
    Find path from start_rc to end_rc.
    start_rc, end_rc: (row, col)
    Returns list of (row, col, layer) or None.
    """
    sr, sc = start_rc
    er, ec = end_rc

    # Priority queue: (f, g, row, col, layer)
    open_heap = []
    h0 = chebyshev(sr, sc, er, ec)
    heapq.heappush(open_heap, (h0, 0.0, sr, sc, start_layer))

    # came_from[(r,c,l)] = (pr,pc,pl)
    came_from = {}
    g_score = {(sr, sc, start_layer): 0.0}

    visited = set()

    while open_heap:
        f, g, r, c, layer = heapq.heappop(open_heap)

        state = (r, c, layer)
        if state in visited:
            continue
        visited.add(state)

        # Goal check
        if r == er and c == ec and layer == end_layer:
            return _reconstruct(came_from, state)

        # 8-directional moves on same layer
        for dr, dc, cost in DIRECTIONS:
            nr, nc = r + dr, c + dc
            if grid.is_blocked(nr, nc, layer):
                continue
            ns = (nr, nc, layer)
            ng = g + cost
            if ng < g_score.get(ns, float('inf')):
                g_score[ns] = ng
                came_from[ns] = state
                h = chebyshev(nr, nc, er, ec)
                heapq.heappush(open_heap, (ng + h, ng, nr, nc, layer))

        # Via: switch layer (only if current cell is not blocked on other layer)
        other = BCU if layer == FCU else FCU
        if not grid.is_blocked(r, c, other):
            ns = (r, c, other)
            ng = g + VIA_COST
            if ng < g_score.get(ns, float('inf')):
                g_score[ns] = ng
                came_from[ns] = state
                h = chebyshev(r, c, er, ec)
                heapq.heappush(open_heap, (ng + h, ng, r, c, other))

    return None  # no path found


def _reconstruct(came_from, end_state):
    path = []
    state = end_state
    while state in came_from:
        path.append(state)
        state = came_from[state]
    path.append(state)
    path.reverse()
    return path
