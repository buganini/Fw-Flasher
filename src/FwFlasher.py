import os
import sys
from threading import Thread
import esptool
import json
from collections import OrderedDict
from PUI.PySide6 import *
import PUI

VERSION = "0.8"

from common import *
from bmp import BMPBackend
from dfu import DFUBackend
from esp import ESPBackend
from openocd import OpenOCDBackend
from py_ocd import PyOCDBackend


class UI(Application):
    def __init__(self):
        super().__init__(icon=resource_path("icon.ico"))
        self.state = state = State()
        self.state.port = ""
        self.state.profile = ""
        self.state.profiles = {}
        self.state.progress = 0
        self.state.root = ""
        self.state.logs = []
        self.state.mac = ""
        self.state.worker = None
        self.state.batch_old_ports = set()
        self.state.batch_working_ports = set()
        self.state.batch_idle_ports = set()
        self.state.batch_worker = OrderedDict()
        self.state.batch_flash = False
        self.state.batch_flashing = False
        self.state.erase_flash = False
        self.state.ports = []

        self.manifest_dir = None
        self.backend = None

        Thread(target=self.ports_watcher, daemon=True).start()

    def ports_watcher(self):
        while True:
            try:
                profile = self.state.profiles.get(self.state.profile)
                if profile:
                    backend = self.getBackend(profile)
                    if backend and backend.list_ports:
                        ports = backend.list_ports(self, self.state.profiles[self.state.profile])
                    else:
                        ports = []
                    self.state.ports = ports
                    if self.state.batch_flashing:
                        current_ports = set(ports)
                        removed_ports = (self.state.batch_old_ports | self.state.batch_working_ports | self.state.batch_idle_ports) - current_ports

                        new_ports = current_ports - self.state.batch_old_ports - self.state.batch_working_ports - self.state.batch_idle_ports
                        print("Removed ports: ", removed_ports)
                        print("New ports: ", new_ports)

                        for p in new_ports:
                            self.state.batch_working_ports.add(p)
                            Thread(target=self.batch_worker, args=[profile, backend, p], daemon=True).start()

                        self.state.batch_old_ports -= removed_ports
                        self.state.batch_working_ports -= removed_ports
                        self.state.batch_idle_ports -= removed_ports
            except:
                import traceback
                traceback.print_exc()
            time.sleep(1)

    def content(self):
        title = f"Firmware Flasher v{VERSION} (esptool {esptool.__version__}, PUI {PUI.__version__} {PUI_BACKEND})"
        with Window(title=title, size=(800, 600), icon=resource_path("icon.ico")).keypress(self.keypress):
            with VBox():
                with HBox():
                    Label("Profile")
                    if self.state.profiles:
                        with ComboBox(text_model=self.state("profile")).change(self.changeProfile):
                            for profile in self.state.profiles.keys():
                                ComboBoxItem(profile)
                    else:
                        Button("Load Manifest").click(lambda e: self.load_manifest())

                    if self.backend and self.backend.list_ports:
                        Label("Port")
                        with ComboBox(text_model=self.state("port")):
                            ComboBoxItem("Auto")
                            for port in self.state.ports:
                                ComboBoxItem(port)

                    if self.backend and self.backend.erase_flash:
                        Checkbox("Erase Flash", self.state("erase_flash"))

                    if self.state.profile:
                        if self.state.worker is None and not self.state.batch_flashing:
                            Button("Flash (Enter)").click(lambda e: self.flash())
                            # Button("Batch Flash").click(lambda e: self.batch_start())
                        elif self.state.batch_flashing:
                            Button("Stop").click(lambda e: self.batch_stop())

                    Spacer()

                    if self.state.profiles and self.state.worker is None and not self.state.batch_flashing:
                        Button("Load Manifest").click(lambda e: self.load_manifest())

                with HBox():
                    Label("Description:")

                    if self.state.profile:
                        desc = self.state.profiles[self.state.profile]["description"]
                        Label(desc)

                    Spacer()

                if self.backend and self.backend.show_mac:
                    with HBox():
                        Label("MAC:")
                        TextField(self.state("mac"))

                if self.state.batch_flashing:
                    with Scroll().layout(weight=1).scrollY():
                        Spacer()
                else:
                    if self.backend and self.backend.show_progress:
                        ProgressBar(progress=self.state.progress, maximum=100)
                    with Scroll().layout(weight=1).scrollY(Scroll.END):
                        Text("\n".join(self.state.logs))

    def keypress(self, e):
        if e.text == "\r":
            self.flash()

    def changeProfile(self, e):
        backend = self.getBackend(self.state.profiles[self.state.profile])
        if backend and backend != self.backend:
            self.state.logs = []
            backend.precheck(self)
            self.backend = backend
            self.state.port = "Auto"
            self.state.erase_flash = self.state.profiles[self.state.profile].get("erase-flash", False)

    def load_manifest(self):
        file = OpenFile("Open Manifest", types="Manifest JSON (*.json)|.*json", dir=self.manifest_dir)
        if file:
            self.manifest_dir = os.path.dirname(file)
            self.loadFile(file)

    def loadFile(self, file):
        self.state.logs = []
        with open(file, "r") as f:
            self.state.profiles = json.load(f, object_pairs_hook=OrderedDict)
            use_bmp = False
            if self.state.profiles:
                for name, profile in self.state.profiles.items():
                    backend = self.getBackend(profile)
                    if not backend:
                        self.state.logs.append(f"Unsupported chip type \"{profile.get('type')}\" in profile \"{name}\"")
                self.state.profile = list(self.state.profiles.keys())[0]
                self.state.root = os.path.abspath(os.path.dirname(file))
                self.changeProfile(None)

    def getBackend(self, profile):
        if not profile:
            return None
        if profile.get("type", "").startswith("esp"):
            return ESPBackend
        elif profile.get("type", "") == "bmp":
            return BMPBackend
        elif profile.get("type", "") == "openocd":
            return OpenOCDBackend
        elif profile.get("type", "") == "dfu":
            return DFUBackend
        elif profile.get("type", "") == "pyocd":
            return PyOCDBackend
        else:
            print("Unsupported chip type: %s" % profile.get("type"))
            return None

    def flash(self):
        self.state.progress = 0
        profile = self.state.profiles.get(self.state.profile)
        if not profile:
            return

        port = self.state.port

        backend = self.getBackend(profile)
        if backend:
            Thread(target=self.thread_watcher, args=[backend.flash, port, profile], daemon=True).start()

    def batch_start(self):
        self.state.batch_old_ports = set(self.state.ports)
        self.state.batch_new_ports = set()
        self.state.batch_working_ports = set()
        self.state.batch_worker = OrderedDict()
        self.state.batch_flash = True
        self.state.batch_flashing = True

    def batch_stop(self):
        self.state.batch_flash = False

    def thread_watcher(self, func, port, profile):
        self.ok = False

        worker = Thread(target=func, args=[self, port, profile], daemon=True)
        self.state.worker = worker
        worker.start()
        worker.join()
        if self.ok:
            print("Done")
            self.state.logs.append("Done")
        else:
            self.state.logs.append("Error")
        self.state.worker = None



if __name__ == "__main__":
    ui = UI()

    if len(sys.argv) > 1:
        ui.loadFile(sys.argv[1])
    elif os.path.exists("manifest/manifest.json"):
        ui.loadFile("manifest/manifest.json")

    ui.run()

