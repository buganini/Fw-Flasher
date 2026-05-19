import sys
import os
import esptool

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
        if args[0] == "pyocd":
            sys.argv.pop(0)
            from pyocd import __main__ as pyocd_main
            pyocd_main.main()
            return
        else:
            ui.loadFile(args[0])
    elif os.path.exists("manifest/manifest.json"):
        ui.loadFile("manifest/manifest.json")

    ui.run()
