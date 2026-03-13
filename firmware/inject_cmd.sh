#!/bin/bash
# Inject a command string into firmware's CDC RX ring buffer via GDB
# Usage: ./inject_cmd.sh "mover 1"
# Appends CR (0x0D) so firmware processes it as KEY_ENTER.

CMD="$1"
if [ -z "$CMD" ]; then
    echo "Usage: $0 \"command\""
    exit 1
fi

# Build GDB script: read rxHead, write each byte, update rxHead
TMPGDB=$(mktemp /tmp/gdb_inject.XXXXXX)

cat > "$TMPGDB" <<'HEADER'
set $h = rxHead
set $buf = (uint8_t *)&UserRxBufferFS
HEADER

# Write each command byte
for (( i=0; i<${#CMD}; i++ )); do
    BYTE=$(printf '%d' "'${CMD:$i:1}")
    echo "set \$buf[\$h] = $BYTE" >> "$TMPGDB"
    echo "set \$h = (\$h + 1) % 512" >> "$TMPGDB"
done

# Append CR (0x0D) for KEY_ENTER
cat >> "$TMPGDB" <<'FOOTER'
set $buf[$h] = 13
set $h = ($h + 1) % 512
set rxHead = $h
detach
FOOTER

arm-none-eabi-gdb -nx -batch \
  -ex "set mem inaccessible-by-default off" \
  -ex "target extended-remote /dev/ttyACM0" \
  -ex "monitor swdp_scan" \
  -ex "attach 1" \
  -ex "file ./build/stepper_sc.elf" \
  -x "$TMPGDB" \
  2>&1 | grep -v "^Python\|^arm-none\|^Could not\|^Limited\|^Suggest\|warning:\|^$"

rm -f "$TMPGDB"
