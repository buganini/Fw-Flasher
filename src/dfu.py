import glob
import os
import time
import sys
import shutil
import re
from common import *

def find_dfu_util():
    try:
        base_path = sys._MEIPASS
        bin_path = os.path.join(base_path, "bin")
        dfu_util = glob.glob(os.path.join(bin_path, "dfu-util*"))
        if sys.platform.startswith('win'):
            dfu_util = [x for x in dfu_util if "static" in x]
        if dfu_util:
            return dfu_util[0]
    except Exception:
        base_path = os.path.dirname(sys.argv[0])
        if sys.platform.startswith('win'):
            osname = "win64"
        elif sys.platform.startswith('linux'):
            osname = "linux-amd64"
        elif sys.platform.startswith('darwin'):
            osname = "darwin-x86_64"
        else:
            osname = None
        if osname:
            dfu_util = glob.glob(os.path.join(base_path, f"dfu-util-*/{osname}/dfu-util*"))
            if dfu_util:
                return os.path.abspath(dfu_util[0])
    return shutil.which("dfu-util")

dfu_util = find_dfu_util()

class DFUBackend(Backend):
    show_progress = True
    erase_flash = None

    @staticmethod
    def list_ports(context, profile):
        cmd = [
            dfu_util, "-l"
        ]
        # print(" ".join(cmd))
        # context.logs.append(" ".join(cmd))
        ports = []
        for line in spawn(cmd):
            line = strip(line)
            if line.startswith("Found"):
                ports.append(line.split(": ", 1)[1])
        return ports

    @staticmethod
    def precheck(context):
        if dfu_util:
            print(f"Found {dfu_util}")
        else:
            context.logs.append("Error: dfu_util not found")

    @staticmethod
    def flash(context, port, profile):
        if not dfu_util:
            return

        context.logs = []

        files = []
        downloads = profile.get('downloads', [])
        for download in downloads:
            files.append(download['download'])

        for file in files:
            if os.path.isabs(file):
                pass
            else:
                file = os.path.join(context.main.state.root, file)
            if not os.path.exists(file):
                context.logs.append(f"Error: File not found: {file}")
                return

        if port == "Auto":
            ports = DFUBackend.list_ports(context, profile)
            if ports:
                port = ports[0]
            else:
                port = None

        if not port:
            context.logs.append("Error: DFU port not found")
            return

        context.ok = False

        device_path = re.search(r'path="([^"]+)"', port)
        print("device_path", device_path)
        if device_path:
            device_path = device_path.group(1)
        else:
            return

        tasks = []
        for download in downloads:
            args = []
            dfuse_address = profile.get('dfuse-address', '0x08002000:leave')
            if dfuse_address:
                args.extend(["--dfuse-address", dfuse_address])

            file = download['download']
            if os.path.isabs(file):
                pass
            else:
                file = os.path.join(context.main.state.root, file)

            args.extend(["--download", file])

            alt = download.get('alt')
            if alt is not None:
                args.extend(["--alt", str(alt)])

            if download.get('reset'):
                args.extend(["--reset"])

            tasks.append(args)

        has_progress = False

        for task in tasks:
            cmd = [
                dfu_util,
                "-p", device_path,
                *task
            ]

            print(" ".join(cmd))
            context.logs.append(" ".join(cmd))
            has_erase_phase = False
            for line in spawn(cmd):
                line = strip(line)
                if not line:
                    continue
                m = re.search(r'\s*(\S*)\s*\[[ =]*\] *(\d+)%', line)
                if m:
                    phase = m.group(1)
                    progress = int(m.group(2))
                    if phase == "Erase":
                        has_erase_phase = True
                        progress *= 0.5
                    elif phase == "Download":
                        if has_erase_phase:
                            progress *= 0.5
                            progress += 50
                    context.progress = progress
                    has_progress = True
                    continue
                context.logs.append(line)

        if has_progress:
            context.ok = True
            context.done = True