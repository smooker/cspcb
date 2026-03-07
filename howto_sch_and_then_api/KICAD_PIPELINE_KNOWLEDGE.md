# KiCad Schematic Generation Pipeline — Knowledge Base
> Captured from a real working session. Pass this to any Claude to bootstrap KiCad schematic automation.

---

## 1. The Library to Use

**kicad-sch-api** — do NOT hand-roll S-expressions. Ever.

```bash
pip install kicad-sch-api
```

- Repo: https://github.com/circuit-synth/kicad-sch-api
- Docs: https://github.com/circuit-synth/kicad-sch-api/blob/main/docs/GETTING_STARTED.md
- API Reference: https://github.com/circuit-synth/kicad-sch-api/blob/main/docs/API_REFERENCE.md

---

## 2. Core API — What Actually Works

### Create / Load / Save
```python
import kicad_sch_api as ksa
from kicad_sch_api.core.component_bounds import get_component_bounding_box

sch = ksa.create_schematic("title")
sch = ksa.load_schematic("file.kicad_sch")
sch.save("output.kicad_sch")
```

### Add Components
```python
comp = sch.components.add(
    lib_id="Device:R",
    reference="R1",
    value="10k",
    position=(100.0, 100.0),
    footprint="Resistor_SMD:R_0805_2012Metric"
)
```
- `reference` for power symbols MUST be `#PWRnnn` format (e.g. `#PWR001`)
- Use a global counter to generate unique `#PWRnnn` refs

### Get a Component Object
```python
comp = sch.components.get("R1")   # returns component object, not position
```

### List All Components
```python
for comp in sch.components:
    print(comp.reference, comp.lib_id, comp.position)  # position is a Point object
```

### Pin Positions
```python
pos = sch.get_component_pin_position("R1", "1")
# Returns Point object — use pos.x, pos.y  (NOT pos[0], pos[1])
```

### List Component Pins
```python
pins = sch.list_component_pins("R1")
# Returns list of (pin_name, Point) tuples — NOT (number, name, type)
# pin_name is the name string e.g. "B", "C", "E", "1", "2"
# Point has .x and .y attributes
for pin_name, pin_point in pins:
    print(pin_name, pin_point.x, pin_point.y)
```

### Wiring
```python
# Direct wire between two pins
sch.add_wire_between_pins("R1", "2", "R2", "1")

# Wire from a position to a pin
sch.add_wire_to_pin((x, y), "R1", "1")

# Net label at a position
sch.add_label("NET_NAME", position=(x, y))
```

### No-Connect Markers
```python
# NOT: sch.add_no_connect(...)  — this method does NOT exist
# CORRECT:
sch.no_connects.add(position=(x, y))
```

### Bounding Box
```python
from kicad_sch_api.core.component_bounds import get_component_bounding_box

comp = sch.components.get("R1")           # get the object first
bbox = get_component_bounding_box(comp, include_properties=False)
print(bbox.width, bbox.height)            # in mm
```
- Pass the **component object**, NOT the reference string
- `include_properties=False` gives the symbol body only

---

## 3. Coordinate System — CRITICAL

- **+Y is DOWN** in schematic space (screen coordinates)
- **+X is RIGHT** (normal)
- Grid is **1.27mm (50 mil)** — all positions must snap to grid
- Common grid values: 0, 1.27, 2.54, 3.81, 5.08, 6.35, 7.62...

```python
GRID = 2.54
x = round(x / GRID) * GRID   # snap to grid
```

---

## 4. Power Symbols

Place actual `power:GND`, `power:+5V` etc. symbols at each pin — do NOT just add labels for power nets.

