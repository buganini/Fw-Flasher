# Sample
``` json
{
    "description": "STM32 U5",
    "type": "openocd",
    "interface": "stlink.cfg",
    "target": "stm32u5x.cfg",
    "before": [
        "reset halt"
    ],
    "after": [
        "reset halt",
        "reset run"
    ],
    "programs": [
        "bootloader.hex",
        "firmware.hex"
    ]
}
```

``` json
{
    "description": "[OpenOCD/ST-Link] STM32 Controller",
    "type": "openocd",
    "interface": "stlink.cfg",
    "target": "stm32f1x.cfg",
    "before": [
        "reset halt",
        "stm32f1x unlock 0"
    ],
    "after": [
        "reset halt",
        "stm32f1x lock 0",
        "reset run"
    ],
    "programs": [
        "bootloader.hex",
        ["firmware.bin", "0x08000000"]
    ]
}
```

# Arguments
* interface

    Passed to OpenOCD with `-f`
* target

    Passed to OpenOCD with `-f`
* before

    List of commands to run with `-c` before flashing
* after

    List of commands to run with `-c` after flashing
* programs

    List of files to flash; each file is either a `.hex` file or a file with a programming address