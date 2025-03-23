import os
import pexpect

from common import *

openocd = "openocd"

class OpenOCDBackend(Backend):
    list_ports = None
    erase_flash = None

    @staticmethod
    def flash(main, port, profile):
        if not openocd:
            return

        main.state.logs = []

        file = profile.get('program', '')
        if file.startswith("/"):
            pass
        else:
            file = os.path.join(main.state.root, file)
        if not os.path.exists(file):
            main.state.logs.append(f"Error: File not found: {file}")
            return

        main.ok = False

        file = file.replace("\\", "/").replace("\"", "\\\"")

        cmd = [
            openocd,
            "-f", profile.get("interface", ""),
            "-f", profile.get("target", ""),
            "-c", f"program \"{file}\" verify reset exit",
        ]
        print(" ".join(cmd))
        main.state.logs.append(" ".join(cmd))
        child = pexpect.spawn(cmd[0], cmd[1:], timeout=300)
        child.logfile_read = sys.stdout.buffer

        while True:
            try:
                child.expect('\n')
                line = child.before
                line = line.decode("utf-8", errors="ignore")
                line = strip(line)
                main.state.logs.append(line)
                if "Programming Finished" in line:
                    main.ok = True
            except pexpect.EOF:
                break
