#!/bin/bash
mv ~/Downloads/netlist_to_schematic.py .
chmod +x ./netlist_to_schematic.py
./netlist_to_schematic.py stepper.net
eeschema ./stepper.kicad_sch
