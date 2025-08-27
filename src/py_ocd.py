import os
import re
from common import *
from pyocd.core.helpers import ConnectHelper
from pyocd.flash.file_programmer import FileProgrammer
from pyocd.target.family.target_nRF91 import ModemUpdater

class PyOCDBackend(Backend):
    show_progress = True
    erase_flash = True

    @staticmethod
    def list_ports(main, profile):
        allProbes = ConnectHelper.get_all_connected_probes(blocking=True)
        return [p.unique_id for p in allProbes]

    @staticmethod
    def flash(main, port, profile):
        main.state.logs = []

        files = []
        commands = profile.get('commands', [])
        target = profile.get('target', None)
        if not target:
            main.state.logs.append("Error: target not set")
            return

        write_cmds_num = 0
        for cmd in commands:
            if len(cmd) == 0:
                main.state.logs.append("Error: command is empty")
                return
            if cmd[0] in ("load", "nrf91-update-modem-fw"):
                write_cmds_num += 1
                if len(cmd) == 1:
                    main.state.logs.append("Error: command is missing file")
                    return
                files.append(cmd[1])
            else:
                main.state.logs.append(f"Error: unknown command: {cmd[0]}")
                return

        for file in files:
            if os.path.isabs(file):
                pass
            else:
                file = os.path.join(main.state.root, file)
            if not os.path.exists(file):
                main.state.logs.append(f"Error: File not found: {file}")
                return

        main.ok = True

        options = {}
        frequency = profile.get('frequency', None)
        if frequency:
            options['frequency'] = frequency
            main.state.logs.append(f"Frequency: {frequency}")

        kwargs = {}
        if options:
            kwargs["options"] = options
        if port != "Auto":
            kwargs["unique_id"] = port

        main.state.logs.append(f"Starting PyOCD with options: {kwargs}")

        with ConnectHelper.session_with_chosen_probe(target_override=target, **kwargs) as session:
            target = session.board.target

            if main.state.erase_flash:
                main.state.logs.append("Erasing flash...")
                target.mass_erase()
                main.state.logs.append("Flash erased")

            try:
                write_cmds_done = 0
                for cmd in commands:
                    main.state.progress = int(write_cmds_done / write_cmds_num * 100)

                    file = cmd[1]
                    if os.path.isabs(file):
                        pass
                    else:
                        file = os.path.join(main.state.root, file)

                    if cmd[0] == "load":
                        main.state.logs.append(f"Loading {file}...")
                        def progress(progress):
                            print(f"load progress: {progress}")
                            main.state.progress = int(write_cmds_done / write_cmds_num * 100) + (progress*100)/write_cmds_num + 1
                            main.wait()

                        programmer = FileProgrammer(session, progress=progress)
                        programmer.program(file)
                        write_cmds_done += 1

                    elif cmd[0] == "nrf91-update-modem-fw":
                        main.state.logs.append(f"nrf91-update-modem-fw {file}...")
                        def progress(progress):
                            print(f"nrf91-update-modem-fw progress: {progress}")
                            main.state.progress = int(write_cmds_done / write_cmds_num * 100) + (progress*100)/write_cmds_num + 1
                            main.wait()
                        update = ModemUpdater(session, progress=progress)
                        update.program_and_verify(file)
                        write_cmds_done += 1

                main.state.progress = 100
            except Exception as e:
                import traceback
                main.state.logs.append(traceback.format_exc())
                main.ok = False
