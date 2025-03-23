import os
import pexpect
import shutil

from common import *

def find_openocd():
    try:
        base_path = sys._MEIPASS
        bin_path = os.path.join(base_path, "bin")
        openocd = glob.glob(os.path.join(bin_path, "openocd*"))
        if openocd:
            return openocd[0], os.path.abspath(os.path.join(os.path.dirname(openocd[0]), "..", "openocd"))
    except Exception:
        base_path = os.path.dirname(sys.argv[0])
        openocd = glob.glob(os.path.join(base_path, "*openocd-*/bin/openocd*"))
        if openocd:
            return openocd[0], os.path.abspath(os.path.join(os.path.dirname(openocd[0]), "..", "openocd"))

    openocd = shutil.which("openocd")
    if openocd:
        return openocd, os.path.abspath(os.path.join(os.path.dirname(openocd), "..", "share", "openocd"))

    return None

openocd = find_openocd()

class OpenOCDBackend(Backend):
    list_ports = None
    erase_flash = None

    @staticmethod
    def precheck(main):
        if openocd:
            print(f"Found {openocd}")
        else:
            main.state.logs.append("Error: OpenOCD not found")

    @staticmethod
    def flash(main, port, profile):
        if not openocd:
            return

        main.state.logs = []

        file = profile.get('program', '')
        if os.path.isabs(file):
            pass
        else:
            file = os.path.join(main.state.root, file)
        if not os.path.exists(file):
            main.state.logs.append(f"Error: File not found: {file}")
            return


        file = file.replace("\\", "/").replace("\"", "\\\"")

        interface = profile.get("interface", "")
        if not os.path.isabs(interface):
            interface = os.path.join(openocd[1], "scripts", "interface", interface)

        main.ok = True
        target = profile.get("target", "")
        if not os.path.isabs(target):
            target = os.path.join(openocd[1], "scripts", "target", target)

        if not os.path.exists(interface):
            main.state.logs.append(f"Error: Interface file not found: {interface}")
            main.ok = False

        if not os.path.exists(target):
            main.state.logs.append(f"Error: Target file not found: {target}")
            main.ok = False

        if not main.ok:
            return

        cmd = [
            openocd[0],
            "-f", interface,
            "-f", target,
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
