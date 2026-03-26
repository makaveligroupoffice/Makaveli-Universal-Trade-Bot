from __future__ import annotations
import os
import pandas as pd
import json
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
        df['sma_hourly'] = df['close'].rolling(window=60).mean()
        
        # --- Trend Indicators ---
        df['sma10'] = df['close'].rolling(window=10).mean()
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma50'] = df['close'].rolling(window=min(50, len(df))).mean()
        df['sma200'] = df['close'].rolling(window=min(200, len(df))).mean()
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        
        # --- Momentum Indicators ---
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi14'] = 100 - (100 / (1 + rs))
        
        df['macd'] = df['ema12'] - df['ema26']
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # --- Volatility Indicators ---
        df['bb_mid'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * 2)
        
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['tr'] = df.apply(lambda r: max(r['high'] - r['low'], abs(r['high'] - r['close']), abs(r['low'] - r['close'])), axis=1)
        df['atr20'] = df['tr'].rolling(window=20).mean()
        df['kc_upper'] = df['ema20'] + (df['atr20'] * 2)
        df['kc_lower'] = df['ema20'] - (df['atr20'] * 2)

        df['atr14'] = df['tr'].rolling(window=14).mean()
        
        # --- Stochastic Slow ---
        low14 = df['low'].rolling(window=14).min()
        high14 = df['high'].rolling(window=14).max()
        df['stoch_k'] = 100 * ((df['close'] - low14) / (high14 - low14))
        df['stoch_d'] = df['stoch_k'].rolling(window=3).mean() 
        
        # --- ADX ---
        df['up_move'] = df['high'].diff()
        df['down_move'] = df['low'].diff().abs()
        df['plus_dm'] = df.apply(lambda r: r['up_move'] if r['up_move'] > r['down_move'] and r['up_move'] > 0 else 0, axis=1)
        df['minus_dm'] = df.apply(lambda r: r['down_move'] if r['down_move'] > r['up_move'] and r['down_move'] > 0 else 0, axis=1)
        
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
            if df['upper_band'].iloc[i] < final_upper_band[i-1] or df['close'].iloc[i-1] > final_upper_band[i-1]:
                final_upper_band[i] = df['upper_band'].iloc[i]
            else:
                final_upper_band[i] = final_upper_band[i-1]
            
            if df['lower_band'].iloc[i] > final_lower_band[i-1] or df['close'].iloc[i-1] < final_lower_band[i-1]:
                final_lower_band[i] = df['lower_band'].iloc[i]
            else:
                final_lower_band[i] = final_lower_band[i-1]
            
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

        # --- ELITE FEATURE: 'Whale Watcher' (Order Flow Imbalance) ---
        df['buying_pressure'] = (df['close'] - df['low']) / (df['high'] - df['low']) * df['volume']
        df['selling_pressure'] = (df['high'] - df['close']) / (df['high'] - df['low']) * df['volume']
        df['pressure_delta'] = df['buying_pressure'] - df['selling_pressure']
        df['pressure_delta_ema'] = df['pressure_delta'].ewm(span=14, adjust=False).mean()
        
        df['avg_delta'] = df['pressure_delta'].abs().rolling(20).mean()
        df['whale_buy_wall'] = (df['pressure_delta'] > 0) & (df['pressure_delta'] > df['avg_delta'] * 2)
        df['whale_sell_wall'] = (df['pressure_delta'] < 0) & (df['pressure_delta'].abs() > df['avg_delta'] * 2)

        # --- Technical Ratings & Momentum Scoring ---
        df['mom_rsi'] = df['rsi14'] / 100.0
        df['mom_macd'] = (df['macd_hist'] - df['macd_hist'].rolling(50).min()) / (df['macd_hist'].rolling(50).max() - df['macd_hist'].rolling(50).min())
        df['mom_adx'] = df['adx'] / 100.0
        df['momentum_score'] = (df['mom_rsi'] + df['mom_macd'] + df['mom_adx']) / 3.0 * 100.0

        # Technical Ratings
        df['tr_rsi'] = df['rsi14'].apply(lambda x: 1 if x < 30 else (-1 if x > 70 else 0))
        df['tr_macd'] = df['macd_hist'].apply(lambda x: 1 if x > 0 else -1)
        df['tr_stoch'] = df['stoch_k'].apply(lambda x: 1 if x < 20 else (-1 if x > 80 else 0))
        df['tr_ma'] = df.apply(lambda r: 1 if r['close'] > r['sma20'] and r['sma10'] > r['sma20'] else -1, axis=1)
        df['tech_rating'] = (df['tr_rsi'] + df['tr_macd'] + df['tr_stoch'] + df['tr_ma']) / 4.0

        # --- Candlestick Patterns ---
        df = CandlestickPatterns.detect_all(df)

        # --- Chart Patterns ---
        df = ChartPatterns.detect_all(df)

        # --- Market Regime Intelligence ---
        df['is_chop'] = df['adx'] < Config.CHOP_ADX_THRESHOLD
        df['vol_compression'] = df['bb_std'].rolling(20).min() / df['bb_std'].rolling(20).max() < 0.5
        df['avg_volume50'] = df['volume'].rolling(50).mean()
        df['is_thin_market'] = df['volume'] < (df['avg_volume50'] * 0.5)

        return df

    @staticmethod
    def should_buy(bars, dynamic_config: dict | None = None, active_strategies: list | None = None, symbol: str = "") -> tuple[bool, str, float, dict]:
        # Ultimate Bot: Load optimized params if available
        if dynamic_config is None:
            dynamic_config = {}
            if os.path.exists(Config.OPTIMIZED_PARAMS_FILE):
                try:
                    with open(Config.OPTIMIZED_PARAMS_FILE, 'r') as f:
                        dynamic_config.update(json.load(f))
                except:
                    pass

        df = Strategy._calculate_indicators(bars)
        if df is None:
            return False, "not enough bars", 0.0, {}

        import pandas as pd
        last = df.iloc[-1]
        last_indicators = last.to_dict()
        prev = df.iloc[-2]
        
        active = active_strategies if active_strategies else Config.ACTIVE_STRATEGIES
        matches = []
        strength_score = 0.0
        
        from intelligence import ConfidenceEngine
        from risk import RiskManager
        rm = RiskManager()
        scores = ConfidenceEngine.calculate_scores(bars, "CONFLUENCE", rm)
        trade_score = scores.get("trade", 0)
        
        volatility_excessive = last['atr14'] > (last['close'] * 0.005)  # Adjusted threshold for volatility
        last_candle_green = last['close'] > prev['close']
        
        from datetime import datetime
        now_hhmm = int(datetime.now().strftime("%H%M"))
        is_after_hours = now_hhmm > 1600 or now_hhmm < 930

        min_rvol_base = 3.0 if is_after_hours else 1.8
        
        from intelligence import MarketRegimeIntelligence
        regime = MarketRegimeIntelligence.get_current_regime(bars)
        
        # 1. Market Regime Filters (Ultimate Bot Layer)
        if "CHOP" in regime:
            # Only allow specific mean-reversion or scalping strategies in chop
            allowed_in_chop = ["SCALPING", "RSI", "BOLLINGER"]
            active = [s for s in active if s in allowed_in_chop]
            if not active:
                return False, f"Market regime is {regime}, no suitable active strategies", 0.0, last_indicators

        if "LOW_LIQUIDITY" in regime:
            # Tighten RVOL requirements in low liquidity
            min_rvol_base *= 1.5

        if "TRENDING_BEAR" in regime and "TREND" in active:
            # Don't buy in a strong bear trend unless it's a deep reversal
            if not ("RSI" in active and last['rsi14'] < 25):
                return False, f"Market regime is {regime}, trend-following buys disabled", 0.0, last_indicators

        # 2. Institutional Flow & News
        if last.get('whale_sell_wall') and not last.get('whale_buy_wall'):
            return False, "Institutional Sell Wall detected (Whale Watcher)", 0.0, last_indicators

        if not Strategy.is_news_safe(symbol, None, bars=bars):
            return False, "Unsafe news conditions (spike or negative news detected)", 0.0, last_indicators

        volatility_excessive = last['atr14'] > (last['close'] * 0.005)  # Adjusted threshold for volatility
        min_close_relative = 0.85 if is_after_hours else 0.8
        close_relative_pos = (last['close'] - last['low']) / (last['high'] - last['low']) if (last['high'] - last['low']) > 0 else 0
        
        min_rvol_base = 3.0 if is_after_hours else 1.8
        volume_spike = last['rvol'] > (dynamic_config.get("min_rvol", min_rvol_base) if dynamic_config else min_rvol_base)

        smc_match = False
        if "LIQUIDITY" in active:
            if last['sweep_low'] and last_candle_green:
                matches.append("LIQUIDITY_SWEEP_LOW")
                strength_score += 0.5
                smc_match = True
            if last['fvg_bull'] and last['close'] > last['high'].shift(2):
                matches.append("FVG_RECOVERY")
                strength_score += 0.4
                smc_match = True
            if last['imbalance_bull']:
                matches.append("ORDER_IMBALANCE_BULL")
                strength_score += 0.3
                smc_match = True

        trend_match = False
        long_term_bullish = last['close'] > last['sma200']
        hourly_trend_bullish = last['close'] > last['sma_hourly'] if not pd.isna(last['sma_hourly']) else True
        sniper_stack = last['close'] > last['sma10'] > last['sma20']
        if 'sma50' in last and not pd.isna(last['sma50']):
            sniper_stack = sniper_stack and last['sma20'] > last['sma50']
        
        vwap_filter = last['close'] > last['vwap'] if 'vwap' in last else True

        if "TREND" in active:
            if long_term_bullish and hourly_trend_bullish and sniper_stack and last_candle_green and close_relative_pos >= min_close_relative and vwap_filter:
                matches.append("TREND_SNIPER")
                strength_score += 0.5
                trend_match = True

        if Config.ENABLE_REENTRY_LOGIC and not trend_match and "TREND" in active:
            near_ema = (abs(last['close'] - last['sma10']) / last['close'] < (Config.REENTRY_PULLBACK_PCT / 100.0))
            if long_term_bullish and sniper_stack and near_ema and last_candle_green:
                matches.append("TREND_REENTRY_PULLBACK")
                strength_score += 0.4
                trend_match = True

        if "SUPERTREND" in active:
            if last['supertrend_bull'] and not prev['supertrend_bull']:
                matches.append("SUPERTREND_FLIP")
                strength_score += 0.4
                trend_match = True

        mom_match = False
        if "RSI" in active:
            if last['rsi14'] < 30 and last_candle_green:  # Adjusted RSI threshold for oversold
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

        scalp_match = False
        if "SCALPING" in active:
             ema_cross = last['sma10'] > last['sma20'] and prev['sma10'] <= prev['sma20']
             vol_ok = last['atr14'] > (last['close'] * 0.001) 
             if ema_cross and vol_ok and last['rvol'] > 1.5:
                 matches.append("SCALP_CROSS")
                 strength_score += 0.4
                 scalp_match = True

        break_match = False
        if "BREAKOUT" in active:
            highest_20 = df['high'].rolling(20).max().iloc[-2]
            if last['close'] > highest_20 and volume_spike:
                matches.append("RANGE_BREAKOUT")
                strength_score += 0.5
                break_match = True

        num_families = sum([trend_match, mom_match, pa_match, break_match, scalp_match])
        
        final_strength = min(1.0, strength_score)
        
        is_trending = last['adx'] > Config.MIN_ADX_TREND
        rsi_safe = last['rsi14'] < 70

        meets_base_confluence = (num_families >= 3 and final_strength >= 0.75 and rsi_safe) or (num_families >= 2 and final_strength >= 0.85 and rsi_safe)
        
        if not meets_base_confluence:
            if "TREND_SNIPER" in matches and last['rvol'] > 3.5 and is_trending:
                 pass 
            elif "AGGRESSIVE" in active and final_strength >= 0.6 and last_candle_green and rsi_safe:
                 pass 
            else:
                 return False, "insufficient confluence or signal strength", 0.0, last_indicators

        if "TREND_SNIPER" in matches and not is_trending:
                return False, f"TREND_SNIPER rejected: weak trend (ADX: {last['adx']:.1f})", 0.0, last_indicators

        quality_score = 0.0
        if last['close'] > last['sma200']: quality_score += 15
        if last['close'] > last['sma_hourly']: quality_score += 15
        
        if last['rvol'] > 2.0: quality_score += 15
        if last['rvol'] > 3.5: quality_score += 15
        
        if not last['is_chop']: quality_score += 10
        if not last['is_thin_market']: quality_score += 10
        
        quality_score += (num_families / 5.0) * 20.0
        
        if last['sweep_low']: quality_score += 10 
        if last['fake_breakout_bull']: quality_score -= 20 
        
        from intelligence import MarketDNA, ConfidenceEngine
        dna_profile = MarketDNA.get_asset_profile(symbol)
        if dna_profile == "MACRO_TREND" and is_trending:
             quality_score += 10
        elif dna_profile == "VOLATILITY_SPIKE" and last['rvol'] > 4.0:
             quality_score += 15
             
        scores = ConfidenceEngine.calculate_scores(bars, matches[0] if matches else "unknown", None)
        trade_confidence = scores.get("trade", 0)
        
        final_score = (quality_score + trade_confidence) / 2
        last_indicators['trade_quality_score'] = round(final_score, 2)
        last_indicators['market_confidence'] = scores.get("market", 0)
        last_indicators['strategy_confidence'] = scores.get("strategy", 0)

        if final_score < Config.MIN_TRADE_QUALITY_SCORE or trade_confidence < Config.CONFIDENCE_THRESHOLD:
            return False, f"quality/confidence too low ({final_score:.1f} score, {trade_confidence:.1f} conf)", 0.0, last_indicators

        return True, f"CONFLUENCE ({'+'.join(matches)})", final_strength, last_indicators
        
    @staticmethod
    def is_news_safe(symbol: str, market_data_client, news_list: list | None = None, bars=None) -> bool:
        if Config.ENABLE_NEWS_FILTER is False:
            return True

        from news_engine import NewsEngine
        safe, reason = NewsEngine.is_market_safe(symbol, market_data_client)
        if not safe:
            return False

        if bars is not None:
            df = Strategy._calculate_indicators(bars)
            if df is not None and not df.empty:
                last = df.iloc[-1]
                if last.get('recent_news_spike', False):
                    return False

        news = news_list if news_list is not None else (market_data_client.get_news(symbol, days=1) if market_data_client else [])
        negative_keywords = ["lawsuit", "investigation", "bankruptcy", "fraud", "hacked", "restatement", "default"]
        
        for item in news:
            if any(word in item.headline.lower() for word in negative_keywords):
                return False
                
        if len(news) > 10:
            return False
            
        return True

    @staticmethod
    def should_short(bars, dynamic_config: dict | None = None, active_strategies: list | None = None, symbol: str = "") -> tuple[bool, str, float, dict]:
        df = Strategy._calculate_indicators(bars)
        if df is None:
            return False, "not enough bars", 0.0, {}

        import pandas as pd
        last = df.iloc[-1]
        last_indicators = last.to_dict()
        prev = df.iloc[-2]
        
        active = active_strategies if active_strategies else Config.ACTIVE_STRATEGIES
        matches = []
        strength_score = 0.0
        
        from intelligence import ConfidenceEngine
        from risk import RiskManager
        rm = RiskManager()
        scores = ConfidenceEngine.calculate_scores(bars, "CONFLUENCE_SHORT", rm)
        trade_score = scores.get("trade", 0)
        
        if trade_score < Config.MIN_TRADE_SCORE_THRESHOLD:
            return False, f"Trade score too low: {trade_score}", 0.0, last_indicators

        # ELITE FEATURE: 'Whale Watcher' (Order Flow Filter)
        if last.get('whale_buy_wall') and not last.get('whale_sell_wall'):
            return False, "Institutional Buy Wall detected (Whale Watcher)", 0.0, last_indicators

        if not Strategy.is_news_safe(symbol, None, bars=bars):
            return False, "Unsafe news conditions (spike or negative news detected)", 0.0, last_indicators

        volatility_excessive = last['atr14'] > (last['close'] * 0.005)  # Adjusted threshold for volatility
        last_candle_red = last['close'] < prev['close']
        
        from datetime import datetime
        now_hhmm = int(datetime.now().strftime("%H%M"))
        is_after_hours = now_hhmm > 1600 or now_hhmm < 930
        
        min_close_relative = 0.85 if is_after_hours else 0.8
        close_relative_pos = (last['high'] - last['close']) / (last['high'] - last['low']) if (last['high'] - last['low']) > 0 else 0
        
        min_rvol_base = 3.0 if is_after_hours else 1.8
        volume_spike = last['rvol'] > (dynamic_config.get("min_rvol", min_rvol_base) if dynamic_config else min_rvol_base)

        smc_match = False
        if "LIQUIDITY" in active:
            if last['sweep_high'] and last_candle_red:
                matches.append("LIQUIDITY_SWEEP_HIGH")
                strength_score += 0.5
                smc_match = True
            if last['fvg_bear'] and last['close'] < last['low'].shift(2):
                matches.append("FVG_BEAR_RECOVERY")
                strength_score += 0.4
                smc_match = True
            if last['imbalance_bear']:
                matches.append("ORDER_IMBALANCE_BEAR")
                strength_score += 0.3
                smc_match = True

        trend_match = False
        long_term_bearish = last['close'] < last['sma200']
        hourly_trend_bearish = last['close'] < last['sma_hourly'] if not pd.isna(last['sma_hourly']) else True
        sniper_bearish_stack = last['close'] < last['sma10'] < last['sma20']
        if 'sma50' in last and not pd.isna(last['sma50']):
            sniper_bearish_stack = sniper_bearish_stack and last['sma20'] < last['sma50']
            
        vwap_filter_short = last['close'] < last['vwap'] if 'vwap' in last else True

        if "TREND" in active:
            if long_term_bearish and hourly_trend_bearish and sniper_bearish_stack and last_candle_red and close_relative_pos >= min_close_relative and vwap_filter_short:
                matches.append("SNIPER_SHORT")
                strength_score += 0.5
                trend_match = True

        if Config.ENABLE_REENTRY_LOGIC and not trend_match and "TREND" in active:
            near_ema = (abs(last['close'] - last['sma10']) / last['close'] < (Config.REENTRY_PULLBACK_PCT / 100.0))
            if long_term_bearish and sniper_bearish_stack and near_ema and last_candle_red:
                matches.append("TREND_SHORT_REENTRY_PULLBACK")
                strength_score += 0.4
                trend_match = True

        if "SUPERTREND" in active:
            if not last['supertrend_bull'] and prev['supertrend_bull']:
                matches.append("SUPERTREND_BEAR_FLIP")
                strength_score += 0.4
                trend_match = True

        mom_match = False
        if "RSI" in active:
            if last['rsi14'] > 65 and last_candle_red:  # Adjusted RSI threshold for overbought
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

        scalp_match = False
        if "SCALPING" in active:
             ema_cross = last['sma10'] < last['sma20'] and prev['sma10'] >= prev['sma20']
             vol_ok = last['atr14'] > (last['close'] * 0.001) 
             if ema_cross and vol_ok and last['rvol'] > 1.5:
                 matches.append("SCALP_SHORT_CROSS")
                 strength_score += 0.4
                 scalp_match = True

        break_match = False
        if "BREAKOUT" in active:
            lowest_20 = df['low'].rolling(20).min().iloc[-2]
            if last['close'] < lowest_20 and volume_spike:
                matches.append("RANGE_BREAKDOWN")
                strength_score += 0.5
                break_match = True

        num_families = sum([trend_match, mom_match, pa_match, break_match, scalp_match])
        final_strength = min(1.0, strength_score)
        
        is_trending = last['adx'] > Config.MIN_ADX_TREND
        rsi_safe = last['rsi14'] > 30

        meets_base_confluence = (num_families >= 3 and final_strength >= 0.75 and rsi_safe) or (num_families >= 2 and final_strength >= 0.85 and rsi_safe)
        
        if not meets_base_confluence:
            if "SNIPER_SHORT" in matches and last['rvol'] > 3.5 and is_trending:
                 pass 
            elif "AGGRESSIVE" in active and final_strength >= 0.6 and last_candle_red and rsi_safe:
                 pass
            else:
                 return False, "insufficient confluence or signal strength", 0.0, last_indicators

        if "SNIPER_SHORT" in matches and not is_trending:
                return False, f"SNIPER_SHORT rejected: weak trend (ADX: {last['adx']:.1f})", 0.0, last_indicators

        quality_score = 0.0
        if last['close'] < last['sma200']: quality_score += 15
        if last['close'] < last['sma_hourly']: quality_score += 15
        
        if last['rvol'] > 2.0: quality_score += 15
        if last['rvol'] > 3.5: quality_score += 15
        
        if not last['is_chop']: quality_score += 10
        if not last['is_thin_market']: quality_score += 10
        
        quality_score += (num_families / 5.0) * 20.0
        
        if last['sweep_high']: quality_score += 10
        if last['fake_breakout_bear']: quality_score -= 20 
        
        from intelligence import MarketDNA, ConfidenceEngine
        dna_profile = MarketDNA.get_asset_profile(symbol)
        if dna_profile == "MACRO_TREND" and is_trending:
             quality_score += 10
        elif dna_profile == "VOLATILITY_SPIKE" and last['rvol'] > 4.0:
             quality_score += 15
             
        scores = ConfidenceEngine.calculate_scores(bars, matches[0] if matches else "unknown", None)
        trade_confidence = scores.get("trade", 0)
        
        final_score = (quality_score + trade_confidence) / 2
        last_indicators['trade_quality_score'] = round(final_score, 2)
        last_indicators['market_confidence'] = scores.get("market", 0)
        last_indicators['strategy_confidence'] = scores.get("strategy", 0)

        if final_score < Config.MIN_TRADE_QUALITY_SCORE or trade_confidence < Config.CONFIDENCE_THRESHOLD:
            return False, f"quality/confidence too low ({final_score:.1f} score, {trade_confidence:.1f} conf)", 0.0, last_indicators

        return True, f"CONFLUENCE SHORT ({'+'.join(matches)})", final_strength, last_indicators

    @staticmethod
    def should_sell(entry_price: float, current_price: float, bars, high_since_entry: float | None = None, side: str = "buy", dynamic_config: dict | None = None, is_manual: bool = False, entry_time: datetime | None = None) -> tuple[bool, str, float]:
        if current_price <= 0:
            return False, "invalid current price", 1.0

        if entry_time and Config.TIME_BASED_EXIT_MINUTES > 0:
            elapsed = (datetime.now() - entry_time).total_seconds() / 60.0
            if elapsed >= Config.TIME_BASED_EXIT_MINUTES:
                return True, f"time-based exit hit ({Config.TIME_BASED_EXIT_MINUTES} mins elapsed)", 1.0

        sl_pct = (dynamic_config.get("stop_loss_pct", Config.STOP_LOSS_PCT) if dynamic_config else Config.STOP_LOSS_PCT) / 100.0
        tp_pct = (dynamic_config.get("take_profit_pct", Config.TAKE_PROFIT_PCT) if dynamic_config else Config.TAKE_PROFIT_PCT) / 100.0
        ts_pct = Config.TRAILING_STOP_PCT / 100.0 
        ts_activation_pct = Config.TRAILING_STOP_ACTIVATION_PCT / 100.0

        if Config.EXIT_LADDER_ENABLED and entry_price > 0:
            profit_pct = (current_price / entry_price - 1) if side == "buy" else (entry_price / current_price - 1)
            if profit_pct >= tp_pct * 1.5:
                 return True, "TP 4 (EXTREME): full exit", 1.0
            elif profit_pct >= tp_pct:
                 return True, "TP 3 (FULL): target reached", 1.0
            elif profit_pct >= tp_pct * 0.75:
                 return True, "TP 2 (PARTIAL 50%): scaling out", 0.5
            elif profit_pct >= tp_pct * 0.5:
                 return True, "TP 1 (PARTIAL 25%): scaling out", 0.25

        profit_lock_pct = Config.PROFIT_LOCK_PCT / 100.0
        profit_lock_retain_pct = Config.PROFIT_LOCK_RETAIN_PCT / 100.0
        is_profit_locked = False
        if entry_price > 0:
            if side == "buy":
                max_profit_pct = (high_since_entry / entry_price) - 1 if high_since_entry else 0
                if max_profit_pct >= profit_lock_pct:
                    is_profit_locked = True
                    lock_exit_price = entry_price * (1 + (max_profit_pct * profit_lock_retain_pct))
                    if current_price <= lock_exit_price:
                        return True, f"profit lock hit: peak {max_profit_pct*100:.2f}% (locked {max_profit_pct*profit_lock_retain_pct*100:.2f}%)"
            else:
                low_since_entry = high_since_entry
                max_profit_pct = (entry_price / low_since_entry) - 1 if low_since_entry else 0
                if max_profit_pct >= profit_lock_pct:
                    is_profit_locked = True
                    lock_exit_price = entry_price * (1 - (max_profit_pct * profit_lock_retain_pct))
                    if current_price >= lock_exit_price:
                        return True, f"short profit lock hit: peak {max_profit_pct*100:.2f}% (locked {max_profit_pct*profit_lock_retain_pct*100:.2f}%)"

        last_atr = 0.0
        df_full = None
        if len(bars) >= 20:
            df_full = Strategy._calculate_indicators(bars)
            if df_full is not None:
                last_atr = df_full['atr14'].iloc[-1]
                
        if Config.ENABLE_DYNAMIC_ATR_EXITS and last_atr > 0 and entry_price > 0:
            if df_full is not None and not Strategy.is_news_safe("", None, bars=bars):
                tight_sl_price = last_atr * 0.5
                if side == "buy":
                    if current_price < (entry_price - tight_sl_price):
                        return True, "Unsafe news: Tight ATR stop hit (buy)", 1.0
                else:
                    if current_price > (entry_price + tight_sl_price):
                        return True, "Unsafe news: Tight ATR stop hit (short)", 1.0

            atr_sl_price = last_atr * Config.ATR_SL_MULTIPLIER
            atr_tp_price = last_atr * Config.ATR_TP_MULTIPLIER
            
            if Config.ADAPTIVE_TP_ENABLED and df_full is not None:
                if df_full['adx'].iloc[-1] > 35:
                    atr_tp_price *= 1.5 

            atr_sl_pct = atr_sl_price / entry_price
            atr_tp_pct = atr_tp_price / entry_price
            
            sl_pct = min(sl_pct, atr_sl_pct)
            tp_pct = max(tp_pct, atr_tp_pct) 

        be_profit_pct = Config.BREAK_EVEN_PROFIT_PCT / 100.0
        is_at_break_even = False
        if entry_price > 0:
            if side == "buy":
                highest_pct = (high_since_entry / entry_price) - 1 if high_since_entry else 0
                if highest_pct >= be_profit_pct:
                    is_at_break_even = True
            else:
                low_since_entry = high_since_entry
                lowest_pct = (entry_price / low_since_entry) - 1 if low_since_entry else 0
                if lowest_pct >= be_profit_pct:
                    is_at_break_even = True

        is_strong_trend = False
        if len(bars) >= 20:
            import pandas as pd
            df = pd.DataFrame([{"close": float(b.close)} for b in bars[-20:]])
            df['sma20'] = df['close'].rolling(window=20).mean()
            last_close = df['close'].iloc[-1]
            last_sma20 = df['sma20'].iloc[-1]
            if side == "buy":
                is_strong_trend = last_close > (last_sma20 * 1.01)
            else:
                is_strong_trend = last_close < (last_sma20 * 0.99)

        if is_strong_trend:
             ts_pct = ts_pct * 1.5 

        if side == "buy":
            if entry_price > 0:
                effective_sl_pct = 0.0020 if is_at_break_even else sl_pct
                if current_price <= entry_price * (1 - effective_sl_pct):
                    reason = "break-even stop hit" if is_at_break_even else f"stop loss hit ({sl_pct*100:.2f}%)"
                    return True, reason
            if ts_pct > 0 and high_since_entry and entry_price > 0:
                is_activated = (current_price >= entry_price * (1 + ts_activation_pct)) or (high_since_entry >= entry_price * (1 + ts_activation_pct))
                
                if is_activated and Config.ADAPTIVE_TP_ENABLED:
                    if (current_price / entry_price) - 1 > (tp_pct * 0.8):
                        ts_pct *= 0.5 

                if is_activated and current_price <= high_since_entry * (1 - ts_pct):
                    return True, f"trailing stop hit (high: {high_since_entry:.2f})"
            if not is_manual and tp_pct > 0 and current_price >= entry_price * (1 + tp_pct):
                return True, f"take profit hit ({tp_pct*100:.2f}%)"
        else:
            if entry_price > 0:
                effective_sl_pct = 0.0020 if is_at_break_even else sl_pct
                if current_price >= entry_price * (1 + effective_sl_pct):
                    reason = "short break-even stop hit" if is_at_break_even else f"short stop loss hit ({sl_pct*100:.2f}%)"
                    return True, reason
            low_since_entry = high_since_entry
            if ts_pct > 0 and low_since_entry and entry_price > 0:
                is_activated = (current_price <= entry_price * (1 - ts_activation_pct)) or (low_since_entry <= entry_price * (1 - ts_activation_pct))
                
                if is_activated and Config.ADAPTIVE_TP_ENABLED:
                    if (entry_price / current_price) - 1 > (tp_pct * 0.8):
                        ts_pct *= 0.5
                
                if is_activated and current_price >= low_since_entry * (1 + ts_pct):
                    return True, f"short trailing stop hit (low: {low_since_entry:.2f})"
            if not is_manual and tp_pct > 0 and current_price <= entry_price * (1 - tp_pct):
                return True, f"short take profit hit ({tp_pct*100:.2f})"

        if not is_manual and not is_strong_trend:
            if len(bars) >= 20:
                df_full = Strategy._calculate_indicators(bars)
                if df_full is not None:
                    last_rsi = df_full['rsi14'].iloc[-1]
                    if side == "buy" and last_rsi > 75:
                        return True, f"RSI Overbought ({last_rsi:.1f}): Reached peak momentum floor"
                    if side == "short" and last_rsi < 25:
                        return True, f"RSI Oversold ({last_rsi:.1f}): Reached bottom momentum floor"

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
        if strategy_name == "long_call":
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