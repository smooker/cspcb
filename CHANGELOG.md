# stepper_sc — CHANGELOG

---

## [2026-03-07] session 3 — kipy footprint placement breakthrough

### Milestone: All 24 footprints properly placed via kipy IPC

**The bug:** `fp.proto.position.x_nm = value` bypasses the Python property setter.
In KiCad 9, footprint children (pads, silkscreen, courtyard) store **absolute** coordinates.
The property setter applies a delta to ALL children — bypassing it only moves the anchor `+` marker,
leaving pads and outlines at the original location. PCBnew showed floating `+` crosses inside the
board while the actual component bodies remained scattered outside at random coordinates.

**The fix:** Use the property setters:
```python
fp.position    = Vector2.from_xy_mm(x_mm, y_mm)   # moves anchor + all children
fp.orientation = Angle.from_degrees(rot)            # rotates all children around fp center
```

**Result:** `pcb_place.py` ran cleanly — all 24 footprints snapped to their design positions
inside the 90×120mm board outline. PCBnew live-refreshed and showed a real, populated board.

### Fixed
- `stepper_sc/pcb_place.py` — replaced direct proto field writes with property setters
- `stepper_sc/demo_orbit.py` — same fix; also reads `fp.position`/`fp.orientation` via property

### kipy API note
- `Vector2.from_xy_mm(x, y)` — NOT `from_mm` (added in kipy 0.3.0 as `from_xy_mm`)
- `Angle.from_degrees(deg)` — correct class method

---

## [2026-03-07] session 2 — PCB placement + KiCad 9.0.6 live IPC

### Milestone: KiCad 9.0.6 live IPC repaint confirmed working
- KiCad 9.0.2: `view.redraw` via external IPC did **not** force repaint — footprints
  moved in data but PCBnew viewport stayed static.
- KiCad 9.0.6 (emerged today): **full live repaint works** — `demo_orbit.py` animates
  footprints in real time from an external Python script over the IPC socket.

### Added
- `stepper_sc/pcb_place.py` — places all 24 footprints via kipy IPC API
  - Groups: power (J1, U1, C1–C5), PULSE buffer (R1, R2, Q1, J2),
    DIR buffer (R3, R4, Q2, J3), signal terminals (J4–J10, left edge, rot=90°),
    Black Pill headers (J11, J12)
  - Runs from chroot; KiCad must have IPC API enabled

- `stepper_sc/pcb_edge.py` — draws 90×120mm Edge.Cuts board outline via IPC
  - Corners: (25, 25) → (115, 145) mm
  - Uses `seg.proto.shape.segment.{start,end}.{x,y}_nm` proto structure
    (not `seg.proto.{start,end}` — important proto layout detail)

- `stepper_sc/demo_orbit.py` — live IPC demo: orbits first footprint in a circle
  - 15mm radius, 60 steps, 0.05s delay (~3s/orbit)
  - Restores original position on KeyboardInterrupt
  - Confirmed working in KiCad 9.0.6

### Repository
- GitHub: `git@github.com:smooker/cspcb.git`
- `firmware/PyCortexMDebug` added as git submodule
- `firmware/STM32F411.svd` tracked in git
- `.gitignore` covers build artefacts, KiCad temporaries, venv

---

## [2026-03-07] session 1 — schematic generation

### Added
- `fw_to_net.py` — parses `firmware/Core/Inc/main.h` GPIO defines → KiCad Format-E netlist
  - Output: `howto_sch_and_then_api/stepper_sc.net`
  - 24 components, 17 nets
  - PULSE/DIR signals → `output_npn` template (R_base + R_bgnd + Q + J_out)
  - All other signals → `input_direct` (J connector only)

- `howto_sch_and_then_api/stepper_sc_gen.py` — netlist → `stepper_sc.kicad_sch`
  - Grid layout with power symbols and no-connects
  - ERC: clean (0 errors, 0 warnings)

- `howto_sch_and_then_api/stepper_sc.net` — generated netlist (committed)
- `stepper_sc/stepper_sc.kicad_sch` — generated schematic (committed)
- `stepper_sc/stepper_sc.kicad_pro` — KiCad project file
