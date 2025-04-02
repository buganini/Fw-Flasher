# FW Flasher

## Use case
Engineers deliver firmware and a manifest.json file for all the complicated settings, while other non-technical people perform the firmware flashing with simple clicks.

## Features
* Config with [JSON file](https://github.com/buganini/Fw-Flasher/blob/main/manifest.json)

* Multiple backends
    * esptool
        * type=esp*
    * Black Magic Probe
        * type=bmp
    * OpenOCD
        * type=openocd
        * Currently, only CMSIS-DAP supports device enumeration
    * dfu-util
        * type=dfu
        * Still needs zadig to fix driver issue on windows

* Cross-Platform
    * Linux
    * macOS (tested with M2)
    * Windows x64


## Known Issue
* BlackMagicProbe/OpenOCD backends don't have progressive output due to the limit of pexpect

## Screenshots
![Flashing](screenshots/flashing.png)

## Development

### Extra Dependencies
* Download [Arm GNU Toolchain](https://developer.arm.com/downloads/-/gnu-rm) and extract it to the root of the FwFlather so that `arm-none-eabi-gdb` is in the `gcc-arm-none-eabi-X.Y-Z/bin` directory
* Download [OpenOCD](https://github.com/xpack-dev-tools/openocd-xpack/releases) and extract it to the root of the FwFlasher so that `openocd` is in the `*openocd-X.Y-Z/bin` directory
* Download [dfu-util](https://dfu-util.sourceforge.net/releases/) and extract it to the root of the FwFlasher so that `dfu-util` is in the `dfu-util-X.Y-binaries/osname/` directory