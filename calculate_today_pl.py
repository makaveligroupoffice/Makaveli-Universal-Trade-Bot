import json
from datetime import datetime

def calculate_today_stats(start_time="2026-03-16T12:00:00"):
    gross_profit = 0.0
    gross_loss = 0.0
    wins = 0
    losses = 0
    total_pnl = 0.0

    try:
        with open('logs/trade_journal.jsonl', 'r') as f:
            for line in f:
                data = json.loads(line)
                timestamp = data.get('timestamp', '')
                if timestamp >= start_time:
                    pnl = data.get('pnl')
                    if pnl is not None:
                        total_pnl += pnl
                        if pnl > 0:
                            gross_profit += pnl
                            wins += 1
                        elif pnl < 0:
                            gross_loss += abs(pnl)
                            losses += 1
        
        count = wins + losses
        win_rate = (wins / count * 100) if count > 0 else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)
        avg_win = gross_profit / wins if wins > 0 else 0
        avg_loss = gross_loss / losses if losses > 0 else 0
        
        return {
            "wins": wins,
            "losses": losses,
            "total_trades": count,
            "win_rate": win_rate,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "net_pnl": total_pnl,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss
        }
        
    except FileNotFoundError:
        return None

if __name__ == '__main__':
    stats = calculate_today_stats()
    if stats:
        print(f"--- Today's Performance (since 12:00 PM) ---")
        print(f"Total Closed Trades: {stats['total_trades']}")
        print(f"Wins: {stats['wins']}, Losses: {stats['losses']}")
        print(f"Win Rate: {stats['win_rate']:.2f}%")
        print(f"Gross Profit: ${stats['gross_profit']:.2f}")
        print(f"Gross Loss: ${stats['gross_loss']:.2f}")
        print(f"Net PnL: ${stats['net_pnl']:.2f}")
        print(f"Profit Factor: {stats['profit_factor']:.2f}")
        print(f"Average Win: ${stats['avg_win']:.2f}")
        print(f"Average Loss: ${stats['avg_loss']:.2f}")
    else:
        print("Journal not found.")
