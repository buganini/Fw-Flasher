# Sample
``` json
{
    "description": "[PyOCD] NRF91 modem/app firmware",
    "type": "pyocd",
    "target": "nrf91",
    "frequency": 1000000,
    "commands": [
        ["nrf91-update-modem-fw", "mfw_nrf91x1_2.0.2.zip"],
        ["load", "nrf9151_slm.hex"]
    ]
}
```

# Arguments
* target

    Passed to PyOCD with `-t`
* frequency

    optional

* commands

    currently support `load` and `nrf91-update-modem-fw`
