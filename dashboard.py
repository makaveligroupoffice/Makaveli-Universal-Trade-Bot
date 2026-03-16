import json
import os
from datetime import datetime, timedelta
from config import Config
from performance import PerformanceAnalyzer
from broker_alpaca import AlpacaBroker

def generate_dashboard():
    analyzer = PerformanceAnalyzer(Config.TRADE_JOURNAL_FILE)
    stats = analyzer.analyze_recent_trades(days=30)
    
    broker = AlpacaBroker()
    account = broker.get_account()
    positions = broker.get_positions()
    
    equity = float(getattr(account, "equity", 0.0))
    balance = float(getattr(account, "cash", 0.0))
    pnl_day = float(getattr(account, "daily_change", 0.0))
    
    os.system('clear')
    print("="*60)
    print(f" 🚀 TRADEBOT INVESTMENT DASHBOARD - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # 1. Account Overview
    print(f"\n[ACCOUNT OVERVIEW]")
    print(f"Total Equity:    ${equity:,.2f}")
    print(f"Buying Power:    ${float(getattr(account, 'buying_power', 0.0)):,.2f}")
    print(f"Cash Balance:    ${balance:,.2f}")
    print(f"Today's PnL:     ${pnl_day:,.2f} ({float(getattr(account, 'daily_change_pct', 0.0))*100:.2f}%)")
    
    # 2. Performance Stats
    print(f"\n[PERFORMANCE (Last 30 Days)]")
    win_rate = stats.get('win_rate', 0)
    total_trades = stats.get('total_trades', 0)
    total_pnl = stats.get('total_pnl', 0)
    
    color = "\033[92m" if total_pnl >= 0 else "\033[91m"
    reset = "\033[0m"
    
    print(f"Win Rate:        {win_rate:.2f}%")
    print(f"Total Trades:    {total_trades}")
    print(f"Total PnL:       {color}${total_pnl:,.2f}{reset}")
    print(f"Profit Factor:   {stats.get('profit_factor', 0):.2f}")
    
    # 3. Active Positions
    print(f"\n[ACTIVE POSITIONS]")
    if not positions:
        print("No active positions.")
    else:
        print(f"{'SYMBOL':<10} {'QTY':<10} {'PRICE':<10} {'MARKET':<10} {'PnL':<10}")
        for p in positions:
            sym = p.symbol
            qty = float(p.qty)
            entry = float(p.avg_entry_price)
            curr = float(p.current_price)
            pnl = float(p.unrealized_pl)
            pnl_color = "\033[92m" if pnl >= 0 else "\033[91m"
            print(f"{sym:<10} {qty:<10.2f} ${entry:<9.2f} ${curr:<9.2f} {pnl_color}${pnl:<9.2f}{reset}")
            
    # 4. Projected Growth
    print(f"\n[PROJECTED GROWTH]")
    if total_trades > 0:
        avg_pnl_per_trade = total_pnl / total_trades
        daily_trades = total_trades / 30 # average
        monthly_proj = avg_pnl_per_trade * daily_trades * 20 # 20 trading days
        
        print(f"Avg PnL / Trade: ${avg_pnl_per_trade:.2f}")
        print(f"Est. Monthly:    ${monthly_proj:,.2f}")
        print(f"Target (30 Day): $5,000.00 (Current Progress: {((equity-Config.STARTING_EQUITY)/4500)*100:.1f}%)")
    else:
        print("Insufficient data for projections.")

    # 5. Risk Status
    print(f"\n[RISK & STRATEGY STATUS]")
    try:
        with open(Config.RISK_STATE_FILE, "r") as f:
            risk_state = json.load(f)
            daily_pnl = risk_state.get("daily_pnl", 0.0)
            trades_today = risk_state.get("trades_today", 0)
            peak = risk_state.get("peak_equity", equity)
            dd = (peak - equity) / peak * 100
            
            print(f"Trades Today:    {trades_today} / {Config.MAX_TRADES_PER_DAY}")
            print(f"Daily Risk PnL:  ${daily_pnl:.2f}")
            print(f"Max Drawdown:    {dd:.2f}% / {Config.MAX_EQUITY_DRAWDOWN_PCT}%")
            print(f"Stop Loss:       {Config.STOP_LOSS_PCT}% (Hard Bracket)")
            print(f"Take Profit:     {Config.TAKE_PROFIT_PCT}% (Hard Bracket)")
            print(f"Trailing Stop:   {Config.TRAILING_STOP_PCT}% (Activation: {Config.TRAILING_STOP_ACTIVATION_PCT}%)")
            print(f"Limit Orders:    {'ENABLED' if Config.USE_LIMIT_ORDERS else 'DISABLED'}")

            if dd >= Config.MAX_EQUITY_DRAWDOWN_PCT:
                print("\033[91m⚠️ CIRCUIT BREAKER ACTIVE: Trading Suspended\033[0m")
    except:
        print("Risk state not found.")

    print("\n" + "="*60)
    print(" Press Ctrl+C to exit dashboard")

if __name__ == "__main__":
    import time
    try:
        while True:
            generate_dashboard()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nExiting dashboard.")
