import PyInstaller.__main__
import platform
import subprocess
import os
import sys
import itertools
import glob
import shutil

create_dmg = False
codesign_identity = None

pyinstaller_args = []
create_dmg_args = []
if platform.system()=="Darwin":
    # pyinstaller_args.extend(["-i", 'resources/icon.icns'])
    subprocess.run(["security", "find-identity", "-v", "-p", "codesigning"])
    codesign_identity = input("Enter the codesign identity \"Developer ID Application: XXXXXX (XXXXXXXXXX)\" (leave empty for no signing): ").strip()
    if codesign_identity:
        create_dmg_args.extend(["--codesign", codesign_identity])
        create_dmg_args.extend(["--notarize", "notarytool-creds"])
    create_dmg = True
# else:
#     pyinstaller_args.extend(["-i", 'resources/icon.ico'])

if len(sys.argv) > 1 and sys.argv[1].endswith(".json"):
    shutil.copy(sys.argv[1], "build/manifest.json")
    pyinstaller_args.extend(["--add-data", "build/manifest.json:."])
elif os.path.exists("manifest.json"):
    pyinstaller_args.extend(["--add-data", "manifest.json:."])

print(pyinstaller_args)

PyInstaller.__main__.run([
    'fw-flasher.py',
    "--onedir",
    "--noconfirm",
    "--windowed",
    # "--icon=resources/icon.ico",
    # "--add-data=resources/icon.ico:.",
    *pyinstaller_args
])

if codesign_identity:
    for path in itertools.chain(
        glob.glob("dist/fw-flasher.app/**/*.so", recursive=True),
        glob.glob("dist/fw-flasher.app/**/*.dylib", recursive=True),
        glob.glob("dist/fw-flasher.app/**/Python3", recursive=True),
        ["dist/fw-flasher.app"],
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
    if os.path.exists("fw-flasher.dmg"):
        os.unlink("fw-flasher.dmg")
    subprocess.run([
        "create-dmg",
        "--volname", "fw-flasher",
        # "--volicon", "resources/icon.icns",
        "--app-drop-link", "0", "0",
        *create_dmg_args,
        "fw-flasher.dmg", "dist/fw-flasher.app"
    ])
    if codesign_identity:
        subprocess.run(["spctl", "-a", "-t", "open", "--context", "context:primary-signature", "-v", "fw-flasher.dmg"])
