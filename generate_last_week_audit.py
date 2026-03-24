import logging
import os
from datetime import datetime
from config import Config
from bot_runner import AutoTrader
from notifications import send_notification

# Ensure log directory exists
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("audit_gen")

def generate_last_week_audit():
    try:
        log.info("Generating Fast Audit Report for the last 7 days...")
        from performance import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
        report = analyzer.generate_fast_audit_report(days=7)
        
        print("\n" + "="*40)
        print("LAST WEEK FAST AUDIT REPORT PREVIEW")
        print("="*40)
        print(report)
        print("\n" + "="*40)
        
        send_notification(report, title="⚡ Last Week Fast Audit Result")
        print("\nThe report has also been sent via your configured notifications.")

    except Exception as e:
        log.error(f"Error generating last week audit: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    generate_last_week_audit()
