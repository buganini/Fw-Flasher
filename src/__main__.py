import sys
import os
import esptool

from .FwFlasher import UI

ui = UI()

if len(sys.argv) > 1:
    if sys.argv[1] == "esptool":
        esptool.main(sys.argv[2:])
        sys.exit(0)
    else:
        ui.loadFile(sys.argv[1])
elif os.path.exists("manifest/manifest.json"):
    ui.loadFile("manifest/manifest.json")

ui.run()

