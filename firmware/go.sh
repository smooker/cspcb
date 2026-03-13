#!/bin/bash
# go.sh — build, flash, capture, view
# Usage: go.sh [command]
#
# Commands:
#   build          Build firmware
#   flash          Build + flash via BMP GDB
#   capture        Capture mover+movel (asks before moving!)
#   view [file]    Open in pulseview with decoders
#   speed [file]   Generate speed analog channel + open
#   all            build + flash + capture + speed + view
#
# Examples:
#   go.sh build
#   go.sh flash
#   go.sh capture
#   go.sh view capture_both.sr
#   go.sh speed capture_both.sr
#   go.sh all

set -e
cd "$(dirname "$0")"
PROJ="$(dirname "$PWD")"
SPM=400

cmd_build() {
    echo "=== BUILD ==="
    make
}

cmd_flash() {
    cmd_build
    echo "=== FLASH ==="
    arm-none-eabi-gdb -batch \
        -ex "file build/stepper_sc.elf" \
        -ex "target extended-remote /dev/ttyBmpGdb" \
        -ex "monitor swdp_scan" \
        -ex "attach 1" \
        -ex "mem 0x40000000 0x50000000 rw" \
        -ex "load" \
        -ex "compare-sections" \
        -ex "detach"
    echo "Flash OK"
}

cmd_capture() {
    local SR="${PROJ}/capture_both.sr"
    echo "=== CAPTURE ==="
    echo "Will send: mover 5, then movel 5"
    read -p "Motor safe to move? [y/N] " yn
    [ "$yn" = "y" ] || [ "$yn" = "Y" ] || { echo "Aborted"; exit 1; }

    sigrok-cli -d fx2lafw -c samplerate=100K --channels D6,D7 --samples 600000 -o "$SR" &
    local PID=$!
    sleep 0.5
    echo "mover 5" > /dev/ttyACMTarg
    echo "  mover 5 sent"
    sleep 3
    echo "movel 5" > /dev/ttyACMTarg
    echo "  movel 5 sent"
    wait $PID
    echo "Capture done: $SR"
}

cmd_speed() {
    local SR="${1:-${PROJ}/capture_both.sr}"
    local OUT="${SR%.sr}_speed.sr"
    echo "=== SPEED ==="
    python3 - "$SR" "$OUT" "$SPM" << 'PYEOF'
import zipfile, struct, sys

sr_file, out_file, spm = sys.argv[1], sys.argv[2], float(sys.argv[3])
z = zipfile.ZipFile(sr_file)
chunks = sorted([f for f in z.namelist() if f.startswith('logic-1-')])
raw = b''.join(z.read(c) for c in chunks)
meta = z.read('metadata').decode()

# Parse samplerate from metadata
samplerate = 100000
for line in meta.split('\n'):
    if line.startswith('samplerate='):
        samplerate = int(line.split('=')[1].strip())

speed = [0.0] * len(raw)
prev_rising = None
prev_d7 = raw[0] & 0x80
current_speed = 0.0

for i in range(1, len(raw)):
    d7 = raw[i] & 0x80
    d6 = raw[i] & 0x40
    if d7 and not prev_d7:
        if prev_rising is not None:
            period = i - prev_rising
            freq = samplerate / period
            current_speed = freq / spm
            if not d6:
                current_speed = -current_speed
        prev_rising = i
    if prev_rising is not None and (i - prev_rising) > samplerate * 0.1:
        current_speed = 0.0
    speed[i] = current_speed
    prev_d7 = d7

speed_data = struct.pack(f'<{len(speed)}f', *speed)

new_meta = meta.rstrip() + '\n'
if 'total analog' not in new_meta:
    new_meta = new_meta.replace('unitsize=1', 'total analog=1\nanalog9=Speed mm/s\nunitsize=1')

CHUNK = 4 * 1024 * 1024
with zipfile.ZipFile(out_file, 'w', zipfile.ZIP_DEFLATED) as zout:
    zout.writestr('version', '2')
    zout.writestr('metadata', new_meta)
    for c in chunks:
        zout.writestr(c, z.read(c))
    n = 1
    off = 0
    while off < len(speed_data):
        zout.writestr(f'analog-1-9-{n}', speed_data[off:off+CHUNK])
        off += CHUNK
        n += 1

print(f"Speed range: {min(speed):.1f} to {max(speed):.1f} mm/s")
print(f"Written: {out_file}")
PYEOF
}

cmd_view() {
    local SR="${1:-${PROJ}/capture_both_speed.sr}"
    local PVS="${SR%.sr}.pvs"
    echo "=== VIEW ==="
    if [ ! -f "$PVS" ]; then
        echo "No .pvs found, opening raw"
        pulseview "$SR" &
    else
        pulseview "$SR" -s "$PVS" &
    fi
    echo "pulseview: $SR"
}

case "${1:-help}" in
    build)   cmd_build ;;
    flash)   cmd_flash ;;
    capture) cmd_capture ;;
    speed)   cmd_speed "$2" ;;
    view)    cmd_view "$2" ;;
    all)
        cmd_flash
        sleep 2
        cmd_capture
        cmd_speed "${PROJ}/capture_both.sr"
        cmd_view "${PROJ}/capture_both_speed.sr"
        ;;
    *)
        echo "Usage: go.sh {build|flash|capture|speed|view|all} [file]"
        ;;
esac
