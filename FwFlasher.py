import os
import sys
import glob
import serial
from serial.tools import list_ports
from esptool.logger import log, TemplateLogger
import esptool
from threading import Thread
import shutil
import subprocess
import time
import glob
import json
from collections import OrderedDict
from PUI.PySide6 import *
import PUI

VERSION = "0.1"

def serial_ports():
    result = []

    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = [p for p in glob.glob('/dev/tty.*') if all([b not in p for b in ["Bluetooth", "debug"]])]
    else:
        raise EnvironmentError('Unsupported platform')

    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

def find_gdb_port():
    import glob
    if os.uname().sysname == "Darwin":
        ports = glob.glob("/dev/cu.usbmodem*")
        for p in ports:
            if p[:-1]+"1" in ports and p[:-1]+"3" in ports:
                return p[:-1]+"1"
        raise Exception("GDB port not found")
    else:
        raise Exception("Unsupported platform")

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath("resources")

    return os.path.join(base_path, relative_path)

def find_arm_none_eabi_gdb():
    try:
        base_path = sys._MEIPASS
        bin_path = os.path.join(base_path, "bin")
        arm_none_eabi_gdb = glob.glob(os.path.join(bin_path, "arm-none-eabi-gdb*"))
        if arm_none_eabi_gdb:
            arm_none_eabi_gdb = arm_none_eabi_gdb[0]
        else:
            arm_none_eabi_gdb = None
    except Exception:
        base_path = os.path.dirname(sys.argv[0])
        arm_none_eabi_gdb = glob.glob(os.path.join(base_path, "gcc-arm-none-eabi-*/bin/arm-none-eabi-gdb*"))
        if arm_none_eabi_gdb:
            arm_none_eabi_gdb = arm_none_eabi_gdb[0]
        else:
            arm_none_eabi_gdb = None
    return arm_none_eabi_gdb

arm_none_eabi_gdb = find_arm_none_eabi_gdb()

