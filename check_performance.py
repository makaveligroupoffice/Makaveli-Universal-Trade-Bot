from performance import PerformanceAnalyzer
from config import Config
import json

def check_performance():
    analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
    # Check for all time (e.g., 365 days)
    analysis = analyzer.analyze_recent_trades(days=365)
    
    if analysis:
        print(f"--- Performance Summary ---")
        print(f"Total Trades: {analysis['total_trades']}")
        print(f"Win Rate: {analysis['win_rate']:.2%}")
        print(f"Total PnL: ${analysis['total_pnl']:.2f}")
        print(f"Profit Factor: {analysis['profit_factor']:.2f}")
        print(f"Max Drawdown: ${analysis['max_drawdown']:.2f}")
        print(f"Avg Win: ${analysis['avg_win']:.2f}")
        print(f"Avg Loss: ${analysis['avg_loss']:.2f}")
        print(f"Win/Loss Ratio: {analysis['win_loss_ratio']:.2f}")
    else:
        print("No trades found in the journal or journal file missing.")

if __name__ == '__main__':
    check_performance()
