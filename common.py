import sys
import os
import re
import glob
import serial
import pexpect

if sys.platform.startswith('win'):
    from pexpect.popen_spawn import PopenSpawn
    spawn = PopenSpawn
else:
    def spawn(cmd, timeout=30):
        pexpect(cmd[0], cmd[1:], timeout=timeout)


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

    @staticmethod
    def list_ports(main, profile):
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

    @staticmethod
    def precheck(main):
        pass

    @staticmethod
    def flash(main, port, profile):
        pass

    @staticmethod
    def erase_flash(main, port, profile):
        pass

