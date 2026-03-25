import json
import requests
import logging
import hashlib
import uuid
import os
import platform
from config import Config
from bot_state import BotStateStore

logger = logging.getLogger("tradebot.license")

class LicenseManager:
    @staticmethod
    def get_machine_id() -> str:
        """
        Generates a unique hardware fingerprint for the current machine.
        This ensures a license is tied to a single user.
        """
        try:
            # Combine machine architecture, node name, and a unique system-level ID
            machine_info = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
            
            # On MacOS/Linux, we can use a more stable ID if available
            system_id = ""
            if platform.system() == "Darwin":
                # For Mac, we use the serial number or hardware UUID if possible
                import subprocess
                cmd = "system_profiler SPHardwareDataType | grep 'Hardware UUID' | awk '{print $3}'"
                system_id = subprocess.check_output(cmd, shell=True).decode().strip()
            elif platform.system() == "Linux":
                if os.path.exists("/etc/machine-id"):
                    with open("/etc/machine-id", "r") as f:
                        system_id = f.read().strip()
            
            fingerprint = f"{machine_info}-{system_id}"
            return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
        except Exception as e:
            logger.warning(f"Could not generate hardware fingerprint, using fallback: {e}")
            return hashlib.sha256(platform.node().encode()).hexdigest()[:16]

    @staticmethod
    def verify_license() -> bool:
        """
        Checks the remote LICENSE_URL to see if this bot's LICENSE_ID is still authorized.
        Also verifies the machine-binding to prevent license sharing.
        """
        # Step 1: Check Hardware Binding (Anti-Sharing)
        current_machine = LicenseManager.get_machine_id()
        store = BotStateStore(Config.BOT_STATE_FILE)
        state = store.load()
        
        bound_machine = state.get("licensed_machine_id")
        
        # If it's already activated, check if the hardware matches
        if bound_machine and bound_machine != current_machine:
            logger.critical("LICENSE VIOLATION: Bot is being shared or moved to unauthorized hardware.")
            LicenseManager._set_revoked(True, "Machine ID mismatch. License is bound to another device.")
            return False

        if not Config.LICENSE_URL:
            logger.warning("LICENSE_URL not set. Skipping remote verification.")
            return True

        try:
            # Handle local file:// URLs for testing
            if Config.LICENSE_URL.startswith("file://"):
                file_path = Config.LICENSE_URL[7:]
                with open(file_path, "r") as f:
                    data = json.load(f)
            else:
                # We expect a JSON from the server
                response = requests.get(Config.LICENSE_URL, timeout=10)
                response.raise_for_status()
                data = response.json()

            # Logic 1: Global kill switch
            if data.get("status") == "REVOKED_GLOBAL":
                logger.critical("GLOBAL LICENSE REVOCATION DETECTED.")
                LicenseManager._set_revoked(True, "Global revocation triggered.")
                return False

            # Logic 2: ID-based status and machine binding on server
            ids_status = data.get("ids", {})
            license_entry = ids_status.get(Config.LICENSE_ID)
            
            if license_entry:
                if isinstance(license_entry, dict):
                    # Check status
                    if license_entry.get("status") == "REVOKED":
                        logger.critical(f"LICENSE STATUS: REVOKED for ID: {Config.LICENSE_ID}")
                        LicenseManager._set_revoked(True, f"License ID {Config.LICENSE_ID} revoked.")
                        return False
                    
                    # Check server-side machine binding
                    server_machine_id = license_entry.get("machine_id")
                    if server_machine_id and server_machine_id != current_machine:
                        logger.critical(f"LICENSE VIOLATION: Server reports this ID is bound to {server_machine_id}")
                        LicenseManager._set_revoked(True, "Remote machine ID mismatch.")
                        return False
                elif license_entry == "REVOKED":
                    logger.critical(f"LICENSE STATUS: REVOKED for ID: {Config.LICENSE_ID}")
                    LicenseManager._set_revoked(True, f"License ID {Config.LICENSE_ID} revoked.")
                    return False

            # Logic 3: Specific ID revocation list
            revoked_ids = data.get("revoked_ids", [])
            if Config.LICENSE_ID in revoked_ids:
                logger.critical(f"LICENSE REVOKED for ID: {Config.LICENSE_ID}")
                LicenseManager._set_revoked(True, f"License ID {Config.LICENSE_ID} in revocation list.")
                return False

            # If we're here, the license is still valid according to the server
            LicenseManager._set_revoked(False, "License verification successful.")
            
            # If not already bound locally, bind it now
            if not bound_machine:
                state["licensed_machine_id"] = current_machine
                store.save(state)
                logger.info(f"License ID {Config.LICENSE_ID} successfully bound to this machine.")
                
            return True

        except Exception as e:
            logger.error(f"Failed to verify license remotely: {e}")
            return True

    @staticmethod
    def _set_revoked(is_revoked: bool, reason: str):
        store = BotStateStore(Config.BOT_STATE_FILE)
        state = store.load()
        if state.get("license_revoked") != is_revoked:
            state["license_revoked"] = is_revoked
            if is_revoked:
                state["kill_switch_active"] = True
                state["enabled"] = False
                logger.critical(f"AUTO-KILL TRIGGERED: {reason}")
            store.save(state)
            store.log_action("LICENSE_STATUS_CHANGE", f"revoked={is_revoked}, reason={reason}")
