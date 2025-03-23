import sys
import os
import re
import glob
import serial

def strip(s):
    s = re.sub(r'\x1b\[[0-9;]*m', '', s)
    s = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', s)
    return s

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath("resources")

    return os.path.join(base_path, relative_path)

class Backend():
    show_mac = False
    show_progress = False

    def __init__(self, main):
        self.main = main

    def list_ports(self, main):
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

    def precheck(self, main):
        pass

    def flash(self, main, port, profile):
        pass

    def erase_flash(self, main, port, profile):
        pass

