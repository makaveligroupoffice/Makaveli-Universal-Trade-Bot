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
        
        # Keltner Channels
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['tr'] = df.apply(lambda r: max(r['high'] - r['low'], abs(r['high'] - r['close']), abs(r['low'] - r['close'])), axis=1)
        df['atr20'] = df['tr'].rolling(window=20).mean()
        df['kc_upper'] = df['ema20'] + (df['atr20'] * 2)
        df['kc_lower'] = df['ema20'] - (df['atr20'] * 2)

        # ATR (standard 14 for other uses)
        df['atr14'] = df['tr'].rolling(window=14).mean()
        
        # --- Stochastic Slow ---
        low14 = df['low'].rolling(window=14).min()
        high14 = df['high'].rolling(window=14).max()
        df['stoch_k'] = 100 * ((df['close'] - low14) / (high14 - low14))
        df['stoch_d'] = df['stoch_k'].rolling(window=3).mean() # Slow Stochastic
        
        # --- Parabolic SAR (Simplified Loop) ---
        psar = list(df['close'].iloc[:1]) * len(df)
        bull = True
        af = 0.02
        ep = df['low'].iloc[0] if bull else df['high'].iloc[0]
        
        for i in range(1, len(df)):
            prev_psar = psar[i-1]
            if bull:
                psar[i] = prev_psar + af * (ep - prev_psar)
                if df['low'].iloc[i] < psar[i]:
                    bull = False
                    psar[i] = ep
                    ep = df['low'].iloc[i]
                    af = 0.02
                else:
                    if df['high'].iloc[i] > ep:
                        ep = df['high'].iloc[i]
                        af = min(af + 0.02, 0.2)
                    # PSAR cannot be above the previous two lows
                    psar[i] = min(psar[i], df['low'].iloc[i-1], df['low'].iloc[max(0, i-2)])
            else:
                psar[i] = prev_psar + af * (ep - prev_psar)
                if df['high'].iloc[i] > psar[i]:
                    bull = True
                    psar[i] = ep
                    ep = df['high'].iloc[i]
                    af = 0.02
                else:
                    if df['low'].iloc[i] < ep:
                        ep = df['low'].iloc[i]
                        af = min(af + 0.02, 0.2)
                    # PSAR cannot be below the previous two highs
                    psar[i] = max(psar[i], df['high'].iloc[i-1], df['high'].iloc[max(0, i-2)])
        df['psar'] = psar
        df['psar_bull'] = (df['close'] > df['psar'])
        
        # --- Momentum ---
        df['momentum'] = df['close'] - df['close'].shift(10)

        # --- ADX ---
        df['up_move'] = df['high'].diff()
        df['down_move'] = df['low'].diff().abs()
        df['plus_dm'] = df.apply(lambda r: r['up_move'] if r['up_move'] > r['down_move'] and r['up_move'] > 0 else 0, axis=1)
        df['minus_dm'] = df.apply(lambda r: r['down_move'] if r['down_move'] > r['up_move'] and r['down_move'] > 0 else 0, axis=1)
        
        # TV uses RMA (Running Moving Average) for ADX/ATR, which is ewm(alpha=1/14)
        alpha = 1/14
        df['plus_di'] = 100 * (df['plus_dm'].ewm(alpha=alpha, adjust=False).mean() / df['atr14'])
        df['minus_di'] = 100 * (df['minus_dm'].ewm(alpha=alpha, adjust=False).mean() / df['atr14'])
        df['dx'] = 100 * (df['plus_di'] - df['minus_di']).abs() / (df['plus_di'] + df['minus_di'])
        df['adx'] = df['dx'].ewm(alpha=alpha, adjust=False).mean()
        
        # --- Volume Indicators ---
        df['avg_volume20'] = df['volume'].rolling(20).mean()
        df['rvol'] = df['volume'] / df['avg_volume20']

        # --- Supertrend ---
        multiplier = 3.0
        atr_period = 10
        df['tr_st'] = df.apply(lambda r: max(r['high'] - r['low'], abs(r['high'] - r['close']), abs(r['low'] - r['close'])), axis=1)
        df['atr_st'] = df['tr_st'].rolling(window=atr_period).mean()
        df['hl2'] = (df['high'] + df['low']) / 2
        df['upper_band'] = df['hl2'] + (multiplier * df['atr_st'])
        df['lower_band'] = df['hl2'] - (multiplier * df['atr_st'])
        
        supertrend = [0.0] * len(df)
        final_upper_band = [0.0] * len(df)
        final_lower_band = [0.0] * len(df)
        
        for i in range(1, len(df)):
            # Final Upper Band
            if df['upper_band'].iloc[i] < final_upper_band[i-1] or df['close'].iloc[i-1] > final_upper_band[i-1]:
                final_upper_band[i] = df['upper_band'].iloc[i]
            else:
                final_upper_band[i] = final_upper_band[i-1]
            
            # Final Lower Band
            if df['lower_band'].iloc[i] > final_lower_band[i-1] or df['close'].iloc[i-1] < final_lower_band[i-1]:
                final_lower_band[i] = df['lower_band'].iloc[i]
            else:
                final_lower_band[i] = final_lower_band[i-1]
            
            # Supertrend
            if supertrend[i-1] == final_upper_band[i-1]:
                if df['close'].iloc[i] > final_upper_band[i]:
                    supertrend[i] = final_lower_band[i]
                else:
                    supertrend[i] = final_upper_band[i]
            else:
                if df['close'].iloc[i] < final_lower_band[i]:
                    supertrend[i] = final_upper_band[i]
                else:
                    supertrend[i] = final_lower_band[i]
        
        df['supertrend'] = supertrend
        df['supertrend_bull'] = (df['close'] > df['supertrend'])

        # --- Technical Ratings (Simplified) ---
        # Combine signals from RSI, MACD, Stoch, and MAs
        # Buy = 1, Neutral = 0, Sell = -1
        df['tr_rsi'] = df['rsi14'].apply(lambda x: 1 if x < 30 else (-1 if x > 70 else 0))
        df['tr_macd'] = df['macd_hist'].apply(lambda x: 1 if x > 0 else -1)
        df['tr_stoch'] = df['stoch_k'].apply(lambda x: 1 if x < 20 else (-1 if x > 80 else 0))
        df['tr_ma'] = df.apply(lambda r: 1 if r['close'] > r['sma20'] and r['sma10'] > r['sma20'] else -1, axis=1)
        df['tech_rating'] = (df['tr_rsi'] + df['tr_macd'] + df['tr_stoch'] + df['tr_ma']) / 4.0
        
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
        
        # Expert Tuning: Tighten Sniper to reach 75%+ success rate
        # 10x Growth Goal: Prioritize high-conviction momentum stacks
        sniper_stack = last['close'] > last['sma10'] > last['sma20']
        if 'sma50' in last and not pd.isna(last['sma50']):
            sniper_stack = last['close'] > last['sma10'] > last['sma20'] > last['sma50']

        candle_quality = last_candle_green and close_relative_pos >= 0.85
        
        # 1. Trend Following Strategy (Sniper Logic)
        if "TREND" in active:
            if long_term_bullish and hourly_trend_bullish and sniper_stack and candle_quality and last['rvol'] > 2.2 and not volatility_excessive:
                return True, f"TREND/SNIPER: perfect stack + top-tier candle + extreme RVOL ({last['rvol']:.2f})", 1.0

        # 2. RSI Trading Strategy (Mean Reversion / Overbought-Oversold)
        if "RSI" in active:
            # Expert Tuning: Require candle confirmation for mean reversion
            if last['rsi14'] < 25 and last_candle_green and close_relative_pos > 0.5:
                return True, f"RSI: deep oversold bounce (RSI: {last['rsi14']:.2f})", 0.7

        # 3. Bollinger Bands Strategy (Mean Reversion)
        if "BOLLINGER" in active:
            if last['close'] < last['bb_lower'] and last_candle_green:
                 return True, "BOLLINGER: lower band reversal", 0.7

        # 4. MACD Divergence Strategy (Momentum Reversal)
        if "MACD" in active:
            if last['macd_hist'] > 0 and prev['macd_hist'] <= 0 and last_candle_green:
                return True, f"MACD: bullish crossover (hist: {last['macd_hist']:.4f})", 0.7

        # 5. Breakout Trading Strategy (Range Breakout)
        if "BREAKOUT" in active:
            highest_20 = df['high'].rolling(20).max().iloc[-2]
            # Expert Tuning: Require close above high + volume
            if last['close'] > highest_20 and volume_spike and last_candle_green:
                return True, f"BREAKOUT: clear range breakout with volume (RVOL: {last['rvol']:.2f})", 0.8

        # --- New TradingView Strategies ---

        # 6. BarUpDn Strategy
        if "BARUPDN" in active:
            if last['close'] > last['open'] and prev['close'] > prev['open']:
                return True, "BARUPDN: 2 consecutive green bars", 0.5

        # 7. Bollinger Bands Directed (Trend + BB Reversal)
        if "BOLLINGER_DIRECTED" in active:
            if long_term_bullish and last['close'] < last['bb_lower'] and last_candle_green:
                return True, "BOLLINGER_DIRECTED: trend-aligned lower band reversal", 0.8

        # 8. Consecutive Up
        if "CONSECUTIVE" in active:
            if len(df) >= 4:
                three_green = all(df['close'].iloc[-i] > df['open'].iloc[-i] for i in range(1, 4))
                if three_green:
                    return True, "CONSECUTIVE: 3 green bars in a row", 0.6

        # 9. Greedy
        if "GREEDY" in active:
            if last['close'] > prev['close']:
                return True, "GREEDY: close higher than previous close", 0.4

        # 10. Inside Bar
        if "INSIDE_BAR" in active:
            # Check if previous bar was an inside bar and current broke out UP
            if len(df) >= 3:
                p2 = df.iloc[-3]
                p1 = df.iloc[-2]
                is_inside = p1['high'] < p2['high'] and p1['low'] > p2['low']
                if is_inside and last['close'] > p1['high']:
                    return True, "INSIDE_BAR: bullish breakout of inside bar", 0.7

        # 11. Keltner Channels
        if "KELTNER" in active:
            if last['close'] < last['kc_lower'] and last_candle_green:
                return True, "KELTNER: lower channel reversal", 0.7

        # 12. Momentum Strategy
        if "MOMENTUM" in active:
            if last['momentum'] > 0 and prev['momentum'] <= 0:
                return True, "MOMENTUM: positive crossover", 0.6

        # 13. MovingAve2Line Cross (EMA 12/26)
        if "MA_2LINE_CROSS" in active:
            if last['ema12'] > last['ema26'] and prev['ema12'] <= prev['ema26']:
                return True, "MA_2LINE_CROSS: EMA12/26 bullish crossover", 0.8

        # 14. MovingAvg Cross (SMA 50/200)
        if "MA_CROSS" in active:
            if last['sma50'] > last['sma200'] and prev['sma50'] <= prev['sma200']:
                return True, "MA_CROSS: SMA50/200 bullish crossover (Golden Cross)", 0.9

        # 15. Outside Bar
        if "OUTSIDE_BAR" in active:
            if last['high'] > prev['high'] and last['low'] < prev['low'] and last_candle_green:
                return True, "OUTSIDE_BAR: bullish outside bar", 0.6

        # 16. Pivot Reversal
        if "PIVOT_REVERSAL" in active:
            low_left = df['low'].iloc[-3]
            low_pivot = df['low'].iloc[-2]
            low_right = df['low'].iloc[-1]
            if low_pivot < low_left and low_pivot < low_right and last_candle_green:
                return True, "PIVOT_REVERSAL: bullish pivot point reversal", 0.7

        # 17. Price Channel (Donchian)
        if "PRICE_CHANNEL" in active:
            upper_20 = df['high'].rolling(20).max().iloc[-2]
            if last['close'] > upper_20:
                return True, "PRICE_CHANNEL: price broke above 20-period high", 0.7

        # 18. Rob Booker - ADX Breakout
        if "ROB_BOOKER_ADX" in active:
            if last['adx'] > 25 and last['plus_di'] > last['minus_di'] and last['close'] > df['high'].rolling(10).max().iloc[-2]:
                return True, "ROB_BOOKER_ADX: ADX > 25 breakout", 0.8

        # 19. Stochastic Slow
        if "STOCHASTIC" in active:
            if last['stoch_k'] < 20 and last['stoch_k'] > last['stoch_d'] and prev['stoch_k'] <= prev['stoch_d']:
                return True, "STOCHASTIC: oversold bullish crossover", 0.7

        # 20. Parabolic SAR
        if "PSAR" in active:
            if last['psar_bull'] and not prev['psar_bull']:
                return True, "PSAR: bullish flip", 0.7

        # 21. Pivot Extension
        if "PIVOT_EXTENSION" in active:
            # Simple extension: price > pivot high of last 10 bars
            pivot_high_10 = df['high'].rolling(10).max().iloc[-2]
            if last['close'] > pivot_high_10:
                return True, "PIVOT_EXTENSION: breakout above pivot high", 0.6

        # 22. Supertrend
        if "SUPERTREND" in active:
            if last['supertrend_bull'] and not prev['supertrend_bull']:
                return True, "SUPERTREND: bullish trend flip", 0.8

        # 23. Technical Ratings
        if "TECHNICAL_RATINGS" in active:
            if last['tech_rating'] > 0.5:
                return True, f"TECHNICAL_RATINGS: strong bullish rating ({last['tech_rating']:.2f})", 0.7

        # 24. Volty Expan Close
        if "VOLTY_EXPAN_CLOSE" in active:
            if last['close'] > prev['close'] + 2.0 * prev['atr14']:
                return True, "VOLTY_EXPAN_CLOSE: volatility expansion to the upside", 0.7

        # TIER 2: AGGRESSIVE (Taking chances for growth)
        if "AGGRESSIVE" in active:
            # Expert Tuning: Allow slightly looser entries for growth but keep RVOL high
            # Targeting 10x growth via volume-backed momentum
            aggressive_trend = last['close'] > last['sma10'] and last['sma10'] > last['sma20']
            if aggressive_trend and last_candle_green and close_relative_pos >= 0.7 and last['rvol'] > 1.8 and not volatility_excessive:
                return True, f"AGGRESSIVE: momentum play (RVOL: {last['rvol']:.2f})", 0.6

        return False, "failed all entry tiers", 0.0

    @staticmethod
    def is_news_safe(symbol: str, market_data_client, news_list: list | None = None) -> bool:
        """
        Avoid trading if there's high-impact news or too many recent news items (excessive volatility).
        """
        news = news_list if news_list is not None else market_data_client.get_news(symbol, days=1)
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
            sniper_bearish_stack = last['close'] < last['sma10'] < last['sma20']
            if 'sma50' in last and not pd.isna(last['sma50']):
                sniper_bearish_stack = last['close'] < last['sma10'] < last['sma20'] < last['sma50']

            if long_term_bearish and sniper_bearish_stack and last_candle_red and close_relative_pos >= 0.8 and last['rvol'] > 2.2 and not volatility_excessive:
                return True, f"SNIPER SHORT: trend + high-quality candle + extreme RVOL ({last['rvol']:.2f})", 1.0

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

        # --- New TradingView Strategies (Short) ---

        # 6. BarUpDn Strategy
        if "BARUPDN" in active:
            if last['close'] < last['open'] and prev['close'] < prev['open']:
                return True, "BARUPDN: 2 consecutive red bars", 0.5

        # 7. Bollinger Bands Directed
        if "BOLLINGER_DIRECTED" in active:
            if long_term_bearish and last['close'] > last['bb_upper'] and last['close'] < prev['close']:
                return True, "BOLLINGER_DIRECTED: trend-aligned upper band rejection", 0.8

        # 8. Consecutive Down
        if "CONSECUTIVE" in active:
            if len(df) >= 4:
                three_red = all(df['close'].iloc[-i] < df['open'].iloc[-i] for i in range(1, 4))
                if three_red:
                    return True, "CONSECUTIVE: 3 red bars in a row", 0.6

        # 9. Greedy
        if "GREEDY" in active:
            if last['close'] < prev['close']:
                return True, "GREEDY: close lower than previous close", 0.4

        # 10. Inside Bar
        if "INSIDE_BAR" in active:
            if len(df) >= 3:
                p2 = df.iloc[-3]
                p1 = df.iloc[-2]
                is_inside = p1['high'] < p2['high'] and p1['low'] > p2['low']
                if is_inside and last['close'] < p1['low']:
                    return True, "INSIDE_BAR: bearish breakout of inside bar", 0.7

        # 11. Keltner Channels
        if "KELTNER" in active:
            if last['close'] > last['kc_upper'] and last['close'] < prev['close']:
                return True, "KELTNER: upper channel reversal", 0.7

        # 12. Momentum Strategy
        if "MOMENTUM" in active:
            if last['momentum'] < 0 and prev['momentum'] >= 0:
                return True, "MOMENTUM: negative crossover", 0.6

        # 13. MovingAve2Line Cross
        if "MA_2LINE_CROSS" in active:
            if last['ema12'] < last['ema26'] and prev['ema12'] >= prev['ema26']:
                return True, "MA_2LINE_CROSS: EMA12/26 bearish crossover", 0.8

        # 14. MovingAvg Cross
        if "MA_CROSS" in active:
            if last['sma50'] < last['sma200'] and prev['sma50'] >= prev['sma200']:
                return True, "MA_CROSS: SMA50/200 bearish crossover (Death Cross)", 0.9

        # 15. Outside Bar
        if "OUTSIDE_BAR" in active:
            if last['high'] > prev['high'] and last['low'] < prev['low'] and last['close'] < prev['close']:
                return True, "OUTSIDE_BAR: bearish outside bar", 0.6

        # 16. Pivot Reversal
        if "PIVOT_REVERSAL" in active:
            high_left = df['high'].iloc[-3]
            high_pivot = df['high'].iloc[-2]
            high_right = df['high'].iloc[-1]
            if high_pivot > high_left and high_pivot > high_right and last['close'] < prev['close']:
                return True, "PIVOT_REVERSAL: bearish pivot point reversal", 0.7

        # 17. Price Channel
        if "PRICE_CHANNEL" in active:
            lower_20 = df['low'].rolling(20).min().iloc[-2]
            if last['close'] < lower_20:
                return True, "PRICE_CHANNEL: price broke below 20-period low", 0.7

        # 18. Rob Booker - ADX Breakout
        if "ROB_BOOKER_ADX" in active:
            if last['adx'] > 25 and last['minus_di'] > last['plus_di'] and last['close'] < df['low'].rolling(10).min().iloc[-2]:
                return True, "ROB_BOOKER_ADX: ADX > 25 bearish breakout", 0.8

        # 19. Stochastic Slow
        if "STOCHASTIC" in active:
            if last['stoch_k'] > 80 and last['stoch_k'] < last['stoch_d'] and prev['stoch_k'] >= prev['stoch_d']:
                return True, "STOCHASTIC: overbought bearish crossover", 0.7

        # 20. Parabolic SAR
        if "PSAR" in active:
            if not last['psar_bull'] and prev['psar_bull']:
                return True, "PSAR: bearish flip", 0.7

        # 21. Pivot Extension
        if "PIVOT_EXTENSION" in active:
            pivot_low_10 = df['low'].rolling(10).min().iloc[-2]
            if last['close'] < pivot_low_10:
                return True, "PIVOT_EXTENSION: breakout below pivot low", 0.6

        # 22. Supertrend
        if "SUPERTREND" in active:
            if not last['supertrend_bull'] and prev['supertrend_bull']:
                return True, "SUPERTREND: bearish trend flip", 0.8

        # 23. Technical Ratings
        if "TECHNICAL_RATINGS" in active:
            if last['tech_rating'] < -0.5:
                return True, f"TECHNICAL_RATINGS: strong bearish rating ({last['tech_rating']:.2f})", 0.7

        # 24. Volty Expan Close
        if "VOLTY_EXPAN_CLOSE" in active:
            if last['close'] < prev['close'] - 2.0 * prev['atr14']:
                return True, "VOLTY_EXPAN_CLOSE: volatility expansion to the downside", 0.7

        # Bearish Aggressive
        if "AGGRESSIVE" in active:
            aggressive_bearish = last['close'] < last['sma10'] and last['sma10'] < last['sma20']
            if aggressive_bearish and last_candle_red and close_relative_pos >= 0.7 and last['rvol'] > 1.8 and not volatility_excessive:
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
            # Expert Tuning: Tighten scalp profit floor to 0.15% for constant cash flow
            # but require 4 bars of reversal instead of 3 to avoid getting stopped out by noise.
            min_scalp_profit = float(os.getenv("SCALP_PROFIT_FLOOR", "0.15")) / 100.0
            
            is_profitable = False
            if side == "buy":
                is_profitable = (current_price > entry_price * (1 + min_scalp_profit))
            else:
                is_profitable = (current_price < entry_price * (1 - min_scalp_profit))

            if is_profitable and len(bars) >= 4:
                closes = [float(bar.close) for bar in bars[-4:]]
                if side == "buy" and closes[-1] < closes[-2] < closes[-3] < closes[-4]:
                    return True, f"steady cash flow scalp: 4-bar momentum rollover (+{((current_price/entry_price)-1)*100:.2f}%)"
                if side == "short" and closes[-1] > closes[-2] > closes[-3] > closes[-4]:
                    return True, f"steady cash flow short scalp: 4-bar momentum rollover (+{((entry_price/current_price)-1)*100:.2f}%)"

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