from market_data import MarketDataClient
import pandas as pd
from strategy import Strategy

def analyze_positions():
    client = MarketDataClient()
    symbols = ['BMNR', 'CPNG', 'HYG']
    strategy = Strategy()
    
    for symbol in symbols:
        print(f"\n--- {symbol} 1-min Analysis ---")
        bars_raw = client.get_recent_bars(symbol, minutes=30)
        if not bars_raw:
            print(f"No 1-min bars for {symbol}")
            continue
        
        # Convert to DataFrame for simple stats in THIS script
        bars_df = pd.DataFrame([
            {
                "timestamp": b.timestamp,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume
            } for b in bars_raw
        ])
        bars_df['sma5'] = bars_df['close'].rolling(5).mean()
        
        # Basic indicators
        latest_price = client.get_latest_mid_price(symbol)
        last_bar = bars_df.iloc[-1]
        
        # Simple stats
        avg_vol = bars_df['volume'].mean()
        last_vol = last_bar['volume']
        last_sma5 = bars_df['sma5'].iloc[-1]
        
        print(f"Latest: {latest_price} | 5m SMA: {last_sma5:.4f} | {'ABOVE' if latest_price > last_sma5 else 'BELOW'} SMA5")
        print(f"Volume Ratio (last/avg): {last_vol/avg_vol:.2f}x")
        
        # Try to use some strategy methods for signal check
        import json
        with open('logs/bot_state.json', 'r') as f:
            state = json.load(f)
            pos_info = state.get('positions', {}).get(symbol, {})
            entry_price = pos_info.get('entry_price', 0)
            high_since = pos_info.get('high_since_entry', latest_price)
            
        if entry_price > 0:
            qty = pos_info.get('qty', 0)
            unrealized = (latest_price - entry_price) * qty
            print(f"Entry: {entry_price} | Unrealized: ${unrealized:.2f}")
            # Pass RAW bars to should_sell as it expects a list of objects
            should_exit, reason = strategy.should_sell(entry_price, latest_price, bars_raw, high_since_entry=high_since)
            print(f"Should Exit (Logic): {should_exit} | Reason: {reason}")
        else:
            print("No entry found in bot_state.")

if __name__ == "__main__":
    analyze_positions()
