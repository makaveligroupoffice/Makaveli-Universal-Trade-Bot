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
        broker = AlpacaBroker()
        clock = broker.get_clock()
        
        # If market is still open, we might want to wait or check how long until it closes.
        # But this script is intended to be called at EOD.
        
        today_str = datetime.now().strftime('%Y-%m-%dT00:00:00')
        stats = calculate_today_stats(start_time=today_str)
        
        if not stats or stats['total_trades'] == 0:
            report = f"📅 EOD Summary ({datetime.now().strftime('%Y-%m-%d')})\nNo trades executed today."
        else:
            report = (
                f"🏁 EOD Performance Report ({datetime.now().strftime('%Y-%m-%d')})\n"
                f"-----------------------------------\n"
                f"📈 Win Rate: {stats['win_rate']:.2f}%\n"
                f"💰 Net PnL: ${stats['net_pnl']:.2f}\n"
                f"📊 Profit Factor: {stats['profit_factor']:.2f}\n"
                f"✅ Wins: {stats['wins']} | ❌ Losses: {stats['losses']}\n"
                f"💵 Gross Profit: ${stats['gross_profit']:.2f}\n"
                f"💸 Gross Loss: ${stats['gross_loss']:.2f}\n"
                f"📏 Avg Win: ${stats['avg_win']:.2f} | Avg Loss: ${stats['avg_loss']:.2f}\n"
                f"-----------------------------------\n"
            )

        logging.info(f"Generated EOD report:\n{report}")
        send_notification(report, title="TradeBot EOD Performance")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] EOD Report sent.")

    except Exception as e:
        logging.error(f"Error generating EOD report: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    run_eod_report()
