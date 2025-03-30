import glob
import os
import time
import sys
import pexpect
import shutil
import re
from common import *

def find_dfu_util():
    try:
        base_path = sys._MEIPASS
        bin_path = os.path.join(base_path, "dfu-util")
        dfu_util = glob.glob(os.path.join(bin_path, "dfu-util*"))
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
    def list_ports(main, profile):
        cmd = [
            dfu_util, "-l"
        ]
        # print(" ".join(cmd))
        # main.state.logs.append(" ".join(cmd))
        child = spawn(cmd, timeout=300)
        ports = []
        while True:
            try:
                child.expect(['\n'])
                line = child.before
                line = line.decode("utf-8", errors="ignore")
                line = strip(line)
                if line.startswith("Found"):
                    ports.append(line.split(": ", 1)[1])
            except pexpect.EOF:
                break
        return ports

    @staticmethod
    def precheck(main):
        if dfu_util:
            print(f"Found {dfu_util}")
        else:
            main.state.logs.append("Error: dfu_util not found")

    @staticmethod
    def flash(main, port, profile):
        if not dfu_util:
            return

        main.state.logs = []

        file = profile.get('download', '')
        if os.path.isabs(file):
            pass
        else:
            file = os.path.join(main.state.root, file)
        if not os.path.exists(file):
            main.state.logs.append(f"Error: File not found: {file}")
            return

        if port == "Auto":
            ports = DFUBackend.list_ports(main, profile)
            if ports:
                port = ports[0]
            else:
                port = None

        if not port:
            main.state.logs.append("Error: DFU port not found")
            return

        main.ok = True

        device_path = re.search(r'path="([^"]+)"', port)
        print("device_path", device_path)
        if device_path:
            device_path = device_path.group(1)
        else:
            return

        cmd = [
            dfu_util,
            "-p", device_path,
        ]

        dfuse_address = profile.get('dfuse-address', '0x08002000:leave')
        if dfuse_address:
            cmd.extend(["--dfuse-address", dfuse_address])

        cmd.extend(["--download", file])

        print(" ".join(cmd))
        main.state.logs.append(" ".join(cmd))
        child = spawn(cmd, timeout=300)
        child.logfile_read = sys.stdout.buffer
        while True:
            try:
                child.expect(['\r', '\n'])
                line = child.before
                line = line.decode("utf-8", errors="ignore")
                line = strip(line)
                if not line:
                    continue
                m = re.search(r'\] *(\d+)%', line)
                if m:
                    main.state.progress = int(m.group(1))
                    continue
                main.state.logs.append(line)
            except pexpect.EOF:
                break
