import os
import shutil
import zipfile
import logging
from datetime import datetime
from config import Config

log = logging.getLogger("autobot")

class BackupManager:
    """
    Handles automatic backups of the database, configuration, and logs.
    """
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = backup_dir
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self) -> str | None:
        """
        Creates a timestamped zip backup of critical project files.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"tradebot_backup_{timestamp}.zip"
        backup_path = os.path.join(self.backup_dir, backup_name)

        log.info(f"Starting automatic backup to {backup_name}...")

        try:
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 1. Database (instance/users.db)
                db_path = "instance/users.db"
                if os.path.exists(db_path):
                    zipf.write(db_path, os.path.basename(db_path))
                
                # 2. Config (.env) - CRITICAL: Keep safe!
                env_path = ".env"
                if os.path.exists(env_path):
                    zipf.write(env_path, os.path.basename(env_path))
                
                # 3. Strategy (strategy.py) - The bot's DNA
                strategy_path = "strategy.py"
                if os.path.exists(strategy_path):
                    zipf.write(strategy_path, os.path.basename(strategy_path))

                # 4. Logs (recent ones)
                log_dir = Config.LOG_DIR
                if os.path.exists(log_dir):
                    for folder, subs, files in os.walk(log_dir):
                        for filename in files:
                            # Only backup the last 5MB of logs to avoid huge zips
                            file_path = os.path.join(folder, filename)
                            if os.path.getsize(file_path) < 5 * 1024 * 1024:
                                arcname = os.path.relpath(file_path, os.getcwd())
                                zipf.write(file_path, arcname)

            log.info(f"Backup completed successfully: {backup_path}")
            self._cleanup_old_backups(keep=10) # Keep only latest 10
            return backup_path
        except Exception as e:
            log.error(f"Backup failed: {e}")
            return None

    def _cleanup_old_backups(self, keep: int = 10):
        """
        Removes older backups to save disk space.
        """
        try:
            backups = sorted([
                os.path.join(self.backup_dir, f) 
                for f in os.listdir(self.backup_dir) 
                if f.startswith("tradebot_backup_") and f.endswith(".zip")
            ], key=os.path.getmtime, reverse=True)

            if len(backups) > keep:
                for old_backup in backups[keep:]:
                    os.remove(old_backup)
                    log.info(f"Removed old backup: {old_backup}")
        except Exception as e:
            log.error(f"Failed to cleanup old backups: {e}")

if __name__ == "__main__":
    # Test backup
    bm = BackupManager()
    bm.create_backup()
