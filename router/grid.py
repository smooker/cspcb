"""
grid.py — Board grid and obstacle map.

Two layers: 0=F.Cu, 1=B.Cu
Cell (row, col, layer) is blocked if copper/courtyard occupies it.
"""
import math
import numpy as np

# Layer indices
FCU = 0
BCU = 1
NLAYERS = 2

class Grid:
    def __init__(self, x0, y0, x1, y1, resolution=0.1):
        """
        x0,y0,x1,y1: board bounding box in mm
        resolution: cell size in mm
        """
        self.x0 = x0
        self.y0 = y0
        self.resolution = resolution
        self.cols = math.ceil((x1 - x0) / resolution) + 1
        self.rows = math.ceil((y1 - y0) / resolution) + 1

        # blocked[layer][row][col] = True if obstacle
        self.blocked = [
            np.zeros((self.rows, self.cols), dtype=bool)
            for _ in range(NLAYERS)
        ]

    def mm_to_cell(self, x, y):
        """Convert mm coords to (row, col)."""
        col = round((x - self.x0) / self.resolution)
        row = round((y - self.y0) / self.resolution)
        return row, col

    def cell_to_mm(self, row, col):
        """Convert (row, col) to mm coords (center of cell)."""
        x = self.x0 + col * self.resolution
        y = self.y0 + row * self.resolution
        return x, y

    def in_bounds(self, row, col):
        return 0 <= row < self.rows and 0 <= col < self.cols

    def is_blocked(self, row, col, layer):
        if not self.in_bounds(row, col):
            return True
        return self.blocked[layer][row, col]

    def block_rect(self, x0, y0, x1, y1, layer, inflate=0.0):
        """Block all cells within the rectangle (mm), inflated by inflate mm."""
        bx0 = x0 - inflate
        by0 = y0 - inflate
        bx1 = x1 + inflate
        by1 = y1 + inflate

        c0 = max(0, math.floor((bx0 - self.x0) / self.resolution))
        r0 = max(0, math.floor((by0 - self.y0) / self.resolution))
        c1 = min(self.cols - 1, math.ceil((bx1 - self.x0) / self.resolution))
        r1 = min(self.rows - 1, math.ceil((by1 - self.y0) / self.resolution))

        if layer == 'both':
            for l in range(NLAYERS):
                self.blocked[l][r0:r1+1, c0:c1+1] = True
        else:
            self.blocked[layer][r0:r1+1, c0:c1+1] = True

    def block_segment(self, x0, y0, x1, y1, width, layer, inflate=0.0):
        """Block cells along a line segment with given width + inflate."""
        half = width / 2 + inflate
        dx = x1 - x0
        dy = y1 - y0
        length = math.sqrt(dx*dx + dy*dy)
        if length < 1e-9:
            self.block_rect(x0-half, y0-half, x0+half, y0+half, layer)
            return

        # Bounding box of the segment + half-width
        bx0 = min(x0, x1) - half
        by0 = min(y0, y1) - half
        bx1 = max(x0, x1) + half
        by1 = max(y0, y1) + half

        c0 = max(0, math.floor((bx0 - self.x0) / self.resolution))
        r0 = max(0, math.floor((by0 - self.y0) / self.resolution))
        c1 = min(self.cols - 1, math.ceil((bx1 - self.x0) / self.resolution))
        r1 = min(self.rows - 1, math.ceil((by1 - self.y0) / self.resolution))

        nx = -dy / length
        ny = dx / length

        lay = [layer] if layer != 'both' else list(range(NLAYERS))
        for r in range(r0, r1+1):
            for c in range(c0, c1+1):
                cx, cy = self.cell_to_mm(r, c)
                # Project onto segment
                t = ((cx-x0)*dx + (cy-y0)*dy) / (length*length)
                t = max(0.0, min(1.0, t))
                px = x0 + t*dx
                py = y0 + t*dy
                dist = math.sqrt((cx-px)**2 + (cy-py)**2)
                if dist <= half:
                    for l in lay:
                        self.blocked[l][r, c] = True

    def unblock_cell(self, row, col, layer):
        """Unblock a specific cell (use for pad targets)."""
        if self.in_bounds(row, col):
            self.blocked[layer][row, col] = False
