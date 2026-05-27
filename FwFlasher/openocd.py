import os
import shutil

from .common import *

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
    show_progress = False

    @staticmethod
    def build_programs(profile):
        ret = []

        programs = profile.get("programs", [])
        for program in programs:
            if isinstance(program, str):
                ret.append((program, None))
            else:
                ret.append((program[0], program[1]))

        return ret

    @staticmethod
    def precheck(main, profile):
        if openocd:
            print(f"Found {openocd}")
        else:
            context.logs.append("Error: OpenOCD not found")
            return False

        ok = True
        programs = OpenOCDBackend.build_programs(profile)
        for i,program in enumerate(programs):
            file = program[0]
            if not file.lower().endswith(".hex") and program[1] is None:
                ok = False
                main.context.logs.append(f"Error: {file} requires a offset")
                continue
            if not os.path.isabs(file):
                file = os.path.join(main.state.root, file)
            if not os.path.exists(file):
                ok = False
                main.context.logs.append(f"Error: File not found: {file}")
        if not programs:
            main.context.logs.append("Error: Nothing to flash")
            ok = False
        return ok

    @staticmethod
    def list_ports(context, profile):
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
        # print(" ".join(cmd))
        serial_idents = ["CMSIS-DAP: Serial# =", "Device: Serial number ="]
        for line in spawn(cmd, print_output=False):
            line = strip(line)

            for ident in serial_idents:
                if ident in line:
                    ports.append(line.split(ident)[1].strip())
                    break

        return ports

    @staticmethod
    def erase_flash(context, port, profile):
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
        context.logs.append(" ".join(cmd))
        for line in spawn(cmd):
            if hasattr(line, "decode"):
                line = line.decode("utf-8", errors="ignore")
            line = strip(line)
            context.logs.append(line)
            if "Programming Finished" in line:
                context.ok = True

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
    def determine_port(context, profile, port):
        if port == "Auto":
            ports = OpenOCDBackend.list_ports(context, profile)
            if ports:
                port = ports[0]
            else:
                port = None
        return port

    @staticmethod
    def flash(context, port, profile):
        if not openocd:
            return

        context.logs = []

        programs = OpenOCDBackend.build_programs(profile)

        context.ok = True
        interface = OpenOCDBackend.get_interface(profile)
        target = OpenOCDBackend.get_target(profile)
        if not os.path.exists(interface):
            context.logs.append(f"Error: Interface file not found: {interface}")
            context.ok = False

        if not os.path.exists(target):
            context.logs.append(f"Error: Target file not found: {target}")
            context.ok = False

        if not context.ok:
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
            context.logs.append(" ".join(cmd))
            for line in spawn(cmd):
                line = strip(line)
                context.logs.append(line)

        if context.main.state.erase_flash:
            OpenOCDBackend.erase_flash(main, port, profile)

        context.ok = False

        for program in programs:
            file = program[0]
            program_offset = program[1]
            if not os.path.isabs(file):
                file = os.path.join(context.main.state.root, file)

            file = file.replace("\\", "/").replace("\"", "\\\"")

            cmd = [
                openocd[0],
                "-f", interface,
            ]

            if port:
                cmd.extend(["-c", f"adapter serial \"{port}\""])

            transport = profile.get('transport')
            if transport:
                cmd.extend(["-c", f"transport select {transport}"])

            if program_offset:
                program_offset = f" {program_offset}"
            else:
                program_offset = ""
            cmd.extend([
                "-f", target,
                "-c", f"program \"{file}\" verify reset exit{program_offset}",
            ])
            print(" ".join(cmd))
            context.logs.append(" ".join(cmd))
            for line in spawn(cmd):
                line = strip(line)
                context.logs.append(line)
                if "Programming Finished" in line:
                    context.ok = True

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
            context.logs.append(" ".join(cmd))
            for line in spawn(cmd):
                line = strip(line)
                context.logs.append(line)

        context.done = True