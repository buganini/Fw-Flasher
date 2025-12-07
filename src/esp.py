import os
from threading import Thread

import esptool
import espefuse
import espsecure
import uuid
import gc

from common import *

class ESPBackend(Backend):
    show_mac = True
    show_progress = True
    erase_flash = True

    @staticmethod
    def exec_in_thread(func, args):
        def wrapper(func, args):
            func(args)
        t = Thread(target=wrapper, args=(func, args), daemon=True)
        t.start()
        t.join()

    @staticmethod
    def determine_port(context, profile, port):
        if port == "Auto":
            port = ESPBackend.list_ports(context, profile)[0]
        return port

    @staticmethod
    def flash(context, port, profile):
        context.logs = []

        if not port:
            context.logs.append("Error: Port not found")
            return

        security = profile.get("security", {})

        secure_boot_digest = security.get("secure_boot_digest", "")
        secure_boot_digest_block = security.get("secure_boot_digest_block", "")
        secure_boot_digest_purpose = security.get("secure_boot_digest_purpose", "")
        secure_boot_overwrite_bootloader = security.get("secure_boot_overwrite_bootloader", False)

        flash_encryption_key = security.get("flash_encryption_key", "")
        flash_encryption_key_block = security.get("flash_encryption_key_block", "")
        flash_encryption_key_purpose = security.get("flash_encryption_key_purpose", "")

        secure_boot_settings = [secure_boot_digest, secure_boot_digest_block, secure_boot_digest_purpose]
        flash_encryption_settings = [flash_encryption_key, flash_encryption_key_block, flash_encryption_key_purpose]


        flash_encryption_key_generated = False

        if any(secure_boot_settings):
            if secure_boot_digest:
                if not os.path.isabs(secure_boot_digest):
                    secure_boot_digest = os.path.join(context.main.manifest_dir, secure_boot_digest)
                if not os.path.exists(secure_boot_digest):
                    context.logs.append(f"Error: Secure boot digest file not found: {secure_boot_digest}")
                    return
            else:
                context.logs.append(f"Error: Secure boot digest is not set")
                return

        loader = esptool.cmds.detect_chip(port)
        secinfo = loader.get_security_info()
        initial_flash_encryption_enabled = bool(secinfo["flash_crypt_cnt"] & 1)
        initial_secure_boot_enabled = secinfo["parsed_flags"]["SECURE_BOOT_EN"]
        secinfo = None
        loader = None
        gc.collect()

        context.logs.append("Security status:")
        context.logs.append(f"Flash encryption: {initial_flash_encryption_enabled}")
        context.logs.append(f"Secure Boot: {initial_secure_boot_enabled}")

        if any(flash_encryption_settings):
            if flash_encryption_key:
                if not os.path.isabs(flash_encryption_key):
                    flash_encryption_key = os.path.join(context.main.manifest_dir, flash_encryption_key)
                if not os.path.exists(flash_encryption_key):
                    context.logs.append(f"Error: Secure boot digest file not found: {flash_encryption_key}")
                    return
            elif flash_encryption_key == "":
                if not initial_flash_encryption_enabled:
                    flash_encryption_key = os.path.join(context.main.temp_dir, uuid.uuid4().hex)
                    cmd = [
                        "generate-flash-encryption-key",
                        flash_encryption_key
                    ]
                    context.logs.append("espsecure " + " ".join(cmd))
                    flash_encryption_key_generated = True
                    try:
                        ESPBackend.exec_in_thread(espsecure.main, cmd)
                        context.logs.append("espsecure generate-flash-encryption-key done")
                    except Exception as e:
                        import traceback
                        context.ok = False
                        context.progress = 0
                        context.logs.append(f"Error: {e}")
                        context.logs.append(f"Error: {traceback.format_exc()}")
                        traceback.print_exc()
                        return
            else:
                context.logs.append(f"Error: Flash encryption key is not set")
                return

        if profile.get("type") == "esp32c2":
            context.logs.append(f"Error: eFuse combination for ESP32-C2 is not implemented")
            return

        # refresh
        secure_boot_settings = [secure_boot_digest, secure_boot_digest_block, secure_boot_digest_purpose]
        flash_encryption_settings = [flash_encryption_key, flash_encryption_key_block, flash_encryption_key_purpose]

        manual_flash_encryption = False
        auto_flash_encryption = False
        flash_erased = False

        if any(flash_encryption_settings) and initial_flash_encryption_enabled:
            auto_flash_encryption = True

        if all(flash_encryption_settings) and not initial_flash_encryption_enabled:
            manual_flash_encryption = True
            try:
                loader = esptool.cmds.detect_chip(port)
                esptool.cmds.erase_flash(loader)
                flash_erased = True
            except:
                pass
            loader = None
            gc.collect()
            print("esptool erase-flash done")

            cmd = [
                "--port", port,
                "--do-not-confirm",
                "burn-key", flash_encryption_key_block, flash_encryption_key, flash_encryption_key_purpose
            ]
            context.logs.append("espefuse " + " ".join(cmd))
            context.ok = True
            try:
                ESPBackend.exec_in_thread(espefuse.main, cmd)
                context.logs.append("espefuse burn-key for flash_encryption_key done")
            except Exception as e:
                import traceback
                context.ok = False
                context.progress = 0
                context.logs.append(f"Error: {e}")
                context.logs.append(f"Error: {traceback.format_exc()}")
                traceback.print_exc()
                return

            cmd = [
                "--port", port,
                "--do-not-confirm",
                "burn-efuse",
                "SPI_BOOT_CRYPT_CNT", "7"
            ]
            context.logs.append("espefuse " + " ".join(cmd))
            context.ok = True
            try:
                ESPBackend.exec_in_thread(espefuse.main, cmd)
                context.logs.append("espefuse burn-efuse for flash_encryption_key done")
            except Exception as e:
                import traceback
                context.ok = False
                context.progress = 0
                context.logs.append(f"Error: {e}")
                context.logs.append(f"Error: {traceback.format_exc()}")
                traceback.print_exc()

        if all(secure_boot_settings):
            if not initial_secure_boot_enabled:
                cmd = [
                    "--port", port,
                    "--do-not-confirm",
                    "burn-key", secure_boot_digest_block, secure_boot_digest, secure_boot_digest_purpose
                ]
                context.logs.append("espefuse " + " ".join(cmd))
                context.ok = True
                try:
                    ESPBackend.exec_in_thread(espefuse.main, cmd)
                    context.logs.append("espefuse burn-key for secure_boot_digest done")
                except Exception as e:
                    import traceback
                    context.ok = False
                    context.progress = 0
                    context.logs.append(f"Error: {e}")
                    context.logs.append(f"Error: {traceback.format_exc()}")
                    traceback.print_exc()
                    return

        context.logs.append("Download encryption status:")
        context.logs.append(f"Auto encryption: {auto_flash_encryption}")
        context.logs.append(f"Manual encryption: {manual_flash_encryption}")

        cmd = [*ARGV0, "esptool"]
        cmd.extend(["--port", port])
        cmd.extend(["--chip", profile.get("type")])
        cmd.extend(["-b", profile.get("baudrate", "460800")])
        cmd.extend([f"--before={profile.get('before', 'default_reset')}"])
        cmd.extend([f"--after={profile.get('after', 'hard_reset')}"])
        if profile.get("no-stub", False) or auto_flash_encryption:
            cmd.extend(["--no-stub"])
        cmd.extend(["write-flash"])
        if context.main.state.erase_flash and profile.get("erase-flash") != "disabled" and not flash_erased and not (initial_secure_boot_enabled and not secure_boot_overwrite_bootloader):
            cmd.extend(["--erase-all"])
            if auto_flash_encryption:
                cmd.extend(["--force"])
        cmd.extend(["--flash-mode", profile.get("flash-mode", "dio")])
        cmd.extend(["--flash-freq", profile.get("flash-freq", "80m")])
        cmd.extend(["--flash-size", profile.get("flash-size", "4MB")])
        if auto_flash_encryption:
            cmd.extend(["--encrypt", "--force"])
        progress_map = {}
        flash_parts_num = 0
        for offset, file in profile.get("write-flash", []):
            if os.path.isabs(file):
                pass
            else:
                file = os.path.join(context.main.state.root, file)
            if not os.path.exists(file):
                context.logs.append(f"Error: File not found: {file}")
                return
            if manual_flash_encryption:
                encrypted_file = os.path.join(context.main.temp_dir, uuid.uuid4().hex)
                try:
                    ESPBackend.exec_in_thread(espsecure.main, [
                        "encrypt-flash-data",
                        "--aes_xts",
                        "--keyfile", flash_encryption_key,
                        "--address", offset,
                        "--output", encrypted_file,
                        file
                    ])
                    # context.logs.append(f"espsecure encrypt-flash-data {file} done")
                except Exception as e:
                    import traceback
                    context.ok = False
                    context.progress = 0
                    context.logs.append(f"Error: {e}")
                    context.logs.append(f"Error: {traceback.format_exc()}")
                    traceback.print_exc()
                    return
                cmd.extend([offset, encrypted_file])
                progress_map[int(offset, 0)] = flash_parts_num
                flash_parts_num += 1
            else:
                if auto_flash_encryption and int(offset, 0) < 0x8000 and not secure_boot_overwrite_bootloader:
                    continue
                cmd.extend([offset, file])
                progress_map[int(offset, 0)] = flash_parts_num
                flash_parts_num += 1

        cmd = [str(x) for x in cmd]
        print(" ".join(f"\"{x}\"" for x in cmd))
        # context.logs.append("esptool " + " ".join(cmd))
        context.ok = True

        flash_parts_progress = 0
        try:
            for line in spawn(cmd):
                m = re.search(r"Writing at (0x[0-9a-fA-F]+)\s*\[.*?\].*?%\s*(\d+)/(\d+)\s*bytes", line)
                if m:
                    offset = int(m.group(1), 0)
                    if offset in progress_map:
                        flash_parts_progress = progress_map[offset]
                    a = int(m.group(2), 0)
                    b = int(m.group(3), 0)
                    context.progress = int(flash_parts_progress / flash_parts_num * 100) + int(a / b * 100) / flash_parts_num
                m = re.search(r"MAC:\s*([0-9a-fA-F:]+)", line)
                if m:
                    context.mac = m.group(1)
                if "Error" in line:
                    context.ok = False
                    context.progress = 0
                    context.logs.append(line)
                    return

            if context.ok:
                context.progress = 100
        except Exception as e:
            import traceback
            context.ok = False
            context.progress = 0
            context.logs.append(f"Error: {e}")
            context.logs.append(f"Error: {traceback.format_exc()}")
            traceback.print_exc()

        if flash_encryption_key_generated:
            os.remove(flash_encryption_key)

        efuse = profile.get("efuse", [])
        if efuse:
            cmd = [
                "--port", port,
                "--do-not-confirm",
                "burn-efuse"
            ]
            for key, value in efuse:
                cmd.append(key)
                cmd.append(value)
            context.logs.append(f"EFUSE: {efuse}")
            context.logs.append("espefuse " + " ".join(cmd))
            context.ok = True
            try:
                ESPBackend.exec_in_thread(espefuse.main, cmd)
                context.logs.append("espefuse burn-efuse done")
            except Exception as e:
                import traceback
                context.ok = False
                context.progress = 0
                context.logs.append(f"Error: {e}")
                context.logs.append(f"Error: {traceback.format_exc()}")
                traceback.print_exc()

        write_protect_efuse = profile.get("write-protect-efuse", [])
        if write_protect_efuse:
            cmd = []
            cmd.extend(["--port", port])
            cmd.append("--do-not-confirm")
            cmd.append("write-protect-efuse")
            for key in write_protect_efuse:
                cmd.append(key)
            context.logs.append("espefuse " + " ".join(cmd))
            ESPBackend.exec_in_thread(espefuse.main, cmd)