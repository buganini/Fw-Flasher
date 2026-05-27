import sys
import os
import esptool
from .py_ocd import sequencer as pyocd_sequencer
from .openocd import openocd_exec

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
        if args[0] == "pyocd":
            sub = args[1]
            if sub == "exec":
                sys.argv.pop(0)
                sys.argv.pop(0)
                from pyocd import __main__ as pyocd_main
                pyocd_main.main()
            elif sub == "cmd":
                port = args[2]
                target = args[3]
                frequency = int(args[4])
                seq = args[5:]
                pyocd_sequencer(port, target, frequency, seq)

            return
        ui.loadFile(args[0])
    elif os.path.exists("manifest/manifest.json"):
        ui.loadFile("manifest/manifest.json")

    ui.run()
