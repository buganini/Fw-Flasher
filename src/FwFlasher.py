import os
import sys
from threading import Thread
import esptool
import json
from collections import OrderedDict
from PUI.PySide6 import *
import PUI
import tempfile
import atexit
import shutil
import esptool

VERSION = "0.8"

from common import *
from bmp import BMPBackend
from dfu import DFUBackend
from esp import ESPBackend
from openocd import OpenOCDBackend
from py_ocd import PyOCDBackend

class TaskContext(StateObject):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.port = None
        self.done = False
        self.ok = True
        self.mac = ""
        self.progress = 0
        self.logs = []

class UI(Application):
    def __init__(self):
        super().__init__(icon=resource_path("icon.ico"))
        self.temp_dir = tempfile.mkdtemp(prefix="fw_flasher_")
        atexit.register(self.cleanup)

        self.state = state = State()
        self.state.port = ""
        self.state.profile = ""
        self.state.profiles = {}
        self.state.root = ""
        self.state.worker = None
        self.state.init_ports = set()
        self.state.working_ports = set()
        self.state.idle_ports = set()
        self.state.batch_worker = OrderedDict()
        self.state.batch_flash = False
        self.state.erase_flash = False
        self.state.ports = []
        self.state.batch_context = []
        self.state.focus = None

        self.context = TaskContext(self)

        self.manifest_dir = None
        self.backend = None

        Thread(target=self.ports_watcher, daemon=True).start()

    def cleanup(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def ports_watcher(self):
        while True:
            try:
                profile = self.state.profiles.get(self.state.profile)
                if profile:
                    backend = self.getBackend(profile)
                    if backend and backend.list_ports:
                        ports = backend.list_ports(self.context, self.state.profiles[self.state.profile])
                    else:
                        ports = []
                    self.state.ports = ports
                    if self.state.batch_flash:
                        current_ports = set(ports)
                        removed_ports = (self.state.init_ports | self.state.working_ports | self.state.idle_ports) - current_ports

                        new_ports = current_ports - self.state.init_ports - self.state.working_ports - self.state.idle_ports
                        # print("Removed ports: ", removed_ports)
                        # print("New ports: ", new_ports)

                        for p in removed_ports:
                            try:
                                self.state.idle_ports.remove(p)
                            except KeyError:
                                pass
                            try:
                                self.state.working_ports.remove(p)
                            except KeyError:
                                pass
                            try:
                                self.state.init_ports.remove(p)
                            except KeyError:
                                pass
                        self.state.batch_context = [c for c in self.state.batch_context if c.port not in removed_ports]

                        for p in new_ports:
                            self.state.working_ports.add(p)
                            Thread(target=self.batch_worker, args=[profile, backend, p], daemon=True).start()

                        self.state.init_ports -= removed_ports
                        self.state.working_ports -= removed_ports
                        self.state.idle_ports -= removed_ports
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

                    if self.state.profile:
                        if self.backend:
                            if self.backend.erase_flash and self.state.profiles[self.state.profile].get("erase-flash") != "disabled":
                                Checkbox("Erase Flash", self.state("erase_flash"))
                        if self.state.worker is None and not self.state.batch_flash:
                            Button("Flash (Enter)").click(lambda e: self.flash())
                            Button("Batch Flash").click(lambda e: self.batch_start())
                        elif self.state.batch_flash:
                            Button("Stop").click(lambda e: self.batch_stop())

                    Spacer()

                    if self.state.profiles and self.state.worker is None and not self.state.batch_flash:
                        Button("Load Manifest").click(lambda e: self.load_manifest())

                with HBox():
                    Label("Description:")

                    if self.state.profile:
                        desc = self.state.profiles[self.state.profile]["description"]
                        Label(desc)

                    Spacer()

                print("refresh")
                if self.state.batch_flash:
                    with Scroll().layout(weight=1):
                        with VBox():
                            for context in self.state.batch_context:
                                print(context.port)
                                with HBox():
                                    Label(context.port)
                                    if self.backend and self.backend.show_mac:
                                        Label("MAC:")
                                        TextField(context("mac"))
                                    ProgressBar(progress=context.progress, maximum=100).layout(weight=1)
                                    Label("Done" if context.done and context.ok else ("" if context.ok else "Error"))
                                    Button("Logs").click(lambda e, context: self.set_focus(context), context)
                            if self.state.focus:
                                Label(context.port)
                                with Scroll().layout(weight=1).scrollY(Scroll.END):
                                    Text("\n".join(self.state.focus.logs))
                            else:
                                Spacer()
                else:
                    if self.backend and self.backend.show_mac:
                        with HBox():
                            Label("MAC:")
                            TextField(self.context("mac"))

                    if self.backend and self.backend.show_progress:
                        ProgressBar(progress=self.context.progress, maximum=100)
                    with Scroll().layout(weight=1).scrollY(Scroll.END):
                        Text("\n".join(self.context.logs))


    def set_focus(self, context):
        self.state.focus = context

    def keypress(self, e):
        if e.text == "\r":
            self.flash()

    def changeProfile(self, e):
        backend = self.getBackend(self.state.profiles[self.state.profile])
        if backend and backend != self.backend:
            self.context.logs = []
            backend.precheck(self)
            self.backend = backend
            self.state.port = "Auto"
        self.state.erase_flash = self.state.profiles[self.state.profile].get("erase-flash", False)

    def load_manifest(self):
        file = OpenFile("Open Manifest", types="Manifest JSON (*.json)|.*json", dir=self.manifest_dir)
        if file:
            self.loadFile(file)

    def loadFile(self, file):
        self.context.logs = []
        with open(file, "r") as f:
            self.state.profiles = json.load(f, object_pairs_hook=OrderedDict)
            use_bmp = False
            if self.state.profiles:
                self.manifest_dir = os.path.dirname(file)
                for name, profile in self.state.profiles.items():
                    backend = self.getBackend(profile)
                    if not backend:
                        self.context.logs.append(f"Unsupported chip type \"{profile.get('type')}\" in profile \"{name}\"")
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
        self.context.progress = 0
        profile = self.state.profiles.get(self.state.profile)
        if not profile:
            return

        port = self.state.port

        backend = self.getBackend(profile)
        if backend:
            Thread(target=self.thread_watcher, args=[backend.flash, self.context, port, profile, backend], daemon=True).start()

    def batch_start(self):
        self.state.init_ports = set(self.state.ports)
        self.state.batch_new_ports = set()
        self.state.working_ports = set()
        self.state.batch_worker = OrderedDict()
        self.state.batch_flash = True

    def batch_stop(self):
        self.state.batch_flash = False

    def batch_worker(self, profile, backend, port):
        context = TaskContext(self)
        context.port = port
        self.state.batch_context.append(context)
        t = Thread(target=self.thread_watcher, args=[backend.flash, context, port, profile, backend], daemon=True)
        t.start()
        t.join()

    def thread_watcher(self, func, context, port, profile, backend):
        port = backend.determine_port(context, profile, port)
        self.state.working_ports.add(port)
        self.ok = False

        worker = Thread(target=func, args=[context, port, profile], daemon=True)
        self.state.worker = worker
        worker.start()
        worker.join()
        if self.ok:
            print("Done")
            self.context.logs.append("Done")
        else:
            self.context.logs.append("Error")
        self.state.worker = None
        self.state.idle_ports.add(port)
        self.state.working_ports.remove(port)



if __name__ == "__main__":
    ui = UI()

    if len(sys.argv) > 1:
        if sys.argv[1] == "esptool":
            esptool.main(sys.argv[2:])
            sys.exit(0)
        else:
            ui.loadFile(sys.argv[1])
    elif os.path.exists("manifest/manifest.json"):
        ui.loadFile("manifest/manifest.json")

    ui.run()

