import json
import os
import pandas as pd
from datetime import datetime
from config import Config
from strategy import Strategy

class PortfolioIntelligence:
    @staticmethod
    def calculate_correlation(df_list, symbols):
        """Calculates correlation matrix between a list of price dataframes."""
        if not df_list or len(df_list) < 2:
            return {}
        
        closes = {}
        for i, df in enumerate(df_list):
            if not df.empty:
                closes[symbols[i]] = df['close']
        
        corr_df = pd.DataFrame(closes).corr()
        return corr_df.to_dict()

    @staticmethod
    def get_sector_allocation(current_positions, risk_manager):
        """Returns the percentage of the portfolio allocated to each sector."""
        sectors = {}
        total_value = 0
        for pos in current_positions:
            sector = risk_manager._get_symbol_sector(pos.symbol)
            value = float(pos.market_value)
            sectors[sector] = sectors.get(sector, 0) + value
            total_value += value
        
        if total_value == 0:
            return {}
        
        return {s: (v / total_value) * 100 for s, v in sectors.items()}

class SelfAdaptingStrategySystem:
    def __init__(self, journal_path="logs/trade_journal.jsonl"):
        self.journal_path = journal_path
        self.perf_file = "logs/strategy_performance.json"

    def update_performance(self):
        """Analyzes the journal and updates performance metrics per strategy family."""
        if not os.path.exists(self.journal_path):
            return
        
        trades = []
        with open(self.journal_path, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get("event") == "fill" and data.get("pnl") is not None:
                        trades.append(data)
                except:
                    continue
        
        if not trades:
            return

        perf = {}
        for t in trades:
            reason = t.get("reason", "unknown")
            # Extract strategy family from reason (e.g., "CONFLUENCE (TREND_SNIPER+SCALPING)")
            families = []
            if "CONFLUENCE" in reason:
                try:
                    families = reason.split("(")[1].split(")")[0].split("+")
                except:
                    families = ["unknown"]
            else:
                families = [reason]
            
            pnl = float(t.get("pnl", 0.0))
            for f in families:
                f = f.strip()
                if f not in perf:
                    perf[f] = {"wins": 0, "losses": 0, "total_pnl": 0.0, "count": 0}
                perf[f]["count"] += 1
                perf[f]["total_pnl"] += pnl
                if pnl > 0:
                    perf[f]["wins"] += 1
                else:
                    perf[f]["losses"] += 1
        
        # Calculate win rates and rankings
        for f in perf:
            perf[f]["win_rate"] = (perf[f]["wins"] / perf[f]["count"]) * 100 if perf[f]["count"] > 0 else 0
        
        with open(self.perf_file, 'w') as f:
            json.dump(perf, f, indent=4)
        
        return perf

    def get_priority_strategies(self):
        """Returns strategies that should be prioritized (high win rate) or disabled."""
        if not os.path.exists(self.perf_file):
            return [], []
        
        with open(self.perf_file, 'r') as f:
            perf = json.load(f)
        
        prioritize = [f for f, data in perf.items() if data["win_rate"] >= 65 and data["count"] >= 5]
        disable = [f for f, data in perf.items() if data["win_rate"] <= 40 and data["count"] >= 5]
        
        return prioritize, disable

class MarketRegimeIntelligence:
    @staticmethod
    def get_current_regime(bars):
        """Detects the current market regime based on indicators."""
        if len(bars) < 50:
            return "UNKNOWN"
        
        from strategy import Strategy
        df = Strategy._calculate_indicators(bars)
        last = df.iloc[-1]
        
        if last['adx'] > 25:
            regime = "TRENDING_" + ("BULL" if last['close'] > last['sma50'] else "BEAR")
        elif last['adx'] < 20:
            regime = "CHOP"
        else:
            regime = "TRANSITION"
            
        if last['is_thin_market']:
            regime += "_LOW_LIQUIDITY"
            
        return regime

class EdgeDecayDetector:
    def __init__(self, journal_path="logs/trade_journal.jsonl"):
        self.journal_path = journal_path

    def analyze_decay(self, window=None):
        """Analyzes rolling win rate to detect edge decay."""
        if window is None:
            window = Config.EDGE_DECAY_WINDOW
            
        if not os.path.exists(self.journal_path):
            return {}

        trades = []
        with open(self.journal_path, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get("event") == "fill" and data.get("pnl") is not None:
                        trades.append(data)
                except:
                    continue
        
        if len(trades) < window:
            return {"status": "INSUFFICIENT_DATA"}

        recent_trades = trades[-window:]
        wins = sum(1 for t in recent_trades if float(t.get("pnl", 0)) > 0)
        win_rate = (wins / window) * 100
        
        decayed = win_rate < Config.EDGE_DECAY_THRESHOLD_WR
        return {
            "win_rate": win_rate,
            "decayed": decayed,
            "status": "DECAY_DETECTED" if decayed else "HEALTHY"
        }

class MarketDNA:
    @staticmethod
    def get_asset_profile(symbol):
        """Returns the behavioral DNA of an asset."""
        symbol = symbol.upper()
        if "/" in symbol: # Crypto
            if "BTC" in symbol or "ETH" in symbol:
                return "MACRO_TREND"
            return "VOLATILITY_SPIKE"
        else: # Stocks
            if any(tech in symbol for tech in ["NVDA", "TSLA", "AAPL", "MSFT", "AMD"]):
                return "MOMENTUM_TECH"
            return "SESSION_BASED"

class ConfidenceEngine:
    @staticmethod
    def calculate_scores(bars, strategy_name, risk_manager):
        """Calculates 0-100 confidence scores for market, strategy, and trade."""
        if not bars:
            return {"market": 0, "strategy": 0, "trade": 0}
            
        from strategy import Strategy
        df = Strategy._calculate_indicators(bars)
        last = df.iloc[-1]
        
        # Market Confidence: Trend strength + Volume + Liquidity
        market_score = 0
        market_score += min(30, last['adx'] * 0.75) # ADX contribution
        market_score += 20 if last['rvol'] > 1.5 else (10 if last['rvol'] > 1.0 else 0)
        market_score += 20 if not last['is_thin_market'] else 0
        market_score += 30 if not last['is_chop'] else 0
        
        # Strategy Confidence: Past performance
        system = SelfAdaptingStrategySystem()
        perf = system.update_performance() or {}
        strat_perf = perf.get(strategy_name, {"win_rate": 50})
        strategy_score = strat_perf.get("win_rate", 50)
        
        # Trade Edge Score (0-100)
        edge_score = 0
        # 1. Trend alignment
        if "TREND" in strategy_name or "SNIPER" in strategy_name:
            edge_score += 25 if last['supertrend_bull'] else 0
        else:
            edge_score += 25 # Default for non-trend specific
            
        # 2. Volume confirmation
        edge_score += 25 if last['vol_delta_ema'] > 0 else 0
        
        # 3. Volatility clean
        edge_score += 25 if not last['is_chop'] and last['adx'] > 15 else 0
        
        # 4. Smart Money Alignment (Liquidity / Sweeps / FVG)
        smc_score = 0
        if last['sweep_low'] or last['fvg_bull'] or last['imbalance_bull']:
            smc_score += 25
        edge_score += smc_score
        
        # Global Trade Score
        trade_score = (market_score * 0.3) + (strategy_score * 0.3) + (edge_score * 0.4)
        
        return {
            "market": round(market_score, 2),
            "strategy": round(strategy_score, 2),
            "edge": round(edge_score, 2),
            "trade": round(trade_score, 2)
        }

class MarketStressIndex:
    @staticmethod
    def get_stress_level(df_list):
        """Detects market instability using correlation and volatility anomalies."""
        if not df_list:
            return 0.0
            
        volatilities = []
        for df in df_list:
            if not df.empty:
                # Simple realized vol
                vol = df['close'].pct_change().std() * (252**0.5)
                volatilities.append(vol)
        
        if not volatilities:
            return 0.0
            
        avg_vol = sum(volatilities) / len(volatilities)
        # Higher index means more stress
        return round(avg_vol * 100, 2)