```python
POWER_SYMBOL_MAP = {
    "GND":   "power:GND",
    "+5V":   "power:+5V",
    "+24V":  "power:+24V",
    "+3.3V": "power:+3.3V",
    "VCC":   "power:VCC",
}

pwr_seq = [0]   # global counter

def place_power_symbol(sch, net_name, host_ref, pin_num, pwr_seq):
    pwr_sym = POWER_SYMBOL_MAP.get(net_name)
    if not pwr_sym:
        return
    pin_pos = sch.get_component_pin_position(host_ref, pin_num)
    if not pin_pos:
        return

    # Offset symbol by host component width to avoid overlap
    host = sch.components.get(host_ref)
    offset_x = 0
    if host:
        try:
            bb = get_component_bounding_box(host, include_properties=False)
            offset_x = bb.width
        except Exception:
            offset_x = 2.54  # fallback

    pwr_seq[0] += 1
    sch.components.add(
        lib_id=pwr_sym,
        reference=f"#PWR{pwr_seq[0]:03d}",
        value=net_name,
        position=(pin_pos.x + offset_x, pin_pos.y),
    )
    sch.add_wire_to_pin((pin_pos.x + offset_x, pin_pos.y), host_ref, pin_num)
```

---

## 5. No-Connect Audit

After placing and wiring everything, mark all unconnected pins:

```python
# Build set of connected (ref, pin) pairs from netlist
connected = set()
for net in nets:
    for node in net["nodes"]:
        connected.add((node["ref"], node["pin"]))

# Place no_connect markers on unconnected pins
for ref in placed:
    pins = sch.list_component_pins(ref)   # [(pin_name, Point), ...]
    for pin_name, pin_point in pins:
        if (ref, str(pin_name)) not in connected:
            sch.no_connects.add(position=(pin_point.x, pin_point.y))
```

---

## 6. KiCad Netlist Format (.net)

Format-E netlist exported by Eeschema. Key fields:

```scheme
(components
  (comp (ref "Q1")
    (value "BC547")
    (footprint "Package_TO_SOT_THT:TO-92_Inline")
    (libsource (lib "Device") (part "Q_NPN"))
  )
)
(nets
  (net (code "5") (name "NET_BASE")
    (node (ref "R1") (pin "2") (pinfunction "~") (pintype "passive"))
    (node (ref "Q1") (pin "1") (pinfunction "B") (pintype "input"))
  )
)
```

### Parsing pin references
- `(pin "1")` is the pin **number** used by the netlist
- `(pinfunction "B")` is the pin **name** in the symbol
- When a symbol uses named pins (B/C/E), the netlist may use numbers (1/2/3)
- **Fix: patch the .net file directly** — replace `(pin "1")` with `(pin "B")` etc.
- Or fix at the source: substitute the part name in the netlist to match installed symbol

### Fixing part names in netlist
```bash
# Replace Q_NPN_BCE (not in your KiCad) with Q_NPN (which is)
sed -i 's/(part "Q_NPN_BCE")/(part "Q_NPN")/g' stepper.net

# Fix pin numbers to match symbol pin names
python3 - << 'PY'
import re
with open('stepper.net', 'r') as f:
    content = f.read()
# For Q1/Q2: replace numeric pin refs with pinfunction names
def replace_pin(m):
    ref, pin_num, pinfunc, pintype = m.group(1), m.group(2), m.group(3), m.group(4)
    if pinfunc and not re.match(r'^(~|Pin_\d+)$', pinfunc):
        return f'(node (ref "{ref}")   (pin "{pinfunc}")  (pinfunction "{pinfunc}")      (pintype "{pintype}"))'
    return m.group(0)
pattern = re.compile(r'\(node \(ref "(Q[12])"\)\s+\(pin "(\d+)"\)\s+\(pinfunction "([^"]*)"\)\s+\(pintype "([^"]*)"\)\)')
content = pattern.sub(replace_pin, content)
with open('stepper.net', 'w') as f:
    f.write(content)
PY
```

---

## 7. Symbol Library Substitution

When netlist lib_ids don't match your KiCad install:

