import json

journal_path = 'logs/trade_journal.jsonl'
wins = 0
losses = 0
total_pnl = 0.0

with open(journal_path, 'r') as f:
    for line in f:
        try:
            data = json.loads(line)
            pnl = data.get('pnl')
            if pnl is not None:
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
                    print(f"WIN: {data['symbol']} | PnL: ${pnl:.2f} | Reason: {data.get('reason')}")
                elif pnl < 0:
                    losses += 1
        except Exception:
            pass

print("\n--- Summary ---")
print(f"Total Wins: {wins}")
print(f"Total Losses: {losses}")
print(f"Total PnL: ${total_pnl:.2f}")
