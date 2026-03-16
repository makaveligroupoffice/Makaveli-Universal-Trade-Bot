import time
import json
import logging
import os
from datetime import datetime, timedelta
from calculate_today_pl import calculate_today_stats
from notifications import send_notification
from config import Config

# Configure logging
logging.basicConfig(
    filename='logs/hourly_reports.log',
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

def run_report():
    try:
        stats = calculate_today_stats()
        if not stats:
            logging.info("No trades found for today yet.")
            return

        report = (
            f"📅 Hourly Update ({datetime.now().strftime('%H:%M')})\n"
            f"-------------------\n"
            f"📈 Win Rate: {stats['win_rate']:.2f}%\n"
            f"💰 Net PnL: ${stats['net_pnl']:.2f}\n"
            f"📊 Profit Factor: {stats['profit_factor']:.2f}\n"
            f"✅ Wins: {stats['wins']} | ❌ Losses: {stats['losses']}\n"
            f"💵 Avg Win: ${stats['avg_win']:.2f} | Avg Loss: ${stats['avg_loss']:.2f}\n"
        )
        
        logging.info(f"Generated hourly report:\n{report}")
        send_notification(report, title="TradeBot Hourly Performance")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Report sent.")
        
    except Exception as e:
        logging.error(f"Error generating hourly report: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    # The user wants an update every hour starting from 14:30.
    # If we run this as a persistent process:
    print("Hourly Performance Reporter started.")
    
    while True:
        now = datetime.now()
        # Calculate target time: today at 14:30
        target = now.replace(hour=14, minute=30, second=0, microsecond=0)
        
        # If it's already past 14:30, find the next "on the half hour" slot
        if now >= target:
            # How many hours passed since 14:30?
            hours_passed = (now - target).total_seconds() // 3600
            target = target + timedelta(hours=hours_passed + 1)
        
        # Check if it's EXACTLY 14:30 (or close enough) right now if we just started
        # Actually, let's just wait until the next target.
        # BUT the user might want the FIRST one at 14:30.
        
        sleep_seconds = (target - now).total_seconds()
        if sleep_seconds > 0:
            print(f"Next report scheduled for {target.strftime('%H:%M:%S')}. Sleeping for {sleep_seconds:.0f}s...")
            # Sleep in chunks to allow for termination or just one big sleep
            time.sleep(sleep_seconds)
        
        run_report()