```python
LIB_ID_MAP = {
    ("Device", "Q_NPN_BCE"):   "Device:Q_NPN",
    ("Device", "Q_NPN_BEC"):   "Device:Q_NPN",
    ("Connector", "Conn_01x02_Screw"): "Connector:Conn_01x02_Pin",
}

FALLBACK_CHAIN = [
    (re.compile(r'Q_NPN', re.I), "Device:Q_NPN"),
    (re.compile(r'Q_PNP', re.I), "Device:Q_PNP"),
    (re.compile(r'Conn_01x02', re.I), "Connector:Conn_01x02_Pin"),
]

def resolve_lib_id(lib, part):
    exact = LIB_ID_MAP.get((lib, part))
    if exact:
        return exact
    for pattern, fallback in FALLBACK_CHAIN:
        if pattern.search(part):
            return fallback
    return f"{lib}:{part}"  # best guess passthrough
```

### Check what's actually in your KiCad install
```bash
# List all NPN symbols
grep 'symbol "Q' /usr/share/kicad/symbols/Device.kicad_sym | grep -v '_[0-9]_[0-9]'

# Get pin names for a specific symbol
awk '/\(symbol "Q_NPN"/{found=1} found{print} found && /^\t\)/{exit}' \
  /usr/share/kicad/symbols/Device.kicad_sym | grep -A 3 '(pin '

# Find available footprints
find /usr/share/kicad/footprints -name "*1x02*"
```

---

## 8. Footprint Pitfalls

- Footprint strings must match **exactly** what's in your KiCad install
- `Connector_PinHeader_2.54mm:Conn_01x02_Pin` may NOT exist — check first
- Use `find /usr/share/kicad/footprints` to verify
- Format: `LibraryName:FootprintName` (no `.pretty`, no `.kicad_mod`)

---

## 9. Layout Strategy

Simple flat grid — works well for netlists up to ~30 components:

```python
COLS   = 5       # components per row
STEP_X = 50.0    # mm between columns
STEP_Y = 20.0    # mm between rows
START_X = 30.0
START_Y = 30.0

def assign_positions(components):
    positions = {}
    for idx, comp in enumerate(components):
        col = idx % COLS
        row = idx // COLS
        x = round((START_X + col * STEP_X) / GRID) * GRID
        y = round((START_Y + row * STEP_Y) / GRID) * GRID
        positions[comp["ref"]] = (x, y)
    return positions
```

---

## 10. Net Wiring Strategy

```python
def should_wire_directly(net):
    """Wire directly for small local nets, labels for everything else."""
    nodes = net["nodes"]
    if len(nodes) < 2 or len(nodes) > 3:
        return False
    if POWER_NET_RE.match(net["name"]):
        return False
    return True
```

- **2-3 node non-power nets** → `add_wire_between_pins()` direct wires
- **Power nets** → power symbols at each pin
- **Everything else** → net labels via `add_label()`

---

## 11. Golden Rules

1. **Read the docs BEFORE writing code** — the README has working examples
2. **Fix the data at the source** — patch the .net file rather than remapping at runtime
3. **Never hand-roll S-expressions** — use kicad-sch-api
4. **Pin names vs pin numbers** — always verify which one your symbol uses
5. **Bounding box needs the object** — `sch.components.get("R1")`, then `get_component_bounding_box(comp)`
6. **No-connect is a collection** — `sch.no_connects.add(position=...)` not `sch.add_no_connect(...)`
7. **Power refs are `#PWRnnn`** — use a global counter, never construct from net/pin names
8. **Point objects** — `pos.x` and `pos.y`, never `pos[0]` and `pos[1]`
9. **Footprints** — verify they exist in your install before using them
10. **Zero warnings, zero errors in PCBNew** — that's the milestone

---

## 12. Complete Working Pipeline

```
stepper.net  →  netlist_to_schematic.py  →  stepper.kicad_sch
                                         ↓
                              26 components placed
                              17 nets wired
                              4 power nets with symbols
                              25 no-connect markers
                              0 ERC errors in PCBNew
```

Files in this milestone:
- `netlist_to_schematic.py` — main converter
- `place_random_parts.py` — random wired circuit generator  
- `rearrange.py` — grid layout tool for existing schematics
- `stepper.net` — patched netlist (Q_NPN fixed, correct footprints)
