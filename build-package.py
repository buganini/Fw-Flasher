import PyInstaller.__main__
import platform
import subprocess
import os
import sys
import itertools
import glob
import shutil
from FwFlasher import find_arm_none_eabi_gdb

create_dmg = False
codesign_identity = None

pyinstaller_args = []
create_dmg_args = []
if platform.system()=="Darwin":
    pyinstaller_args.extend(["-i", 'resources/icon.icns'])
    subprocess.run(["security", "find-identity", "-v", "-p", "codesigning"])
    codesign_identity = input("Enter the codesign identity \"Developer ID Application: XXXXXX (XXXXXXXXXX)\" (leave empty for no signing): ").strip()
    if codesign_identity:
        create_dmg_args.extend(["--codesign", codesign_identity])
        create_dmg_args.extend(["--notarize", "notarytool-creds"])
    create_dmg = True
else:
    pyinstaller_args.extend(["-i", 'resources/icon.ico'])

# if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
#     shutil.copy(sys.argv[1], "build/manifest.json")
#     pyinstaller_args.extend(["--add-data", "build/manifest.json:."])
# elif os.path.exists("manifest.json"):
#     pyinstaller_args.extend(["--add-data", "manifest.json:."])

arm_none_eabi_gdb = find_arm_none_eabi_gdb()
if arm_none_eabi_gdb:
    pyinstaller_args.extend(["--add-binary", arm_none_eabi_gdb + ":bin"])
else:
    print("arm-none-eabi-gdb not found")
    print("Please download it from https://developer.arm.com/downloads/-/gnu-rm and extract it to the root of the FwFlasher so that arm-none-eabi-gdb is in the gcc-arm-none-eabi-X.Y-Z/bin directory")
    sys.exit(1)

print(pyinstaller_args)

PyInstaller.__main__.run([
    'FwFlasher.py',
    "--onedir",
    "--noconfirm",
    "--windowed",
    "--add-data=resources/icon.ico:.",
    *pyinstaller_args
])

if codesign_identity:
    for path in itertools.chain(
        glob.glob("dist/FwFlasher.app/**/*.so", recursive=True),
        glob.glob("dist/FwFlasher.app/**/bin/*", recursive=True),
        glob.glob("dist/FwFlasher.app/**/*.dylib", recursive=True),
        glob.glob("dist/FwFlasher.app/**/Python3", recursive=True),
        ["dist/FwFlasher.app"],
    ):
        print("codesign", path)
        subprocess.run(["codesign",
            "--sign", codesign_identity,
            "--entitlements", "resources/entitlements.plist",
            "--timestamp",
            "--deep",
            str(path),
            "--force",
            "--options", "runtime"
        ])

if create_dmg:
    if os.path.exists("FwFlasher.dmg"):
        os.unlink("FwFlasher.dmg")
    subprocess.run([
        "create-dmg",
        "--volname", "FwFlasher",
        "--volicon", "resources/icon.icns",
        "--app-drop-link", "0", "0",
        *create_dmg_args,
        "FwFlasher.dmg", "dist/FwFlasher.app"
    ])
    if codesign_identity:
        subprocess.run(["spctl", "-a", "-t", "open", "--context", "context:primary-signature", "-v", "FwFlasher.dmg"])
