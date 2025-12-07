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
    def list_ports(context, profile):
        allProbes = ConnectHelper.get_all_connected_probes(blocking=False)
        return [p.unique_id for p in allProbes]

    @staticmethod
    def flash(context, port, profile):
        context.logs = []

        files = []
        commands = profile.get('commands', [])
        target = profile.get('target', None)
        if not target:
            context.logs.append("Error: target not set")
            return

        write_cmds_num = 0
        for cmd in commands:
            if len(cmd) == 0:
                context.logs.append("Error: command is empty")
                return
            if cmd[0] in ("load", "nrf91-update-modem-fw"):
                write_cmds_num += 1
                if len(cmd) == 1:
                    context.logs.append("Error: command is missing file")
                    return
                files.append(cmd[1])
            else:
                context.logs.append(f"Error: unknown command: {cmd[0]}")
                return

        for file in files:
            if os.path.isabs(file):
                pass
            else:
                file = os.path.join(context.main.state.root, file)
            if not os.path.exists(file):
                context.logs.append(f"Error: File not found: {file}")
                return

        context.ok = True

        options = {}
        frequency = profile.get('frequency', None)
        if frequency:
            options['frequency'] = frequency
            context.logs.append(f"Frequency: {frequency}")

        kwargs = {}
        if options:
            kwargs["options"] = options
        if port != "Auto":
            kwargs["unique_id"] = port

        context.logs.append(f"Starting PyOCD with options: {kwargs}")

        with ConnectHelper.session_with_chosen_probe(target_override=target, **kwargs) as session:
            target = session.board.target

            if context.main.state.erase_flash:
                context.logs.append("Erasing flash...")
                target.mass_erase()
                context.logs.append("Flash erased")

            try:
                write_cmds_done = 0
                for cmd in commands:
                    context.progress = int(write_cmds_done / write_cmds_num * 100)

                    file = cmd[1]
                    if os.path.isabs(file):
                        pass
                    else:
                        file = os.path.join(context.main.state.root, file)

                    if cmd[0] == "load":
                        context.logs.append(f"Loading {file}...")
                        def progress(progress):
                            print(f"load progress: {progress}")
                            context.progress = int(write_cmds_done / write_cmds_num * 100) + (progress*100)/write_cmds_num + 1
                            context.main.wait()

                        programmer = FileProgrammer(session, progress=progress)
                        programmer.program(file)
                        write_cmds_done += 1

                    elif cmd[0] == "nrf91-update-modem-fw":
                        context.logs.append(f"nrf91-update-modem-fw {file}...")
                        def progress(progress):
                            print(f"nrf91-update-modem-fw progress: {progress}")
                            context.progress = int(write_cmds_done / write_cmds_num * 100) + (progress*100)/write_cmds_num + 1
                            context.main.wait()
                        update = ModemUpdater(session, progress=progress)
                        update.program_and_verify(file)
                        write_cmds_done += 1

                context.progress = 100
            except Exception as e:
                import traceback
                context.logs.append(traceback.format_exc())
                context.ok = False
