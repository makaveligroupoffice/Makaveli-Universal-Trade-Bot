from __future__ import annotations

from datetime import datetime

from config import Config


class Strategy:
    @staticmethod
    def should_buy(bars) -> tuple[bool, str]:
        if len(bars) < 20:
            return False, "not enough bars"

        import pandas as pd
        df = pd.DataFrame([{"close": float(b.close), "high": float(b.high), "low": float(b.low), "volume": float(b.volume)} for b in bars])
        
        # Simple manual indicators since pandas-ta is unavailable
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma10'] = df['close'].rolling(window=10).mean()
        
        # ATR-like volatility indicator
        df['tr'] = df.apply(lambda r: max(r['high'] - r['low'], abs(r['high'] - r['close']), abs(r['low'] - r['close'])), axis=1)
        df['atr14'] = df['tr'].rolling(window=14).mean()
        
        last_close = df['close'].iloc[-1]
        last_sma20 = df['sma20'].iloc[-1]
        last_sma10 = df['sma10'].iloc[-1]
        last_atr = df['atr14'].iloc[-1]
        
        # Momentum + Trend following
        bullish_trend = last_close > last_sma20 and last_sma10 > last_sma20
        volume_spike = df['volume'].iloc[-1] > df['volume'].rolling(20).mean().iloc[-1] * 1.5
        
        # Don't enter if volatility is extreme (relative to average price)
        volatility_excessive = last_atr > (last_close * 0.02) # > 2% of price per bar is high volatility

        if not bullish_trend:
            return False, "price below SMA20 or SMA10 < SMA20"
        
        if not volume_spike:
            return False, "no volume spike"
            
        if volatility_excessive:
             return False, "volatility too high (ATR > 2%)"

        return True, "trend + volume breakout"

    @staticmethod
    def should_short(bars) -> tuple[bool, str]:
        if len(bars) < 20:
            return False, "not enough bars"

        import pandas as pd
        df = pd.DataFrame([{"close": float(b.close), "high": float(b.high), "low": float(b.low), "volume": float(b.volume)} for b in bars])
        
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma10'] = df['close'].rolling(window=10).mean()
        
        # ATR-like volatility indicator
        df['tr'] = df.apply(lambda r: max(r['high'] - r['low'], abs(r['high'] - r['close']), abs(r['low'] - r['close'])), axis=1)
        df['atr14'] = df['tr'].rolling(window=14).mean()
        
        last_close = df['close'].iloc[-1]
        last_sma20 = df['sma20'].iloc[-1]
        last_sma10 = df['sma10'].iloc[-1]
        last_atr = df['atr14'].iloc[-1]
        
        bearish_trend = last_close < last_sma20 and last_sma10 < last_sma20
        volume_spike = df['volume'].iloc[-1] > df['volume'].rolling(20).mean().iloc[-1] * 1.5
        volatility_excessive = last_atr > (last_close * 0.02)

        if not bearish_trend:
            return False, "price above SMA20 or SMA10 > SMA20"
        
        if not volume_spike:
            return False, "no volume spike"
            
        if volatility_excessive:
            return False, "volatility too high (ATR > 2%)"

        return True, "bearish trend + volume breakout"

    @staticmethod
    def should_sell(entry_price: float, current_price: float, bars, high_since_entry: float | None = None, side: str = "buy", dynamic_config: dict | None = None) -> tuple[bool, str]:
        if current_price <= 0:
            return False, "invalid current price"

        # Use dynamic config if provided, else fallback to global config
        sl_pct = (dynamic_config.get("stop_loss_pct", Config.STOP_LOSS_PCT) if dynamic_config else Config.STOP_LOSS_PCT) / 100.0
        tp_pct = (dynamic_config.get("take_profit_pct", Config.TAKE_PROFIT_PCT) if dynamic_config else Config.TAKE_PROFIT_PCT) / 100.0
        ts_pct = Config.TRAILING_STOP_PCT / 100.0 # Trailing stop still global for now

        if side == "buy":
            # Stop loss
            if current_price <= entry_price * (1 - sl_pct):
                return True, f"stop loss hit ({sl_pct*100:.2f}%)"
            # Trailing stop
            if ts_pct > 0 and high_since_entry:
                if current_price <= high_since_entry * (1 - ts_pct):
                    return True, f"trailing stop hit (high: {high_since_entry:.2f})"
            # Take profit
            if tp_pct > 0 and current_price >= entry_price * (1 + tp_pct):
                return True, f"take profit hit ({tp_pct*100:.2f}%)"
        else: # side == "short"
            # Stop loss (price went UP)
            if current_price >= entry_price * (1 + sl_pct):
                return True, f"short stop loss hit ({sl_pct*100:.2f}%)"
            # Trailing stop (low since entry)
            # For short, high_since_entry actually tracks LOW since entry
            low_since_entry = high_since_entry
            if ts_pct > 0 and low_since_entry:
                if current_price >= low_since_entry * (1 + ts_pct):
                    return True, f"short trailing stop hit (low: {low_since_entry:.2f})"
            # Take profit (price went DOWN)
            if tp_pct > 0 and current_price <= entry_price * (1 - tp_pct):
                return True, f"short take profit hit ({tp_pct*100:.2f}%)"

        # Momentum exit
        if len(bars) >= 3:
            closes = [float(bar.close) for bar in bars[-3:]]
            if side == "buy" and closes[-1] < closes[-2] < closes[-3]:
                return True, "momentum rollover"
            if side == "short" and closes[-1] > closes[-2] > closes[-3]:
                return True, "short momentum rollover"

        now_hhmm = int(datetime.now().strftime("%H%M"))
        if now_hhmm >= int(Config.ALLOWED_END_HHMM):
            return True, "end of trading window"

        return False, "hold"