import subprocess
import os
import logging
from config import Config
from notifications import send_notification

log = logging.getLogger("tradebot.updater")

class AutoUpdater:
    """
    Handles automatic updates by pulling the latest code from GitHub.
    This allows distributed instances of the bot to stay in sync.
    """
    def __init__(self):
        self.enabled = os.getenv("ENABLE_AUTO_UPDATE", "true").lower() == "true"
        self.branch = os.getenv("AUTO_UPDATE_BRANCH", "main")
        self.remote = os.getenv("AUTO_UPDATE_REMOTE", "origin")

    def check_for_updates(self):
        """
        Performs a git pull to sync with the remote repository.
        Returns True if changes were pulled, False otherwise.
        """
        if not self.enabled:
            return False

        try:
            log.info(f"Checking for updates from {self.remote}/{self.branch}...")
            
            # Fetch the latest state from remote
            subprocess.run(["git", "fetch", self.remote], check=True, capture_output=True)
            
            # Check if we are behind the remote
            status = subprocess.run(
                ["git", "rev-list", "HEAD..{} / {}".format(self.remote, self.branch).replace(" / ", "/")], 
                check=True, 
                capture_output=True, 
                text=True
            )
            
            if status.stdout.strip():
                log.info("New updates detected on GitHub. Pulling changes...")
                pull_result = subprocess.run(["git", "pull", self.remote, self.branch], check=True, capture_output=True, text=True)
                
                if "Already up to date" not in pull_result.stdout:
                    log.info("Update successful. Hot-reloading will apply changes.")
                    send_notification(
                        "The tradebot has automatically updated its code from GitHub and is applying changes live.",
                        title="Auto-Update Successful"
                    )
                    return True
            else:
                log.debug("No updates found. Bot is up to date.")
                
        except subprocess.CalledProcessError as e:
            log.error(f"Auto-update failed: {e.stderr if hasattr(e, 'stderr') else e}")
        except Exception as e:
            log.error(f"Unexpected error during auto-update: {e}")
            
        return False
