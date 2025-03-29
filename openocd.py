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
    @staticmethod
    def precheck(main):
        if openocd:
            print(f"Found {openocd}")
        else:
            main.state.logs.append("Error: OpenOCD not found")

    @staticmethod
    def list_ports(main, profile):
        if not openocd:
            return

        interface = profile.get("interface", "")
        if not os.path.isabs(interface):
            interface = os.path.join(openocd[1], "scripts", "interface", interface)

        ports = []

        cmd = [
            openocd[0],
            "-d3",
            "-f", interface,
            "-c", "interface",
        ]
        print(" ".join(cmd))
        child = spawn(cmd, timeout=300)
        child.logfile_read = sys.stdout.buffer

        serial_ident = "CMSIS-DAP: Serial# ="

        while True:
            try:
                child.expect('\n')
                line = child.before
                line = line.decode("utf-8", errors="ignore")
                line = strip(line)

                if serial_ident in line:
                    ports.append(line.split(serial_ident)[1].strip())
            except pexpect.EOF:
                break

        return ports

    @staticmethod
    def erase_flash(main, port, profile):
        cmd = [
            openocd[0],
            "-f", OpenOCDBackend.get_interface(profile),
        ]

        transport = profile.get('transport')
        if transport:
            cmd.extend(["-c", f"transport select {transport}"])

        cmd.extend([
            "-f", OpenOCDBackend.get_target(profile),
            "-c", "init",
            "-c", "reset halt",
            "-c", "flash erase_sector 0 0 last",
            "-c", "exit",
        ])
        print(" ".join(cmd))
        main.state.logs.append(" ".join(cmd))
        child = spawn(cmd, timeout=300)
        child.logfile_read = sys.stdout.buffer

        while True:
            try:
                child.expect('\n')
                line = child.before
                if hasattr(line, "decode"):
                    line = line.decode("utf-8", errors="ignore")
                line = strip(line)
                main.state.logs.append(line)
                if "Programming Finished" in line:
                    main.ok = True
            except pexpect.EOF:
                break

    @staticmethod
    def get_interface(profile):
        interface = profile.get("interface", "")
        if not os.path.isabs(interface):
            interface = os.path.join(openocd[1], "scripts", "interface", interface)
        return interface

    @staticmethod
    def get_target(profile):
        target = profile.get("target", "")
        if not os.path.isabs(target):
            target = os.path.join(openocd[1], "scripts", "target", target)
        return target

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

        if port == "Auto":
            ports = OpenOCDBackend.list_ports(main, profile)
            if ports:
                port = ports[0]
            else:
                port = None


        main.ok = True
        interface = OpenOCDBackend.get_interface(profile)
        target = OpenOCDBackend.get_target(profile)
        if not os.path.exists(interface):
            main.state.logs.append(f"Error: Interface file not found: {interface}")
            main.ok = False

        if not os.path.exists(target):
            main.state.logs.append(f"Error: Target file not found: {target}")
            main.ok = False

        if not main.ok:
            return

        if profile.get("before"):
            cmd = [
                openocd[0],
                "-f", interface,
                "-f", target,
                "-c", "init",
            ]
            transport = profile.get('transport')
            if transport:
                cmd.extend(["-c", f"transport select {transport}"])
            for c in profile.get("before"):
                cmd.extend(["-c", c])
            cmd.extend(["-c", "exit"])
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
                    main.state.logs.append(line)
                except pexpect.EOF:
                    break

        if main.state.erase_flash:
            OpenOCDBackend.erase_flash(main, port, profile)

        cmd = [
            openocd[0],
            "-f", interface,
        ]

        if port:
            cmd.extend(["-c", f"adapter serial \"{port}\""])

        transport = profile.get('transport')
        if transport:
            cmd.extend(["-c", f"transport select {transport}"])

        cmd.extend([
            "-f", target,
            "-c", f"program \"{file}\" verify reset exit",
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
                main.state.logs.append(line)
                if "Programming Finished" in line:
                    main.ok = True
            except pexpect.EOF:
                break

        if profile.get("after"):
            cmd = [
                openocd[0],
                "-f", interface,
                "-f", target,
                "-c", "init",
            ]
            transport = profile.get('transport')
            if transport:
                cmd.extend(["-c", f"transport select {transport}"])
            for c in profile.get("after"):
                cmd.extend(["-c", c])
            cmd.extend(["-c", "exit"])
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
                    main.state.logs.append(line)
                except pexpect.EOF:
                    break