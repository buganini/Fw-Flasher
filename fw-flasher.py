import os
import sys
import glob
import serial
from serial.tools import list_ports
from esptool.logger import log, TemplateLogger
import esptool
from threading import Thread
import json
from collections import OrderedDict
from PUI.PySide6 import *

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

class UI(Application):
    def __init__(self):
        super().__init__()
        ui = self
        self.state = state = State()
        self.state.port = "Auto"
        self.state.profile = ""
        self.state.profiles = []
        self.state.progress = 0
        self.state.root = ""
        self.state.logs = []
        self.state.worker = None

        class CustomLogger(TemplateLogger):
            def print(self, message, *args, **kwargs):
                print(f"{message}", *args, **kwargs)
                if not message.startswith("Writing at"):
                    state.logs.append(message)
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
        with Window(title="Firmware Flasher"):
            with VBox():
                with HBox():
                    Label("Port")
                    with ComboBox(text_model=self.state("port")):
                        ComboBoxItem("Auto")
                        for port in serial_ports():
                            ComboBoxItem(port)

                    Label("Profiles")
                    if self.state.profiles:
                        with ComboBox(text_model=self.state("profile")):
                            for profile in self.state.profiles.keys():
                                ComboBoxItem(profile)
                    else:
                        Button("Load").click(lambda e: self.load())

                    Button("Flash").click(lambda e: self.flash())

                    Spacer()

                with HBox():
                    Label("Description:")

                    if self.state.profile:
                        desc = self.state.profiles[self.state.profile]["description"]
                        Label(desc)

                    Spacer()

                ProgressBar(progress=self.state.progress, maximum=100)

                with Scroll().layout(height=800).scrollY(Scroll.END):
                    Text("\n".join(self.state.logs))

    def load(self):
        file = OpenFile()
        if file:
            self.loadFile(file)

    def loadFile(self, file):
        with open(file, "r") as f:
            self.state.profiles = json.load(f, object_pairs_hook=OrderedDict)
            if self.state.profiles:
                self.state.profile = list(self.state.profiles.keys())[0]
                self.state.root = os.path.dirname(file)

    def flash(self):
        self.state.progress = 0
        profile = self.state.profiles.get(self.state.profile)
        if not profile:
            return

        port = self.state.port
        if port == "Auto":
            port = serial_ports()[0]

        if profile.get("type", "").startswith("esp"):
            self.worker = Thread(target=self.flash_esp, args=[port, profile])
            self.worker.daemon = True
            self.worker.start()
        else:
            print("Unsupported chip type: %s" % profile.get("type"))

    def flash_esp(self, port, profile):
        cmd = []
        cmd.extend(["--port", port])
        cmd.extend(["--chip", profile.get("type")])
        cmd.extend(["-b", profile.get("baudrate", "460800")])
        cmd.extend([f"--before={profile.get('before', 'default_reset')}"])
        cmd.extend([f"--after={profile.get('after', 'hard_reset')}"])
        if profile.get("no-stub", True):
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
                self.state.logs.append(f"Error: File not found: {file}")
                return
            cmd.extend([offset, file])
        cmd = [str(x) for x in cmd]
        self.state.logs.append("esptool.py " + " ".join(cmd))
        try:
            esptool.main(cmd)
        except Exception as e:
            import traceback
            self.state.logs.append(f"Error: {e}")
            self.state.logs.append(f"Error: {traceback.format_exc()}")
            traceback.print_exc()
        self.worker = None

ui = UI()

if len(sys.argv) > 1:
    ui.loadFile(sys.argv[1])
elif os.path.exists("manifest.json"):
    ui.loadFile("manifest.json")

ui.run()

