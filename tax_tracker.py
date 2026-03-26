import json
import pandas as pd
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TaxTracker")

class TaxTracker:
    def __init__(self, journal_file=None):
        self.journal_file = journal_file or Config.TRADE_JOURNAL_FILE

    def generate_tax_report(self, output_file="logs/tax_report_2026.csv"):
        logger.info(f"Generating tax report from {self.journal_file}...")
        
        trades = []
        try:
            with open(self.journal_file, 'r') as f:
                for line in f:
                    entry = json.loads(line)
                    # We only care about closed trades (sell/cover)
                    if entry.get('event') in ['sell_fill', 'cover_fill'] and entry.get('pnl') is not None:
                        trades.append({
                            'timestamp': entry.get('timestamp'),
                            'symbol': entry.get('symbol'),
                            'side': entry.get('side'),
                            'qty': entry.get('qty'),
                            'price': entry.get('price'),
                            'pnl': entry.get('pnl'),
                            'reason': entry.get('reason')
                        })
        except FileNotFoundError:
            logger.error(f"Journal file not found: {self.journal_file}")
            return

        if not trades:
            logger.warning("No closed trades found in journal.")
            return

        df = pd.DataFrame(trades)
        df.to_csv(output_file, index=False)
        logger.info(f"Tax report generated: {output_file}")
        
        total_pnl = df['pnl'].sum()
        logger.info(f"Total PnL for 2026: ${total_pnl:.2f}")

if __name__ == "__main__":
    tracker = TaxTracker()
    tracker.generate_tax_report()
