import sys
import os
import esptool
from .py_ocd import sequencer as pyocd_sequencer
from .openocd import openocd_exec
from .dfu import dfu_util_exec

from .FwFlasher import UI

from .FwFlasher import VERSION as __version__

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    ui = UI()

    if len(args) > 0:
        if args[0] == "esptool":
            esptool.main(args[1:])
            return
        if args[0] == "openocd":
            openocd_exec(args[1:])
            return
        if args[0] == "dfu-util":
            dfu_util_exec(args[1:])
            return
        if args[0] == "pyocd":
            sys.argv.pop(0)
            from pyocd import __main__ as pyocd_main
            pyocd_main.main()
            return
        if args[0] == "pyocd_seq":
            port = args[1]
            target = args[2]
            frequency = int(args[3])
            seq = args[4:]
            pyocd_sequencer(port, target, frequency, seq)
            return
        ui.loadFile(args[0])
    elif os.path.exists("manifest/manifest.json"):
        ui.loadFile("manifest/manifest.json")

    ui.run()