class UI(Application):
    def __init__(self):
        super().__init__(icon=resource_path("icon.ico"))
        ui = self
        self.state = state = State()
        self.state.port = "Auto"
        self.state.profile = ""
        self.state.profiles = []
        self.state.progress = 0
        self.state.root = ""
        self.state.logs = []
        self.state.mac = ""
        self.state.worker = None
        self.state.erase_flash = True

        class CustomLogger(TemplateLogger):
            def print(self, message, *args, **kwargs):
                print(f"{message}", *args, **kwargs)
                ui_changed = False
                if not message.startswith("Writing at"):
                    state.logs.append(message)
                    ui_changed = True
                if message.startswith("MAC: "):
                    state.mac = message.split("MAC: ")[1].strip()
                    ui_changed = True
                if ui_changed:
                    ui.wait()

            def note(self, message):
                self.print(f"NOTE: {message}")

            def warning(self, message):
                self.print(f"WARNING: {message}")

            def error(self, message):
                self.print(message, file=sys.stderr)

            def print_overwrite(self, message, last_line=False):
                # Overwriting not needed, print normally
                self.print(message)

            def set_progress(self, percentage):
                state.progress = percentage
                ui.wait()

        log.set_logger(CustomLogger())

    def content(self):
        title = f"Firmware Flasher v{VERSION} (esptool {esptool.__version__}, PUI {PUI.__version__} {PUI_BACKEND})"
        with Window(title=title, size=(800, 600), icon=resource_path("icon.ico")):
            with VBox():
                with HBox():
                    Label("Profile")
                    if self.state.profiles:
                        with ComboBox(text_model=self.state("profile")):
                            for profile in self.state.profiles.keys():
                                ComboBoxItem(profile)
                    else:
                        Button("Load").click(lambda e: self.load())

                    if self.state.profile:
                        Label("Port")
                        with ComboBox(text_model=self.state("port")):
                            ComboBoxItem("Auto")
                            for port in serial_ports():
                                ComboBoxItem(port)

                    if self.state.profile and self.get_flasher(self.state.profiles[self.state.profile]) == self.flash_esp:
                        Checkbox("Erase Flash", self.state("erase_flash"))

                    if self.state.worker is None:
                        Button("Flash").click(lambda e: self.flash())

                    Spacer()

                with HBox():
                    Label("Description:")

                    if self.state.profile:
                        desc = self.state.profiles[self.state.profile]["description"]
                        Label(desc)

                    Spacer()

                if self.state.profile and self.get_flasher(self.state.profiles[self.state.profile]) == self.flash_esp:
                    with HBox():
                        Label("MAC:")
                        TextField(self.state("mac"))

                if self.state.profile and self.get_flasher(self.state.profiles[self.state.profile]) == self.flash_esp:
                    ProgressBar(progress=self.state.progress, maximum=100)

                with Scroll().layout(weight=1).scrollY(Scroll.END):
                    Text("\n".join(self.state.logs))

    def load(self):
        file = OpenFile()
        if file:
            self.loadFile(file)

    def loadFile(self, file):
        self.state.logs = []
        with open(file, "r") as f:
            self.state.profiles = json.load(f, object_pairs_hook=OrderedDict)
            use_bmp = False
            if self.state.profiles:
                for name, profile in self.state.profiles.items():
                    flasher = self.get_flasher(profile)
                    if not flasher:
                        self.state.logs.append(f"Unsupported chip type \"{profile.get('type')}\" in profile \"{name}\"")
                    elif flasher == self.flash_bmp:
                        use_bmp = True
                self.state.profile = list(self.state.profiles.keys())[0]
                self.state.root = os.path.dirname(file)
            if use_bmp:
                if arm_none_eabi_gdb:
                    print(f"Found {arm_none_eabi_gdb}")
                else:
                    self.state.logs.append("Error: arm-none-eabi-gdb not found")

    def get_flasher(self, profile):
        if profile.get("type", "").startswith("esp"):
            return self.flash_esp
        elif profile.get("type", "") == "bmp":
            return self.flash_bmp
        else:
            print("Unsupported chip type: %s" % profile.get("type"))


    def flash(self):
        self.state.progress = 0
        profile = self.state.profiles.get(self.state.profile)
        if not profile:
            return

        port = self.state.port

        flasher = self.get_flasher(profile)
        if flasher:
            Thread(target=self.thread_watcher, args=[flasher, port, profile], daemon=True).start()

    def thread_watcher(self, func, port, profile):
        worker = Thread(target=func, args=[port, profile], daemon=True)
        self.state.worker = worker
        worker.start()
        worker.join()
        if self.ok:
            print("Done")
            self.state.logs.append("Done")
        self.state.worker = None

    def erase_esp(self, port, profile):
        cmd = []
        cmd.extend(["--port", port])
        cmd.extend(["--chip", profile.get("type")])
        cmd.extend(["erase-flash"])
        cmd = [str(x) for x in cmd]
        esptool.main(cmd)

    def flash_esp(self, port, profile):
        self.state.logs = []

        if port == "Auto":
            port = serial_ports()[0]

        if self.state.erase_flash:
            print("Erase Flash")
            eraser = Thread(target=self.erase_esp, args=[port, profile], daemon=True)
            eraser.start()
            eraser.join()
            self.state.logs.append("Erase Flash Done")

        cmd = []
        cmd.extend(["--port", port])
        cmd.extend(["--chip", profile.get("type")])
        cmd.extend(["-b", profile.get("baudrate", "460800")])
        cmd.extend([f"--before={profile.get('before', 'default_reset')}"])
        cmd.extend([f"--after={profile.get('after', 'hard_reset')}"])
        if profile.get("no-stub", False):
            cmd.extend(["--no-stub"])
        cmd.extend(["write-flash"])
        cmd.extend(["--flash-mode", profile.get("flash-mode", "dio")])
        cmd.extend(["--flash-freq", profile.get("flash-freq", "80m")])
        cmd.extend(["--flash-size", profile.get("flash-size", "4MB")])
        for offset, file in profile.get("write-flash", []):
            if file.startswith("/"):
                pass
            else:
                file = os.path.join(self.state.root, file)
            if not os.path.exists(file):
                # self.state.logs.append(f"Error: File not found: {file}, root={self.state.root}")
                self.state.logs.append(f"Error: File not found: {file}")
                return
            cmd.extend([offset, file])
        cmd = [str(x) for x in cmd]
        print(cmd)
        self.state.logs.append("esptool.py " + " ".join(cmd))
        self.ok = True
        try:
            esptool.main(cmd)
            print("esptool.main() done")
        except Exception as e:
            import traceback
            self.ok = False
            self.state.logs.append(f"Error: {e}")
            self.state.logs.append(f"Error: {traceback.format_exc()}")
            traceback.print_exc()

    def flash_bmp(self, port, profile):
        if not arm_none_eabi_gdb:
            return

        self.state.logs = []

        if port == "Auto":
            port = find_gdb_port()

        self.ok = True

        if profile.get("tpwr", True):
            self.state.logs.append(f"TPWR power cycle")
            cmd = [
                arm_none_eabi_gdb,
                "-ex", f"target extended-remote {port}",
                "-ex", "monitor tpwr disable",
                "-ex", "monitor tpwr enable",
                "-ex", "quit",
            ]
            print(" ".join(cmd))
            self.state.logs.append(" ".join(cmd))
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                line = line.decode("utf-8", errors="ignore")
                line = line.strip()
                print(line)
                self.state.logs.append(line)
            time.sleep(0.5)

        cmd = [
            arm_none_eabi_gdb,
            "-ex", f"target extended-remote {port}",
            "-ex", "monitor tpwr enable",
            "-ex", "monitor swd_scan",
            "-ex", f"attach {profile.get('attach', '1')}",
            "-ex", f"load \"{profile.get('load', '')}\"",
            "-ex", "set confirm off",
            "-ex", "quit",
        ]
        print(" ".join(cmd))
        self.state.logs.append(" ".join(cmd))
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            line = line.decode("utf-8", errors="ignore")
            line = line.strip()
            print(line)
            self.state.logs.append(line)


if __name__ == "__main__":
    ui = UI()

    manifest_json = "manifest.json"
    if getattr(sys, 'frozen', False):
        manifest_json = os.path.join(sys._MEIPASS, manifest_json)

    if len(sys.argv) > 1:
        ui.loadFile(sys.argv[1])
    elif os.path.exists(manifest_json):
        ui.loadFile(manifest_json)

    ui.run()

