import time
import json
import logging
import os
from datetime import datetime, timedelta
from calculate_today_pl import calculate_today_stats
from notifications import send_notification
from config import Config

from broker_alpaca import AlpacaBroker

from eod_performance_report import run_eod_report

# Configure logging
logging.basicConfig(
    filename='logs/hourly_reports.log',
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

def is_market_open():
    try:
        broker = AlpacaBroker()
        clock = broker.get_clock()
        return clock.is_open
    except Exception as e:
        logging.error(f"Error checking market clock: {e}")
        return False

def run_report(force=False):
    try:
        if not force and not is_market_open():
            logging.info("Market is closed. Skipping hourly report.")
            return

        # Use start of today for stats
        today_str = datetime.now().strftime('%Y-%m-%dT00:00:00')
        stats = calculate_today_stats(start_time=today_str)
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
    print("Hourly Performance Reporter started.")
    
    last_market_open = False
    
    while True:
        now = datetime.now()
        
        # Check market status to trigger EOD if it just closed
        try:
            broker = AlpacaBroker()
            clock = broker.get_clock()
            is_open = clock.is_open
            
            # If market was open and now is closed, trigger EOD report
            if last_market_open and not is_open:
                print(f"[{now.strftime('%H:%M:%S')}] Market closed. Triggering EOD report.")
                run_eod_report()
            
            last_market_open = is_open
        except Exception as e:
            print(f"Error checking market clock in main loop: {e}")

        # Sleep logic: every hour on the hour (e.g. 10:00, 11:00)
        # We find the next hour
        target = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        
        sleep_seconds = (target - now).total_seconds()
        if sleep_seconds > 0:
            print(f"Next hourly check scheduled for {target.strftime('%H:%M:%S')}. Sleeping...")
            time.sleep(sleep_seconds)
        
        run_report()
