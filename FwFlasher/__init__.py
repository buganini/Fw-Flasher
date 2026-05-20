import sys
import os
import esptool
from pyocd.core.helpers import ConnectHelper
from pyocd.flash.file_programmer import FileProgrammer
from pyocd.target.family.target_nRF91 import ModemUpdater

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
                kwargs = {
                    **({"unique_id": port} if port != "Auto" else {}),
                    "options": {
                        **({"frequency": frequency} if frequency else {}),
                    }
                }
                with ConnectHelper.session_with_chosen_probe(target_override=target, **kwargs) as session:
                    target = session.board.target

                    write_cmds_num = 0
                    cmds = list(args[5:])
                    print(cmds, flush=True)
                    while cmds:
                        cmd = cmds.pop(0)
                        if cmd in ("load", "nrf91-update-modem-fw"):
                            cmds.pop(0)
                            write_cmds_num += 1

                    write_cmds_done = 0
                    cmds = list(args[5:])
                    while cmds:
                        cmd = cmds.pop(0)
                        progress = int(write_cmds_done / write_cmds_num * 100)
                        print("+PROGRESS:", progress, flush=True)
                        if cmd == "erase":
                            print("Erasing flash...", flush=True)
                            target.mass_erase()
                            print("Flash erased", flush=True)
                        elif cmd == "load":
                            file = cmds.pop(0)
                            print(f"Loading {file}...", flush=True)
                            def progress(progress):
                                progress = int(write_cmds_done / write_cmds_num * 100) + (progress*100)/write_cmds_num
                                print("+PROGRESS:", progress, flush=True)
                            programmer = FileProgrammer(session, progress=progress)
                            programmer.program(file)
                            write_cmds_done += 1
                        elif cmd == "nrf91-update-modem-fw":
                            file = cmds.pop(0)
                            print(f"nrf91-update-modem-fw {file}...", flush=True)
                            def progress(progress):
                                progress = int(write_cmds_done / write_cmds_num * 100) + (progress*100)/write_cmds_num
                                print("+PROGRESS:", progress, flush=True)
                            update = ModemUpdater(session, progress=progress)
                            update.program_and_verify(file)
                            write_cmds_done += 1

            return
        ui.loadFile(args[0])
    elif os.path.exists("manifest/manifest.json"):
        ui.loadFile("manifest/manifest.json")

    ui.run()
