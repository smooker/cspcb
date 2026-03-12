set remote exec-file ./build/stepper.elf

define ld
file ./build/stepper.elf
load ./build/stepper.hex
set remote exec-file ./build/stepper.elf
compare-sections
end

define ag
dashboard -style discard_scrollback False
set mi-async on
set mem inaccessible-by-default off
target extended-remote /dev/ttyBmpGdb
monitor swdp_scan
attach 1
monitor traceswo
end
