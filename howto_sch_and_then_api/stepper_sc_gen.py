#!/usr/bin/env python3
"""
stepper_sc_gen.py — Generate stepper.kicad_sch from stepper.net
Uses kicad-sch-api. No hand-rolled S-expressions.

Key design choices:
  - Pin lookup validates against actual library pin names
  - Power nets → power symbols + wire_to_pin at each pin
  - Small signal nets (≤3 nodes) → direct wires between pins
  - Larger signal nets → net labels at each pin
  - PWR_FLAG co-located with first power symbol on each rail
  - Functional layout: power / PUL buffer / DIR buffer / terminals / BP headers
"""

import sys, os, re

# ── venv bootstrap ──────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
VENV_LIB = os.path.join(HERE, '..', 'venv', 'lib')
pyver = next(d for d in os.listdir(VENV_LIB) if d.startswith('python'))
sys.path.insert(0, os.path.join(VENV_LIB, pyver, 'site-packages'))

import math
import kicad_sch_api as ksa

# ── lib_id map: (netlist lib, part) → available KiCad symbol ────────────────
LIB_ID_MAP = {
    ("Regulator_Linear", "L78M05_TO252"):  "Regulator_Linear:LM78M05_TO252",
    ("Device",           "C_Polarized"):   "Device:C_Polarized",
    ("Device",           "C"):             "Device:C",
    ("Device",           "R"):             "Device:R",
    ("Device",           "Q_NPN"):         "Device:Q_NPN",
    ("Connector",        "Conn_01x02_Screw"): "Connector:Conn_01x02_Pin",
    ("Connector",        "Conn_01x20"):    "Connector:Conn_01x20_Pin",
}

# ── power net → symbol ──────────────────────────────────────────────────────
POWER_SYM = {
    "+24V":  "power:+24V",
    "+5V":   "power:+5V",
    "GND":   "power:GND",
    "+3.3V": "power:+3.3V",
}

POWER_NET_RE = re.compile(
    r'^(\+[\d.]+V|\+3\.3V|\+5V|\+24V|GND|VCC|VDD)$', re.I)

# ── functional layout (mm, snapped to 2.54 grid) ───────────────────────────
# Row 1 y=25:  power supply
# Row 2 y=80:  PUL NPN buffer
# Row 3 y=130: DIR NPN buffer
# Row 4 y=180: signal terminals
# Right side:  Black Pill headers (tall, 20 pins)

_DY = 12.7  # global Y offset from sheet top border

POSITIONS = {
    # Power supply
    "J1":   ( 25.4,  25.4 + _DY),
    "C1":   ( 60.96, 25.4 + _DY),
    "C2":   ( 76.2,  25.4 + _DY),
    "U1":   ( 96.52, 25.4 + _DY),
    "C3":   (116.84, 25.4 + _DY),
    "C4":   (132.08, 25.4 + _DY),
    "C5":   (147.32, 25.4 + _DY),

    # PUL NPN buffer
    "R1":   ( 25.4,  76.2 + _DY),
    "R2":   ( 50.8,  76.2 + _DY),
    "Q1":   ( 76.2,  76.2 + _DY),
    "J2":   (101.6,  76.2 + _DY),

    # DIR NPN buffer  (new netlist: R3=1k-base, R4=10k-bgnd)
    "R3":   ( 25.4, 108.0 + _DY),
    "R4":   ( 50.8, 108.0 + _DY),
    "Q2":   ( 76.2, 108.0 + _DY),
    "J3":   (101.6, 108.0 + _DY),

    # Signal terminals (row)
    "J4":   ( 25.4, 140.0 + _DY),
    "J5":   ( 50.8, 140.0 + _DY),
    "J6":   ( 76.2, 140.0 + _DY),
    "J7":   (101.6, 140.0 + _DY),
    "J8":   (127.0, 140.0 + _DY),
    "J9":   (152.4, 140.0 + _DY),
    "J10":  (177.8, 140.0 + _DY),

    # Black Pill headers (right side)
    "J11":  (215.9,  25.4 + _DY),
    "J12":  (254.0,  25.4 + _DY),
}

# ── netlist parser ──────────────────────────────────────────────────────────

