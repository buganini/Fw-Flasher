import os
import re
from .common import *
from pyocd.core.helpers import ConnectHelper

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

        frequency = str(profile.get('frequency', 0))

        seq = []

        if context.main.state.erase_flash:
            context.logs.append("Erasing flash...")
            seq.append("erase")
            context.logs.append("Flash erased")

        for cmd in commands:
            file = cmd[1]
            if os.path.isabs(file):
                pass
            else:
                file = os.path.join(context.main.state.root, file)
                file = os.path.abspath(file)

            if cmd[0] == "load":
                seq.append("load")
                seq.append(file)
            elif cmd[0] == "nrf91-update-modem-fw":
                seq.append("nrf91-update-modem-fw")
                seq.append(file)

        pcmd = [
            *ARGV0, "pyocd", "cmd",
            port, target, frequency,
            *seq
        ]
        for line in spawn(pcmd):
            if line:
                if line[0] in "[=":
                    continue
                if line.startswith("+PROGRESS:"):
                    progress = float(line.split(":")[1].strip())
                    context.progress = progress
                    continue
            context.logs.append(line)

        if context.ok:
            context.progress = 100
            context.done = True
        else:
            context.ok = False