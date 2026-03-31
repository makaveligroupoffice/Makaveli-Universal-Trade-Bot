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
    def verify_license(store: BotStateStore | None = None) -> bool:
        """
        Checks the remote LICENSE_URL to see if this bot's LICENSE_ID is still authorized.
        Also verifies the machine-binding to prevent license sharing.
        """
        # Step 1: Check Hardware Binding (Anti-Sharing)
        current_machine = LicenseManager.get_machine_id()
        if not store:
            store = BotStateStore(Config.BOT_STATE_FILE)
        state = store.load()
        
        bound_machine = state.get("licensed_machine_id")
        
        # If we have a license_id mismatch between state and config, we might need a reset
        # but let's stick to hardware first.
        
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
                LicenseManager._set_revoked(True, "Global revocation triggered.", store)
                return False

            # Logic 2: ID-based status and machine binding on server
            ids_status = data.get("ids", {})
            license_entry = ids_status.get(Config.LICENSE_ID)
            
            if not license_entry:
                # If the ID isn't in the server's list, we don't necessarily revoke it
                # but we should be cautious. For now, we'll allow it if it's already bound.
                if bound_machine and bound_machine != current_machine:
                    logger.critical("LICENSE VIOLATION: Bot is being shared or moved to unauthorized hardware.")
                    LicenseManager._set_revoked(True, "Machine ID mismatch. License is bound to another device.", store)
                    return False
                return True

            if isinstance(license_entry, dict):
                status = license_entry.get("status", "OK").upper()
                server_machine_id = license_entry.get("machine_id")
                
                if status == "REVOKED":
                    logger.critical(f"LICENSE STATUS: REVOKED for ID: {Config.LICENSE_ID}")
                    LicenseManager._set_revoked(True, f"License ID {Config.LICENSE_ID} revoked.", store)
                    return False
                
                if status == "PENDING":
                    # This allows a license to be bound to the NEXT machine that uses it
                    logger.info(f"License ID {Config.LICENSE_ID} is PENDING. Binding to this machine.")
                    state["licensed_machine_id"] = current_machine
                    store.save(state)
                    # We should also notify the server to update the machine_id if possible
                    # but for now, we just proceed.
                    return True

                if status == "RESET":
                    # Server requested a reset of the hardware binding
                    logger.warning(f"License ID {Config.LICENSE_ID} reset requested by server. Re-binding.")
                    state["licensed_machine_id"] = current_machine
                    store.save(state)
                    return True

                # Check server-side machine binding
                if server_machine_id and server_machine_id != current_machine:
                    # IF the server says it's bound to X, and we are Y, it's a violation.
                    # UNLESS the local state is already bound to Y and the server is just behind?
                    # No, server is source of truth for anti-sharing.
                    logger.critical(f"LICENSE VIOLATION: Server reports this ID is bound to {server_machine_id}")
                    LicenseManager._set_revoked(True, "Remote machine ID mismatch.", store)
                    return False
            
            elif isinstance(license_entry, str):
                if license_entry.upper() == "REVOKED":
                    logger.critical(f"LICENSE STATUS: REVOKED for ID: {Config.LICENSE_ID}")
                    LicenseManager._set_revoked(True, f"License ID {Config.LICENSE_ID} revoked.", store)
                    return False
                elif license_entry.upper() == "PENDING":
                    logger.info(f"License ID {Config.LICENSE_ID} is PENDING (str). Binding to this machine.")
                    state["licensed_machine_id"] = current_machine
                    store.save(state)
                    return True

            # Logic 3: Specific ID revocation list
            revoked_ids = data.get("revoked_ids", [])
            if Config.LICENSE_ID in revoked_ids:
                logger.critical(f"LICENSE REVOKED for ID: {Config.LICENSE_ID}")
                LicenseManager._set_revoked(True, f"License ID {Config.LICENSE_ID} in revocation list.", store)
                return False

            # Logic 4: Check local machine binding if server didn't provide one
            # This handles the case where the server just says "OK" but we already bound locally.
            if bound_machine and bound_machine != current_machine:
                 # Check if the server entry specifically allows a machine change (e.g. by being dict without machine_id)
                 if isinstance(license_entry, dict) and not license_entry.get("machine_id"):
                     logger.warning("Local machine ID mismatch but server allows any machine for this ID. Updating local binding.")
                     state["licensed_machine_id"] = current_machine
                     store.save(state)
                 else:
                     logger.critical("LICENSE VIOLATION: Local state mismatch. Bot is being shared.")
                     LicenseManager._set_revoked(True, "Local Machine ID mismatch.", store)
                     return False

            # If we're here, the license is still valid according to the server
            LicenseManager._set_revoked(False, "License verification successful.", store)
            
            # If not already bound locally, bind it now
            if not bound_machine:
                state["licensed_machine_id"] = current_machine
                store.save(state)
                logger.info(f"License ID {Config.LICENSE_ID} successfully bound to this machine.")
                
            return True

        except Exception as e:
            logger.error(f"Failed to verify license remotely: {e}")
            # If we fail to reach server, we trust the local machine binding
            if bound_machine and bound_machine != current_machine:
                logger.critical("LOCAL LICENSE VIOLATION: Offline check failed.")
                return False
            return True

    @staticmethod
    def _set_revoked(is_revoked: bool, reason: str, store: BotStateStore | None = None):
        if not store:
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