def parse_netlist(path):
    with open(path) as f:
        txt = f.read()

    comps = []
    for m in re.finditer(
            r'\(comp\s+\(ref\s+"([^"]+)"\)(.*?)\n    \)', txt, re.DOTALL):
        ref, body = m.group(1), m.group(2)
        val = re.search(r'\(value\s+"([^"]+)"', body)
        fp  = re.search(r'\(footprint\s+"([^"]+)"', body)
        ls  = re.search(r'\(libsource\s+\(lib\s+"([^"]+)"\)\s+\(part\s+"([^"]+)"\)', body)
        comps.append({
            "ref": ref,
            "value": val.group(1) if val else "",
            "footprint": fp.group(1) if fp else "",
            "lib": ls.group(1) if ls else "",
            "part": ls.group(2) if ls else "",
        })

    nets = []
    for m in re.finditer(
            r'\(net\s+\(code\s+"(\d+)"\)\s+\(name\s+"([^"]*)"\)(.*?)\n    \)',
            txt, re.DOTALL):
        nodes = []
        for n in re.finditer(
                r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)'
                r'\s+\(pinfunction\s+"([^"]*)"\)',
                m.group(3)):
            nodes.append({
                "ref": n.group(1),
                "pin": n.group(2),
                "pinfunc": n.group(3),
            })
        nets.append({"name": m.group(2), "nodes": nodes})

    return comps, nets


# ── main ────────────────────────────────────────────────────────────────────

