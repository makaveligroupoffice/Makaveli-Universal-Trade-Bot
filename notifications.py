import logging
import requests
from config import Config

log = logging.getLogger("tradebot")

def send_notification(message: str, title: str = "Trade Bot Alert"):
    """
    Sends a notification via Discord Webhook or Pushover if configured.
    """
    # 1. Try Discord
    if Config.DISCORD_WEBHOOK_URL:
        try:
            requests.post(
                Config.DISCORD_WEBHOOK_URL,
                json={"content": f"**{title}**\n{message}"},
                timeout=5
            )
        except Exception as e:
            log.error(f"Failed to send Discord notification: {e}")

    # 2. Try Pushover
    if Config.PUSHOVER_USER_KEY and Config.PUSHOVER_APP_TOKEN:
        try:
            requests.post(
                "https://api.pushover.net/1/messages.json",
                data={
                    "token": Config.PUSHOVER_APP_TOKEN,
                    "user": Config.PUSHOVER_USER_KEY,
                    "message": message,
                    "title": title
                },
                timeout=5
            )
        except Exception as e:
            log.error(f"Failed to send Pushover notification: {e}")

    # Fallback log
    if not Config.DISCORD_WEBHOOK_URL and not (Config.PUSHOVER_USER_KEY and Config.PUSHOVER_APP_TOKEN):
        log.debug("No notification service configured. Logging only: " + message)
