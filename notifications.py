import logging
import requests
import smtplib
from email.mime.text import MIMEText
from config import Config

log = logging.getLogger("tradebot")

def send_notification(message: str, title: str = "Trade Bot Alert"):
    """
    Sends a notification via configured services.
    """
    # 1. Discord
    if Config.DISCORD_WEBHOOK_URL:
        try:
            requests.post(Config.DISCORD_WEBHOOK_URL, json={"content": f"**{title}**\n{message}"}, timeout=5)
        except Exception as e:
            log.error(f"Failed to send Discord notification: {e}")

    # 2. Pushover
    if Config.PUSHOVER_USER_KEY and Config.PUSHOVER_APP_TOKEN:
        try:
            requests.post("https://api.pushover.net/1/messages.json", data={
                "token": Config.PUSHOVER_APP_TOKEN, "user": Config.PUSHOVER_USER_KEY,
                "message": message, "title": title
            }, timeout=5)
        except Exception as e:
            log.error(f"Failed to send Pushover notification: {e}")

    # 3. Telegram
    if Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": Config.TELEGRAM_CHAT_ID, "text": f"*{title}*\n{message}", "parse_mode": "Markdown"}, timeout=5)
        except Exception as e:
            log.error(f"Failed to send Telegram notification: {e}")

    # 4. Email
    if Config.EMAIL_SMTP_SERVER and Config.EMAIL_USER and Config.EMAIL_RECEIVER:
        try:
            msg = MIMEText(message)
            msg['Subject'] = title
            msg['From'] = Config.EMAIL_USER
            msg['To'] = Config.EMAIL_RECEIVER
            with smtplib.SMTP(Config.EMAIL_SMTP_SERVER, Config.EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(Config.EMAIL_USER, Config.EMAIL_PASS)
                server.send_message(msg)
        except Exception as e:
            log.error(f"Failed to send Email notification: {e}")

    # 5. SMS (Twilio)
    if Config.SMS_TWILIO_SID and Config.SMS_TWILIO_TOKEN and Config.SMS_RECEIVER:
        try:
            url = f"https://api.twilio.org/2010-04-01/Accounts/{Config.SMS_TWILIO_SID}/Messages.json"
            requests.post(url, data={
                "To": Config.SMS_RECEIVER,
                "From": Config.SMS_TWILIO_NUMBER,
                "Body": f"{title}: {message}"
            }, auth=(Config.SMS_TWILIO_SID, Config.SMS_TWILIO_TOKEN), timeout=5)
        except Exception as e:
            log.error(f"Failed to send SMS notification: {e}")

    # Fallback log
    if not any([Config.DISCORD_WEBHOOK_URL, Config.PUSHOVER_USER_KEY, Config.TELEGRAM_BOT_TOKEN, Config.EMAIL_SMTP_SERVER, Config.SMS_TWILIO_SID]):
        log.debug("No notification service configured. Logging only: " + message)