def main():
    net_path = os.path.join(HERE, "stepper_sc.net")
    out_path = os.path.join(HERE, "stepper_sc.kicad_sch")

    comps, nets = parse_netlist(net_path)
    print(f"Parsed: {len(comps)} components, {len(nets)} nets")

    # ── load symbol libraries ───────────────────────────────────────────────
    SYM_DIR = os.path.join(HERE, '..', 'kicad_sym')
    cache = ksa.get_symbol_cache()
    for lib in ("Device", "Connector", "Regulator_Linear", "power"):
        cache.add_library_path(os.path.join(SYM_DIR, f"{lib}.kicad_sym"))

    sch = ksa.create_schematic("stepper")

    # ── ref remapping (KiCad requires refs to end in a digit) ──────────────
    REF_REMAP = {"J11A": "J11", "J11B": "J12"}

    # ── place components ───────────────────────────────────────────────────
    placed = set()
    for c in comps:
        ref_orig = c["ref"]
        ref      = REF_REMAP.get(ref_orig, ref_orig)
        lib_id = LIB_ID_MAP.get((c["lib"], c["part"]))
        if not lib_id:
            print(f"  SKIP {ref}: no lib_id for {c['lib']}:{c['part']}")
            continue
        pos = POSITIONS.get(ref)
        if not pos:
            print(f"  SKIP {ref}: no position defined")
            continue
        try:
            sch.components.add(
                lib_id=lib_id,
                reference=ref,
                value=c["value"],
                position=pos,
                footprint=c["footprint"],
            )
            placed.add(ref)
            print(f"  + {ref:6s}  {lib_id}")
        except Exception as e:
            print(f"  WARN {ref}: {e}")

    # ── build valid pin name set per ref (from actual library) ─────────────
    valid_pins = {}
    for ref in placed:
        try:
            valid_pins[ref] = {str(pname) for pname, _ in sch.list_component_pins(ref)}
        except Exception:
            valid_pins[ref] = set()

    def resolve_pin(node):
        """Return the pin name kicad-sch-api actually knows for this node."""
        ref = node["ref"]
        vp  = valid_pins.get(ref, set())
        pf  = node["pinfunc"]
        num = node["pin"]
        if pf and pf in vp:
            return pf
        if num in vp:
            return num
        return pf  # last resort

    # Nets driven by a power_out pin — no PWR_FLAG needed
    NO_PWR_FLAG = {"+5V"}

    GRID = 2.54
    PWR_OFFSET = 5.08   # mm to push power symbol outward from pin endpoint

    # Connectors with many pins in a line — use fixed X column per net type
    # so symbols don't drift diagonally and form clean vertical columns
    CONNECTOR_REFS = {"J11", "J12"}
    PWR_COL_OFFSET = {
        "+24V":   5.08,
        "+5V":   10.16,
        "GND":   15.24,
        "+3.3V": 20.32,
    }

    def snap(v):
        return round(v / GRID) * GRID

    def outward_pos(ref, pin_pos):
        """Offset power symbol outward from component body along pin direction."""
        center = POSITIONS.get(ref)
        if not center:
            return (snap(pin_pos.x + PWR_OFFSET), snap(pin_pos.y))
        dx = pin_pos.x - center[0]
        dy = pin_pos.y - center[1]
        length = math.sqrt(dx*dx + dy*dy)
        if length < 0.01:
            return (snap(pin_pos.x + PWR_OFFSET), snap(pin_pos.y))
        nx, ny = dx / length, dy / length
        return (snap(pin_pos.x + nx * PWR_OFFSET),
                snap(pin_pos.y + ny * PWR_OFFSET))

    def connector_pwr_pos(ref, net_name, pin_pos):
        """Fixed X column per net type for multi-pin connectors (J11/J12).
        GND goes down (max Y pin + extra drop), PWR goes up (min Y pin)."""
        col = PWR_COL_OFFSET.get(net_name, 5.08)
        center = POSITIONS.get(ref)
        if center and pin_pos.x < center[0]:
            col = -col  # pins on left side → symbols go further left
        # GND: drop below pin (+Y); positive rails: rise above pin (-Y)
        if net_name == "GND":
            y = snap(pin_pos.y + PWR_OFFSET)
        else:
            y = snap(pin_pos.y - PWR_OFFSET)
        return (snap(pin_pos.x + col), y)

    def power_sym_pos(ref, net_name, pin_pos):
        if ref in CONNECTOR_REFS:
            return connector_pwr_pos(ref, net_name, pin_pos)
        return outward_pos(ref, pin_pos)

    # ── wire nets ──────────────────────────────────────────────────────────
    pwr_seq = [0]
    first_pwr_pos = {}   # net_name → sym_pos of first power symbol placed
    first_pwr_dir = {}   # net_name → unit vector (dx,dy) from pin toward symbol

    for net in nets:
        name  = net["name"]
        nodes = [{**n, "ref": REF_REMAP.get(n["ref"], n["ref"])} for n in net["nodes"]
                 if REF_REMAP.get(n["ref"], n["ref"]) in placed]
        if not nodes:
            continue

        is_power = bool(POWER_NET_RE.match(name))
        pwr_sym  = POWER_SYM.get(name) if is_power else None

        # small signal nets → direct wires
        if not is_power and len(nodes) <= 3:
            try:
                for i in range(len(nodes) - 1):
                    sch.add_wire_between_pins(
                        nodes[i]["ref"],   nodes[i]["pin"],
                        nodes[i+1]["ref"], nodes[i+1]["pin"],
                    )
                continue
            except Exception as e:
                print(f"  WARN wire {name}: {e} — falling back to labels")

        for node in nodes:
            pid = resolve_pin(node)
            try:
                pin_pos = sch.get_component_pin_position(node["ref"], pid)
            except Exception as e:
                print(f"  WARN pin_pos {node['ref']}.{pid}: {e}")
                continue
            if not pin_pos:
                print(f"  WARN no pin_pos for {node['ref']}.{pid}")
                continue

            if pwr_sym:
                pwr_seq[0] += 1
                sym_pos = power_sym_pos(node["ref"], name, pin_pos)
                try:
                    sch.components.add(
                        lib_id=pwr_sym,
                        reference=f"#PWR{pwr_seq[0]:03d}",
                        value=name,
                        position=sym_pos,
                    )
                    # orthogonal only: L-shape if both X and Y differ
                    px, py = pin_pos.x, pin_pos.y
                    sx, sy = sym_pos
                    if abs(px - sx) > 0.01 and abs(py - sy) > 0.01:
                        sch.add_wire((px, py), (sx, py))  # horizontal
                        sch.add_wire((sx, py), (sx, sy))  # vertical
                    else:
                        sch.add_wire((px, py), (sx, sy))
                    if name not in first_pwr_pos:
                        first_pwr_pos[name] = sym_pos
                        dx = sym_pos[0] - pin_pos.x
                        dy = sym_pos[1] - pin_pos.y
                        length = math.sqrt(dx*dx + dy*dy)
                        first_pwr_dir[name] = (dx/length, dy/length) if length > 0.01 else (1.0, 0.0)
                except Exception as e:
                    print(f"  WARN pwr {name} at {node['ref']}.{pid}: {e}")
            else:
                try:
                    sch.add_label(name, position=(pin_pos.x, pin_pos.y))
                except Exception as e:
                    print(f"  WARN label {name} at {node['ref']}.{pid}: {e}")

    # ── PWR_FLAG offset +X from first power symbol, wired to it ────────────
    for net_name, pos in first_pwr_pos.items():
        if net_name in NO_PWR_FLAG:
            continue
        pwr_seq[0] += 1
        pf_pos = (snap(pos[0] + PWR_OFFSET), snap(pos[1]))
        try:
            sch.components.add(
                lib_id="power:PWR_FLAG",
                reference=f"#PWR{pwr_seq[0]:03d}",
                value="PWR_FLAG",
                position=pf_pos,
            )
            sch.add_wire(pos, pf_pos)
            print(f"  PWR_FLAG @ {net_name}  {pos} → {pf_pos}")
        except Exception as e:
            print(f"  WARN PWR_FLAG {net_name}: {e}")

    # ── no-connect unused pins ─────────────────────────────────────────────
    connected = set()
    for net in nets:
        for node in net["nodes"]:
            ref = REF_REMAP.get(node["ref"], node["ref"])
            connected.add((ref, resolve_pin({**node, "ref": ref})))
            connected.add((ref, node["pin"]))

    nc = 0
    for ref in placed:
        try:
            for pname, ppos in sch.list_component_pins(ref):
                if (ref, str(pname)) not in connected:
                    sch.no_connects.add(position=(ppos.x, ppos.y))
                    nc += 1
        except Exception as e:
            print(f"  WARN nc {ref}: {e}")

    print(f"No-connects: {nc}")
    sch.save(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
