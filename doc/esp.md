# Sample
Simple usage
``` json
{
    "description": "[EspTool] ESP32C3 Blink",
    "type": "esp32c3",
    "erase-flash": false,
    "baudrate": 460800,
    "before": "default-reset",
    "after": "hard-reset",
    "no-stub": false,
    "flash-mode": "dio",
    "flash-size": "2MB",
    "flash-freq": "80m",
    "write-flash": [
        ["0x0", "blink/bootloader.bin"],
        ["0x8000", "blink/partition-table.bin"],
        ["0x10000", "blink/blink.bin"]
    ]
}
```

With Secure Boot and Flash Encryption
``` json
{
    "description": "[EspTool] ESP32C3 Blink with flash encryption + secure boot enabled externally",
    "type": "esp32c3",
    "erase-flash": false,
    "baudrate": 460800,
    "before": "default-reset",
    "after": "hard-reset",
    "no-stub": false,
    "flash-mode": "dio",
    "flash-size": "2MB",
    "flash-freq": "80m",
    "write-flash": [
        ["0x0", "blink/bootloader.bin"],
        ["0x8000", "blink/partition-table.bin"],
        ["0x10000", "blink/blink.bin"]
    ],
    "security": {
        "flash_encryption_key": "", // Leave empty to generate a random key
        "flash_encryption_key_block": "BLOCK_KEY0", 
        "flash_encryption_key_purpose": "XTS_AES_128_KEY",
        "secure_boot_overwrite_bootloader": false,
        "secure_boot_digest": "credentials/secure_boot_digest.bin",
        "secure_boot_digest_block": "BLOCK_KEY1",
        "secure_boot_digest_purpose": "SECURE_BOOT_DIGEST0"
    },
    "efuse": [
        ["DIS_DOWNLOAD_ICACHE", "1"],
        ["DIS_DIRECT_BOOT", "1"],
        ["DIS_USB_JTAG", "1"],
        ["DIS_PAD_JTAG", "1"],
        ["SECURE_BOOT_EN", "1"]
    ],
    "write-protect-efuse": ["DIS_ICACHE"]
}
```

# Notice
Secure Boot and Flash Encryption functions are only tested with esp32c3, following
https://docs.espressif.com/projects/esp-idf/en/stable/esp32c3/security/flash-encryption.html

# Arguments
* write-flash

`flash` or `encrypted-flash` according to security settings

* security

configure security accordingly

* efuse

extra efuses to burn after programming
* write-protect-efuse

efuses to lock permanently