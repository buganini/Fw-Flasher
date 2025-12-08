import sys
import os
import esptool

from .FwFlasher import UI

from .FwFlasher import VERSION as __version__

def main(argv=None):
    if argv is None:
        argv = sys.argv
    ui = UI()

    if len(argv) > 1:
        if argv[1] == "esptool":
            esptool.main(argv[2:])
            return
        else:
            ui.loadFile(argv[1])
    elif os.path.exists("manifest/manifest.json"):
        ui.loadFile("manifest/manifest.json")

    ui.run()

