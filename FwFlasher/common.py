import sys
import os
import re
import glob
import serial
import subprocess
import json

try:
    base_path = sys._MEIPASS
    ARGV0 = [sys.argv[0]]
except Exception:
    ARGV0 = [sys.executable, sys.argv[0]]

def spawn(command, print_output=True, **kwargs):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        text=True,
        bufsize=1,
        **kwargs
    )

    # Read output line by line and print simultaneously
    for line in process.stdout:
        if sys.stdout: # sometimes None on Windows
            sys.stdout.flush()   # Force immediate output
        line = line.rstrip("\r\n")
        if print_output:
            print(line)
        yield line

    # Wait for process to complete and get return code
    return_code = process.wait()

    return return_code

def spawn_gdbmi(command):
    for line in spawn(command):
        if line:
            if line[0] in "@~&":
                yield json.loads(line[1:]).rstrip("\r\n")
            elif line[0] in "=":
                continue
            else:
                yield line
        else:
            yield ""

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
    erase_flash = False

    @staticmethod
    def determine_port(context, profile, port):
        return port

    @staticmethod
    def list_ports(context, profile):
        result = []
        working_ports = context.main.state.working_ports

        if sys.platform.startswith('win'):
            from serial.tools import list_ports
            ports = list_ports.comports()
            ports = [p.name for p in ports if p.vid]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = [p for p in glob.glob('/dev/tty.*') if all([b not in p for b in ["Bluetooth", "debug"]])]
        else:
            raise EnvironmentError('Unsupported platform')

        for port in ports:
            if port in working_ports:
                result.append(port)
                continue
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        return result

    @staticmethod
    def precheck(context):
        pass

    @staticmethod
    def flash(context, port, profile):
        pass
