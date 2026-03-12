dashboard -style discard_scrollback False
#set mi-async on
#set mem inaccessible-by-default off
#target extended-remote /dev/ttyBmpGdb
#monitor swdp_scan
#attach 1
#monitor traceswo
stop

#file ./build/prom_emulation.elf
#load ./build/prom_emulation.hex
set remote exec-file ./build/stepper.elf
#stop
#compare-sections

#dump binary memory result.bin 0x0801f800 0x0801ffff
#x/2048x 0x0801f800
#hbreak main
#next
#watch huart
#watch data[0]
#run

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
