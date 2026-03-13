from __future__ import annotations
import os
from datetime import datetime

from config import Config


class Strategy:
    @staticmethod
    def should_buy(bars, dynamic_config: dict | None = None) -> tuple[bool, str]:
        if len(bars) < 20:
            return False, "not enough bars"

        import pandas as pd
        df = pd.DataFrame([{"close": float(b.close), "high": float(b.high), "low": float(b.low), "volume": float(b.volume)} for b in bars])
        
        # Simple manual indicators since pandas-ta is unavailable
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma10'] = df['close'].rolling(window=10).mean()
        df['sma200'] = df['close'].rolling(window=min(200, len(df))).mean() # Long-term trend
        
        # ATR-like volatility indicator
        df['tr'] = df.apply(lambda r: max(r['high'] - r['low'], abs(r['high'] - r['close']), abs(r['low'] - r['close'])), axis=1)
        df['atr14'] = df['tr'].rolling(window=14).mean()
        
        last_close = df['close'].iloc[-1]
        last_sma20 = df['sma20'].iloc[-1]
        last_sma10 = df['sma10'].iloc[-1]
        last_sma200 = df['sma200'].iloc[-1]
        last_atr = df['atr14'].iloc[-1]
        
        # Momentum + Trend following
        # 75% Win Rate Tip: Only trade in alignment with the long-term trend (SMA200)
        long_term_bullish = last_close > last_sma200
        # Medium-term trend: Price above SMA20 and SMA10 above SMA20
        # Short-term trend: Price above SMA10
        bullish_trend = last_close > last_sma20 and last_sma10 > last_sma20 and last_close > last_sma10
        
        # Candle confirmation: Last candle must be green and close near high
        last_candle_green = last_close > df['close'].iloc[-2]
        close_near_high = (last_close - df['low'].iloc[-1]) > (df['high'].iloc[-1] - df['low'].iloc[-1]) * 0.7
        
        # Relative Volume (RVOL) Check: Volume must be significantly higher than average
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        rvol = df['volume'].iloc[-1] / avg_volume if avg_volume > 0 else 0
        
        # Evolution: Use learned min_rvol if available
        min_rvol = dynamic_config.get("min_rvol", 1.8) if dynamic_config else 1.8
        volume_spike = rvol > min_rvol # Increased threshold for better quality signals
        
        # Don't enter if volatility is extreme (relative to average price)
        volatility_excessive = last_atr > (last_close * 0.02) # > 2% of price per bar is high volatility

        if not long_term_bullish:
            return False, "price below SMA200 (avoiding counter-trend)"

        if not bullish_trend:
            return False, "trend not strong enough (need Close > SMA10 > SMA20)"
        
        if not (last_candle_green and close_near_high):
            return False, "lack of price confirmation (need green candle close near high)"
        
        if not volume_spike:
            return False, f"low relative volume (RVOL: {rvol:.2f} < {min_rvol})"
            
        if volatility_excessive:
             return False, "volatility too high (ATR > 2%)"

        return True, f"trend + high RVOL ({rvol:.2f}) breakout"

    @staticmethod
    def should_short(bars, dynamic_config: dict | None = None) -> tuple[bool, str]:
        if len(bars) < 20:
            return False, "not enough bars"

        import pandas as pd
        df = pd.DataFrame([{"close": float(b.close), "high": float(b.high), "low": float(b.low), "volume": float(b.volume)} for b in bars])
        
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma10'] = df['close'].rolling(window=10).mean()
        df['sma200'] = df['close'].rolling(window=min(200, len(df))).mean()
        
        # ATR-like volatility indicator
        df['tr'] = df.apply(lambda r: max(r['high'] - r['low'], abs(r['high'] - r['close']), abs(r['low'] - r['close'])), axis=1)
        df['atr14'] = df['tr'].rolling(window=14).mean()
        
        last_close = df['close'].iloc[-1]
        last_sma20 = df['sma20'].iloc[-1]
        last_sma10 = df['sma10'].iloc[-1]
        last_sma200 = df['sma200'].iloc[-1]
        last_atr = df['atr14'].iloc[-1]
        
        long_term_bearish = last_close < last_sma200
        # Medium-term trend: Price below SMA20 and SMA10 below SMA20
        # Short-term trend: Price below SMA10
        bearish_trend = last_close < last_sma20 and last_sma10 < last_sma20 and last_close < last_sma10
        
        # Candle confirmation: Last candle must be red and close near low
        last_candle_red = last_close < df['close'].iloc[-2]
        close_near_low = (df['high'].iloc[-1] - last_close) > (df['high'].iloc[-1] - df['low'].iloc[-1]) * 0.7
        
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        rvol = df['volume'].iloc[-1] / avg_volume if avg_volume > 0 else 0
        
        min_rvol = dynamic_config.get("min_rvol", 1.8) if dynamic_config else 1.8
        volume_spike = rvol > min_rvol
        
        volatility_excessive = last_atr > (last_close * 0.02)

        if not long_term_bearish:
            return False, "price above SMA200 (avoiding counter-trend short)"

        if not bearish_trend:
            return False, "bearish trend not strong enough (need Close < SMA10 < SMA20)"
        
        if not (last_candle_red and close_near_low):
            return False, "lack of bearish price confirmation (need red candle close near low)"
        
        if not volume_spike:
            return False, f"low relative volume (RVOL: {rvol:.2f} < {min_rvol})"
            
        if volatility_excessive:
            return False, "volatility too high (ATR > 2%)"

        return True, f"bearish trend + high RVOL ({rvol:.2f}) breakout"

    @staticmethod
    def should_sell(entry_price: float, current_price: float, bars, high_since_entry: float | None = None, side: str = "buy", dynamic_config: dict | None = None, is_manual: bool = False) -> tuple[bool, str]:
        if current_price <= 0:
            return False, "invalid current price"

        # Use dynamic config if provided, else fallback to global config
        sl_pct = (dynamic_config.get("stop_loss_pct", Config.STOP_LOSS_PCT) if dynamic_config else Config.STOP_LOSS_PCT) / 100.0
        tp_pct = (dynamic_config.get("take_profit_pct", Config.TAKE_PROFIT_PCT) if dynamic_config else Config.TAKE_PROFIT_PCT) / 100.0
        ts_pct = Config.TRAILING_STOP_PCT / 100.0 

        # --- Dynamic Strategy Switch: Scalp vs. Hold ---
        is_strong_trend = False
        if len(bars) >= 20:
            import pandas as pd
            df = pd.DataFrame([{"close": float(b.close)} for b in bars[-20:]])
            df['sma20'] = df['close'].rolling(window=20).mean()
            last_close = df['close'].iloc[-1]
            last_sma20 = df['sma20'].iloc[-1]
            # Strong trend: Price is at least 1% above SMA20 (for longs) or below (for shorts)
            if side == "buy":
                is_strong_trend = last_close > (last_sma20 * 1.01)
            else:
                is_strong_trend = last_close < (last_sma20 * 0.99)

        # If it's a strong trend, LOOSEN the trailing stop to allow for bigger moves
        if is_strong_trend:
             ts_pct = ts_pct * 2.0 # Allow 2x room for strong runners

        if side == "buy":
            # Stop loss - Only if not manual or if entry_price is set
            if entry_price > 0 and current_price <= entry_price * (1 - sl_pct):
                return True, f"stop loss hit ({sl_pct*100:.2f}%)"
            # Trailing stop - Always apply to manual trades
            if ts_pct > 0 and high_since_entry:
                if current_price <= high_since_entry * (1 - ts_pct):
                    return True, f"trailing stop hit (high: {high_since_entry:.2f})"
            # Take profit - Only if not manual or if entry_price is set
            if not is_manual and tp_pct > 0 and current_price >= entry_price * (1 + tp_pct):
                return True, f"take profit hit ({tp_pct*100:.2f}%)"
        else: # side == "short"
            # Stop loss (price went UP)
            if entry_price > 0 and current_price >= entry_price * (1 + sl_pct):
                return True, f"short stop loss hit ({sl_pct*100:.2f}%)"
            # Trailing stop (low since entry)
            low_since_entry = high_since_entry
            if ts_pct > 0 and low_since_entry:
                if current_price >= low_since_entry * (1 + ts_pct):
                    return True, f"short trailing stop hit (low: {low_since_entry:.2f})"
            # Take profit (price went DOWN)
            if not is_manual and tp_pct > 0 and current_price <= entry_price * (1 - tp_pct):
                return True, f"short take profit hit ({tp_pct*100:.2f}%)"

        # --- Momentum rollover (The "Scalp" exit) ---
        # Skip this aggressive exit for manual trades or VERY strong "Hold" trends
        if not is_manual and not is_strong_trend:
            # Re-enabled "pennies" logic: lock in small profits (0.25%+) to keep cash flow constant
            # unless we're in a clear runner.
            min_scalp_profit = float(os.getenv("SCALP_PROFIT_FLOOR", "0.25")) / 100.0
            
            is_profitable = False
            if side == "buy":
                is_profitable = (current_price > entry_price * (1 + min_scalp_profit))
            else:
                is_profitable = (current_price < entry_price * (1 - min_scalp_profit))

            if is_profitable and len(bars) >= 3:
                closes = [float(bar.close) for bar in bars[-3:]]
                if side == "buy" and closes[-1] < closes[-2] < closes[-3]:
                    return True, f"steady cash flow scalp: momentum rollover (+{((current_price/entry_price)-1)*100:.2f}%)"
                if side == "short" and closes[-1] > closes[-2] > closes[-3]:
                    return True, f"steady cash flow short scalp: momentum rollover (+{((entry_price/current_price)-1)*100:.2f}%)"

        now_hhmm = int(datetime.now().strftime("%H%M"))
        if now_hhmm >= int(Config.ALLOWED_END_HHMM):
            return True, "end of trading window"

        return False, "hold"

    @staticmethod
    def get_option_strategy_legs(underlying_symbol: str, strategy_name: str, chain, current_price: float) -> list[dict] | None:
        """
        Calculates legs for various option strategies based on the current option chain.
        Supported: covered_call, cash_secured_put, long_call, long_put, bull_call_spread, bear_put_spread, straddle
        """
        # This is a placeholder for complex strategy logic
        # In a real scenario, you'd pick the best expiration and strike
        # For now, we return None as a signal that manual strike selection is preferred via webhook
        return None