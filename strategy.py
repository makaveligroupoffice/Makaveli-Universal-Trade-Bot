from __future__ import annotations
import os
import pandas as pd
from datetime import datetime

from config import Config


class Strategy:
    @staticmethod
    def _calculate_indicators(bars):
        """
        Calculates all required technical indicators for various strategies.
        """
        if len(bars) < 20:
            return None

        import pandas as pd
        df = pd.DataFrame([{"close": float(b.close), "high": float(b.high), "low": float(b.low), "volume": float(b.volume)} for b in bars])
        
        # --- Multi-Timeframe Logic (Internal Emulation) ---
        # If we have 200 bars of 1m, the last 60 bars represent 1 hour.
        # We can calculate an 'Hourly' trend within the 1m data.
        df['sma_hourly'] = df['close'].rolling(window=60).mean()
        
        # --- Trend Indicators ---
        df['sma10'] = df['close'].rolling(window=10).mean()
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma50'] = df['close'].rolling(window=min(50, len(df))).mean()
        df['sma200'] = df['close'].rolling(window=min(200, len(df))).mean()
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        
        # --- Momentum Indicators ---
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi14'] = 100 - (100 / (1 + rs))
        
        # MACD
        df['macd'] = df['ema12'] - df['ema26']
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # --- Volatility Indicators ---
        # Bollinger Bands
        df['bb_mid'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * 2)
        
        # ATR
        df['tr'] = df.apply(lambda r: max(r['high'] - r['low'], abs(r['high'] - r['close']), abs(r['low'] - r['close'])), axis=1)
        df['atr14'] = df['tr'].rolling(window=14).mean()
        
        # --- Volume Indicators ---
        df['avg_volume20'] = df['volume'].rolling(20).mean()
        df['rvol'] = df['volume'] / df['avg_volume20']
        
        return df

    @staticmethod
    def should_buy(bars, dynamic_config: dict | None = None) -> tuple[bool, str, float]:
        """
        Returns (should_buy, reason, signal_strength)
        """
        df = Strategy._calculate_indicators(bars)
        if df is None:
            return False, "not enough bars", 0.0

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Strategy Family: Trend Following / Breakout / Momentum
        # Current logic (Sniper/Aggressive) falls into this family
        
        long_term_bullish = last['close'] > last['sma200']
        bullish_trend = last['close'] > last['sma20'] and last['sma10'] > last['sma20'] and last['close'] > last['sma10']
        last_candle_green = last['close'] > prev['close']
        close_relative_pos = (last['close'] - last['low']) / (last['high'] - last['low']) if (last['high'] - last['low']) > 0 else 0
        
        min_rvol = dynamic_config.get("min_rvol", 1.8) if dynamic_config else 1.8
        volume_spike = last['rvol'] > min_rvol
        volatility_excessive = last['atr14'] > (last['close'] * 0.02)

        active = Config.ACTIVE_STRATEGIES
        
        # TIER 1: SNIPER (Standard High Conviction)
        hourly_trend_bullish = last['close'] > last['sma_hourly'] if not pd.isna(last['sma_hourly']) else True
        
        # 1. Trend Following Strategy (Sniper Logic)
        if "TREND" in active:
            if long_term_bullish and hourly_trend_bullish and bullish_trend and last_candle_green and close_relative_pos >= 0.7 and volume_spike and not volatility_excessive:
                return True, f"TREND/SNIPER: trend + high RVOL ({last['rvol']:.2f}) breakout", 1.0

        # 2. RSI Trading Strategy (Mean Reversion / Overbought-Oversold)
        if "RSI" in active:
            if last['rsi14'] < 30 and last['close'] > prev['close']:
                return True, f"RSI: oversold bounce (RSI: {last['rsi14']:.2f})", 0.7

        # 3. Bollinger Bands Strategy (Mean Reversion)
        if "BOLLINGER" in active:
            if last['close'] < last['bb_lower'] and last['close'] > prev['close']:
                 return True, "BOLLINGER: lower band bounce", 0.7

        # 4. MACD Divergence Strategy (Momentum Reversal)
        if "MACD" in active:
            if last['macd_hist'] > 0 and prev['macd_hist'] <= 0:
                return True, f"MACD: bullish crossover (hist: {last['macd_hist']:.4f})", 0.7

        # 5. Breakout Trading Strategy (Range Breakout)
        if "BREAKOUT" in active:
            highest_20 = df['high'].rolling(20).max().iloc[-2]
            if last['close'] > highest_20 and volume_spike:
                return True, f"BREAKOUT: new 20-bar high with volume (RVOL: {last['rvol']:.2f})", 0.8

        # TIER 2: AGGRESSIVE (Taking chances for growth)
        if "AGGRESSIVE" in active:
            aggressive_trend = last['close'] > last['sma10'] and last['sma10'] > last['sma20']
            if aggressive_trend and last_candle_green and close_relative_pos >= 0.5 and volume_spike and not volatility_excessive:
                return True, f"AGGRESSIVE: momentum play (RVOL: {last['rvol']:.2f})", 0.6

        return False, "failed all entry tiers", 0.0

    @staticmethod
    def is_news_safe(symbol: str, market_data_client) -> bool:
        """
        Avoid trading if there's high-impact news or too many recent news items (excessive volatility).
        """
        news = market_data_client.get_news(symbol, days=1)
        # Check for specific negative keywords in headlines
        negative_keywords = ["lawsuit", "investigation", "bankruptcy", "fraud", "hacked"]
        
        for item in news:
            if any(word in item.headline.lower() for word in negative_keywords):
                return False
                
        # If news frequency is extremely high (>10 in 24h), it might be too volatile
        if len(news) > 10:
            return False
            
        return True

    @staticmethod
    def should_short(bars, dynamic_config: dict | None = None) -> tuple[bool, str, float]:
        """
        Returns (should_short, reason, signal_strength)
        """
        df = Strategy._calculate_indicators(bars)
        if df is None:
            return False, "not enough bars", 0.0

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        long_term_bearish = last['close'] < last['sma200']
        bearish_trend = last['close'] < last['sma20'] and last['sma10'] < last['sma20'] and last['close'] < last['sma10']
        last_candle_red = last['close'] < prev['close']
        close_relative_pos = (last['high'] - last['close']) / (last['high'] - last['low']) if (last['high'] - last['low']) > 0 else 0
        
        min_rvol = dynamic_config.get("min_rvol", 1.8) if dynamic_config else 1.8
        volume_spike = last['rvol'] > min_rvol
        volatility_excessive = last['atr14'] > (last['close'] * 0.02)

        active = Config.ACTIVE_STRATEGIES

        # 1. Bearish Trend Following (Sniper)
        if "TREND" in active:
            if long_term_bearish and bearish_trend and last_candle_red and close_relative_pos >= 0.7 and volume_spike and not volatility_excessive:
                return True, f"SNIPER SHORT: trend + high RVOL ({last['rvol']:.2f})", 1.0

        # 2. RSI Overbought (Mean Reversion)
        if "RSI" in active:
            if last['rsi14'] > 70 and last['close'] < prev['close']:
                return True, f"RSI: overbought reversal (RSI: {last['rsi14']:.2f})", 0.7

        # 3. Bollinger Bands Upper Reversal
        if "BOLLINGER" in active:
            if last['close'] > last['bb_upper'] and last['close'] < prev['close']:
                return True, "BOLLINGER: upper band rejection", 0.7

        # 4. MACD Bearish Crossover
        if "MACD" in active:
            if last['macd_hist'] < 0 and prev['macd_hist'] >= 0:
                return True, f"MACD: bearish crossover (hist: {last['macd_hist']:.4f})", 0.7

        # 5. Breakout Trading Strategy (Bearish Breakout)
        if "BREAKOUT" in active:
            lowest_20 = df['low'].rolling(20).min().iloc[-2]
            if last['close'] < lowest_20 and volume_spike:
                return True, f"BREAKOUT: new 20-bar low with volume (RVOL: {last['rvol']:.2f})", 0.8

        # Bearish Aggressive
        if "AGGRESSIVE" in active:
            aggressive_bearish = last['close'] < last['sma10'] and last['sma10'] < last['sma20']
            if aggressive_bearish and last_candle_red and close_relative_pos >= 0.5 and volume_spike and not volatility_excessive:
                return True, f"AGGRESSIVE SHORT: momentum play (RVOL: {last['rvol']:.2f})", 0.6

        return False, "failed all entry tiers", 0.0

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
        if strategy_name == "long_call":
            # Simple ATM or slightly OTM call
            best_strike = None
            min_diff = float('inf')
            for strike in chain.strikes:
                if strike >= current_price:
                    diff = strike - current_price
                    if diff < min_diff:
                        min_diff = diff
                        best_strike = strike
            if best_strike:
                return [{"symbol": f"{underlying_symbol}", "strike": best_strike, "side": "buy", "type": "call"}]

        elif strategy_name == "long_put":
            # Simple ATM or slightly OTM put
            best_strike = None
            min_diff = float('inf')
            for strike in chain.strikes:
                if strike <= current_price:
                    diff = current_price - strike
                    if diff < min_diff:
                        min_diff = diff
                        best_strike = strike
            if best_strike:
                return [{"symbol": f"{underlying_symbol}", "strike": best_strike, "side": "buy", "type": "put"}]

        return None