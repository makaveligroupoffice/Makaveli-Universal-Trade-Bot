from __future__ import annotations
import os
import pandas as pd
from datetime import datetime

from config import Config
from candlestick_patterns import CandlestickPatterns
from chart_patterns import ChartPatterns


class Strategy:
    @staticmethod
    def _calculate_indicators(bars):
        """
        Calculates all required technical indicators for various strategies.
        """
        if len(bars) < 20:
            return None

        import pandas as pd
        df = pd.DataFrame([{"open": float(b.open), "close": float(b.close), "high": float(b.high), "low": float(b.low), "volume": float(b.volume)} for b in bars])
        
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
        
        # --- VWAP (Simplified) ---
        df['cum_vol'] = df['volume'].cumsum()
        df['cum_pv'] = ((df['high'] + df['low'] + df['close']) / 3 * df['volume']).cumsum()
        df['vwap'] = df['cum_pv'] / df['cum_vol']
        df['above_vwap'] = df['close'] > df['vwap']

        # --- Volume Indicators ---
        df['avg_volume20'] = df['volume'].rolling(20).mean()
        df['rvol'] = df['volume'] / df['avg_volume20']
        df['volume_spike'] = df['volume'] > (df['avg_volume20'] * 3.0)

        # --- Liquidity Zones & Order Blocks (Simplified Detection) ---
        # Order Block: Large candle preceding a strong move, where price consolidates later
        df['body_size'] = (df['close'] - df['open']).abs()
        df['is_bullish_ob'] = (df['close'] < df['open']) & (df['volume'] > df['avg_volume20'] * 1.5) & (df['close'].shift(-1) > df['high'])
        df['is_bearish_ob'] = (df['close'] > df['open']) & (df['volume'] > df['avg_volume20'] * 1.5) & (df['close'].shift(-1) < df['low'])

        # Fair Value Gap (FVG)
        df['fvg_bull'] = (df['low'] > df['high'].shift(2))
        df['fvg_bear'] = (df['high'] < df['low'].shift(2))

        # Break of Structure (BOS)
        df['hh'] = (df['high'] > df['high'].shift(1).rolling(10).max())
        df['ll'] = (df['low'] < df['low'].shift(1).rolling(10).min())
        df['bos_bull'] = df['hh'] & (df['close'] > df['high'].shift(1))
        df['bos_bear'] = df['ll'] & (df['close'] < df['low'].shift(1))

        # Liquidity Sweep
        df['sweep_low'] = (df['low'] < df['low'].rolling(20).min().shift(1)) & (df['close'] > df['low'].rolling(20).min().shift(1))
        df['sweep_high'] = (df['high'] > df['high'].rolling(20).max().shift(1)) & (df['close'] < df['high'].rolling(20).max().shift(1))

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

        # --- Technical Ratings & Momentum Scoring ---
        # Momentum Scoring System (0-100)
        df['mom_rsi'] = df['rsi14'] / 100.0
        df['mom_macd'] = (df['macd_hist'] - df['macd_hist'].rolling(50).min()) / (df['macd_hist'].rolling(50).max() - df['macd_hist'].rolling(50).min())
        df['mom_adx'] = df['adx'] / 100.0
        df['momentum_score'] = (df['mom_rsi'] + df['mom_macd'] + df['mom_adx']) / 3.0 * 100.0

        # Technical Ratings (Simplified)
        # Combine signals from RSI, MACD, Stoch, and MAs
        # Buy = 1, Neutral = 0, Sell = -1
        df['tr_rsi'] = df['rsi14'].apply(lambda x: 1 if x < 30 else (-1 if x > 70 else 0))
        df['tr_macd'] = df['macd_hist'].apply(lambda x: 1 if x > 0 else -1)
        df['tr_stoch'] = df['stoch_k'].apply(lambda x: 1 if x < 20 else (-1 if x > 80 else 0))
        df['tr_ma'] = df.apply(lambda r: 1 if r['close'] > r['sma20'] and r['sma10'] > r['sma20'] else -1, axis=1)
        df['tech_rating'] = (df['tr_rsi'] + df['tr_macd'] + df['tr_stoch'] + df['tr_ma']) / 4.0

        # --- Candlestick Patterns ---
        df = CandlestickPatterns.detect_all(df)

        # --- Chart Patterns ---
        df = ChartPatterns.detect_all(df)

        # --- Auto Trend Detector ---
        # Find local peaks/troughs (support/resistance)
        df['support'] = df['low'].rolling(window=20).min()
        df['resistance'] = df['high'].rolling(window=20).max()
        df['near_support'] = df['close'] < (df['support'] * 1.01)
        df['near_resistance'] = df['close'] > (df['resistance'] * 0.99)
        
        return df

    @staticmethod
    def should_buy(bars, dynamic_config: dict | None = None) -> tuple[bool, str, float, dict]:
        """
        Returns (should_buy, reason, signal_strength, indicators)
        Uses confluence of multiple strategy families to ensure high-probability entries.
        Target: 75%+ Win Ratio
        """
        df = Strategy._calculate_indicators(bars)
        if df is None:
            return False, "not enough bars", 0.0, {}

        import pandas as pd
        last = df.iloc[-1]
        last_indicators = last.to_dict()
        prev = df.iloc[-2]
        
        active = Config.ACTIVE_STRATEGIES
        matches = []
        strength_score = 0.0
        
        # Base filters
        volatility_excessive = last['atr14'] > (last['close'] * 0.03) 
        last_candle_green = last['close'] > prev['close']
        
        # Determine if we are in After-Hours for stricter filtering
        from datetime import datetime
        now_hhmm = int(datetime.now().strftime("%H%M"))
        is_after_hours = now_hhmm > 1600 or now_hhmm < 930

        # Stricter Relative Position for AH (Top 15% instead of 20%)
        min_close_relative = 0.85 if is_after_hours else 0.8
        close_relative_pos = (last['close'] - last['low']) / (last['high'] - last['low']) if (last['high'] - last['low']) > 0 else 0
        
        # Stricter RVOL for AH (3.0 instead of 1.8)
        min_rvol_base = 3.0 if is_after_hours else 1.8
        volume_spike = last['rvol'] > (dynamic_config.get("min_rvol", min_rvol_base) if dynamic_config else min_rvol_base)

        # 1. FAMILY: TREND
        trend_match = False
        long_term_bullish = last['close'] > last['sma200']
        hourly_trend_bullish = last['close'] > last['sma_hourly'] if not pd.isna(last['sma_hourly']) else True
        sniper_stack = last['close'] > last['sma10'] > last['sma20']
        if 'sma50' in last and not pd.isna(last['sma50']):
            sniper_stack = sniper_stack and last['sma20'] > last['sma50']
        
        # VWAP Filter
        vwap_filter = last['close'] > last['vwap'] if 'vwap' in last else True

        if "TREND" in active:
            if long_term_bullish and hourly_trend_bullish and sniper_stack and last_candle_green and close_relative_pos >= min_close_relative and vwap_filter:
                matches.append("TREND_SNIPER")
                strength_score += 0.5
                trend_match = True

        if "SUPERTREND" in active:
            if last['supertrend_bull'] and not prev['supertrend_bull']:
                matches.append("SUPERTREND_FLIP")
                strength_score += 0.4
                trend_match = True

        # 2. FAMILY: MOMENTUM / REVERSION
        mom_match = False
        if "RSI" in active:
            if last['rsi14'] < 30 and last_candle_green:
                matches.append("RSI_OVERSOLD")
                strength_score += 0.4
                mom_match = True
        
        if "MACD" in active:
            if last['macd_hist'] > 0 and prev['macd_hist'] <= 0:
                matches.append("MACD_CROSS")
                strength_score += 0.4
                mom_match = True

        if "STOCHASTIC" in active:
            if last['stoch_k'] < 20 and last['stoch_k'] > last['stoch_d'] and prev['stoch_k'] <= prev['stoch_d']:
                matches.append("STOCH_CROSS")
                strength_score += 0.3
                mom_match = True
        
        if "BOLLINGER" in active:
            if last['close'] < last['bb_lower'] and last_candle_green:
                matches.append("BB_REVERSAL")
                strength_score += 0.3
                mom_match = True

        if "MOMENTUM" in active:
            if last['momentum'] > 0 and prev['momentum'] <= 0:
                matches.append("MOM_UP")
                strength_score += 0.2
                mom_match = True

        # 3. FAMILY: PRICE ACTION / PATTERNS
        pa_match = False
        if "INSIDE_BAR" in active and len(df) >= 3:
             p1 = df.iloc[-2]; p2 = df.iloc[-3]
             if p1['high'] < p2['high'] and p1['low'] > p2['low'] and last['close'] > p1['high']:
                 matches.append("INSIDE_BREAKOUT")
                 strength_score += 0.3
                 pa_match = True

        if "PATTERNS" in active:
            biases = CandlestickPatterns.get_biases()
            found_p = []
            for p, bias in biases.items():
                if last.get(p) and bias == "bullish":
                    found_p.append(p.replace('CP_', ''))
            if found_p:
                matches.append(f"CANDLE_{found_p[0]}")
                strength_score += 0.4
                pa_match = True

        if "CHART" in active:
            biases = ChartPatterns.get_biases()
            found_c = []
            for p, bias in biases.items():
                if last.get(p) and bias == "bullish":
                    found_c.append(p.replace('CH_', ''))
            if found_c:
                matches.append(f"CHART_{found_c[0]}")
                strength_score += 0.5
                pa_match = True

        # 4. FAMILY: SCALPING (1-minute aggressive)
        scalp_match = False
        if "SCALPING" in active:
             # Fast EMAs (9/21) cross
             ema_cross = last['sma10'] > last['sma20'] and prev['sma10'] <= prev['sma20']
             # Volatility requirement
             vol_ok = last['atr14'] > (last['close'] * 0.001) # Minimum movement
             if ema_cross and vol_ok and last['rvol'] > 1.5:
                 matches.append("SCALP_CROSS")
                 strength_score += 0.4
                 scalp_match = True

        # 5. FAMILY: BREAKOUT / VOLUME
        break_match = False
        if "BREAKOUT" in active:
            highest_20 = df['high'].rolling(20).max().iloc[-2]
            if last['close'] > highest_20 and volume_spike:
                matches.append("RANGE_BREAKOUT")
                strength_score += 0.5
                break_match = True

        # --- CONFLUENCE LOGIC ---
        # We need at least 2 families or 1 very strong signal (Sniper)
        num_families = sum([trend_match, mom_match, pa_match, break_match, scalp_match])
        
        # Final Decision
        final_strength = min(1.0, strength_score)
        
        # --- High Probability Filters ---
        # 1. ADX Trend Strength: Ensure a trend exists for trend-based entries
        is_trending = last['adx'] > Config.MIN_ADX_TREND
        
        # 2. RSI Extreme: Avoid buying at the absolute peak
        rsi_safe = last['rsi14'] < 70

        # Increase requirement to 3 families or 2 families + high strength
        # AND require ADX for TREND_SNIPER
        if (num_families >= 3 and final_strength >= 0.7 and rsi_safe) or (num_families >= 2 and final_strength >= 0.85 and rsi_safe):
            if "TREND_SNIPER" in matches and not is_trending:
                return False, f"TREND_SNIPER rejected: weak trend (ADX: {last['adx']:.1f})", 0.0, last_indicators
            return True, f"CONFLUENCE ({'+'.join(matches)})", final_strength, last_indicators
        
        # Stricter Sniper: Requires trend match + higher RVOL + ADX trend
        if "TREND_SNIPER" in matches and last['rvol'] > 3.5 and is_trending:
            return True, "SNIPER: ultra-high-conviction trend stack + volume", 1.0, last_indicators

        if "AGGRESSIVE" in active and final_strength >= 0.6 and last_candle_green and rsi_safe:
             return True, f"AGGRESSIVE: {matches[0] if matches else 'MOMENTUM'}", final_strength, last_indicators

        return False, "insufficient confluence or signal strength", 0.0, last_indicators

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
    def should_short(bars, dynamic_config: dict | None = None) -> tuple[bool, str, float, dict]:
        """
        Returns (should_short, reason, signal_strength, indicators)
        Uses confluence for high-probability short entries.
        """
        df = Strategy._calculate_indicators(bars)
        if df is None:
            return False, "not enough bars", 0.0, {}

        import pandas as pd
        last = df.iloc[-1]
        last_indicators = last.to_dict()
        prev = df.iloc[-2]
        
        active = Config.ACTIVE_STRATEGIES
        matches = []
        strength_score = 0.0
        
        # Base filters
        volatility_excessive = last['atr14'] > (last['close'] * 0.03)
        last_candle_red = last['close'] < prev['close']
        
        # Determine if we are in After-Hours for stricter filtering
        from datetime import datetime
        now_hhmm = int(datetime.now().strftime("%H%M"))
        is_after_hours = now_hhmm > 1600 or now_hhmm < 930
        
        # Stricter Relative Position for AH (Bottom 15% instead of 20%)
        min_close_relative = 0.85 if is_after_hours else 0.8
        close_relative_pos = (last['high'] - last['close']) / (last['high'] - last['low']) if (last['high'] - last['low']) > 0 else 0
        
        # Stricter RVOL for AH (3.0 instead of 1.8)
        min_rvol_base = 3.0 if is_after_hours else 1.8
        volume_spike = last['rvol'] > (dynamic_config.get("min_rvol", min_rvol_base) if dynamic_config else min_rvol_base)

        # 1. FAMILY: TREND
        trend_match = False
        long_term_bearish = last['close'] < last['sma200']
        hourly_trend_bearish = last['close'] < last['sma_hourly'] if not pd.isna(last['sma_hourly']) else True
        sniper_bearish_stack = last['close'] < last['sma10'] < last['sma20']
        if 'sma50' in last and not pd.isna(last['sma50']):
            sniper_bearish_stack = sniper_bearish_stack and last['sma20'] < last['sma50']
            
        # VWAP Filter for Shorts
        vwap_filter_short = last['close'] < last['vwap'] if 'vwap' in last else True

        if "TREND" in active:
            if long_term_bearish and hourly_trend_bearish and sniper_bearish_stack and last_candle_red and close_relative_pos >= min_close_relative and vwap_filter_short:
                matches.append("SNIPER_SHORT")
                strength_score += 0.5
                trend_match = True

        if "SUPERTREND" in active:
            if not last['supertrend_bull'] and prev['supertrend_bull']:
                matches.append("SUPERTREND_BEAR_FLIP")
                strength_score += 0.4
                trend_match = True

        # 2. FAMILY: MOMENTUM / REVERSION
        mom_match = False
        if "RSI" in active:
            if last['rsi14'] > 70 and last_candle_red:
                matches.append("RSI_OVERBOUGHT")
                strength_score += 0.4
                mom_match = True
        
        if "MACD" in active:
            if last['macd_hist'] < 0 and prev['macd_hist'] >= 0:
                matches.append("MACD_BEAR_CROSS")
                strength_score += 0.4
                mom_match = True

        if "BOLLINGER" in active:
            if last['close'] > last['bb_upper'] and last_candle_red:
                matches.append("BB_REJECTION")
                strength_score += 0.3
                mom_match = True
        
        if "MOMENTUM" in active:
            if last['momentum'] < 0 and prev['momentum'] >= 0:
                matches.append("MOM_DOWN")
                strength_score += 0.2
                mom_match = True

        # 3. FAMILY: PRICE ACTION / PATTERNS
        pa_match = False
        if "INSIDE_BAR" in active and len(df) >= 3:
             p1 = df.iloc[-2]; p2 = df.iloc[-3]
             if p1['high'] < p2['high'] and p1['low'] > p2['low'] and last['close'] < p1['low']:
                 matches.append("INSIDE_BEAR_BREAKOUT")
                 strength_score += 0.3
                 pa_match = True

        if "PATTERNS" in active:
            biases = CandlestickPatterns.get_biases()
            found_p = []
            for p, bias in biases.items():
                if last.get(p) and bias == "bearish":
                    found_p.append(p.replace('CP_', ''))
            if found_p:
                matches.append(f"CANDLE_{found_p[0]}")
                strength_score += 0.4
                pa_match = True

        if "CHART" in active:
            biases = ChartPatterns.get_biases()
            found_c = []
            for p, bias in biases.items():
                if last.get(p) and bias == "bearish":
                    found_c.append(p.replace('CH_', ''))
            if found_c:
                matches.append(f"CHART_{found_c[0]}")
                strength_score += 0.5
                pa_match = True

        # 4. FAMILY: SCALPING (1-minute aggressive short)
        scalp_match = False
        if "SCALPING" in active:
             # Fast EMAs (9/21) cross down
             ema_cross = last['sma10'] < last['sma20'] and prev['sma10'] >= prev['sma20']
             # Volatility requirement
             vol_ok = last['atr14'] > (last['close'] * 0.001) # Minimum movement
             if ema_cross and vol_ok and last['rvol'] > 1.5:
                 matches.append("SCALP_SHORT_CROSS")
                 strength_score += 0.4
                 scalp_match = True

        # 4. FAMILY: BREAKOUT / VOLUME
        break_match = False
        if "BREAKOUT" in active:
            lowest_20 = df['low'].rolling(20).min().iloc[-2]
            if last['close'] < lowest_20 and volume_spike:
                matches.append("RANGE_BREAKDOWN")
                strength_score += 0.5
                break_match = True

        # --- CONFLUENCE LOGIC ---
        num_families = sum([trend_match, mom_match, pa_match, break_match, scalp_match])
        # Final Decision
        final_strength = min(1.0, strength_score)
        
        # --- High Probability Filters ---
        # 1. ADX Trend Strength: Ensure a trend exists for trend-based shorting
        is_trending = last['adx'] > Config.MIN_ADX_TREND
        
        # 2. RSI Extreme: Avoid shorting at the absolute bottom
        rsi_safe = last['rsi14'] > 30

        # Increase requirement to 3 families or 2 families + high strength
        if (num_families >= 3 and final_strength >= 0.7 and rsi_safe) or (num_families >= 2 and final_strength >= 0.85 and rsi_safe):
            if "SNIPER_SHORT" in matches and not is_trending:
                return False, f"SNIPER_SHORT rejected: weak trend (ADX: {last['adx']:.1f})", 0.0, last_indicators
            return True, f"CONFLUENCE SHORT ({'+'.join(matches)})", final_strength, last_indicators
        
        # Stricter Sniper Short: Requires trend match + higher RVOL + ADX trend
        if "SNIPER_SHORT" in matches and last['rvol'] > 3.5 and is_trending:
            return True, "SNIPER SHORT: ultra-high-conviction trend stack + volume", 1.0, last_indicators

        if "AGGRESSIVE" in active and final_strength >= 0.6 and last_candle_red and rsi_safe:
             return True, f"AGGRESSIVE SHORT: {matches[0] if matches else 'MOMENTUM'}", final_strength, last_indicators

        return False, "insufficient confluence or signal strength", 0.0, last_indicators

    @staticmethod
    def should_sell(entry_price: float, current_price: float, bars, high_since_entry: float | None = None, side: str = "buy", dynamic_config: dict | None = None, is_manual: bool = False, entry_time: datetime | None = None) -> tuple[bool, str]:
        if current_price <= 0:
            return False, "invalid current price"

        # --- Time-Based Exit ---
        if entry_time and Config.TIME_BASED_EXIT_MINUTES > 0:
            elapsed = (datetime.now() - entry_time).total_seconds() / 60.0
            if elapsed >= Config.TIME_BASED_EXIT_MINUTES:
                return True, f"time-based exit hit ({Config.TIME_BASED_EXIT_MINUTES} mins elapsed)"

        # Use dynamic config if provided, else fallback to global config
        sl_pct = (dynamic_config.get("stop_loss_pct", Config.STOP_LOSS_PCT) if dynamic_config else Config.STOP_LOSS_PCT) / 100.0
        tp_pct = (dynamic_config.get("take_profit_pct", Config.TAKE_PROFIT_PCT) if dynamic_config else Config.TAKE_PROFIT_PCT) / 100.0
        ts_pct = Config.TRAILING_STOP_PCT / 100.0 
        ts_activation_pct = Config.TRAILING_STOP_ACTIVATION_PCT / 100.0

        # --- Profit Lock System ---
        profit_lock_pct = Config.PROFIT_LOCK_PCT / 100.0
        profit_lock_retain_pct = Config.PROFIT_LOCK_RETAIN_PCT / 100.0
        is_profit_locked = False
        if entry_price > 0:
            if side == "buy":
                max_profit_pct = (high_since_entry / entry_price) - 1 if high_since_entry else 0
                if max_profit_pct >= profit_lock_pct:
                    is_profit_locked = True
                    # Exit if we drop below the locked percentage of PEAK profit
                    # e.g. if we reached 2.5%, and retain 80%, we exit at 2.0%
                    lock_exit_price = entry_price * (1 + (max_profit_pct * profit_lock_retain_pct))
                    if current_price <= lock_exit_price:
                        return True, f"profit lock hit: peak {max_profit_pct*100:.2f}% (locked {max_profit_pct*profit_lock_retain_pct*100:.2f}%)"
            else: # short
                low_since_entry = high_since_entry
                max_profit_pct = (entry_price / low_since_entry) - 1 if low_since_entry else 0
                if max_profit_pct >= profit_lock_pct:
                    is_profit_locked = True
                    lock_exit_price = entry_price * (1 - (max_profit_pct * profit_lock_retain_pct))
                    if current_price >= lock_exit_price:
                        return True, f"short profit lock hit: peak {max_profit_pct*100:.2f}% (locked {max_profit_pct*profit_lock_retain_pct*100:.2f}%)"

        # --- Dynamic ATR-Based Exits ---
        last_atr = 0.0
        if len(bars) >= 20:
            df_full = Strategy._calculate_indicators(bars)
            if df_full is not None:
                last_atr = df_full['atr14'].iloc[-1]
                
        if Config.ENABLE_DYNAMIC_ATR_EXITS and last_atr > 0 and entry_price > 0:
            # Override SL/TP with ATR multiples if more conservative
            atr_sl_price = last_atr * Config.ATR_SL_MULTIPLIER
            atr_tp_price = last_atr * Config.ATR_TP_MULTIPLIER
            
            atr_sl_pct = atr_sl_price / entry_price
            atr_tp_pct = atr_tp_price / entry_price
            
            # Use the tighter of the two (fixed pct vs ATR)
            sl_pct = min(sl_pct, atr_sl_pct)
            tp_pct = max(tp_pct, atr_tp_pct) # For TP we might want to go LARGER with ATR if it's trending

        # --- Break-Even Stop Logic ---
        be_profit_pct = Config.BREAK_EVEN_PROFIT_PCT / 100.0
        is_at_break_even = False
        if entry_price > 0:
            if side == "buy":
                highest_pct = (high_since_entry / entry_price) - 1 if high_since_entry else 0
                if highest_pct >= be_profit_pct:
                    is_at_break_even = True
            else: # short
                low_since_entry = high_since_entry # Reuse variable name
                lowest_pct = (entry_price / low_since_entry) - 1 if low_since_entry else 0
                if lowest_pct >= be_profit_pct:
                    is_at_break_even = True

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
        # Targeting 10x growth by letting winners run
        if is_strong_trend:
             ts_pct = ts_pct * 1.5 # 1.5x room for strong runners (tightened from 2.0x)

        if side == "buy":
            # Stop loss
            if entry_price > 0:
                effective_sl_pct = 0.0020 if is_at_break_even else sl_pct # Use 0.20% buffer for BE to avoid noise
                if current_price <= entry_price * (1 - effective_sl_pct):
                    reason = "break-even stop hit" if is_at_break_even else f"stop loss hit ({sl_pct*100:.2f}%)"
                    return True, reason
            # Trailing stop - Only once in enough profit
            if ts_pct > 0 and high_since_entry and entry_price > 0:
                is_activated = (current_price >= entry_price * (1 + ts_activation_pct)) or (high_since_entry >= entry_price * (1 + ts_activation_pct))
                if is_activated and current_price <= high_since_entry * (1 - ts_pct):
                    return True, f"trailing stop hit (high: {high_since_entry:.2f})"
            # Take profit - Only if not manual or if entry_price is set
            if not is_manual and tp_pct > 0 and current_price >= entry_price * (1 + tp_pct):
                return True, f"take profit hit ({tp_pct*100:.2f}%)"
        else: # side == "short"
            # Stop loss (price went UP)
            if entry_price > 0:
                effective_sl_pct = 0.0020 if is_at_break_even else sl_pct
                if current_price >= entry_price * (1 + effective_sl_pct):
                    reason = "short break-even stop hit" if is_at_break_even else f"short stop loss hit ({sl_pct*100:.2f}%)"
                    return True, reason
            # Trailing stop (low since entry)
            low_since_entry = high_since_entry
            if ts_pct > 0 and low_since_entry and entry_price > 0:
                is_activated = (current_price <= entry_price * (1 - ts_activation_pct)) or (low_since_entry <= entry_price * (1 - ts_activation_pct))
                if is_activated and current_price >= low_since_entry * (1 + ts_pct):
                    return True, f"short trailing stop hit (low: {low_since_entry:.2f})"
            # Take profit (price went DOWN)
            if not is_manual and tp_pct > 0 and current_price <= entry_price * (1 - tp_pct):
                return True, f"short take profit hit ({tp_pct*100:.2f}%)"

        # --- Momentum rollover (The "Scalp" exit) ---
        # Skip this aggressive exit for manual trades or VERY strong "Hold" trends
        if not is_manual and not is_strong_trend:
            # Check RSI extremes for early profit taking
            if len(bars) >= 20:
                df_full = Strategy._calculate_indicators(bars)
                if df_full is not None:
                    last_rsi = df_full['rsi14'].iloc[-1]
                    if side == "buy" and last_rsi > 75:
                        return True, f"RSI Overbought ({last_rsi:.1f}): Reached peak momentum floor"
                    if side == "short" and last_rsi < 25:
                        return True, f"RSI Oversold ({last_rsi:.1f}): Reached bottom momentum floor"

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