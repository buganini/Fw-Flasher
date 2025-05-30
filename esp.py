import os
from threading import Thread

import esptool

from common import *

class ESPBackend(Backend):
    show_mac = True
    show_progress = True

    @staticmethod
    def flash(main, port, profile):
        from esptool.logger import log, TemplateLogger

        if hasattr(log, "set_logger"):
            class CustomLogger(TemplateLogger):
                def print(self, message="", *args, **kwargs):
                    print(f"{message}", *args, **kwargs)
                    ui_changed = False
                    if not message.startswith("Writing at"):
                        main.state.logs.append(message)
                        ui_changed = True
                    if message.startswith("MAC: "):
                        main.state.mac = message.split("MAC: ")[1].strip()
                        ui_changed = True
                    if ui_changed:
                        main.wait()

                def note(self, message):
                    self.print(f"NOTE: {message}")

                def warning(self, message):
                    self.print(f"WARNING: {message}")

                def error(self, message):
                    self.print(message, file=sys.stderr)

                def stage(self, finish=False):
                    # Collapsible stages not needed in this example
                    pass

                def progress_bar(
                    self,
                    cur_iter,
                    total_iters,
                    prefix = "",
                    suffix = "",
                    bar_length: int = 30,
                ):
                    percent = int(100 * (cur_iter / float(total_iters)))
                    main.state.progress = percent
                    main.wait()

            log.set_logger(CustomLogger())

        main.state.logs = []

        if port == "Auto":
            port = ESPBackend.list_ports(main, profile)[0]

        if not port:
            main.state.logs.append("Error: Port not found")
            return

        cmd = []
        cmd.extend(["--port", port])
        cmd.extend(["--chip", profile.get("type")])
        cmd.extend(["-b", profile.get("baudrate", "460800")])
        cmd.extend([f"--before={profile.get('before', 'default_reset')}"])
        cmd.extend([f"--after={profile.get('after', 'hard_reset')}"])
        if profile.get("no-stub", False):
            cmd.extend(["--no-stub"])
        cmd.extend(["write-flash"])
        if main.state.erase_flash:
            cmd.extend(["-e"])
        cmd.extend(["--flash-mode", profile.get("flash-mode", "dio")])
        cmd.extend(["--flash-freq", profile.get("flash-freq", "80m")])
        cmd.extend(["--flash-size", profile.get("flash-size", "4MB")])
        for offset, file in profile.get("write-flash", []):
            if os.path.isabs(file):
                pass
            else:
                file = os.path.join(main.state.root, file)
            if not os.path.exists(file):
                main.state.logs.append(f"Error: File not found: {file}")
                return
            cmd.extend([offset, file])
        cmd = [str(x) for x in cmd]
        print(cmd)
        main.state.logs.append("esptool.py " + " ".join(cmd))
        main.ok = True
        try:
            esptool.main(cmd)
            print("esptool.main() done")
        except Exception as e:
            import traceback
            main.ok = False
            main.state.logs.append(f"Error: {e}")
            main.state.logs.append(f"Error: {traceback.format_exc()}")
            traceback.print_exc()
