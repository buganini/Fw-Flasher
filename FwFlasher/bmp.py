import glob
import os
import time
import sys
import shutil
import re
from .common import *
import subprocess
import serial

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
    show_progress = True
    show_monitor = True

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
                ret.append("/dev/"+p.name)
                sn.add(p.serial_number)
        # if not sys.platform.startswith('win'):
        #     ret = ["/dev/"+p for p in ret]
        return ret

    @staticmethod
    def get_monitor_port(main, port):
        return port[:-1]+"3"

    @staticmethod
    def precheck(context):
        if arm_none_eabi_gdb:
            print(f"Found {arm_none_eabi_gdb}")
        else:
            context.logs.append("Error: arm-none-eabi-gdb not found")

    @staticmethod
    def twpr_cycle(context, port):
        context.logs.append(f"TPWR power cycle")
        cmd = [
            arm_none_eabi_gdb,
            "--interpreter=mi",
            "-ex", f"target extended-remote {port}",
            "-ex", "monitor tpwr disable",
            "-ex", "quit",
        ]
        print(" ".join(cmd))
        context.logs.append(" ".join(cmd))
        for line in spawn_gdbmi(cmd):
            line = strip(line)
            context.logs.append(line)
        time.sleep(1)

        cmd = [
            arm_none_eabi_gdb,
            "--interpreter=mi",
            "-ex", f"target extended-remote {port}",
            "-ex", "monitor tpwr enable",
            "-ex", "quit",
        ]
        print(" ".join(cmd))
        context.logs.append(" ".join(cmd))
        for line in spawn_gdbmi(cmd):
            line = strip(line)
            context.logs.append(line)
        time.sleep(0.1)

    @staticmethod
    def flash(context, port, profile):
        if not arm_none_eabi_gdb:
            return

        context.monitor_logs = []

        context.logs = []
        context.progress = 0

        file = profile.get('load', '')
        if os.path.isabs(file):
            pass
        else:
            file = os.path.join(context.main.state.root, file)
        if not os.path.exists(file):
            context.logs.append(f"Error: File not found: {file}")
            return

        if port == "Auto":
            ports = BMPBackend.list_ports(context, profile)
            if ports:
                port = ports[0]
            else:
                port = None

        if not port:
            context.logs.append("Error: BMP port not found")
            return

        context.ok = False

        if profile.get("tpwr", True):
            BMPBackend.twpr_cycle(context, port)

        file = file.replace("\\", "\\\\").replace(" ", "\\ ")
        cmd = [
            arm_none_eabi_gdb,
            "--interpreter=mi",
            "-ex", f"target extended-remote {port}",
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
        context.ok = True
        context.logs.append(" ".join(cmd))
        for line in spawn_gdbmi(cmd):
            line = strip(line)
            if line.startswith("+download,"):
                kv = {k:v[1:-1] for k,v in [kv.split("=") for kv in line[11:-1].split(",")]}
                if "total-size" in kv and "total-sent" in kv:
                    context.progress = int(int(kv["total-sent"]) / int(kv["total-size"]) * 100)
                context.main.wait()
            if "Error" in line:
                context.ok = False
            context.logs.append(line)
        if context.ok:
            context.progress = 100
            context.done = True
            context.logs.append("Flash done")

            if profile.get("monitor", False):
                BMPBackend.monitor(context, port, profile)
        else:
            context.logs.append("Flash error")
            context.progress = 0

        if profile.get("tpwr", True):
            BMPBackend.twpr_cycle(context, port)

    def monitor(context, port, profile):
        monitor_port = BMPBackend.get_monitor_port(context, port)
        context.logs.append(f"Monitor start on port {monitor_port}")
        cmd = [
            arm_none_eabi_gdb,
            "--interpreter=mi",
            "-ex", f"target extended-remote {port}",
            "-ex", "monitor swd_scan",
            "-ex", "set confirm off",
            "-ex", f"attach {profile.get('attach', '1')}",
            "-ex", f"monitor rtt enable",
            "-ex", f"run",
            "-ex", "quit",
        ]
        context.monitor_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ser = serial.Serial(monitor_port, 115200, timeout=0.25)
        while context.monitor_proc and context.monitor_proc.poll() is None:
            line = ser.readline()
            line = line.decode("utf-8").rstrip("\r\n")
            line = re.sub(r"\x1b\[[0-9;]*m", "", line)
            context.monitor_logs.append(line)
            context.main.wait()
        ser.close()
        context.monitor_proc = None
        context.logs.append("Monitor done")