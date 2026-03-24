import json
import requests
import logging
from config import Config
from bot_state import BotStateStore

logger = logging.getLogger("tradebot.license")

class LicenseManager:
    @staticmethod
    def verify_license() -> bool:
        """
        Checks the remote LICENSE_URL to see if this bot's LICENSE_ID is still authorized.
        If it can't reach the server, it fails closed (returns True/OK for now, or you can change to False/Strict).
        """
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
                # We expect a JSON from the server: {"status": "OK", "revoked_ids": ["client_id_1", "client_id_2"]}
                # OR {"ids": {"client_id_1": "OK", "client_id_2": "REVOKED"}}
                response = requests.get(Config.LICENSE_URL, timeout=10)
                response.raise_for_status()
                data = response.json()

            # Logic 1: Global kill switch
            if data.get("status") == "REVOKED_GLOBAL":
                logger.critical("GLOBAL LICENSE REVOCATION DETECTED.")
                LicenseManager._set_revoked(True, "Global revocation triggered.")
                return False

            # Logic 2: Specific ID revocation
            revoked_ids = data.get("revoked_ids", [])
            if Config.LICENSE_ID in revoked_ids:
                logger.critical(f"LICENSE REVOKED for ID: {Config.LICENSE_ID}")
                LicenseManager._set_revoked(True, f"License ID {Config.LICENSE_ID} revoked by server.")
                return False

            # Logic 3: ID-based status
            ids_status = data.get("ids", {})
            if Config.LICENSE_ID in ids_status and ids_status[Config.LICENSE_ID] == "REVOKED":
                logger.critical(f"LICENSE STATUS: REVOKED for ID: {Config.LICENSE_ID}")
                LicenseManager._set_revoked(True, f"License ID {Config.LICENSE_ID} specifically marked as REVOKED.")
                return False

            # If we're here, the license is still valid according to the server
            LicenseManager._set_revoked(False, "License verification successful.")
            return True

        except Exception as e:
            logger.error(f"Failed to verify license remotely: {e}")
            # In a real license situation, you might want to return False here to prevent usage offline.
            # But for a "sharing" bot, we'll allow it to continue if the server is just down.
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
