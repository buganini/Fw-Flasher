import glob
import os
import time
import sys
import pexpect
import shutil
import re
from common import *

def find_arm_none_eabi_gdb():
    try:
        base_path = sys._MEIPASS
        bin_path = os.path.join(base_path, "bin")
        arm_none_eabi_gdb = glob.glob(os.path.join(bin_path, "arm-none-eabi-gdb*"))
        arm_none_eabi_gdb = [f for f in arm_none_eabi_gdb if "gdb-" not in f]
        if arm_none_eabi_gdb:
            return arm_none_eabi_gdb[0]
    except Exception:
        base_path = os.path.dirname(sys.argv[0])
        arm_none_eabi_gdb = glob.glob(os.path.join(base_path, "gcc-arm-none-eabi-*/bin/arm-none-eabi-gdb*"))
        arm_none_eabi_gdb = [f for f in arm_none_eabi_gdb if "gdb-" not in f]
        if arm_none_eabi_gdb:
            return arm_none_eabi_gdb[0]
    return shutil.which("arm-none-eabi-gdb")

arm_none_eabi_gdb = find_arm_none_eabi_gdb()

class BMPBackend(Backend):
    erase_flash = None

    @staticmethod
    def list_ports(main, profile):
        from serial.tools import list_ports
        ports = list_ports.comports()
        ports = [p for p in ports if len([x for x in ports if x.serial_number and x.serial_number==p.serial_number])==2]
        ports.sort(key=lambda p: [int(x) if x.isdigit() else x.lower () for x in re.findall(r"(\d+|\D+)", p.name)])
        ret = []
        sn = set()
        for p in ports:
            if not p.serial_number in sn:
                ret.append(p.name)
                sn.add(p.serial_number)
        if not sys.platform.startswith('win'):
            ret = ["/dev/"+p for p in ret]
        return ret

    @staticmethod
    def precheck(main):
        if arm_none_eabi_gdb:
            print(f"Found {arm_none_eabi_gdb}")
        else:
            main.state.logs.append("Error: arm-none-eabi-gdb not found")

    @staticmethod
    def flash(main, port, profile):
        if not arm_none_eabi_gdb:
            return

        main.state.logs = []

        file = profile.get('load', '')
        if os.path.isabs(file):
            pass
        else:
            file = os.path.join(main.state.root, file)
        if not os.path.exists(file):
            main.state.logs.append(f"Error: File not found: {file}")
            return

        if port == "Auto":
            ports = BMPBackend.list_ports(main, profile)
            if ports:
                port = ports[0]
            else:
                port = None

        if not port:
            main.state.logs.append("Error: BMP port not found")
            return

        main.ok = False

        if profile.get("tpwr", True):
            main.state.logs.append(f"TPWR power cycle")
            cmd = [
                arm_none_eabi_gdb,
                "-ex", "set pagination off",
                "-ex", f"target extended-remote {port}",
                "-ex", "monitor tpwr disable",
                "-ex", "monitor tpwr enable",
                "-ex", "quit",
            ]
            print(" ".join(cmd))
            main.state.logs.append(" ".join(cmd))
            child = spawn(cmd, timeout=300)
            while True:
                try:
                    child.expect(['\n'])
                    line = child.before
                    line = line.decode("utf-8", errors="ignore")
                    line = strip(line)
                    main.state.logs.append(line)
                except pexpect.EOF:
                    break
            time.sleep(0.5)

        file = file.replace("\\", "\\\\").replace(" ", "\\ ")
        cmd = [
            arm_none_eabi_gdb,
            "-ex", "set pagination off",
            "-ex", f"target extended-remote {port}",
            "-ex", "monitor tpwr enable",
        ]
        if profile.get("connect_rst", False):
            cmd.extend([
                "-ex", "monitor connect_rst enable",
            ])
        cmd.extend([
            "-ex", "monitor swd_scan",
            "-ex", "set confirm off",
            "-ex", f"attach {profile.get('attach', '1')}",
            "-ex", f"load {file}",
            "-ex", "quit",
        ])
        print(" ".join(cmd))
        main.state.logs.append(" ".join(cmd))
        child = spawn(cmd, timeout=300)
        child.logfile_read = sys.stdout.buffer
        while True:
            try:
                child.expect('\n')
                line = child.before
                line = line.decode("utf-8", errors="ignore")
                line = strip(line)
                if "Transfer rate" in line:
                    main.ok = True
                main.state.logs.append(line)
            except pexpect.EOF:
                break
