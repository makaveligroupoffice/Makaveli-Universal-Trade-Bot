import logging
import time
from datetime import datetime
from calculate_today_pl import calculate_today_stats
from notifications import send_notification
from broker_alpaca import AlpacaBroker

# Configure logging
logging.basicConfig(
    filename='logs/daily_summary.log',
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

def run_eod_report():
    try:
        from bot_runner import AutoTrader
        # Use AutoTrader's built-in reporting logic for consistency
        trader = AutoTrader()
        trader._send_daily_report()
        trader._send_quality_analysis()
        trader._send_bot_health_report()
        
        # Check if it's the end of the week (Friday)
        if datetime.now().weekday() == 4:
            trader._send_weekly_report()
            trader._send_fast_audit_report()
            
        print(f"[{datetime.now().strftime('%H:%M:%S')}] EOD Comprehensive Reports sent.")

    except Exception as e:
        logging.error(f"Error generating EOD report: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    run_eod_report()
