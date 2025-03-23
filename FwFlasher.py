import os
import sys
from threading import Thread
import esptool
import json
from collections import OrderedDict
from PUI.PySide6 import *
import PUI

VERSION = "0.4"

from common import *
from esp import ESPBackend
from bmp import BMPBackend


class UI(Application):
    def __init__(self):
        super().__init__(icon=resource_path("icon.ico"))
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
        self.backend = None

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

                    backend = self.getBackend(self.state.profiles[self.state.profile])
                    if backend and backend.list_ports:
                        backend.precheck(self)

                        Label("Port")
                        with ComboBox(text_model=self.state("port")):
                            ComboBoxItem("Auto")
                            for port in backend.list_ports(self):
                                ComboBoxItem(port)

                    if backend and backend.erase_flash:
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

                if backend and backend.show_mac:
                    with HBox():
                        Label("MAC:")
                        TextField(self.state("mac"))

                if backend and backend.show_progress:
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
                    backend = self.getBackend(profile)
                    if not backend:
                        self.state.logs.append(f"Unsupported chip type \"{profile.get('type')}\" in profile \"{name}\"")
                self.state.profile = list(self.state.profiles.keys())[0]
                self.state.root = os.path.dirname(file)

    def getBackend(self, profile):
        if profile.get("type", "").startswith("esp"):
            return ESPBackend(self)
        elif profile.get("type", "") == "bmp":
            return BMPBackend(self)
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

    manifest_json = "manifest.json"
    if getattr(sys, 'frozen', False):
        manifest_json = os.path.join(sys._MEIPASS, manifest_json)

    if len(sys.argv) > 1:
        ui.loadFile(sys.argv[1])
    elif os.path.exists(manifest_json):
        ui.loadFile(manifest_json)

    ui.run()

